from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


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
