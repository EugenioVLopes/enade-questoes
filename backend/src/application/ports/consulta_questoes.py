"""Porta de leitura (read model) da consulta de Questões, fila de Revisão e contadores de abas."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable
from uuid import UUID

from domain.classificacao import Classificacao, DivergenciaReclassificacao
from domain.enums import SituacaoGabarito
from domain.prova import Questao


class StatusRevisao(StrEnum):
    """Situação de revisão de uma Questão sob uma Taxonomia."""

    SEM_CLASSIFICACAO = "sem_classificacao"
    PENDENTE_REVISAO = "pendente_revisao"
    APROVADA = "aprovada"
    PENDENTE = "pendente"
    """Filtro composto da aba `Pendentes`: sem classificação vigente ou vigente em `pendente_revisao`."""


class OrdenacaoConsulta(StrEnum):
    CONSULTA = "consulta"
    FILA_REVISAO = "fila_revisao"


@dataclass(frozen=True, slots=True)
class FiltroConsultaQuestoes:
    termo: str | None = None
    prova_id: UUID | None = None
    ano: int | None = None
    taxonomia_id: UUID | None = None
    disciplina_codigo: str | None = None
    incluir_secundarias: bool = True
    topico: str | None = None
    status_revisao: StatusRevisao | None = None
    revisao_prioritaria: bool | None = None
    com_divergencia: bool | None = None
    usa_disciplina_arquivada: bool | None = None
    situacao_gabarito: SituacaoGabarito | None = None
    com_alerta_extracao: bool | None = None
    ordenacao: OrdenacaoConsulta = OrdenacaoConsulta.CONSULTA
    limite: int = 50
    deslocamento: int = 0


@dataclass(frozen=True, slots=True)
class ItemConsultaQuestao:
    questao: Questao
    prova_exame: str
    prova_curso: str
    prova_ano: int
    classificacao: Classificacao | None
    revisao_prioritaria: bool
    tem_divergencia_aberta: bool
    usa_disciplina_arquivada: bool


@dataclass(frozen=True, slots=True)
class PaginaConsultaQuestoes:
    itens: tuple[ItemConsultaQuestao, ...]
    total: int


@dataclass(frozen=True, slots=True)
class ContadoresRevisao:
    pendentes: int
    divergencias: int
    disciplina_arquivada: int


@runtime_checkable
class ConsultaQuestoes(Protocol):
    def consultar(self, filtro: FiltroConsultaQuestoes) -> PaginaConsultaQuestoes: ...

    def contar_abas_revisao(self, taxonomia_id: UUID) -> ContadoresRevisao: ...

    def listar_divergencias_abertas_da_questao(self, questao_id: UUID) -> list[DivergenciaReclassificacao]: ...
