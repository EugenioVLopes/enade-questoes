"""Travas determinísticas pós-LLM, cálculo de revisão prioritária e critério de divergência."""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from domain.classificacao import Classificacao
from domain.exceptions import ErroValidacaoDominio
from domain.prova import AlertaExtracao
from domain.taxonomia import MAX_CHARS_TOPICO, Taxonomia, normalizar_topico

CONFIANCA_MINIMA_REVISAO = 0.75
MAX_DISCIPLINAS_SECUNDARIAS = 2
MAX_TOPICOS = 4
ALERTA_BAIXA_CONFIANCA = "baixa_confianca"

_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class ResultadoValidacaoClassificacao:
    """Resultado das travas determinísticas aplicadas à saída bruta do LLM."""

    valida: bool
    elegivel_retry: bool
    motivo_rejeicao: str | None = None
    disciplina_principal: str | None = None
    disciplinas_secundarias: tuple[str, ...] = ()
    topicos: tuple[str, ...] = ()
    justificativa: str = ""
    confianca: float = 0.0
    revisao_prioritaria: bool = False
    houve_saneamento: bool = False
    alertas_validacao: tuple[str, ...] = ()


def calcular_revisao_prioritaria(
    confianca: float,
    alertas_extracao: Sequence[AlertaExtracao] = (),
    alertas_saneamento: Sequence[str] = (),
) -> bool:
    """Determina se a Classificação exige revisão humana prioritária.

    Retorna True quando houver QUALQUER um dos critérios:
    - Algum AlertaExtracao crítico ainda aberto;
    - Algum saneamento determinístico das travas pós-LLM;
    - Grau de confiança estritamente inferior a 0.75.
    """
    tem_alerta_extracao_critico = any(alerta.is_critico and alerta.is_aberto for alerta in alertas_extracao)
    tem_saneamento = any(alerta != ALERTA_BAIXA_CONFIANCA for alerta in alertas_saneamento)
    return tem_alerta_extracao_critico or tem_saneamento or (confianca < CONFIANCA_MINIMA_REVISAO)


