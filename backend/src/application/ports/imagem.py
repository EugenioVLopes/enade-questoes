"""Porta de validação e normalização de imagens enviadas manualmente na curadoria."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class NormalizadorImagem(Protocol):
    def normalizar_para_png(self, conteudo: bytes) -> bytes:
        """Valida um upload PNG/JPEG e devolve o conteúdo em PNG.

        Deve lançar ``ErroValidacaoDominio`` para conteúdo vazio, corrompido ou de formato não suportado.
        """
        ...
