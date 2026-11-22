"""Tipos compartilhados de entrada HTTP."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator

_SURROGATE_ISOLADO = re.compile("[\ud800-\udfff]")


def _rejeitar_caracteres_invalidos(valor: str) -> str:
    if "\x00" in valor:
        raise ValueError("O texto não pode conter o caractere NUL.")
    if _SURROGATE_ISOLADO.search(valor):
        raise ValueError("O texto não pode conter surrogates Unicode isolados.")
    return valor


TextoSeguro = Annotated[str, AfterValidator(_rejeitar_caracteres_invalidos)]
"""Texto aceito na borda HTTP: sem NUL e sem surrogates isolados (não codificáveis em UTF-8)."""
