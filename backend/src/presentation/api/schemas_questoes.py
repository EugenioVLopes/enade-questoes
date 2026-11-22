"""Schemas Pydantic dos endpoints de Questões, revisão humana e edição de conteúdo/mídia."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from domain.enums import (
    CodigoAlertaExtracao,
    LetraAlternativa,
    OrigemAtivoVisual,
    OrigemClassificacao,
    ResolucaoDivergencia,
    SeveridadeAlerta,
    SituacaoGabarito,
    StatusAlerta,
    StatusClassificacao,
    StatusDivergencia,
)
from presentation.api.tipos import TextoSeguro

# Limites de tamanho na borda HTTP: entradas maiores são rejeitadas com 422 antes de qualquer processamento.
LIMITE_ENUNCIADO = 20_000
LIMITE_ALTERNATIVA = 5_000
LIMITE_JUSTIFICATIVA = 5_000
LIMITE_TOPICO = 200
LIMITE_CODIGO_DISCIPLINA = 200
MAX_TOPICOS = 20
MAX_DISCIPLINAS_SECUNDARIAS = 2
MAX_ALTERNATIVAS = 5

# ---------------------------------------------------------------------------
# Componentes de leitura
# ---------------------------------------------------------------------------


class ProvaResumoResponse(BaseModel):
    id: UUID
    exame: str
    curso: str
    ano: int


class AlternativaResponse(BaseModel):
    letra: LetraAlternativa
    texto: str


class AtivoVisualResponse(BaseModel):
    id: UUID
    origem: OrigemAtivoVisual
    alternativa_letra: LetraAlternativa | None = None
    ordem: int
    pagina: int | None = None
    url_arquivo: str


class GabaritoResponse(BaseModel):
    situacao_gabarito: SituacaoGabarito
    alternativa_correta: LetraAlternativa | None = None


class AlertaExtracaoResponse(BaseModel):
    id: UUID
    codigo: CodigoAlertaExtracao
    severidade: SeveridadeAlerta
    status: StatusAlerta
    mensagem: str
    resolvido_em: datetime | None = None


class ClassificacaoResponse(BaseModel):
    id: UUID
    questao_id: UUID
    taxonomia_id: UUID
    disciplina_principal: str
    disciplinas_secundarias: list[str]
    topicos: list[str]
    justificativa: str
    confianca: float
    origem: OrigemClassificacao
    status: StatusClassificacao
    vigente: bool
    revisao_prioritaria: bool
    execucao_id: UUID | None = None
    substitui_classificacao_id: UUID | None = None
    alertas_validacao: list[str]
    criada_em: datetime | None = None
    revisada_em: datetime | None = None


class DivergenciaResponse(BaseModel):
    id: UUID
    questao_id: UUID
    taxonomia_id: UUID
    execucao_id: UUID
    classificacao_vigente_id: UUID
    classificacao_candidata_id: UUID | None = None
    disciplina_principal_candidata: str
    disciplinas_secundarias_candidatas: list[str]
    topicos_candidatos: list[str]
    justificativa_candidata: str
    confianca_candidata: float
    status: StatusDivergencia
    resolucao: ResolucaoDivergencia | None = None
    criada_em: datetime | None = None
    resolvida_em: datetime | None = None


class ClassificacaoOutraTaxonomiaResponse(BaseModel):
    taxonomia_id: UUID
    taxonomia_codigo: str
    taxonomia_nome: str
    classificacao: ClassificacaoResponse


class DetalheQuestaoResponse(BaseModel):
    id: UUID
    prova: ProvaResumoResponse
    numero: int
    componente: str
    tipo: str
    paginas: list[int]
    enunciado: str
    editada_manualmente: bool
    versao: int
    alternativas: list[AlternativaResponse]
    ativos_visuais: list[AtivoVisualResponse]
    gabarito: GabaritoResponse
    alertas_extracao: list[AlertaExtracaoResponse]
    taxonomia_id: UUID | None = None
    classificacao_vigente: ClassificacaoResponse | None = None
    disciplinas_arquivadas_em_uso: list[str]
    divergencia_aberta: DivergenciaResponse | None = None
    historico: list[ClassificacaoResponse]
    outras_taxonomias: list[ClassificacaoOutraTaxonomiaResponse]


# ---------------------------------------------------------------------------
# Lista / fila de revisão
# ---------------------------------------------------------------------------


class ClassificacaoResumoResponse(BaseModel):
    id: UUID
    origem: OrigemClassificacao
    status: StatusClassificacao
    confianca: float
    revisao_prioritaria: bool
    disciplina_principal: str
    disciplinas_secundarias: list[str]
    topicos: list[str]


class ItemQuestaoResponse(BaseModel):
    id: UUID
    prova: ProvaResumoResponse
    numero: int
    trecho: str
    situacao_gabarito: SituacaoGabarito
    editada_manualmente: bool
    alertas_abertos: list[CodigoAlertaExtracao]
    revisao_prioritaria: bool
    tem_divergencia_aberta: bool
    usa_disciplina_arquivada: bool
    classificacao: ClassificacaoResumoResponse | None = None


class ContadoresRevisaoResponse(BaseModel):
    pendentes: int
    divergencias: int
    disciplina_arquivada: int


class ListaQuestoesResponse(BaseModel):
    itens: list[ItemQuestaoResponse]
    total: int
    pagina: int
    tamanho_pagina: int
    taxonomia_id: UUID | None = None
    contadores: ContadoresRevisaoResponse | None = None


# ---------------------------------------------------------------------------
# Revisão humana
# ---------------------------------------------------------------------------


class CorrigirClassificacaoRequest(BaseModel):
    disciplina_principal: TextoSeguro = Field(min_length=1, max_length=LIMITE_CODIGO_DISCIPLINA)
    disciplinas_secundarias: list[Annotated[TextoSeguro, Field(max_length=LIMITE_CODIGO_DISCIPLINA)]] = Field(
        default_factory=list, max_length=MAX_DISCIPLINAS_SECUNDARIAS
    )
    topicos: list[Annotated[TextoSeguro, Field(max_length=LIMITE_TOPICO)]] = Field(
        default_factory=list, max_length=MAX_TOPICOS
    )
    justificativa: TextoSeguro = Field(default="", max_length=LIMITE_JUSTIFICATIVA)


class ResolverDivergenciaRequest(BaseModel):
    resolucao: ResolucaoDivergencia
    classificacao: CorrigirClassificacaoRequest | None = None


class ResolverDivergenciaResponse(BaseModel):
    divergencia: DivergenciaResponse
    classificacao_vigente: ClassificacaoResponse | None = None


# ---------------------------------------------------------------------------
# Edição curada
# ---------------------------------------------------------------------------


class AlternativaEdicaoRequest(BaseModel):
    letra: LetraAlternativa
    texto: TextoSeguro = Field(max_length=LIMITE_ALTERNATIVA)


class GabaritoEdicaoRequest(BaseModel):
    situacao_gabarito: SituacaoGabarito
    alternativa_correta: LetraAlternativa | None = None


class EditarQuestaoRequest(BaseModel):
    enunciado: TextoSeguro | None = Field(default=None, max_length=LIMITE_ENUNCIADO)
    alternativas: list[AlternativaEdicaoRequest] | None = Field(default=None, max_length=MAX_ALTERNATIVAS)
    gabarito: GabaritoEdicaoRequest | None = None
    versao: int | None = Field(default=None, ge=1, le=2_147_483_647)


class AtualizarAlertaRequest(BaseModel):
    status: Literal["resolvido"]