def _slug_completo_sem_limite(raw: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii").lower().strip()
    return _NON_ALNUM_PATTERN.sub("-", ascii_text).strip("-")


def validar_e_normalizar_classificacao(
    dados_brutos: Mapping[str, Any],
    taxonomia: Taxonomia,
    alertas_extracao: Sequence[AlertaExtracao] = (),
) -> ResultadoValidacaoClassificacao:
    """Aplica as travas determinísticas pós-LLM sem dependência de frameworks."""
    if not isinstance(dados_brutos, Mapping):
        return ResultadoValidacaoClassificacao(
            valida=False,
            elegivel_retry=True,
            motivo_rejeicao="payload_bruto_nao_e_mapeamento",
        )

    mapa_ativas = taxonomia.mapa_ativas()

    raw_principal = dados_brutos.get("disciplina_principal")
    if not isinstance(raw_principal, str) or not raw_principal.strip():
        return ResultadoValidacaoClassificacao(
            valida=False,
            elegivel_retry=True,
            motivo_rejeicao="disciplina_principal_ausente_ou_invalida",
        )
    principal = raw_principal.strip()
    if principal not in mapa_ativas:
        return ResultadoValidacaoClassificacao(
            valida=False,
            elegivel_retry=True,
            motivo_rejeicao=f"disciplina_principal_fora_do_catalogo_ativo:{principal}",
        )

    raw_justificativa = dados_brutos.get("justificativa")
    if not isinstance(raw_justificativa, str) or not raw_justificativa.strip():
        return _rejeicao_elegivel_retry("justificativa_vazia_ou_invalida")
    justificativa = raw_justificativa.strip()

    raw_confianca = dados_brutos.get("confianca")
    if (
        isinstance(raw_confianca, bool)
        or not isinstance(raw_confianca, int | float)
        or not math.isfinite(raw_confianca)
    ):
        return ResultadoValidacaoClassificacao(
            valida=False,
            elegivel_retry=True,
            motivo_rejeicao="confianca_ausente_ou_nao_numerica",
        )
    confianca_float = float(raw_confianca)

    alertas_saneamento: list[str] = []
    if confianca_float < 0.0 or confianca_float > 1.0:
        alertas_saneamento.append("confianca_ajustada_ao_intervalo")
    confianca = max(0.0, min(1.0, confianca_float))

    raw_secundarias = dados_brutos.get("disciplinas_secundarias", ())
    if raw_secundarias is None:
        raw_secundarias = ()
    if isinstance(raw_secundarias, str | bytes | bytearray | memoryview) or not isinstance(raw_secundarias, Sequence):
        return ResultadoValidacaoClassificacao(
            valida=False,
            elegivel_retry=True,
            motivo_rejeicao="disciplinas_secundarias_formato_invalido",
        )

    sec_limpas: list[str] = []
    sec_vistas: set[str] = set()
    for item in raw_secundarias:
        if not isinstance(item, str) or not item.strip():
            alertas_saneamento.append(f"removida_secundaria_invalida:{item!r}")
            continue
        sec = item.strip()
        if sec == principal:
            alertas_saneamento.append(f"removida_secundaria_igual_principal:{sec}")
            continue
        if sec not in mapa_ativas:
            alertas_saneamento.append(f"removida_secundaria_invalida:{sec}")
            continue
        if sec in sec_vistas:
            alertas_saneamento.append(f"removida_secundaria_duplicada:{sec}")
            continue
        sec_vistas.add(sec)
        sec_limpas.append(sec)

    if len(sec_limpas) > MAX_DISCIPLINAS_SECUNDARIAS:
        alertas_saneamento.append(f"secundarias_truncadas_para_2:{len(sec_limpas)}")
        sec_limpas = sec_limpas[:MAX_DISCIPLINAS_SECUNDARIAS]

    raw_topicos = dados_brutos.get("topicos", ())
    if raw_topicos is None:
        raw_topicos = ()
    if isinstance(raw_topicos, str | bytes | bytearray | memoryview) or not isinstance(raw_topicos, Sequence):
        return ResultadoValidacaoClassificacao(
            valida=False,
            elegivel_retry=True,
            motivo_rejeicao="topicos_formato_invalido",
        )

    topicos_limpos: list[str] = []
    topicos_vistos: set[str] = set()
    for raw_topico in raw_topicos:
        if not isinstance(raw_topico, str):
            alertas_saneamento.append("topico_nao_textual_descartado")
            continue
        slug_completo = _slug_completo_sem_limite(raw_topico)
        norm = normalizar_topico(raw_topico)
        if not norm:
            alertas_saneamento.append("topico_vazio_ou_excedente_descartado")
            continue
        if len(slug_completo) > MAX_CHARS_TOPICO and norm != slug_completo:
            alertas_saneamento.append(f"topico_truncado_limite_32:{norm}")
        if norm in topicos_vistos:
            continue
        topicos_vistos.add(norm)
        topicos_limpos.append(norm)

    if len(topicos_limpos) > MAX_TOPICOS:
        alertas_saneamento.append(f"topicos_truncados_para_4:{len(topicos_limpos)}")
        topicos_limpos = topicos_limpos[:MAX_TOPICOS]

    if not topicos_limpos:
        alertas_saneamento.append("topicos_vazios_apos_normalizacao")

    houve_saneamento = bool(alertas_saneamento)
    alertas_validacao = list(alertas_saneamento)
    if confianca < CONFIANCA_MINIMA_REVISAO:
        alertas_validacao.append(ALERTA_BAIXA_CONFIANCA)

    revisao_prioritaria = calcular_revisao_prioritaria(
        confianca=confianca,
        alertas_extracao=alertas_extracao,
        alertas_saneamento=alertas_saneamento,
    )

    return ResultadoValidacaoClassificacao(
        valida=True,
        elegivel_retry=False,
        motivo_rejeicao=None,
        disciplina_principal=principal,
        disciplinas_secundarias=tuple(sec_limpas),
        topicos=tuple(topicos_limpos),
        justificativa=justificativa,
        confianca=confianca,
        revisao_prioritaria=revisao_prioritaria,
        houve_saneamento=houve_saneamento,
        alertas_validacao=tuple(alertas_validacao),
    )


def _rejeicao_elegivel_retry(motivo: str) -> ResultadoValidacaoClassificacao:
    return ResultadoValidacaoClassificacao(
        valida=False,
        elegivel_retry=True,
        motivo_rejeicao=motivo,
    )


def _extrair_par_curricular(item: Classificacao | Mapping[str, Any]) -> tuple[str, frozenset[str]]:
    if isinstance(item, Classificacao):
        return item.disciplina_principal, frozenset(item.disciplinas_secundarias)
    if not isinstance(item, Mapping):
        raise ErroValidacaoDominio("Item para detecção de divergência deve ser Classificacao ou Mapping.")

    raw_principal = item.get("disciplina_principal", "")
    if not isinstance(raw_principal, str) or not raw_principal.strip():
        raise ErroValidacaoDominio("'disciplina_principal' inválida para detecção de divergência.")
    principal = raw_principal.strip()

    raw_secundarias = item.get("disciplinas_secundarias", ())
    if raw_secundarias is None:
        return principal, frozenset()
    if isinstance(raw_secundarias, str | bytes | bytearray | memoryview | Mapping) or not isinstance(
        raw_secundarias, Iterable
    ):
        raise ErroValidacaoDominio(
            "'disciplinas_secundarias' deve ser uma coleção iterável de strings (não str/bytes/Mapping)."
        )

    limpas: set[str] = set()
    for sec in raw_secundarias:
        if not isinstance(sec, str):
            raise ErroValidacaoDominio(f"Disciplina secundária inválida para detecção de divergência: {sec!r}.")
        slug = sec.strip()
        if slug:
            limpas.add(slug)
    return principal, frozenset(limpas)


def detectar_divergencia(
    vigente: Classificacao | Mapping[str, Any],
    candidata: Classificacao | Mapping[str, Any],
) -> bool:
    """Detecta divergência comparando exclusivamente (disciplina_principal, set(disciplinas_secundarias))."""
    principal_vigente, secundarias_vigente = _extrair_par_curricular(vigente)
    principal_candidata, secundarias_candidata = _extrair_par_curricular(candidata)
    return (principal_vigente != principal_candidata) or (secundarias_vigente != secundarias_candidata)
