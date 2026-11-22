"""Worker local sequencial em thread dedicada para Ingestão e Classificação."""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4

from application.health import WorkerStatus
from application.ports.armazenamento import ArmazenamentoArquivos
from application.ports.extracao import ExtratorGabarito, ExtratorProva
from application.ports.repositorios import (
    RepositorioExecucoesClassificacao,
    RepositorioIngestoes,
    RepositorioProvas,
    RepositorioQuestoes,
)
from domain.alertas_extracao import avaliar_alertas_extracao
from domain.enums import ComponenteProva, SituacaoGabarito, StatusIngestao, TipoQuestao
from domain.prova import (
    Alternativa,
    AtivoVisual,
    Gabarito,
    Ingestao,
    MetadadosIngestao,
    Questao,
)
from domain.reprocessamento import reconciliar_reprocessamento_prova

logger = logging.getLogger(__name__)


def _agora_utc() -> datetime:
    return datetime.now(UTC)


@runtime_checkable
class ClassificacaoEncadeadaHook(Protocol):
    """Gancho acionado após conclusão bem-sucedida de uma Ingestão com taxonomia encadeada."""

    def __call__(
        self,
        *,
        prova_id: UUID,
        taxonomia_id: UUID,
        perfil_id: UUID | None,
    ) -> UUID | None: ...


