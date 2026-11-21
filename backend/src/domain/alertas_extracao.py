"""Avaliação determinística e ciclo de vida dos 6 Alertas de Extração."""

from __future__ import annotations

import re
from collections.abc import Collection
from datetime import datetime
from uuid import UUID

from domain.enums import CodigoAlertaExtracao, LetraAlternativa, SituacaoGabarito, StatusAlerta, TipoQuestao
from domain.exceptions import ErroInvarianteDominio
from domain.prova import ALERTAS_ESTRUTURAIS, AlertaExtracao, Questao

MARCADOR_FORMULA_NAO_DECODIFICADA = "<!-- formula-not-decoded -->"
PATTERN_FORMULA_NAO_DECODIFICADA = re.compile(r"<!--\s*formula-not-decoded\s*-->")
MIN_CHARS_ENUNCIADO_PADRAO = 15
MIN_ALFANUMERICOS_ENUNCIADO_PADRAO = 8

_HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
_MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MARKDOWN_PUNCT_PATTERN = re.compile(r"[#*`_~|>\[\]()]+")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_LETRAS_ESPERADAS = [
    LetraAlternativa.A,
    LetraAlternativa.B,
    LetraAlternativa.C,
    LetraAlternativa.D,
    LetraAlternativa.E,
]

_MENSAGENS_PADRAO: dict[CodigoAlertaExtracao, str] = {
    CodigoAlertaExtracao.FORMULA_NAO_DECODIFICADA: (
        "Enunciado ou alternativa contém marcador '<!-- formula-not-decoded -->'."
    ),
    CodigoAlertaExtracao.ALTERNATIVAS_INCOMPLETAS: (
        "Questão objetiva sem 5 alternativas válidas e ordenadas de A a E."
    ),
    CodigoAlertaExtracao.PDF_VIA_OCR: (
        "Prova processada com fallback de OCR de página inteira; exige inspeção visual."
    ),
    CodigoAlertaExtracao.ENUNCIADO_SUSPEITO: (
        "Enunciado vazio, corrompido ou abaixo do limiar mínimo de texto legível."
    ),
    CodigoAlertaExtracao.FONTE_SYMBOL_DETECTADA: (
        "Página de origem usa fonte Symbol/MT-Extra; verificar símbolos gregos e matemáticos."
    ),
    CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA: (
        "PDF de gabarito foi enviado na ingestão, mas não contém registro para esta questão."
    ),
}


def _texto_legivel_enunciado(enunciado: str) -> str:
    sem_comentarios = _HTML_COMMENT_PATTERN.sub(" ", enunciado)
    sem_imagens = _MARKDOWN_IMAGE_PATTERN.sub(" ", sem_comentarios)
    sem_marcadores = _MARKDOWN_PUNCT_PATTERN.sub(" ", sem_imagens)
    return _WHITESPACE_PATTERN.sub(" ", sem_marcadores).strip()


def _formula_nao_decodificada(questao: Questao) -> bool:
    if PATTERN_FORMULA_NAO_DECODIFICADA.search(questao.enunciado):
        return True
    return any(PATTERN_FORMULA_NAO_DECODIFICADA.search(alt.texto) for alt in questao.alternativas)


def _alternativas_incompletas(questao: Questao) -> bool:
    if questao.tipo != TipoQuestao.OBJETIVA:
        return False
    if len(questao.alternativas) != 5:
        return True
    if [alt.letra for alt in questao.alternativas] != _LETRAS_ESPERADAS:
        return True
    return any(not alt.texto.strip() for alt in questao.alternativas)


def _enunciado_suspeito(
    questao: Questao,
    min_chars_enunciado: int,
    min_alfanumericos: int,
) -> bool:
    if "\ufffd" in questao.enunciado:
        return True
    legivel = _texto_legivel_enunciado(questao.enunciado)
    if len(legivel) < min_chars_enunciado:
        return True
    qtd_alfanum = sum(1 for ch in legivel if ch.isalnum())
    return qtd_alfanum < min_alfanumericos


def _gabarito_ausente_na_prova(questao: Questao, gabarito_enviado_na_prova: bool) -> bool:
    return gabarito_enviado_na_prova and questao.gabarito.situacao_gabarito == SituacaoGabarito.PENDENTE


def _condicoes_estruturais(
    questao: Questao,
    *,
    gabarito_enviado_na_prova: bool,
    min_chars_enunciado: int,
    min_alfanumericos: int,
) -> dict[CodigoAlertaExtracao, bool]:
    return {
        CodigoAlertaExtracao.FORMULA_NAO_DECODIFICADA: _formula_nao_decodificada(questao),
        CodigoAlertaExtracao.ALTERNATIVAS_INCOMPLETAS: _alternativas_incompletas(questao),
        CodigoAlertaExtracao.ENUNCIADO_SUSPEITO: _enunciado_suspeito(
            questao,
            min_chars_enunciado=min_chars_enunciado,
            min_alfanumericos=min_alfanumericos,
        ),
        CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA: _gabarito_ausente_na_prova(
            questao,
            gabarito_enviado_na_prova=gabarito_enviado_na_prova,
        ),
    }


