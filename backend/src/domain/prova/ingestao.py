"""Ingestão de prova e seus metadados."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from domain.enums import StatusIngestao
from domain.exceptions import ErroInvarianteDominio, ErroValidacaoDominio
from domain.prova._validacao import _validar_inteiro_nao_negativo, _validar_inteiro_positivo


@dataclass(frozen=True, slots=True)
class MetadadosIngestao:
    """Telemetria agregada da etapa de extração de uma Ingestão."""

    total_questoes_extraidas: int = 0
    imagens_detectadas: int = 0
    imagens_filtradas_margem: int = 0
    formulas_recortadas: int = 0
    usou_ocr: bool = False
    paginas_fonte_symbol: tuple[int, ...] = ()
    gabarito_enviado: bool = False
    taxonomia_id_encadeada: UUID | None = None
    perfil_id_encadeada: UUID | None = None
    execucao_classificacao_id: UUID | None = None
    status_classificacao_encadeada: str | None = None

    def __post_init__(self) -> None:
        _validar_inteiro_nao_negativo(self.total_questoes_extraidas, "total_questoes_extraidas")
        _validar_inteiro_nao_negativo(self.imagens_detectadas, "imagens_detectadas")
        _validar_inteiro_nao_negativo(self.imagens_filtradas_margem, "imagens_filtradas_margem")
        _validar_inteiro_nao_negativo(self.formulas_recortadas, "formulas_recortadas")
        paginas = tuple(_validar_inteiro_positivo(p, "paginas_fonte_symbol") for p in self.paginas_fonte_symbol)
        object.__setattr__(self, "paginas_fonte_symbol", paginas)
        if self.status_classificacao_encadeada is not None:
            status_limpo = self.status_classificacao_encadeada.strip()
            object.__setattr__(self, "status_classificacao_encadeada", status_limpo or None)


@dataclass(slots=True)
class Ingestao:
    """Processo registrado de carga, extração e estruturação de uma Prova."""

    prova_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: StatusIngestao = StatusIngestao.PENDENTE
    mensagem_erro: str | None = None
    metadados: MetadadosIngestao = field(default_factory=MetadadosIngestao)
    iniciada_em: datetime | None = None
    concluida_em: datetime | None = None
    criada_em: datetime | None = None

    def __post_init__(self) -> None:
        try:
            self.status = StatusIngestao(self.status)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Status de ingestão inválido: {self.status!r}.") from err

    def iniciar(self, agora: datetime) -> None:
        permitidos = {
            StatusIngestao.PENDENTE,
            StatusIngestao.ERRO,
            StatusIngestao.INTERROMPIDA,
            StatusIngestao.CONCLUIDA,
        }
        if self.status not in permitidos:
            raise ErroInvarianteDominio(f"Não é possível iniciar ingestão no estado '{self.status.value}'.")
        self.status = StatusIngestao.PROCESSANDO
        self.iniciada_em = agora
        self.mensagem_erro = None
        self.concluida_em = None

    def concluir(self, agora: datetime, metadados: MetadadosIngestao) -> None:
        if self.status != StatusIngestao.PROCESSANDO:
            raise ErroInvarianteDominio(
                f"Só é possível concluir ingestão em 'processando'; estado atual: '{self.status.value}'."
            )
        self.status = StatusIngestao.CONCLUIDA
        self.concluida_em = agora
        self.metadados = metadados
        self.mensagem_erro = None

    def falhar(self, mensagem: str, agora: datetime) -> None:
        if self.status != StatusIngestao.PROCESSANDO:
            raise ErroInvarianteDominio(
                f"Só é possível falhar ingestão em 'processando'; estado atual: '{self.status.value}'."
            )
        if not mensagem.strip():
            raise ErroValidacaoDominio("Mensagem de erro da ingestão não pode ser vazia.")
        self.status = StatusIngestao.ERRO
        self.mensagem_erro = mensagem.strip()
        self.concluida_em = agora

    def interromper(self, agora: datetime, motivo: str = "Processo interrompido durante execução.") -> None:
        if self.status != StatusIngestao.PROCESSANDO:
            raise ErroInvarianteDominio(
                f"Só é possível interromper ingestão em 'processando'; estado atual: '{self.status.value}'."
            )
        self.status = StatusIngestao.INTERROMPIDA
        self.mensagem_erro = motivo.strip() or "Processo interrompido durante execução."
        self.concluida_em = agora
