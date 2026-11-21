"""Exceções puras da camada de domínio do Enade Questões."""

from __future__ import annotations


class ErroDominio(Exception):
    """Exceção base para violações de regras e invariantes de domínio."""


class ErroValidacaoDominio(ErroDominio, ValueError):
    """Erro de validação de dados ou contratos de entrada no domínio."""


class ErroInvarianteDominio(ErroDominio):
    """Erro disparado quando uma invariante ou transição de estado é violada."""


class FaixaQuestoesIndisponivelError(ErroDominio):
    """Ano de prova sem faixa padrão conhecida e sem override explícito."""
