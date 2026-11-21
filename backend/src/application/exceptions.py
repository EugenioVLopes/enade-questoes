"""Exceções da camada de aplicação mapeáveis para respostas HTTP."""

from __future__ import annotations

from uuid import UUID

from domain.exceptions import ErroDominio


class ErroAplicacao(ErroDominio):
    """Exceção base para erros semânticos da camada de aplicação."""


class RecursoNaoEncontradoError(ErroAplicacao):
    """Recurso solicitado não existe."""


class ConflitoProvaExistenteError(ErroAplicacao):
    """Já existe uma Prova cadastrada com a mesma chave natural (exame, curso, ano)."""

    def __init__(self, prova_id: UUID, exame: str, curso: str, ano: int) -> None:
        self.prova_id = prova_id
        self.exame = exame
        self.curso = curso
        self.ano = ano
        super().__init__(f"Já existe uma prova cadastrada para ({exame}, {curso}, {ano}) com id '{prova_id}'.")


class ConflitoEstadoIngestaoError(ErroAplicacao):
    """Operação incompatível com uma Ingestão atualmente pendente ou em processamento."""


class ArquivoPdfAusenteError(ErroAplicacao):
    """Arquivo PDF obrigatório ausente no armazenamento local."""
