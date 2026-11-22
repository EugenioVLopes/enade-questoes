from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt

type EscopoExecucaoLiteral = Literal["todas", "prova_id", "pendentes", "disciplina_arquivada", "questao_ids"]
type StatusExecucaoLiteral = Literal[
    "pendente",
    "processando",
    "concluida",
    "concluida_com_erros",
    "interrompida",
    "erro",
]


class WorkerHealthResponse(BaseModel):
    estado: Literal["ocioso", "ocupado"]
    tarefa_ativa: str | None = None
    tipo: Literal["ingestao", "classificacao"] | None = None
    alvo: str | None = None
    processadas: int | None = None
    total: int | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degradado"]
    banco_dados: Literal["conectado", "indisponivel"]
    worker: WorkerHealthResponse


class ErroDetalheResponse(BaseModel):
    detail: str


class ConflitoProvaResponse(BaseModel):
    detail: str
    prova_id: UUID
    exame: str
    curso: str
    ano: int


class MetadadosIngestaoResponse(BaseModel):
    total_questoes_extraidas: int
    imagens_detectadas: int
    imagens_filtradas_margem: int
    formulas_recortadas: int
    usou_ocr: bool
    paginas_fonte_symbol: list[int]
    gabarito_enviado: bool


class IngestaoResumoResponse(BaseModel):
    id: UUID
    status: Literal["pendente", "processando", "concluida", "erro", "interrompida"]
    mensagem_erro: str | None = None
    iniciada_em: datetime | None = None
    concluida_em: datetime | None = None
    criada_em: datetime | None = None
    metadados: MetadadosIngestaoResponse


class ContagemQuestoesResponse(BaseModel):
    total: int
    editadas_manualmente: int
    gabarito_validas: int
    gabarito_anuladas: int
    gabarito_pendentes: int


class ContagemAlertasResponse(BaseModel):
    abertos: int
    criticos_abertos: int
    questoes_com_alerta_aberto: int


class ClassificacaoEncadeadaResponse(BaseModel):
    solicitada: bool
    taxonomia_id: UUID | None = None
    perfil_id: UUID | None = None
    execucao_id: UUID | None = None
    status: str | None = None


class ProvaDetalheResponse(BaseModel):
    id: UUID
    exame: str
    curso: str
    ano: int
    questao_inicio: int
    questao_fim: int
    possui_gabarito: bool
    criada_em: datetime | None = None
    atualizada_em: datetime | None = None
    ultima_ingestao: IngestaoResumoResponse | None = None
    questoes: ContagemQuestoesResponse
    alertas: ContagemAlertasResponse
    classificacao_encadeada: ClassificacaoEncadeadaResponse


class ListaProvasResponse(BaseModel):
    itens: list[ProvaDetalheResponse]
    total: int


class ProvaIngestaoAceitaResponse(BaseModel):
    prova_id: UUID
    ingestao_id: UUID
    status: Literal["pendente", "processando", "concluida", "erro", "interrompida"]
    exame: str
    curso: str
    ano: int
    questao_inicio: int
    questao_fim: int
    possui_gabarito: bool


class ResumoAtualizacaoGabaritoResponse(BaseModel):
    mantidas: int
    alteradas: int
    anuladas: int
    sem_correspondencia: list[int]
    questoes_sem_gabarito: list[int]


class ReprocessarProvaRequest(BaseModel):
    sobrescrever_editadas: bool = False


class ReprocessarProvaAceitaResponse(BaseModel):
    prova_id: UUID
    ingestao_id: UUID
    status: Literal["pendente", "processando", "concluida", "erro", "interrompida"]
    sobrescrever_editadas: bool


class DisciplinaCriacaoInput(BaseModel):
    codigo: str
    nome: str
    ementa: str = ""
    ativa: bool = True


class TaxonomiaCriarRequest(BaseModel):
    codigo: str
    nome: str
    curso_referencia: str = ""
    disciplinas: list[DisciplinaCriacaoInput] = Field(default_factory=list)


class TaxonomiaAtualizarRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str | None = None
    curso_referencia: str | None = None


