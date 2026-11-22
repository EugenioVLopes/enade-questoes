"""Casos de uso, serviço de lote no worker e encadeamento de Execuções de Classificação."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from application.classificacao import ClassificarQuestaoService
from application.exceptions import RecursoNaoEncontradoError
from application.ports.repositorios import (
    RepositorioClassificacoes,
    RepositorioDivergenciasReclassificacao,
    RepositorioExecucoesClassificacao,
    RepositorioPerfisClassificacao,
    RepositorioProvas,
    RepositorioQuestoes,
    RepositorioTaxonomias,
)
from application.seed import CODIGO_PERFIL_PADRAO, VERSAO_PERFIL_PADRAO
from application.worker import WorkerLocal
from domain.classificacao import DivergenciaReclassificacao, ExecucaoClassificacao
from domain.enums import (
    EscopoExecucao,
    StatusClassificacao,
    StatusDivergencia,
    StatusExecucaoClassificacao,
)
from domain.exceptions import ErroValidacaoDominio
from domain.prova import Prova
from domain.travas_classificacao import detectar_divergencia


def _agora_utc() -> datetime:
    return datetime.now(UTC)


def _normalizar_questao_ids_entrada(questao_ids: Sequence[UUID]) -> list[UUID]:
    if isinstance(questao_ids, str | bytes | bytearray | memoryview | Mapping) or not isinstance(questao_ids, Iterable):
        raise ErroValidacaoDominio("'questao_ids' deve ser uma coleção de UUIDs.")
    return list(dict.fromkeys(questao_ids))


class CriarExecucaoClassificacaoUseCase:
    def __init__(
        self,
        repo_taxonomias: RepositorioTaxonomias,
        repo_perfis: RepositorioPerfisClassificacao,
        repo_provas: RepositorioProvas,
        repo_questoes: RepositorioQuestoes,
        repo_execucoes: RepositorioExecucoesClassificacao,
        worker: WorkerLocal,
    ) -> None:
        self._repo_taxonomias = repo_taxonomias
        self._repo_perfis = repo_perfis
        self._repo_provas = repo_provas
        self._repo_questoes = repo_questoes
        self._repo_execucoes = repo_execucoes
        self._worker = worker

    def execute(
        self,
        *,
        taxonomia_id: UUID,
        perfil_id: UUID,
        escopo: EscopoExecucao,
        incluir_revisadas: bool = False,
        prova_id: UUID | None = None,
        questao_ids: Sequence[UUID] = (),
    ) -> ExecucaoClassificacao:
        try:
            escopo_norm = EscopoExecucao(escopo)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Escopo de execução inválido: {escopo!r}.") from err

        if not isinstance(incluir_revisadas, bool):
            raise ErroValidacaoDominio("'incluir_revisadas' deve ser booleano.")

        ids_unicos = _normalizar_questao_ids_entrada(questao_ids)

        if escopo_norm == EscopoExecucao.PROVA_ID:
            if prova_id is None:
                raise ErroValidacaoDominio("Escopo 'prova_id' exige o parâmetro 'prova_id'.")
            if ids_unicos:
                raise ErroValidacaoDominio("Escopo 'prova_id' não aceita 'questao_ids'.")
        elif escopo_norm == EscopoExecucao.QUESTAO_IDS:
            if not ids_unicos:
                raise ErroValidacaoDominio("Escopo 'questao_ids' exige ao menos um ID em 'questao_ids'.")
            if prova_id is not None:
                raise ErroValidacaoDominio("Escopo 'questao_ids' não aceita 'prova_id'.")
        else:
            if prova_id is not None or ids_unicos:
                raise ErroValidacaoDominio(f"Escopo '{escopo_norm.value}' não aceita 'prova_id' nem 'questao_ids'.")

        taxonomia = self._repo_taxonomias.buscar_por_id(taxonomia_id)
        if taxonomia is None:
            raise RecursoNaoEncontradoError(f"Taxonomia '{taxonomia_id}' não encontrada.")
        if not taxonomia.ativas():
            raise ErroValidacaoDominio(
                f"Taxonomia '{taxonomia.codigo}' não possui disciplinas ativas para classificação."
            )

        perfil = self._repo_perfis.buscar_por_id(perfil_id)
        if perfil is None:
            raise RecursoNaoEncontradoError(f"Perfil de classificação '{perfil_id}' não encontrado.")

        if escopo_norm == EscopoExecucao.PROVA_ID:
            assert prova_id is not None  # noqa: S101
            prova = self._repo_provas.buscar_por_id(prova_id)
            if prova is None:
                raise RecursoNaoEncontradoError(f"Prova '{prova_id}' não encontrada.")
            questoes = self._repo_questoes.listar_por_prova(prova.id)
            alvo_label = f"{prova.exame} {prova.ano}"
        elif escopo_norm == EscopoExecucao.QUESTAO_IDS:
            questoes = self._repo_questoes.listar_por_ids(ids_unicos)
            encontrados = {q.id for q in questoes}
            faltantes = [str(qid) for qid in ids_unicos if qid not in encontrados]
            if faltantes:
                raise RecursoNaoEncontradoError(f"Questão(ões) não encontrada(s): {', '.join(faltantes)}.")
            alvo_label = f"{taxonomia.codigo} ({len(ids_unicos)} questões)"
        elif escopo_norm == EscopoExecucao.TODAS:
            questoes = self._repo_questoes.listar_todas()
            alvo_label = taxonomia.nome
        elif escopo_norm == EscopoExecucao.PENDENTES:
            questoes = self._repo_questoes.listar_pendentes_classificacao(taxonomia.id)
            alvo_label = f"{taxonomia.nome} (pendentes)"
        else:
            questoes = self._repo_questoes.listar_com_disciplina_arquivada(taxonomia.id)
            alvo_label = f"{taxonomia.nome} (disciplina arquivada)"

        alvo_ids = tuple(q.id for q in questoes)
        execucao = ExecucaoClassificacao(
            taxonomia_id=taxonomia.id,
            perfil_id=perfil.id,
            snapshot_taxonomia=taxonomia.snapshot_dict(),
            snapshot_perfil=perfil.snapshot_dict(),
            escopo=escopo_norm,
            incluir_revisadas=incluir_revisadas,
            status=StatusExecucaoClassificacao.PENDENTE,
            total_itens=len(alvo_ids),
            escopo_prova_id=prova_id,
            escopo_questao_ids=tuple(ids_unicos),
            questao_ids_alvo=alvo_ids,
        )
        salva = self._repo_execucoes.salvar(execucao)
        self._worker.enfileirar_classificacao(salva.id, alvo=alvo_label, total=salva.total_itens)
        return salva


class ListarExecucoesClassificacaoUseCase:
    def __init__(self, repo_execucoes: RepositorioExecucoesClassificacao) -> None:
        self._repo_execucoes = repo_execucoes

    def execute(self, *, taxonomia_id: UUID | None = None) -> list[ExecucaoClassificacao]:
        return self._repo_execucoes.listar(taxonomia_id=taxonomia_id)


class DetalharExecucaoClassificacaoUseCase:
    def __init__(self, repo_execucoes: RepositorioExecucoesClassificacao) -> None:
        self._repo_execucoes = repo_execucoes

    def execute(self, execucao_id: UUID) -> ExecucaoClassificacao:
        execucao = self._repo_execucoes.buscar_por_id(execucao_id)
        if execucao is None:
            raise RecursoNaoEncontradoError(f"Execução de classificação '{execucao_id}' não encontrada.")
        return execucao


class RetomarExecucaoClassificacaoUseCase:
    def __init__(
        self,
        repo_execucoes: RepositorioExecucoesClassificacao,
        repo_provas: RepositorioProvas,
        worker: WorkerLocal,
    ) -> None:
        self._repo_execucoes = repo_execucoes
        self._repo_provas = repo_provas
        self._worker = worker

    def execute(self, execucao_id: UUID) -> ExecucaoClassificacao:
        execucao = self._repo_execucoes.buscar_por_id(execucao_id)
        if execucao is None:
            raise RecursoNaoEncontradoError(f"Execução de classificação '{execucao_id}' não encontrada.")

        execucao.preparar_retomada()
        salva = self._repo_execucoes.salvar(execucao)

        alvo_label = str(salva.snapshot_taxonomia.get("nome", "Classificação"))
        if salva.escopo == EscopoExecucao.PROVA_ID and salva.escopo_prova_id is not None:
            prova = self._repo_provas.buscar_por_id(salva.escopo_prova_id)
            if prova is not None:
                alvo_label = f"{prova.exame} {prova.ano}"

        self._worker.enfileirar_classificacao(salva.id, alvo=alvo_label, total=salva.total_itens)
        return salva


class ExecutarLoteClassificacaoService:
    """Executor sequencial de lote de classificação sobre snapshots congelados."""

    def __init__(
        self,
        *,
        repo_execucoes: RepositorioExecucoesClassificacao,
        repo_questoes: RepositorioQuestoes,
        repo_provas: RepositorioProvas,
        repo_classificacoes: RepositorioClassificacoes,
        repo_divergencias: RepositorioDivergenciasReclassificacao,
        classificar_questao: ClassificarQuestaoService,
    ) -> None:
        self._repo_execucoes = repo_execucoes
        self._repo_questoes = repo_questoes
        self._repo_provas = repo_provas
        self._repo_classificacoes = repo_classificacoes
        self._repo_divergencias = repo_divergencias
        self._classificar_questao = classificar_questao

    def __call__(
        self,
        execucao_id: UUID,
        atualizar_progresso: Callable[[int, int], None] | None = None,
    ) -> None:
        execucao = self._repo_execucoes.buscar_por_id(execucao_id)
        if execucao is None or execucao.status not in {
            StatusExecucaoClassificacao.PENDENTE,
            StatusExecucaoClassificacao.INTERROMPIDA,
        }:
            return

        execucao.iniciar(_agora_utc())
        execucao = self._repo_execucoes.salvar(execucao)
        if atualizar_progresso is not None:
            atualizar_progresso(execucao.processadas, execucao.total_itens)

        try:
            taxonomia = execucao.reconstruir_taxonomia_snapshot()
            perfil = execucao.reconstruir_perfil_snapshot()
            if not taxonomia.ativas():
                raise ErroValidacaoDominio(f"Snapshot da taxonomia '{taxonomia.codigo}' não possui disciplinas ativas.")

            pendentes_ids = execucao.questao_ids_pendentes()
            provas_por_id: dict[UUID, Prova | None] = {}

            for questao_id in pendentes_ids:
                questao = self._repo_questoes.buscar_por_id(questao_id)
                if questao is None:
                    execucao.registrar_erro_item(questao_id, f"Questão '{questao_id}' não encontrada.")
                    execucao = self._repo_execucoes.salvar(execucao)
                    if atualizar_progresso is not None:
                        atualizar_progresso(execucao.processadas, execucao.total_itens)
                    continue

                if questao.prova_id not in provas_por_id:
                    provas_por_id[questao.prova_id] = self._repo_provas.buscar_por_id(questao.prova_id)
                prova = provas_por_id[questao.prova_id]

                vigente = self._repo_classificacoes.buscar_vigente(questao.id, execucao.taxonomia_id)
                if (
                    vigente is not None
                    and vigente.status == StatusClassificacao.APROVADA
                    and not execucao.incluir_revisadas
                ):
                    execucao.registrar_pulo_item(questao.id)
                    execucao = self._repo_execucoes.salvar(execucao)
                    if atualizar_progresso is not None:
                        atualizar_progresso(execucao.processadas, execucao.total_itens)
                    continue

                try:
                    resultado = self._classificar_questao.classificar(
                        questao=questao,
                        taxonomia=taxonomia,
                        perfil=perfil,
                        prova=prova,
                        execucao_id=execucao.id,
                    )
                except Exception as err:
                    mensagem = str(err).strip() or type(err).__name__
                    execucao.registrar_erro_item(questao.id, mensagem)
                    execucao = self._repo_execucoes.salvar(execucao)
                    if atualizar_progresso is not None:
                        atualizar_progresso(execucao.processadas, execucao.total_itens)
                    continue

                if not resultado.sucesso or resultado.classificacao is None:
                    mensagem = (
                        resultado.erro.mensagem
                        if resultado.erro is not None
                        else "Classificação rejeitada pelas travas determinísticas."
                    )
                    execucao.registrar_erro_item(
                        questao.id,
                        mensagem,
                        cache_hit=resultado.metricas.cache_hit,
                        prompt_tokens=resultado.metricas.prompt_tokens,
                        completion_tokens=resultado.metricas.completion_tokens,
                    )
                    execucao = self._repo_execucoes.salvar(execucao)
                    if atualizar_progresso is not None:
                        atualizar_progresso(execucao.processadas, execucao.total_itens)
                    continue

                nova = resultado.classificacao
                abriu_divergencia = False
                try:
                    if vigente is None:
                        self._repo_classificacoes.salvar(nova)
                    elif vigente.status == StatusClassificacao.PENDENTE_REVISAO:
                        nova.substitui_classificacao_id = vigente.id
                        self._repo_classificacoes.registrar_substituicao(vigente, nova)
                    else:
                        candidata = replace(
                            nova,
                            vigente=False,
                            substitui_classificacao_id=vigente.id,
                        )
                        candidata_salva = self._repo_classificacoes.salvar(candidata)
                        if detectar_divergencia(vigente, candidata_salva):
                            divergencia = DivergenciaReclassificacao(
                                questao_id=questao.id,
                                taxonomia_id=execucao.taxonomia_id,
                                execucao_id=execucao.id,
                                classificacao_vigente_id=vigente.id,
                                disciplina_principal_candidata=candidata_salva.disciplina_principal,
                                disciplinas_secundarias_candidatas=candidata_salva.disciplinas_secundarias,
                                topicos_candidatos=candidata_salva.topicos,
                                justificativa_candidata=candidata_salva.justificativa,
                                confianca_candidata=candidata_salva.confianca,
                                classificacao_candidata_id=candidata_salva.id,
                                status=StatusDivergencia.ABERTA,
                            )
                            self._repo_divergencias.salvar(divergencia)
                            abriu_divergencia = True
                except Exception as err:
                    mensagem = str(err).strip() or type(err).__name__
                    execucao.registrar_erro_item(
                        questao.id,
                        mensagem,
                        cache_hit=resultado.metricas.cache_hit,
                        prompt_tokens=resultado.metricas.prompt_tokens,
                        completion_tokens=resultado.metricas.completion_tokens,
                    )
                    execucao = self._repo_execucoes.salvar(execucao)
                    if atualizar_progresso is not None:
                        atualizar_progresso(execucao.processadas, execucao.total_itens)
                    continue

                execucao.registrar_sucesso_item(
                    questao.id,
                    cache_hit=resultado.metricas.cache_hit,
                    prompt_tokens=resultado.metricas.prompt_tokens,
                    completion_tokens=resultado.metricas.completion_tokens,
                    abriu_divergencia=abriu_divergencia,
                )
                execucao = self._repo_execucoes.salvar(execucao)
                if atualizar_progresso is not None:
                    atualizar_progresso(execucao.processadas, execucao.total_itens)

            execucao.concluir(_agora_utc())
            self._repo_execucoes.salvar(execucao)
        except Exception:
            if execucao.status == StatusExecucaoClassificacao.PROCESSANDO:
                execucao.falhar(_agora_utc())
                self._repo_execucoes.salvar(execucao)
            raise


class HookClassificacaoEncadeada:
    """Agenda classificação encadeada (escopo PROVA_ID) após conclusão de uma Ingestão."""

    def __init__(
        self,
        *,
        repo_perfis: RepositorioPerfisClassificacao,
        criar_execucao: CriarExecucaoClassificacaoUseCase,
    ) -> None:
        self._repo_perfis = repo_perfis
        self._criar_execucao = criar_execucao

    def __call__(
        self,
        *,
        prova_id: UUID,
        taxonomia_id: UUID,
        perfil_id: UUID | None,
    ) -> UUID:
        if perfil_id is not None:
            perfil_id_efetivo = perfil_id
        else:
            perfil = self._repo_perfis.buscar_por_codigo_e_versao(CODIGO_PERFIL_PADRAO, VERSAO_PERFIL_PADRAO)
            if perfil is None:
                perfis = self._repo_perfis.listar()
                padroes = [p for p in perfis if p.codigo == CODIGO_PERFIL_PADRAO]
                if padroes:
                    perfil = padroes[-1]
                elif perfis:
                    perfil = perfis[-1]
                else:
                    raise RecursoNaoEncontradoError(
                        "Nenhum PerfilClassificacao disponível para classificação encadeada."
                    )
            perfil_id_efetivo = perfil.id

        execucao = self._criar_execucao.execute(
            taxonomia_id=taxonomia_id,
            perfil_id=perfil_id_efetivo,
            escopo=EscopoExecucao.PROVA_ID,
            incluir_revisadas=False,
            prova_id=prova_id,
        )
        return execucao.id
