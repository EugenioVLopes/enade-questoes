"""Enumerações canônicas da camada de domínio do Enade Questões."""

from __future__ import annotations

from enum import StrEnum


class StatusIngestao(StrEnum):
    PENDENTE = "pendente"
    PROCESSANDO = "processando"
    CONCLUIDA = "concluida"
    ERRO = "erro"
    INTERROMPIDA = "interrompida"


class ComponenteProva(StrEnum):
    COMPONENTE_ESPECIFICO = "componente_especifico"


class TipoQuestao(StrEnum):
    OBJETIVA = "objetiva"
    DISCURSIVA = "discursiva"


class LetraAlternativa(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class OrigemAtivoVisual(StrEnum):
    PICTURE_DOCLING = "picture_docling"
    FORMULA_RECORTE = "formula_recorte"
    UPLOAD_MANUAL = "upload_manual"


class SituacaoGabarito(StrEnum):
    VALIDA = "valida"
    ANULADA = "anulada"
    PENDENTE = "pendente"


class CodigoAlertaExtracao(StrEnum):
    FORMULA_NAO_DECODIFICADA = "formula_nao_decodificada"
    ALTERNATIVAS_INCOMPLETAS = "alternativas_incompletas"
    PDF_VIA_OCR = "pdf_via_ocr"
    ENUNCIADO_SUSPEITO = "enunciado_suspeito"
    FONTE_SYMBOL_DETECTADA = "fonte_symbol_detectada"
    GABARITO_AUSENTE_NA_PROVA = "gabarito_ausente_na_prova"


class SeveridadeAlerta(StrEnum):
    CRITICO = "critico"
    INFORMATIVO = "informativo"


class StatusAlerta(StrEnum):
    ABERTO = "aberto"
    RESOLVIDO = "resolvido"


class EscopoExecucao(StrEnum):
    TODAS = "todas"
    PROVA_ID = "prova_id"
    PENDENTES = "pendentes"
    DISCIPLINA_ARQUIVADA = "disciplina_arquivada"
    QUESTAO_IDS = "questao_ids"


class StatusExecucaoClassificacao(StrEnum):
    PENDENTE = "pendente"
    PROCESSANDO = "processando"
    CONCLUIDA = "concluida"
    CONCLUIDA_COM_ERROS = "concluida_com_erros"
    INTERROMPIDA = "interrompida"
    ERRO = "erro"


class OrigemClassificacao(StrEnum):
    AUTOMATICA = "automatica"
    HUMANA = "humana"


class StatusClassificacao(StrEnum):
    PENDENTE_REVISAO = "pendente_revisao"
    APROVADA = "aprovada"


class StatusDivergencia(StrEnum):
    ABERTA = "aberta"
    RESOLVIDA = "resolvida"


class ResolucaoDivergencia(StrEnum):
    ACEITAR_CANDIDATA = "aceitar_candidata"
    MANTER_HUMANA = "manter_humana"
    EDITAR_MANUALMENTE = "editar_manualmente"
