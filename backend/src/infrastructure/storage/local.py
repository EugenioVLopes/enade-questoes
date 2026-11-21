"""Adaptador de armazenamento local de arquivos em DATA_DIR."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path, PurePosixPath

from domain.exceptions import ErroValidacaoDominio

_DRIVE_PREFIX_RE = re.compile(r"^[A-Za-z]:")


class ArmazenamentoArquivosLocal:
    """Implementação local de ``ArmazenamentoArquivos`` confinada a ``DATA_DIR``."""

    def __init__(self, base_dir: Path | str) -> None:
        self._base_dir = Path(base_dir).resolve()

    @property
    def base_dir(self) -> Path:
        return self._base_dir

    def _validar_e_resolver(self, chave: str) -> tuple[str, Path]:
        if not isinstance(chave, str) or not chave.strip():
            raise ErroValidacaoDominio("Chave de armazenamento não pode ser vazia.")
        if "\x00" in chave:
            raise ErroValidacaoDominio("Chave de armazenamento não pode conter byte NUL.")
        if "\\" in chave:
            raise ErroValidacaoDominio(f"Chave de armazenamento não pode conter barra invertida: {chave!r}.")
        if chave.startswith("/") or _DRIVE_PREFIX_RE.match(chave) or Path(chave).is_absolute():
            raise ErroValidacaoDominio(f"Chave de armazenamento deve ser relativa (não absoluta): {chave!r}.")

        segmentos = chave.split("/")
        if any(parte in {"", ".", ".."} for parte in segmentos):
            raise ErroValidacaoDominio(f"Chave de armazenamento contém segmento inválido: {chave!r}.")

        chave_normalizada = PurePosixPath(*segmentos).as_posix()

        # Verifica ancestrais existentes antes de qualquer escrita/criação de diretórios
        # para bloquear escape por symlink intermediário ou final.
        atual = self._base_dir
        for parte in segmentos:
            atual = atual / parte
            if atual.exists() or atual.is_symlink():
                resolvido = atual.resolve()
                if resolvido == self._base_dir or not resolvido.is_relative_to(self._base_dir):
                    raise ErroValidacaoDominio(f"Caminho fora de DATA_DIR não permitido: {chave!r}.")

        alvo_resolvido = (self._base_dir / chave_normalizada).resolve()
        if alvo_resolvido == self._base_dir or not alvo_resolvido.is_relative_to(self._base_dir):
            raise ErroValidacaoDominio(f"Caminho fora de DATA_DIR não permitido: {chave!r}.")

        return chave_normalizada, alvo_resolvido

    def resolver_caminho(self, chave: str) -> Path:
        _, alvo = self._validar_e_resolver(chave)
        return alvo

    def salvar(self, chave: str, conteudo: bytes) -> str:
        if not isinstance(conteudo, bytes | bytearray | memoryview):
            raise ErroValidacaoDominio("Conteúdo para armazenamento deve ser binário (bytes).")

        chave_normalizada, alvo = self._validar_e_resolver(chave)
        alvo.parent.mkdir(parents=True, exist_ok=True)

        fd, caminho_tmp = tempfile.mkstemp(prefix=".tmp-", dir=alvo.parent)
        try:
            with os.fdopen(fd, "wb") as arquivo_tmp:
                arquivo_tmp.write(conteudo)
                arquivo_tmp.flush()
                os.fsync(arquivo_tmp.fileno())
            os.replace(caminho_tmp, alvo)
        except Exception:
            Path(caminho_tmp).unlink(missing_ok=True)
            raise

        return chave_normalizada

    def ler(self, chave: str) -> bytes:
        _, alvo = self._validar_e_resolver(chave)
        if not alvo.exists():
            raise FileNotFoundError(f"Arquivo não encontrado no armazenamento: {chave}")
        if alvo.is_dir():
            raise IsADirectoryError(f"Chave de armazenamento aponta para um diretório: {chave}")
        return alvo.read_bytes()

    def remover(self, chave: str) -> None:
        _, alvo = self._validar_e_resolver(chave)
        if alvo.is_dir():
            raise IsADirectoryError(f"Não é permitido remover um diretório pela chave: {chave}")
        alvo.unlink(missing_ok=True)

    def existe(self, chave: str) -> bool:
        _, alvo = self._validar_e_resolver(chave)
        return alvo.is_file()
