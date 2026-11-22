"""Casos de uso da revisão humana: aprovar, corrigir e resolver divergências de reclassificação."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from application.busca import buscar_taxonomia_ou_404
from application.exceptions import RecursoNaoEncontradoError
from application.ports.consulta_questoes import ConsultaQuestoes
from application.ports.repositorios import (
    RepositorioClassificacoes,
    RepositorioDivergenciasReclassificacao,
    RepositorioQuestoes,
    RepositorioTaxonomias,
)
from domain.classificacao import Classificacao, DivergenciaReclassificacao, criar_classificacao_humana
from domain.enums import ResolucaoDivergencia, StatusClassificacao, StatusDivergencia
from domain.exceptions import ErroInvarianteDominio, ErroValidacaoDominio
from domain.taxonomia import Taxonomia


def _agora_utc() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class CorrecaoClassificacao:
    """Payload de curadoria humana: 1 principal + 0..2 secundárias + 0..N Tópicos."""

    disciplina_principal: str
    disciplinas_secundarias: tuple[str, ...] = ()
    topicos: tuple[str, ...] = ()
    justificativa: str = ""


@dataclass(frozen=True, slots=True)
class ResultadoResolucaoDivergencia:
    divergencia: DivergenciaReclassificacao
    classificacao_vigente: Classificacao | None


def _validar_codigos_ativos(taxonomia: Taxonomia, codigos: Iterable[str]) -> None:
    ativas = taxonomia.mapa_ativas()
    for codigo in codigos:
        if codigo.strip() not in ativas:
            raise ErroValidacaoDominio(
                f"Disciplina {codigo!r} não existe ou está arquivada na Taxonomia '{taxonomia.codigo}'."
            )


def _montar_classificacao_humana(
    *,
    taxonomia: Taxonomia,
    questao_id: UUID,
    correcao: CorrecaoClassificacao,
    substitui_classificacao_id: UUID,
    agora: datetime,
) -> Classificacao:
    _validar_codigos_ativos(taxonomia, (correcao.disciplina_principal, *correcao.disciplinas_secundarias))
    return criar_classificacao_humana(
        questao_id=questao_id,
        taxonomia_id=taxonomia.id,
        disciplina_principal=correcao.disciplina_principal,
        disciplinas_secundarias=correcao.disciplinas_secundarias,
        topicos=correcao.topicos,
        justificativa=correcao.justificativa,
        agora=agora,
        substitui_classificacao_id=substitui_classificacao_id,
    )


def _garantir_questao(repo_questoes: RepositorioQuestoes, questao_id: UUID) -> None:
    if repo_questoes.buscar_por_id(questao_id) is None:
        raise RecursoNaoEncontradoError(f"Questão '{questao_id}' não encontrada.")


def _vigente_ou_404(
    repo_classificacoes: RepositorioClassificacoes, questao_id: UUID, taxonomia_id: UUID
) -> Classificacao:
    vigente = repo_classificacoes.buscar_vigente(questao_id, taxonomia_id)
    if vigente is None:
        raise RecursoNaoEncontradoError(
            f"Questão '{questao_id}' não possui Classificação vigente na Taxonomia '{taxonomia_id}'."
        )
    return vigente


class AprovarClassificacaoUseCase:
    def __init__(
        self,
        *,
        repo_questoes: RepositorioQuestoes,
        repo_classificacoes: RepositorioClassificacoes,
    ) -> None:
        self._repo_questoes = repo_questoes
        self._repo_classificacoes = repo_classificacoes

    def execute(self, questao_id: UUID, taxonomia_id: UUID) -> Classificacao:
        _garantir_questao(self._repo_questoes, questao_id)
        vigente = _vigente_ou_404(self._repo_classificacoes, questao_id, taxonomia_id)
        if vigente.status != StatusClassificacao.PENDENTE_REVISAO:
            raise ErroInvarianteDominio(
                f"Classificação vigente já está '{vigente.status.value}'; apenas 'pendente_revisao' pode ser aprovada."
            )
        agora = _agora_utc()
        vigente.aprovar(agora)
        # UPDATE condicional (sem regravar a linha lida): se uma correção ou resolução trocou a vigente depois da
        # leitura, nada é atualizado e a aprovação conflita em vez de tentar reviver uma linha antiga.
        aprovada = self._repo_classificacoes.aprovar_se_pendente_vigente(vigente.id, agora)
        if aprovada is None:
            raise ErroInvarianteDominio(
                "A Classificação vigente mudou ou já foi aprovada durante a operação; recarregue e tente novamente."
            )
        return aprovada


class CorrigirClassificacaoUseCase:
    def __init__(
        self,
        *,
        repo_questoes: RepositorioQuestoes,
        repo_taxonomias: RepositorioTaxonomias,
        repo_classificacoes: RepositorioClassificacoes,
        consulta: ConsultaQuestoes,
    ) -> None:
        self._repo_questoes = repo_questoes
        self._repo_taxonomias = repo_taxonomias
        self._repo_classificacoes = repo_classificacoes
        self._consulta = consulta

    def execute(self, questao_id: UUID, taxonomia_id: UUID, correcao: CorrecaoClassificacao) -> Classificacao:
        _garantir_questao(self._repo_questoes, questao_id)
        taxonomia = buscar_taxonomia_ou_404(self._repo_taxonomias, taxonomia_id)
        vigente = _vigente_ou_404(self._repo_classificacoes, questao_id, taxonomia_id)
        if any(
            d.taxonomia_id == taxonomia_id for d in self._consulta.listar_divergencias_abertas_da_questao(questao_id)
        ):
            raise ErroInvarianteDominio(
                "A Questão possui Divergência de Reclassificação aberta nesta Taxonomia; use o endpoint 'resolver'."
            )

        agora = _agora_utc()
        nova = _montar_classificacao_humana(
            taxonomia=taxonomia,
            questao_id=questao_id,
            correcao=correcao,
            substitui_classificacao_id=vigente.id,
            agora=agora,
        )
        # Não persistir `vigente` antes: `registrar_substituicao` lê o estado vigente no banco.
        return self._repo_classificacoes.registrar_substituicao(vigente, nova)


class ResolverDivergenciaUseCase:
    def __init__(
        self,
        *,
        repo_questoes: RepositorioQuestoes,
        repo_taxonomias: RepositorioTaxonomias,
        repo_classificacoes: RepositorioClassificacoes,
        repo_divergencias: RepositorioDivergenciasReclassificacao,
    ) -> None:
        self._repo_questoes = repo_questoes
        self._repo_taxonomias = repo_taxonomias
        self._repo_classificacoes = repo_classificacoes
        self._repo_divergencias = repo_divergencias

    def execute(
        self,
        questao_id: UUID,
        divergencia_id: UUID,
        resolucao: ResolucaoDivergencia,
        correcao: CorrecaoClassificacao | None = None,
    ) -> ResultadoResolucaoDivergencia:
        _garantir_questao(self._repo_questoes, questao_id)
        divergencia = self._repo_divergencias.buscar_por_id(divergencia_id)
        if divergencia is None or divergencia.questao_id != questao_id:
            raise RecursoNaoEncontradoError(f"Divergência '{divergencia_id}' não encontrada na questão '{questao_id}'.")
        if divergencia.status != StatusDivergencia.ABERTA:
            raise ErroInvarianteDominio("Divergência já foi resolvida.")

        if resolucao == ResolucaoDivergencia.EDITAR_MANUALMENTE:
            if correcao is None:
                raise ErroValidacaoDominio("Resolução 'editar_manualmente' exige o campo 'classificacao'.")
            taxonomia = buscar_taxonomia_ou_404(self._repo_taxonomias, divergencia.taxonomia_id)
            nova: Classificacao | None = _montar_classificacao_humana(
                taxonomia=taxonomia,
                questao_id=questao_id,
                correcao=correcao,
                substitui_classificacao_id=divergencia.classificacao_vigente_id,
                agora=_agora_utc(),
            )
        else:
            if correcao is not None:
                raise ErroValidacaoDominio(f"Resolução '{resolucao.value}' não aceita o campo 'classificacao'.")
            nova = None

        resolvida = self._repo_divergencias.resolver_atomicamente(
            divergencia_id, resolucao, _agora_utc(), nova_classificacao=nova
        )
        vigente = self._repo_classificacoes.buscar_vigente(questao_id, divergencia.taxonomia_id)
        return ResultadoResolucaoDivergencia(divergencia=resolvida, classificacao_vigente=vigente)
