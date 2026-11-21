"""Caso de uso de classificação multimodal, schema plano e montagem segura de prompts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from application.exceptions import AtivoVisualAusenteError
from application.ports.armazenamento import ArmazenamentoArquivos
from application.ports.classificacao import ClassificadorMultimodal, ResultadoChamada
from domain.classificacao import Classificacao, PerfilClassificacao
from domain.enums import LetraAlternativa, OrigemClassificacao, StatusClassificacao
from domain.exceptions import ErroValidacaoDominio
from domain.prova import AtivoVisual, Prova, Questao
from domain.taxonomia import Taxonomia
from domain.travas_classificacao import (
    ResultadoValidacaoClassificacao,
    validar_e_normalizar_classificacao,
)

_ORDEM_LETRAS: dict[LetraAlternativa, int] = {
    LetraAlternativa.A: 0,
    LetraAlternativa.B: 1,
    LetraAlternativa.C: 2,
    LetraAlternativa.D: 3,
    LetraAlternativa.E: 4,
}
_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)(?::([^}]+))?\}")


@dataclass(frozen=True, slots=True)
class MetricasClassificacao:
    """Telemetria agregada da classificação de uma questão."""

    prompt_tokens: int
    completion_tokens: int
    latencia_ms: float
    cache_hit: bool
    tentativas: int
    saneada: bool
    modo_schema: str
    cache_key: str
    modelo_efetivo: str = ""
    retry_corretivo: bool = False


@dataclass(frozen=True, slots=True)
class ErroClassificacaoEstruturado:
    """Erro estruturado retornado quando a saída do LLM persiste inválida após retry corretivo."""

    codigo: str
    mensagem: str
    motivo_rejeicao: str
    tentativas: int
    retry_corretivo: bool
    dados_brutos: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ResultadoClassificacaoQuestao:
    """Resultado completo do caso de uso de classificação (sem persistência automática)."""

    sucesso: bool
    metricas: MetricasClassificacao
    validacao: ResultadoValidacaoClassificacao
    classificacao: Classificacao | None = None
    erro: ErroClassificacaoEstruturado | None = None


def construir_json_schema_plano(taxonomia: Taxonomia) -> dict[str, Any]:
    """Gera JSON Schema plano (sem ``$defs``, ``$ref`` nem ``title``) a partir das disciplinas ativas."""
    codigos = [disciplina.codigo for disciplina in taxonomia.ativas()]
    if not codigos:
        raise ErroValidacaoDominio(
            f"Taxonomia '{taxonomia.codigo}' não possui disciplinas ativas para construir o JSON Schema."
        )

    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "disciplina_principal",
            "disciplinas_secundarias",
            "topicos",
            "justificativa",
            "confianca",
        ],
        "properties": {
            "disciplina_principal": {
                "type": "string",
                "enum": codigos,
                "description": "Código slug exato da disciplina principal.",
            },
            "disciplinas_secundarias": {
                "type": "array",
                "items": {"type": "string", "enum": codigos},
                "maxItems": 2,
                "description": "De 0 a 2 códigos de disciplinas secundárias (não repetir a principal).",
            },
            "topicos": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 4,
                "description": "De 1 a 4 tópicos curtos em kebab-case sem acentos.",
            },
            "justificativa": {
                "type": "string",
                "description": "Justificativa técnica concisa em português (2 a 4 frases).",
            },
            "confianca": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Grau de confiança entre 0.0 e 1.0.",
            },
        },
    }


def _renderizar_template_seguro(template: str, valores: Mapping[str, Any]) -> str:
    """Substitui placeholders conhecidos em passagem única sem interpretar `{}` no conteúdo."""

    def _substituir(match: re.Match[str]) -> str:
        chave = match.group(1)
        spec = match.group(2)
        if chave not in valores:
            return match.group(0)
        valor = valores[chave]
        if spec:
            try:
                return format(valor, spec)
            except (TypeError, ValueError):
                return str(valor)
        return str(valor)

    return _PLACEHOLDER_RE.sub(_substituir, template)


def _formatar_catalogo_disciplinas(taxonomia: Taxonomia) -> str:
    ativas = taxonomia.ativas()
    if not ativas:
        raise ErroValidacaoDominio(
            f"Taxonomia '{taxonomia.codigo}' não possui disciplinas ativas para montar o prompt."
        )
    return "\n".join(f"- `{d.codigo}` ({d.nome}): {d.ementa}" for d in ativas)


def _formatar_alternativas(questao: Questao) -> str:
    if not questao.alternativas:
        return "(sem alternativas)"
    ordenadas = sorted(
        questao.alternativas,
        key=lambda alt: _ORDEM_LETRAS.get(alt.letra, 99),
    )
    return "\n".join(f"{alt.letra.value}) {alt.texto}" for alt in ordenadas)


def _formatar_alertas_extracao(questao: Questao) -> str:
    abertos = [alerta.codigo.value for alerta in questao.alertas_extracao if alerta.is_aberto]
    if not abertos:
        return ""
    return f"Alertas de extração do PDF: {', '.join(abertos)}\n"


def _formatar_bloco_ativos(total_imagens: int) -> str:
    if total_imagens <= 0:
        return ""
    return f"\n[{total_imagens} imagem(ns) da questão anexada(s) abaixo — considere-as integralmente na análise.]"


def _normalizar_snapshot_taxonomia(taxonomia: Taxonomia) -> dict[str, Any]:
    snap = dict(taxonomia.snapshot_dict())
    snap.pop("id", None)
    disciplinas = snap.get("disciplinas")
    if isinstance(disciplinas, list):
        snap["disciplinas"] = [
            {k: v for k, v in d.items() if k != "id"} if isinstance(d, Mapping) else d for d in disciplinas
        ]
    return snap


def _normalizar_snapshot_perfil(perfil: PerfilClassificacao) -> dict[str, Any]:
    snap = dict(perfil.snapshot_dict())
    snap.pop("id", None)
    return snap


def _hash_snapshot_canonico(snapshot: Mapping[str, Any]) -> str:
    serializado = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


def _extrair_secoes_template(template: str) -> tuple[str, str] | None:
    """Separa marcadores `[SYSTEM]` e `[USER]` antes da substituição de placeholders."""
    idx_system = template.find("[SYSTEM]")
    idx_user = template.find("[USER]")
    if idx_system == -1 or idx_user == -1:
        return None
    if idx_system < idx_user:
        tmpl_system = (template[:idx_system] + template[idx_system + len("[SYSTEM]") : idx_user]).strip()
        tmpl_user = template[idx_user + len("[USER]") :].strip()
        return tmpl_system, tmpl_user
    tmpl_user = (template[:idx_user] + template[idx_user + len("[USER]") : idx_system]).strip()
    tmpl_system = template[idx_system + len("[SYSTEM]") :].strip()
    return tmpl_system, tmpl_user


def montar_prompts_classificacao(
    *,
    questao: Questao,
    taxonomia: Taxonomia,
    perfil: PerfilClassificacao,
    prova: Prova | None = None,
    total_imagens: int | None = None,
) -> tuple[str, str]:
    """Monta `(system, user)` de forma segura contra `{}` em enunciados e alterações de taxonomia/perfil."""
    n_imagens = len(questao.ativos_visuais) if total_imagens is None else total_imagens
    catalogo_disciplinas = _formatar_catalogo_disciplinas(taxonomia)

    valores: dict[str, Any] = {
        "diretrizes_gerais": perfil.diretrizes_gerais,
        "perfil_codigo": perfil.codigo,
        "perfil_versao": perfil.versao,
        "taxonomia_nome": taxonomia.nome,
        "taxonomia_codigo": taxonomia.codigo,
        "curso_referencia": taxonomia.curso_referencia,
        "catalogo_disciplinas": catalogo_disciplinas,
        "guia_fronteiras": perfil.guia_fronteiras,
        "numero": questao.numero,
        "exame": prova.exame if prova is not None else "ENADE",
        "ano": prova.ano if prova is not None else "N/A",
        "curso": (prova.curso if prova is not None else taxonomia.curso_referencia) or "N/A",
        "componente": questao.componente.value,
        "bloco_alertas_extracao": _formatar_alertas_extracao(questao),
        "enunciado": questao.enunciado,
        "alternativas": _formatar_alternativas(questao),
        "bloco_ativos_visuais": _formatar_bloco_ativos(n_imagens),
    }

    hash_perfil = _hash_snapshot_canonico(_normalizar_snapshot_perfil(perfil))
    hash_taxonomia = _hash_snapshot_canonico(_normalizar_snapshot_taxonomia(taxonomia))
    cabecalho_rastreabilidade = (
        f"PERFIL DE CLASSIFICAÇÃO: {perfil.codigo}@{perfil.versao} (snapshot={hash_perfil})\n"
        f"TAXONOMIA: {taxonomia.codigo} | {taxonomia.nome} | Curso: {taxonomia.curso_referencia or 'N/A'} "
        f"(snapshot={hash_taxonomia})"
    )

    secoes = _extrair_secoes_template(perfil.template_prompt)
    if secoes is not None:
        tmpl_system, tmpl_user = secoes
        system_limpo = _renderizar_template_seguro(tmpl_system, valores).strip()
        user_limpo = _renderizar_template_seguro(tmpl_user, valores).strip()
        if cabecalho_rastreabilidade not in system_limpo:
            system_limpo = (
                f"{cabecalho_rastreabilidade}\n\n{system_limpo}" if system_limpo else cabecalho_rastreabilidade
            )
        return system_limpo, user_limpo

    renderizado = _renderizar_template_seguro(perfil.template_prompt, valores)
    system_partes = [
        cabecalho_rastreabilidade,
        "",
        perfil.diretrizes_gerais,
        "",
        f"TAXONOMIA ATIVA: {taxonomia.nome} (`{taxonomia.codigo}`)",
        "CATÁLOGO FECHADO DE DISCIPLINAS PERMITIDAS (use SOMENTE estes códigos):",
        catalogo_disciplinas,
    ]
    if perfil.guia_fronteiras:
        system_partes.extend(["", perfil.guia_fronteiras])
    system_fallback = "\n".join(system_partes).strip()

    user_fallback = renderizado.strip()
    if questao.enunciado and questao.enunciado not in user_fallback:
        user_fallback = f"{user_fallback}\n\nENUNCIADO:\n{questao.enunciado}".strip()
    if questao.alternativas and valores["alternativas"] not in user_fallback:
        user_fallback = f"{user_fallback}\n\nALTERNATIVAS:\n{valores['alternativas']}".strip()
    if valores["bloco_ativos_visuais"] and valores["bloco_ativos_visuais"].strip() not in user_fallback:
        user_fallback = f"{user_fallback}{valores['bloco_ativos_visuais']}".strip()
    return system_fallback, user_fallback


def _ordenar_ativos_visuais(ativos: Sequence[AtivoVisual]) -> list[AtivoVisual]:
    return sorted(ativos, key=lambda ativo: (ativo.ordem, str(ativo.id)))


class ClassificarQuestaoService:
    """Caso de uso de classificação multimodal de uma Questão com travas e 1 retry corretivo."""

    def __init__(
        self,
        classificador: ClassificadorMultimodal,
        armazenamento: ArmazenamentoArquivos | None = None,
    ) -> None:
        self._classificador = classificador
        self._armazenamento = armazenamento

    def _carregar_imagens_questao(
        self,
        questao: Questao,
        imagens_por_chave: Mapping[str, bytes] | None = None,
    ) -> list[bytes]:
        imagens: list[bytes] = []
        for ativo in _ordenar_ativos_visuais(questao.ativos_visuais):
            chave = ativo.chave_arquivo
            if not chave or not chave.strip():
                raise AtivoVisualAusenteError(
                    f"AtivoVisual '{ativo.id}' da questão {questao.numero} não possui chave_arquivo definida."
                )

            if imagens_por_chave is not None and chave in imagens_por_chave:
                imagens.append(imagens_por_chave[chave])
                continue

            if self._armazenamento is None:
                raise AtivoVisualAusenteError(
                    f"Não há armazenamento configurado para carregar o AtivoVisual '{chave}' "
                    f"da questão {questao.numero}."
                )

            try:
                conteudo = self._armazenamento.ler(chave)
            except FileNotFoundError as exc:
                raise AtivoVisualAusenteError(
                    f"Arquivo de AtivoVisual '{chave}' ausente no armazenamento para a questão {questao.numero}."
                ) from exc
            imagens.append(conteudo)
        return imagens

    def classificar(
        self,
        *,
        questao: Questao,
        taxonomia: Taxonomia,
        perfil: PerfilClassificacao,
        prova: Prova | None = None,
        execucao_id: UUID | None = None,
        ignorar_cache: bool = False,
        max_tokens: int = 4096,
        imagens_por_chave: Mapping[str, bytes] | None = None,
    ) -> ResultadoClassificacaoQuestao:
        schema = construir_json_schema_plano(taxonomia)
        nome_schema = f"classificacao_{taxonomia.codigo.replace('-', '_')}"
        imagens_png = self._carregar_imagens_questao(questao, imagens_por_chave=imagens_por_chave)

        system, user = montar_prompts_classificacao(
            questao=questao,
            taxonomia=taxonomia,
            perfil=perfil,
            prova=prova,
            total_imagens=len(imagens_png),
        )

        usar_cache = not ignorar_cache
        chamadas: list[ResultadoChamada] = []

        primeira = self._classificador.classificar_estruturado(
            system=system,
            user=user,
            imagens_png=imagens_png,
            schema=schema,
            nome_schema=nome_schema,
            max_tokens=max_tokens,
            usar_cache=usar_cache,
        )
        chamadas.append(primeira)

        validacao = validar_e_normalizar_classificacao(
            primeira.dados_brutos,
            taxonomia,
            questao.alertas_extracao,
        )
        ultima_chamada = primeira
        retry_corretivo = False

        if not validacao.valida and validacao.elegivel_retry:
            retry_corretivo = True
            codigos_ativos = ", ".join(d.codigo for d in taxonomia.ativas())
            user_retry = (
                f"{user}\n\n"
                "[CORREÇÃO OBRIGATÓRIA]: sua resposta anterior falhou na validação de domínio "
                f"({validacao.motivo_rejeicao}). "
                f"Retorne novamente o JSON usando EXCLUSIVAMENTE códigos ativos do catálogo: [{codigos_ativos}]."
            )
            segunda = self._classificador.classificar_estruturado(
                system=system,
                user=user_retry,
                imagens_png=imagens_png,
                schema=schema,
                nome_schema=nome_schema,
                max_tokens=max_tokens,
                usar_cache=usar_cache,
            )
            chamadas.append(segunda)
            ultima_chamada = segunda
            validacao = validar_e_normalizar_classificacao(
                segunda.dados_brutos,
                taxonomia,
                questao.alertas_extracao,
            )

        metricas = MetricasClassificacao(
            prompt_tokens=sum(c.prompt_tokens for c in chamadas),
            completion_tokens=sum(c.completion_tokens for c in chamadas),
            latencia_ms=round(sum(c.latencia_ms for c in chamadas), 2),
            cache_hit=all(c.from_cache for c in chamadas),
            tentativas=sum(c.tentativas for c in chamadas),
            saneada=validacao.houve_saneamento,
            modo_schema=ultima_chamada.modo_schema,
            cache_key=ultima_chamada.cache_key,
            modelo_efetivo=ultima_chamada.modelo_efetivo,
            retry_corretivo=retry_corretivo,
        )

        if not validacao.valida or validacao.disciplina_principal is None:
            motivo = validacao.motivo_rejeicao or "classificacao_invalida"
            return ResultadoClassificacaoQuestao(
                sucesso=False,
                metricas=metricas,
                validacao=validacao,
                classificacao=None,
                erro=ErroClassificacaoEstruturado(
                    codigo="classificacao_invalida_pos_retry" if retry_corretivo else "classificacao_invalida",
                    mensagem=(f"Questão {questao.numero:02d} permaneceu inválida após validação de domínio: {motivo}"),
                    motivo_rejeicao=motivo,
                    tentativas=metricas.tentativas,
                    retry_corretivo=retry_corretivo,
                    dados_brutos=dict(ultima_chamada.dados_brutos),
                ),
            )

        classificacao = Classificacao(
            questao_id=questao.id,
            taxonomia_id=taxonomia.id,
            disciplina_principal=validacao.disciplina_principal,
            disciplinas_secundarias=validacao.disciplinas_secundarias,
            topicos=validacao.topicos,
            justificativa=validacao.justificativa,
            confianca=validacao.confianca,
            origem=OrigemClassificacao.AUTOMATICA,
            status=StatusClassificacao.PENDENTE_REVISAO,
            vigente=True,
            revisao_prioritaria=validacao.revisao_prioritaria,
            execucao_id=execucao_id,
            alertas_validacao=validacao.alertas_validacao,
        )
        return ResultadoClassificacaoQuestao(
            sucesso=True,
            metricas=metricas,
            validacao=validacao,
            classificacao=classificacao,
            erro=None,
        )
