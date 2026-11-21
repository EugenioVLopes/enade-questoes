"""Porta de armazenamento de arquivos e artefatos binários em disco/storage."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ArmazenamentoArquivos(Protocol):
    """Porta de leitura e escrita de PDFs, JSON bruto, PNGs e cache."""

    def salvar(self, chave: str, conteudo: bytes) -> str: ...

    def ler(self, chave: str) -> bytes: ...

    def remover(self, chave: str) -> None: ...

    def existe(self, chave: str) -> bool: ...

    def resolver_caminho(self, chave: str) -> Path: ...
