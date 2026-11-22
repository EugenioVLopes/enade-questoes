"""Portas de repositórios de domínio (Protocol) na camada de aplicação."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from domain.avaliacao import ConjuntoOuro
from domain.classificacao import (
    Classificacao,
    DivergenciaReclassificacao,
    ExecucaoClassificacao,
    PerfilClassificacao,
)
from domain.enums import ResolucaoDivergencia, StatusClassificacao, StatusDivergencia
from domain.prova import AtivoVisual, Ingestao, Prova, Questao
from domain.taxonomia import Disciplina, Taxonomia


@runtime_checkable
class RepositorioProvas(Protocol):
    def salvar(self, prova: Prova) -> Prova: ...

    def buscar_por_id(self, prova_id: UUID) -> Prova | None: ...

    def buscar_por_chave_natural(self, exame: str, curso: str, ano: int) -> Prova | None: ...

    def listar(self) -> list[Prova]: ...


@runtime_checkable
class RepositorioIngestoes(Protocol):
    def salvar(self, ingestao: Ingestao) -> Ingestao: ...

    def buscar_por_id(self, ingestao_id: UUID) -> Ingestao | None: ...

    def buscar_ultima_por_prova(self, prova_id: UUID) -> Ingestao | None: ...

    def listar_por_prova(self, prova_id: UUID) -> list[Ingestao]: ...

    def marcar_em_processamento_como_interrompidas(self, agora: datetime, motivo: str) -> int: ...


@runtime_checkable
class RepositorioQuestoes(Protocol):
    def salvar(self, questao: Questao) -> Questao: ...

    def salvar_lote(self, questoes: Sequence[Questao]) -> list[Questao]: ...

    def buscar_por_id(self, questao_id: UUID) -> Questao | None: ...

    def buscar_por_prova_e_numero(self, prova_id: UUID, numero: int) -> Questao | None: ...

    def listar_por_prova(self, prova_id: UUID) -> list[Questao]: ...

    def listar_todas(self) -> list[Questao]: ...

    def listar_pendentes_classificacao(self, taxonomia_id: UUID) -> list[Questao]: ...

    def listar_com_disciplina_arquivada(self, taxonomia_id: UUID) -> list[Questao]: ...

    def listar_por_ids(self, questao_ids: Sequence[UUID]) -> list[Questao]: ...


@runtime_checkable
class RepositorioAtivosVisuais(Protocol):
    def salvar(self, ativo: AtivoVisual) -> AtivoVisual: ...

    def buscar_por_id(self, ativo_id: UUID) -> AtivoVisual | None: ...

    def listar_por_questao(self, questao_id: UUID) -> list[AtivoVisual]: ...

    def remover(self, ativo_id: UUID) -> None: ...


@runtime_checkable
class RepositorioTaxonomias(Protocol):
    def salvar(self, taxonomia: Taxonomia) -> Taxonomia: ...

    def buscar_por_id(self, taxonomia_id: UUID) -> Taxonomia | None: ...

    def buscar_por_codigo(self, codigo: str) -> Taxonomia | None: ...

    def listar(self) -> list[Taxonomia]: ...

    def buscar_disciplina_por_id(self, disciplina_id: UUID) -> tuple[UUID, Disciplina] | None: ...

    def adicionar_disciplina(
        self,
        taxonomia_id: UUID,
        disciplina: Disciplina,
        *,
        ordem: int | None = None,
    ) -> Disciplina: ...

    def salvar_disciplina(
        self,
        taxonomia_id: UUID,
        disciplina: Disciplina,
        *,
        ordem: int | None = None,
    ) -> Disciplina: ...

    def contar_classificacoes_vigentes_por_disciplina(
        self,
        taxonomia_id: UUID,
        disciplina_codigo: str,
    ) -> int: ...

    def contar_classificacoes_vigentes_por_disciplinas(self, taxonomia_id: UUID) -> dict[str, int]: ...

    def contar_classificacoes_vigentes_por_taxonomias(
        self,
        taxonomia_ids: Sequence[UUID],
    ) -> dict[UUID, dict[str, int]]: ...


@runtime_checkable
class RepositorioPerfisClassificacao(Protocol):
    def salvar(self, perfil: PerfilClassificacao) -> PerfilClassificacao: ...

    def buscar_por_id(self, perfil_id: UUID) -> PerfilClassificacao | None: ...

    def buscar_por_codigo_e_versao(self, codigo: str, versao: str) -> PerfilClassificacao | None: ...

    def listar(self) -> list[PerfilClassificacao]: ...


@runtime_checkable
class RepositorioExecucoesClassificacao(Protocol):
    def salvar(self, execucao: ExecucaoClassificacao) -> ExecucaoClassificacao: ...

    def buscar_por_id(self, execucao_id: UUID) -> ExecucaoClassificacao | None: ...

    def listar(self, *, taxonomia_id: UUID | None = None) -> list[ExecucaoClassificacao]: ...

    def marcar_em_processamento_como_interrompidas(self, agora: datetime) -> int: ...


@runtime_checkable
class RepositorioClassificacoes(Protocol):
    def salvar(self, classificacao: Classificacao) -> Classificacao: ...

    def registrar_substituicao(
        self,
        anterior: Classificacao,
        nova: Classificacao,
    ) -> Classificacao: ...

    def buscar_por_id(self, classificacao_id: UUID) -> Classificacao | None: ...

    def buscar_vigente(self, questao_id: UUID, taxonomia_id: UUID) -> Classificacao | None: ...

    def listar_historico(self, questao_id: UUID, taxonomia_id: UUID) -> list[Classificacao]: ...

    def listar_vigentes_por_questao(self, questao_id: UUID) -> list[Classificacao]: ...

    def listar_fila_revisao(
        self,
        taxonomia_id: UUID,
        *,
        status: StatusClassificacao | None = None,
        apenas_revisao_prioritaria: bool = False,
    ) -> list[Classificacao]: ...


@runtime_checkable
class RepositorioDivergenciasReclassificacao(Protocol):
    def salvar(self, divergencia: DivergenciaReclassificacao) -> DivergenciaReclassificacao: ...

    def buscar_por_id(self, divergencia_id: UUID) -> DivergenciaReclassificacao | None: ...

    def listar(
        self,
        *,
        taxonomia_id: UUID | None = None,
        status: StatusDivergencia | None = None,
    ) -> list[DivergenciaReclassificacao]: ...

    def resolver_atomicamente(
        self,
        divergencia_id: UUID,
        resolucao: ResolucaoDivergencia,
        agora: datetime,
        nova_classificacao: Classificacao | None = None,
    ) -> DivergenciaReclassificacao:
        """Resolve a divergência e atualiza a classificação vigente na mesma transação.

        Contratos por tipo de resolução:
        - ``EDITAR_MANUALMENTE``: ``nova_classificacao`` é obrigatória e deve representar
          a nova classificação humana aprovada e vigente que substitui a anterior.
        - ``MANTER_HUMANA``: ``nova_classificacao`` deve ser ``None``.
        - ``ACEITAR_CANDIDATA``: ``nova_classificacao`` é opcional (``None`` quando o
          repositório cria a substituição a partir dos dados candidatos da divergência).
        """
        ...


@runtime_checkable
class RepositorioConjuntoOuro(Protocol):
    def exportar_elegiveis(self, taxonomia_codigo: str, agora: datetime) -> ConjuntoOuro: ...

    def salvar_snapshot(self, conjunto: ConjuntoOuro, destino: str) -> str: ...

    def carregar_snapshot(self, origem: str) -> ConjuntoOuro: ...