@runtime_checkable
class ExecutorClassificacao(Protocol):
    """Contrato para execução de tarefas de classificação enfileiradas no WorkerLocal."""

    def __call__(
        self,
        execucao_id: UUID,
        atualizar_progresso: Callable[[int, int], None],
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class TarefaIngestao:
    """Tarefa sequencial de ingestão/reprocessamento de uma Prova."""

    prova_id: UUID
    ingestao_id: UUID
    sobrescrever_editadas: bool = False


@dataclass(frozen=True, slots=True)
class TarefaClassificacao:
    """Tarefa sequencial de execução de classificação em lote."""

    execucao_id: UUID
    alvo: str = "Classificação"
    total: int = 0
    executor: Callable[[Callable[[int, int], None]], None] | None = None


_SENTINELA_PARAR = object()
type _ItemFila = TarefaIngestao | TarefaClassificacao | object


class WorkerLocal:
    """Fila sequencial local que executa estritamente 1 tarefa pesada por vez."""

    def __init__(
        self,
        *,
        repo_provas: RepositorioProvas,
        repo_ingestoes: RepositorioIngestoes,
        repo_questoes: RepositorioQuestoes,
        repo_execucoes: RepositorioExecucoesClassificacao,
        armazenamento: ArmazenamentoArquivos,
        extrator_prova: ExtratorProva,
        extrator_gabarito: ExtratorGabarito,
        classificacao_hook: ClassificacaoEncadeadaHook | None = None,
        classificacao_executor: ExecutorClassificacao | None = None,
    ) -> None:
        self._repo_provas = repo_provas
        self._repo_ingestoes = repo_ingestoes
        self._repo_questoes = repo_questoes
        self._repo_execucoes = repo_execucoes
        self._armazenamento = armazenamento
        self._extrator_prova = extrator_prova
        self._extrator_gabarito = extrator_gabarito
        self._classificacao_hook = classificacao_hook
        self._classificacao_executor = classificacao_executor

        self._fila: queue.Queue[_ItemFila] = queue.Queue()
        self._lifecycle_lock = threading.Lock()
        self._status_lock = threading.Lock()
        self._cond = threading.Condition()
        self._pendentes_ou_ativos = 0
        self._parando = threading.Event()
        self._thread: threading.Thread | None = None
        self._status = WorkerStatus()

    def configurar_classificacao(
        self,
        *,
        hook: ClassificacaoEncadeadaHook | None = None,
        executor: ExecutorClassificacao | None = None,
    ) -> None:
        """Permite configurar hook pós-ingestão e executor de classificação após criação do worker."""
        if hook is not None:
            self._classificacao_hook = hook
        if executor is not None:
            self._classificacao_executor = executor

    def iniciar(self) -> None:
        """Executa recuperação de boot e inicia a thread consumidora única."""
        with self._lifecycle_lock:
            if self._thread is not None and self._thread.is_alive():
                return

            self._recuperar_tarefas_interrompidas()
            self._drenar_sentinelas_residuais()
            self._parando.clear()
            self._thread = threading.Thread(
                target=self._loop,
                name="worker-local-enade",
                daemon=True,
            )
            self._thread.start()

    def parar(self, timeout: float = 5.0) -> None:
        """Sinaliza parada limpa e aguarda encerramento da thread consumidora."""
        with self._lifecycle_lock:
            thread = self._thread
            if thread is None:
                return
            self._parando.set()
            self._fila.put(_SENTINELA_PARAR)

        thread.join(timeout=timeout)
        with self._lifecycle_lock:
            if not thread.is_alive():
                self._thread = None

    def enfileirar_ingestao(
        self,
        prova_id: UUID,
        ingestao_id: UUID,
        *,
        sobrescrever_editadas: bool = False,
    ) -> None:
        """Enfileira uma Ingestão para processamento sequencial."""
        tarefa = TarefaIngestao(
            prova_id=prova_id,
            ingestao_id=ingestao_id,
            sobrescrever_editadas=sobrescrever_editadas,
        )
        with self._cond:
            self._pendentes_ou_ativos += 1
            self._fila.put(tarefa)

    def enfileirar_classificacao(
        self,
        execucao_id: UUID,
        *,
        alvo: str = "Classificação",
        total: int = 0,
        executor: Callable[[Callable[[int, int], None]], None] | None = None,
    ) -> None:
        """Enfileira uma Execução de Classificação na mesma fila sequencial."""
        tarefa = TarefaClassificacao(
            execucao_id=execucao_id,
            alvo=alvo,
            total=total,
            executor=executor,
        )
        with self._cond:
            self._pendentes_ou_ativos += 1
            self._fila.put(tarefa)

    def aguardar_ocioso(self, timeout: float = 10.0) -> None:
        """Bloqueia até que todas as tarefas enfileiradas e ativas tenham terminado."""
        with self._cond:
            concluido = self._cond.wait_for(
                lambda: self._pendentes_ou_ativos == 0,
                timeout=timeout,
            )
        if not concluido:
            raise TimeoutError(f"WorkerLocal não ficou ocioso dentro de {timeout:.1f}s.")

    def status_atual(self) -> WorkerStatus:
        """Retorna snapshot thread-safe do estado atual do worker."""
        with self._status_lock:
            return self._status

    def _recuperar_tarefas_interrompidas(self) -> None:
        agora = _agora_utc()
        ingestoes_interrompidas = self._repo_ingestoes.marcar_em_processamento_como_interrompidas(
            agora,
            "Processo interrompido durante reinício do servidor.",
        )
        execucoes_interrompidas = self._repo_execucoes.marcar_em_processamento_como_interrompidas(agora)
        if ingestoes_interrompidas or execucoes_interrompidas:
            logger.warning(
                "Recuperação de boot do worker: %d ingestões e %d execuções marcadas como interrompidas.",
                ingestoes_interrompidas,
                execucoes_interrompidas,
            )

    def _definir_status_ocupado(
        self,
        *,
        tipo: str,
        alvo: str,
        processadas: int,
        total: int,
    ) -> None:
        verbo = "Ingerindo" if tipo == "ingestao" else "Classificando"
        resumo = f"{verbo} {alvo}: {processadas}/{total}" if total > 0 else f"{verbo} {alvo}"
        with self._status_lock:
            self._status = WorkerStatus(
                estado="ocupado",
                tarefa_ativa=resumo,
                tipo=tipo,
                alvo=alvo,
                processadas=processadas,
                total=total,
            )

    def _definir_status_ocioso(self) -> None:
        with self._status_lock:
            self._status = WorkerStatus()

    def _concluir_item_fila(self) -> None:
        with self._cond:
            if self._pendentes_ou_ativos > 0:
                self._pendentes_ou_ativos -= 1
            self._cond.notify_all()

    def _drenar_sentinelas_residuais(self) -> None:
        with self._cond:
            itens_validos: list[_ItemFila] = []
            while True:
                try:
                    item = self._fila.get_nowait()
                except queue.Empty:
                    break
                try:
                    if item is not _SENTINELA_PARAR:
                        itens_validos.append(item)
                finally:
                    self._fila.task_done()
            for item in itens_validos:
                self._fila.put(item)

    def _drenar_fila_ao_parar(self) -> None:
        while True:
            try:
                item = self._fila.get_nowait()
            except queue.Empty:
                break
            try:
                if item is not _SENTINELA_PARAR:
                    self._concluir_item_fila()
            finally:
                self._fila.task_done()

    def _loop(self) -> None:
        while True:
            item = self._fila.get()
            try:
                if item is _SENTINELA_PARAR:
                    self._drenar_fila_ao_parar()
                    return
                if self._parando.is_set():
                    self._concluir_item_fila()
                    self._drenar_fila_ao_parar()
                    return

                if isinstance(item, TarefaIngestao):
                    try:
                        self._executar_ingestao(item)
                    finally:
                        self._definir_status_ocioso()
                        self._concluir_item_fila()
                elif isinstance(item, TarefaClassificacao):
                    try:
                        self._executar_classificacao(item)
                    finally:
                        self._definir_status_ocioso()
                        self._concluir_item_fila()
            except Exception:  # pragma: no cover - proteção extrema do loop
                logger.exception("Erro inesperado no loop do WorkerLocal.")
            finally:
                self._fila.task_done()

            if self._parando.is_set():
                self._drenar_fila_ao_parar()
                return

    def _executar_ingestao(self, tarefa: TarefaIngestao) -> None:
        prova = self._repo_provas.buscar_por_id(tarefa.prova_id)
        ingestao = self._repo_ingestoes.buscar_por_id(tarefa.ingestao_id)
        if prova is None or ingestao is None:
            logger.warning(
                "Tarefa de ingestão ignorada por ausência de prova (%s) ou ingestão (%s).",
                tarefa.prova_id,
                tarefa.ingestao_id,
            )
            return

        taxonomia_id_encadeada = ingestao.metadados.taxonomia_id_encadeada
        perfil_id_encadeada = ingestao.metadados.perfil_id_encadeada
        alvo = f"{prova.exame} {prova.ano}"
        total_faixa = len(prova.faixa_ce) if prova.faixa_ce is not None else 0

        ingestao.iniciar(_agora_utc())
        ingestao = self._repo_ingestoes.salvar(ingestao)
        self._definir_status_ocupado(tipo="ingestao", alvo=alvo, processadas=0, total=total_faixa)

        novas_chaves_ativos: list[str] = []
        try:
            if not prova.caminho_pdf:
                raise ValueError(f"Prova '{prova.id}' não possui caminho_pdf cadastrado.")
            if prova.faixa_ce is None:
                raise ValueError(f"Prova '{prova.id}' não possui faixa_ce definida.")

            caminho_pdf = self._armazenamento.resolver_caminho(prova.caminho_pdf)
            resultado_prova = self._extrator_prova.extrair(caminho_pdf, prova.faixa_ce)

            chave_extracao_bruta = f"provas/{prova.id}/extracao_bruta.json"
            self._armazenamento.salvar(
                chave_extracao_bruta,
                resultado_prova.extracao_bruta_json.encode("utf-8"),
            )
            prova.caminho_extracao_bruta = chave_extracao_bruta

            gabaritos_por_numero: dict[int, Gabarito] = {}
            gabarito_enviado = False
            if prova.caminho_gabarito:
                caminho_gabarito = self._armazenamento.resolver_caminho(prova.caminho_gabarito)
                resultado_gab = self._extrator_gabarito.extrair(caminho_gabarito)
                gabaritos_por_numero = resultado_gab.mapa_objetivas()
                gabarito_enviado = True

            questoes_atuais = self._repo_questoes.listar_por_prova(prova.id)
            atuais_por_numero = {q.numero: q for q in questoes_atuais}
            chaves_antes = {
                ativo.chave_arquivo for q in questoes_atuais for ativo in q.ativos_visuais if ativo.chave_arquivo
            }

            total_itens = len(resultado_prova.questoes) if resultado_prova.questoes else total_faixa
            self._definir_status_ocupado(tipo="ingestao", alvo=alvo, processadas=0, total=total_itens)

            questoes_extraidas: list[Questao] = []
            for idx, q_ext in enumerate(resultado_prova.questoes, start=1):
                q_atual = atuais_por_numero.get(q_ext.numero)
                preservar_edicao = bool(
                    q_atual is not None and q_atual.editada_manualmente and not tarefa.sobrescrever_editadas
                )

                ativos: list[AtivoVisual] = []
                if not preservar_edicao:
                    for ativo_ext in q_ext.ativos_visuais:
                        ativo_id = uuid4()
                        chave_ativo = f"provas/{prova.id}/ativos/{ativo_id}.png"
                        self._armazenamento.salvar(chave_ativo, ativo_ext.conteudo_png)
                        novas_chaves_ativos.append(chave_ativo)
                        ativos.append(
                            AtivoVisual(
                                id=ativo_id,
                                origem=ativo_ext.origem,
                                ordem=ativo_ext.ordem,
                                alternativa_letra=ativo_ext.alternativa_letra,
                                pagina=ativo_ext.pagina,
                                bbox=ativo_ext.bbox,
                                chave_arquivo=chave_ativo,
                            )
                        )

                alternativas = [Alternativa(letra=alt_ext.letra, texto=alt_ext.texto) for alt_ext in q_ext.alternativas]
                gabarito = gabaritos_por_numero.get(q_ext.numero, Gabarito(SituacaoGabarito.PENDENTE))
                questao = Questao(
                    prova_id=prova.id,
                    numero=q_ext.numero,
                    enunciado=q_ext.enunciado,
                    componente=ComponenteProva.COMPONENTE_ESPECIFICO,
                    tipo=TipoQuestao.OBJETIVA,
                    paginas=q_ext.paginas,
                    alternativas=alternativas,
                    ativos_visuais=ativos,
                    gabarito=gabarito,
                )
                avaliar_alertas_extracao(
                    questao,
                    usou_ocr=resultado_prova.metadados.usou_ocr,
                    paginas_com_fonte_symbol=resultado_prova.metadados.paginas_fonte_symbol,
                    gabarito_enviado_na_prova=gabarito_enviado,
                )
                questoes_extraidas.append(questao)
                self._definir_status_ocupado(tipo="ingestao", alvo=alvo, processadas=idx, total=total_itens)

            if questoes_atuais:
                reconciliacao = reconciliar_reprocessamento_prova(
                    questoes_atuais,
                    questoes_extraidas,
                    sobrescrever_editadas=tarefa.sobrescrever_editadas,
                    agora=_agora_utc(),
                )
                questoes_finais = list(reconciliacao.questoes_finais)
            else:
                questoes_finais = questoes_extraidas

            # Questões que o reprocessamento manteve intactas (mesmo objeto lido) não são regravadas: assim uma edição
            # do revisor durante a extração nunca é revertida nem gera conflito de versão.
            lidas_por_id = {q.id: q for q in questoes_atuais}
            a_gravar = [q for q in questoes_finais if lidas_por_id.get(q.id) is not q]
            questoes_persistidas = [q for q in questoes_finais if lidas_por_id.get(q.id) is q]
            questoes_persistidas += self._repo_questoes.salvar_lote_do_sistema(
                a_gravar, sobrescrever_alteradas=tarefa.sobrescrever_editadas
            )
            prova.atualizada_em = _agora_utc()
            self._repo_provas.salvar(prova)

            chaves_depois = {
                ativo.chave_arquivo for q in questoes_persistidas for ativo in q.ativos_visuais if ativo.chave_arquivo
            }
            for chave_orfa in (chaves_antes | set(novas_chaves_ativos)) - chaves_depois:
                self._remover_arquivo_silencioso(chave_orfa)

            metadados_finais = MetadadosIngestao(
                total_questoes_extraidas=len(questoes_extraidas),
                imagens_detectadas=resultado_prova.metadados.imagens_detectadas,
                imagens_filtradas_margem=resultado_prova.metadados.imagens_filtradas_margem,
                formulas_recortadas=resultado_prova.metadados.formulas_recortadas,
                usou_ocr=resultado_prova.metadados.usou_ocr,
                paginas_fonte_symbol=resultado_prova.metadados.paginas_fonte_symbol,
                gabarito_enviado=gabarito_enviado,
                taxonomia_id_encadeada=taxonomia_id_encadeada,
                perfil_id_encadeada=perfil_id_encadeada,
                execucao_classificacao_id=None,
                status_classificacao_encadeada=(
                    "aguardando_agendamento" if taxonomia_id_encadeada is not None else None
                ),
            )
            ingestao.concluir(_agora_utc(), metadados_finais)
            ingestao = self._repo_ingestoes.salvar(ingestao)
        except Exception as err:
            logger.exception("Falha na ingestão '%s' da prova '%s'.", tarefa.ingestao_id, tarefa.prova_id)
            for chave_nova in novas_chaves_ativos:
                self._remover_arquivo_silencioso(chave_nova)
            if ingestao.status == StatusIngestao.PROCESSANDO:
                mensagem = str(err).strip() or type(err).__name__
                ingestao.falhar(mensagem, _agora_utc())
                self._repo_ingestoes.salvar(ingestao)
            return

        if taxonomia_id_encadeada is not None:
            self._executar_hook_classificacao(
                ingestao=ingestao,
                prova_id=prova.id,
                taxonomia_id=taxonomia_id_encadeada,
                perfil_id=perfil_id_encadeada,
            )

    def _executar_hook_classificacao(
        self,
        *,
        ingestao: Ingestao,
        prova_id: UUID,
        taxonomia_id: UUID,
        perfil_id: UUID | None,
    ) -> None:
        if self._classificacao_hook is None:
            try:
                ingestao.metadados = replace(
                    ingestao.metadados,
                    status_classificacao_encadeada="hook_nao_configurado",
                )
                self._repo_ingestoes.salvar(ingestao)
            except Exception:
                logger.exception("Falha ao atualizar status do hook não configurado na ingestão '%s'.", ingestao.id)
            return

        try:
            execucao_id = self._classificacao_hook(
                prova_id=prova_id,
                taxonomia_id=taxonomia_id,
                perfil_id=perfil_id,
            )
            ingestao.metadados = replace(
                ingestao.metadados,
                execucao_classificacao_id=execucao_id,
                status_classificacao_encadeada="agendada",
            )
            self._repo_ingestoes.salvar(ingestao)
        except Exception:
            logger.exception(
                "Erro no hook de classificação encadeada da ingestão '%s' (ingestão permanece concluída).",
                ingestao.id,
            )
            try:
                ingestao.metadados = replace(
                    ingestao.metadados,
                    status_classificacao_encadeada="erro_agendamento",
                )
                self._repo_ingestoes.salvar(ingestao)
            except Exception:
                logger.exception("Falha ao registrar erro_agendamento na ingestão '%s'.", ingestao.id)

    def _executar_classificacao(self, tarefa: TarefaClassificacao) -> None:
        def atualizar_progresso(processadas: int, total: int) -> None:
            self._definir_status_ocupado(
                tipo="classificacao",
                alvo=tarefa.alvo,
                processadas=processadas,
                total=total,
            )

        self._definir_status_ocupado(
            tipo="classificacao",
            alvo=tarefa.alvo,
            processadas=0,
            total=tarefa.total,
        )
        try:
            if tarefa.executor is not None:
                tarefa.executor(atualizar_progresso)
            elif self._classificacao_executor is not None:
                self._classificacao_executor(tarefa.execucao_id, atualizar_progresso)
        except Exception:
            logger.exception("Falha na execução de classificação '%s' no worker.", tarefa.execucao_id)

    def _remover_arquivo_silencioso(self, chave: str) -> None:
        try:
            self._armazenamento.remover(chave)
        except Exception:
            logger.warning("Não foi possível remover arquivo órfão '%s'.", chave)
