"""Validadores de inteiros compartilhados pelas entidades de prova."""

from __future__ import annotations

from domain.exceptions import ErroValidacaoDominio


def _validar_inteiro_positivo(valor: int, campo: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
        raise ErroValidacaoDominio(f"'{campo}' deve ser inteiro >= 1; recebido: {valor!r}.")
    return valor


def _validar_inteiro_nao_negativo(valor: int, campo: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise ErroValidacaoDominio(f"'{campo}' deve ser inteiro >= 0; recebido: {valor!r}.")
    return valor
