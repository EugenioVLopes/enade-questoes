"""Portas somente-leitura de Avaliação Offline e histórico IA × Humano."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from domain.avaliacao import ChaveQuestaoOuro
from domain.classificacao import PerfilClassificacao
from domain.prova import Prova, Questao
from domain.taxonomia import Taxonomia


@dataclass(frozen=True, slots=True)
class RegistroHistoricoClassificacao:
    """Par IA × veredito vigente aprovado para cálculo de concordância histórica."""

    taxonomia_codigo: str
    perfil_codigo: str
    perfil_versao: str
    modelo: str
    ia_disciplina_principal: str
    ia_disciplinas_secundarias: tuple[str, ...]
    final_disciplina_principal: str
    final_disciplinas_secundarias: tuple[str, ...]


@runtime_checkable
class ConsultaAvaliacao(Protocol):
    """Consultas somente-leitura necessárias para preflight, avaliação offline e histórico."""

    def buscar_taxonomia_por_codigo(self, codigo: str) -> Taxonomia | None: ...

    def buscar_perfil_por_codigo_versao(self, codigo: str, versao: str) -> PerfilClassificacao | None: ...

    def carregar_questoes_por_chaves(
        self,
        chaves: Sequence[ChaveQuestaoOuro],
    ) -> dict[ChaveQuestaoOuro, tuple[Prova, Questao]]: ...

    def listar_registros_historico(
        self,
        taxonomia_codigo: str | None = None,
    ) -> Sequence[RegistroHistoricoClassificacao]: ...