class DisciplinaCriarRequest(BaseModel):
    codigo: str
    nome: str
    ementa: str = ""
    ativa: bool = True
    ordem: StrictInt | None = None


class DisciplinaAtualizarRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nome: str | None = None
    ementa: str | None = None
    ativa: bool | None = None
    ordem: StrictInt | None = None


class DisciplinaResponse(BaseModel):
    id: UUID
    taxonomia_id: UUID
    codigo: str
    nome: str
    ementa: str
    ativa: bool
    classificacoes_vigentes_impactadas: int


class TaxonomiaResponse(BaseModel):
    id: UUID
    codigo: str
    nome: str
    curso_referencia: str
    disciplinas: list[DisciplinaResponse]


class ListaTaxonomiasResponse(BaseModel):
    itens: list[TaxonomiaResponse]
    total: int


class PerfilClassificacaoCriarRequest(BaseModel):
    versao: str
    codigo: str | None = None
    perfil_base_id: UUID | None = None
    diretrizes_gerais: str | None = None
    guia_fronteiras: str | None = None
    template_prompt: str | None = None
    descricao: str | None = None


class PerfilClassificacaoResponse(BaseModel):
    id: UUID
    codigo: str
    versao: str
    diretrizes_gerais: str
    guia_fronteiras: str
    template_prompt: str
    descricao: str
    criado_em: datetime | None = None


class ListaPerfisClassificacaoResponse(BaseModel):
    itens: list[PerfilClassificacaoResponse]
    total: int


class ExecucaoClassificacaoCriarRequest(BaseModel):
    taxonomia_id: UUID
    perfil_id: UUID
    escopo: EscopoExecucaoLiteral = "todas"
    incluir_revisadas: bool = False
    prova_id: UUID | None = None
    questao_ids: list[UUID] = Field(default_factory=list)


class ExecucaoClassificacaoAceitaResponse(BaseModel):
    execucao_id: UUID
    taxonomia_id: UUID
    perfil_id: UUID
    escopo: EscopoExecucaoLiteral
    escopo_prova_id: UUID | None = None
    escopo_questao_ids: list[UUID]
    incluir_revisadas: bool
    status: StatusExecucaoLiteral
    total_itens: int
    processadas: int


class SnapshotTaxonomiaResumoResponse(BaseModel):
    id: UUID | None = None
    codigo: str
    nome: str
    curso_referencia: str = ""
    total_disciplinas: int
    disciplinas_codigos: list[str] = Field(default_factory=list)


class SnapshotPerfilResumoResponse(BaseModel):
    id: UUID | None = None
    codigo: str
    versao: str
    descricao: str = ""


class SnapshotExecucaoResumoResponse(BaseModel):
    taxonomia: SnapshotTaxonomiaResumoResponse
    perfil: SnapshotPerfilResumoResponse


class ExecucaoClassificacaoResumoResponse(BaseModel):
    id: UUID
    taxonomia_id: UUID
    perfil_id: UUID
    escopo: EscopoExecucaoLiteral
    escopo_prova_id: UUID | None = None
    escopo_questao_ids: list[UUID]
    incluir_revisadas: bool
    status: StatusExecucaoLiteral
    total_itens: int
    processadas: int
    total_erros: int
    divergencias_abertas: int
    cache_hits: int
    prompt_tokens: int
    completion_tokens: int
    criada_em: datetime | None = None
    iniciada_em: datetime | None = None
    concluida_em: datetime | None = None
    snapshot_resumo: SnapshotExecucaoResumoResponse


class ExecucaoClassificacaoDetalheResponse(ExecucaoClassificacaoResumoResponse):
    erros_por_questao: dict[str, str]
    snapshot_taxonomia: dict[str, Any]
    snapshot_perfil: dict[str, Any]
    questao_ids_alvo: list[UUID]
    questao_ids_concluidas: list[UUID]


class ListaExecucoesClassificacaoResponse(BaseModel):
    itens: list[ExecucaoClassificacaoResumoResponse]
    total: int