def avaliar_alertas_extracao(
    questao: Questao,
    *,
    usou_ocr: bool = False,
    paginas_com_fonte_symbol: Collection[int] = (),
    gabarito_enviado_na_prova: bool = False,
    min_chars_enunciado: int = MIN_CHARS_ENUNCIADO_PADRAO,
    min_alfanumericos: int = MIN_ALFANUMERICOS_ENUNCIADO_PADRAO,
) -> list[AlertaExtracao]:
    """Avalia os 6 alertas determinísticos de extração na ingestão da Questão."""
    condicoes = _condicoes_estruturais(
        questao,
        gabarito_enviado_na_prova=gabarito_enviado_na_prova,
        min_chars_enunciado=min_chars_enunciado,
        min_alfanumericos=min_alfanumericos,
    )
    paginas_symbol = set(paginas_com_fonte_symbol)
    condicoes[CodigoAlertaExtracao.PDF_VIA_OCR] = usou_ocr
    condicoes[CodigoAlertaExtracao.FONTE_SYMBOL_DETECTADA] = bool(set(questao.paginas) & paginas_symbol)

    ordem_codigos = (
        CodigoAlertaExtracao.FORMULA_NAO_DECODIFICADA,
        CodigoAlertaExtracao.ALTERNATIVAS_INCOMPLETAS,
        CodigoAlertaExtracao.PDF_VIA_OCR,
        CodigoAlertaExtracao.ENUNCIADO_SUSPEITO,
        CodigoAlertaExtracao.FONTE_SYMBOL_DETECTADA,
        CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA,
    )
    alertas = [
        AlertaExtracao(
            codigo=codigo,
            status=StatusAlerta.ABERTO,
            mensagem=_MENSAGENS_PADRAO[codigo],
        )
        for codigo in ordem_codigos
        if condicoes[codigo]
    ]
    questao.alertas_extracao = alertas
    return list(questao.alertas_extracao)


def reavaliar_alertas_estruturais(
    questao: Questao,
    agora: datetime,
    *,
    gabarito_enviado_na_prova: bool | None = None,
    min_chars_enunciado: int = MIN_CHARS_ENUNCIADO_PADRAO,
    min_alfanumericos: int = MIN_ALFANUMERICOS_ENUNCIADO_PADRAO,
) -> list[AlertaExtracao]:
    """Reavalia os 4 alertas estruturais após edição, preservando os de inspeção."""
    mapa_existentes = {alerta.codigo: alerta for alerta in questao.alertas_extracao}
    if gabarito_enviado_na_prova is None:
        gabarito_enviado_na_prova = CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA in mapa_existentes

    condicoes = _condicoes_estruturais(
        questao,
        gabarito_enviado_na_prova=gabarito_enviado_na_prova,
        min_chars_enunciado=min_chars_enunciado,
        min_alfanumericos=min_alfanumericos,
    )

    for codigo in ALERTAS_ESTRUTURAIS:
        ativo = condicoes[codigo]
        existente = mapa_existentes.get(codigo)
        if ativo:
            if existente is None:
                questao.alertas_extracao.append(
                    AlertaExtracao(
                        codigo=codigo,
                        status=StatusAlerta.ABERTO,
                        mensagem=_MENSAGENS_PADRAO[codigo],
                    )
                )
            elif not existente.is_aberto:
                existente.reabrir(_MENSAGENS_PADRAO[codigo])
        elif existente is not None and existente.is_aberto:
            existente.resolver(agora)

    return list(questao.alertas_extracao)


def marcar_alerta_verificado(
    questao: Questao,
    codigo_ou_id: CodigoAlertaExtracao | UUID,
    agora: datetime,
    *,
    permitir_estrutural: bool = False,
) -> AlertaExtracao:
    """Resolve explicitamente um alerta de inspeção (pdf_via_ocr / fonte_symbol_detectada)."""
    alvo: AlertaExtracao | None = None
    for alerta in questao.alertas_extracao:
        if isinstance(codigo_ou_id, UUID) and alerta.id == codigo_ou_id:
            alvo = alerta
            break
        if isinstance(codigo_ou_id, CodigoAlertaExtracao) and alerta.codigo == codigo_ou_id:
            alvo = alerta
            break

    if alvo is None:
        raise ErroInvarianteDominio(f"Alerta não encontrado na questão {questao.numero}: {codigo_ou_id!r}.")

    if not permitir_estrutural and alvo.is_estrutural:
        raise ErroInvarianteDominio(
            f"Alerta estrutural '{alvo.codigo.value}' deve ser resolvido pela correção do conteúdo."
        )

    alvo.resolver(agora)
    questao.editada_manualmente = True
    return alvo
