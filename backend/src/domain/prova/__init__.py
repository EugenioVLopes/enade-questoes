"""Entidades e objetos de valor de Conteúdo de Prova (desacoplados de classificação)."""

from __future__ import annotations

from domain.prova.alerta_extracao import (
    ALERTAS_ESTRUTURAIS,
    ALERTAS_INSPECAO,
    SEVERIDADE_POR_CODIGO,
    AlertaExtracao,
)
from domain.prova.ingestao import Ingestao, MetadadosIngestao
from domain.prova.prova import FaixaQuestoes, Prova
from domain.prova.questao import Alternativa, AtivoVisual, BoundingBox, Gabarito, Questao

__all__ = [
    "ALERTAS_ESTRUTURAIS",
    "ALERTAS_INSPECAO",
    "SEVERIDADE_POR_CODIGO",
    "AlertaExtracao",
    "Alternativa",
    "AtivoVisual",
    "BoundingBox",
    "FaixaQuestoes",
    "Gabarito",
    "Ingestao",
    "MetadadosIngestao",
    "Prova",
    "Questao",
]
