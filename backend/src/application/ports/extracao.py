"""Portas e DTOs de extração de Prova, Gabarito e renderização de páginas PDF."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from domain.enums import LetraAlternativa, OrigemAtivoVisual, TipoQuestao
from domain.prova import BoundingBox, FaixaQuestoes, Gabarito, MetadadosIngestao


@dataclass(frozen=True, slots=True)
class AlternativaExtraida:
    """Alternativa bruta extraída do caderno de prova."""

    letra: LetraAlternativa
    texto: str


@dataclass(frozen=True, slots=True)
class AtivoVisualExtraido:
    """Ativo visual bruto recortado ou extraído durante a ingestão do PDF."""

    origem: OrigemAtivoVisual
    conteudo_png: bytes
    ordem: int
    pagina: int
    bbox: BoundingBox | None = None
    alternativa_letra: LetraAlternativa | None = None


@dataclass(frozen=True, slots=True)
class QuestaoExtraida:
    """Questão estruturada retornada pelo adaptador de extração de PDF."""

    numero: int
    enunciado: str
    paginas: tuple[int, ...]
    alternativas: tuple[AlternativaExtraida, ...]
    ativos_visuais: tuple[AtivoVisualExtraido, ...]


@dataclass(frozen=True, slots=True)
class ResultadoExtracaoProva:
    """Resultado completo da extração de uma Prova."""

    questoes: tuple[QuestaoExtraida, ...]
    extracao_bruta_json: str
    metadados: MetadadosIngestao


@dataclass(frozen=True, slots=True)
class ItemGabaritoExtraido:
    """Entrada individual parseada de um PDF oficial de Gabarito."""

    numero: int
    tipo: TipoQuestao
    gabarito: Gabarito
    rotulo: str = ""


@dataclass(frozen=True, slots=True)
class ResultadoExtracaoGabarito:
    """Resultado completo da extração de um PDF de Gabarito."""

    itens: tuple[ItemGabaritoExtraido, ...]

    def mapa_objetivas(self) -> dict[int, Gabarito]:
        return {item.numero: item.gabarito for item in self.itens if item.tipo == TipoQuestao.OBJETIVA}


@runtime_checkable
class ExtratorProva(Protocol):
    """Porta de extração estruturada de questões e ativos visuais a partir de PDF."""

    def extrair(self, caminho_pdf: Path, faixa_ce: FaixaQuestoes) -> ResultadoExtracaoProva: ...


@runtime_checkable
class ExtratorGabarito(Protocol):
    """Porta de extração oficial de gabaritos separando objetivas e discursivas."""

    def extrair(self, caminho_pdf: Path) -> ResultadoExtracaoGabarito: ...


@runtime_checkable
class RenderizadorPaginaPdf(Protocol):
    """Porta de renderização sob demanda de páginas do PDF original para PNG."""

    def contar_paginas(self, caminho_pdf: Path) -> int: ...

    def renderizar_pagina(self, caminho_pdf: Path, pagina: int, dpi: int = 150) -> bytes: ...
