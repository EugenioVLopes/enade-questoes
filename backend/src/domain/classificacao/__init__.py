"""Entidades de Classificação, Perfis, Execuções e Divergências de Reclassificação."""

from __future__ import annotations

from domain.classificacao.classificacao import (
    Classificacao,
    DivergenciaReclassificacao,
    criar_classificacao_humana,
    normalizar_topicos_curadoria,
)
from domain.classificacao.execucao import ExecucaoClassificacao
from domain.classificacao.perfil import PerfilClassificacao

__all__ = [
    "Classificacao",
    "DivergenciaReclassificacao",
    "ExecucaoClassificacao",
    "PerfilClassificacao",
    "criar_classificacao_humana",
    "normalizar_topicos_curadoria",
]
