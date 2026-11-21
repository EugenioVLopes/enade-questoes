"""Casos de uso de entrega controlada de mídia e renderização de páginas PDF."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID

from application.exceptions import RecursoNaoEncontradoError
from application.ports.armazenamento import ArmazenamentoArquivos
from application.ports.extracao import RenderizadorPaginaPdf
from application.ports.repositorios import RepositorioAtivosVisuais, RepositorioProvas
from domain.exceptions import ErroValidacaoDominio


@dataclass(frozen=True, slots=True)
class ImagemPngResultado:
    conteudo_png: bytes
    etag: str


def _calcular_etag(conteudo: bytes) -> str:
    digest = hashlib.sha256(conteudo).hexdigest()
    return f'"{digest}"'


class ObterPaginaProvaImagemUseCase:
    def __init__(
        self,
        *,
        repo_provas: RepositorioProvas,
        armazenamento: ArmazenamentoArquivos,
        renderizador: RenderizadorPaginaPdf,
    ) -> None:
        self._repo_provas = repo_provas
        self._armazenamento = armazenamento
        self._renderizador = renderizador

    def execute(self, prova_id: UUID, pagina: int, *, dpi: int = 150) -> ImagemPngResultado:
        if isinstance(pagina, bool) or not isinstance(pagina, int) or pagina < 1:
            raise ErroValidacaoDominio(f"'pagina' deve ser inteiro >= 1; recebido: {pagina!r}.")

        prova = self._repo_provas.buscar_por_id(prova_id)
        if prova is None or not prova.caminho_pdf:
            raise RecursoNaoEncontradoError(f"Prova '{prova_id}' ou PDF original não encontrado.")

        if not self._armazenamento.existe(prova.caminho_pdf):
            raise RecursoNaoEncontradoError(f"Arquivo PDF da prova '{prova_id}' não encontrado no armazenamento.")

        caminho_pdf = self._armazenamento.resolver_caminho(prova.caminho_pdf)
        total_paginas = self._renderizador.contar_paginas(caminho_pdf)
        if pagina > total_paginas:
            raise RecursoNaoEncontradoError(
                f"Página {pagina} inexistente no PDF da prova '{prova_id}' (total de páginas: {total_paginas})."
            )

        png_bytes = self._renderizador.renderizar_pagina(caminho_pdf, pagina, dpi=dpi)
        return ImagemPngResultado(conteudo_png=png_bytes, etag=_calcular_etag(png_bytes))


class ObterAtivoVisualArquivoUseCase:
    def __init__(
        self,
        *,
        repo_ativos: RepositorioAtivosVisuais,
        armazenamento: ArmazenamentoArquivos,
    ) -> None:
        self._repo_ativos = repo_ativos
        self._armazenamento = armazenamento

    def execute(self, ativo_id: UUID) -> ImagemPngResultado:
        ativo = self._repo_ativos.buscar_por_id(ativo_id)
        if ativo is None or not ativo.chave_arquivo:
            raise RecursoNaoEncontradoError(f"Ativo visual '{ativo_id}' não encontrado.")

        try:
            png_bytes = self._armazenamento.ler(ativo.chave_arquivo)
        except FileNotFoundError as err:
            raise RecursoNaoEncontradoError(
                f"Arquivo de imagem do ativo visual '{ativo_id}' não encontrado no armazenamento."
            ) from err

        return ImagemPngResultado(conteudo_png=png_bytes, etag=_calcular_etag(png_bytes))
