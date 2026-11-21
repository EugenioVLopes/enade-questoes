"""Testes de integração do WorkerLocal sequencial e recuperação de boot."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from application.ports.extracao import (
    AlternativaExtraida,
    ItemGabaritoExtraido,
    QuestaoExtraida,
    ResultadoExtracaoGabarito,
    ResultadoExtracaoProva,
)
from application.worker import _SENTINELA_PARAR, WorkerLocal
from domain.classificacao import ExecucaoClassificacao, PerfilClassificacao
from domain.enums import (
    EscopoExecucao,
    LetraAlternativa,
    SituacaoGabarito,
    StatusExecucaoClassificacao,
    StatusIngestao,
    TipoQuestao,
)
from domain.prova import FaixaQuestoes, Gabarito, Ingestao, MetadadosIngestao, Prova
from domain.taxonomia import Disciplina, Taxonomia
from infrastructure.config import Settings
from infrastructure.persistence.repositorios import (
    RepositorioExecucoesClassificacaoSqlAlchemy,
    RepositorioIngestoesSqlAlchemy,
    RepositorioPerfisClassificacaoSqlAlchemy,
    RepositorioProvasSqlAlchemy,
    RepositorioQuestoesSqlAlchemy,
    RepositorioTaxonomiasSqlAlchemy,
)
from infrastructure.storage.local import ArmazenamentoArquivosLocal
from presentation.main import build_app


class _FakeExtratorProvaControlado:
    def __init__(
        self,
        *,
        ao_entrar: threading.Event | None = None,
        liberar: threading.Event | None = None,
        erro_por_pdf: dict[str, Exception] | None = None,
    ) -> None:
        self._ao_entrar = ao_entrar
        self._liberar = liberar
        self._erro_por_pdf = erro_por_pdf or {}
        self.lock = threading.Lock()
        self.ativos_simultaneos = 0
        self.max_simultaneos = 0
        self.ordem_execucao: list[str] = []

    def extrair(self, caminho_pdf: Path, faixa_ce: FaixaQuestoes) -> ResultadoExtracaoProva:
        with self.lock:
            self.ativos_simultaneos += 1
            self.max_simultaneos = max(self.max_simultaneos, self.ativos_simultaneos)
            self.ordem_execucao.append(caminho_pdf.as_posix())
        try:
            if self._ao_entrar is not None:
                self._ao_entrar.set()
            if self._liberar is not None:
                self._liberar.wait(timeout=5.0)
            for chave, erro in self._erro_por_pdf.items():
                if chave in caminho_pdf.as_posix():
                    raise erro
            questoes = tuple(
                QuestaoExtraida(
                    numero=numero,
                    enunciado=f"Enunciado completo da questão {numero} sobre sistemas distribuídos.",
                    paginas=(1,),
                    alternativas=tuple(
                        AlternativaExtraida(letra=letra, texto=f"Alternativa {letra.value} da questão {numero}.")
                        for letra in LetraAlternativa
                    ),
                    ativos_visuais=(),
                )
                for numero in range(faixa_ce.inicio, faixa_ce.inicio + 2)
            )
            return ResultadoExtracaoProva(
                questoes=questoes,
                extracao_bruta_json='{"pages": []}',
                metadados=MetadadosIngestao(total_questoes_extraidas=len(questoes)),
            )
        finally:
            with self.lock:
                self.ativos_simultaneos -= 1


class _FakeExtratorGabaritoVazio:
    def extrair(self, caminho_pdf: Path) -> ResultadoExtracaoGabarito:
        return ResultadoExtracaoGabarito(
            itens=(
                ItemGabaritoExtraido(
                    numero=10,
                    tipo=TipoQuestao.OBJETIVA,
                    gabarito=Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.A),
                ),
            )
        )


def _criar_worker(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
    *,
    extrator_prova: _FakeExtratorProvaControlado | None = None,
    classificacao_hook: object | None = None,
) -> WorkerLocal:
    return WorkerLocal(
        repo_provas=RepositorioProvasSqlAlchemy(session_factory),
        repo_ingestoes=RepositorioIngestoesSqlAlchemy(session_factory),
        repo_questoes=RepositorioQuestoesSqlAlchemy(session_factory),
        repo_execucoes=RepositorioExecucoesClassificacaoSqlAlchemy(session_factory),
        armazenamento=ArmazenamentoArquivosLocal(tmp_path),
        extrator_prova=extrator_prova or _FakeExtratorProvaControlado(),
        extrator_gabarito=_FakeExtratorGabaritoVazio(),
        classificacao_hook=classificacao_hook,  # type: ignore[arg-type]
    )


def test_worker_local_recupera_ingestoes_e_execucoes_em_processamento_no_boot(
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    repo_provas = RepositorioProvasSqlAlchemy(session_factory_teste)
    repo_ingestoes = RepositorioIngestoesSqlAlchemy(session_factory_teste)
    repo_tax = RepositorioTaxonomiasSqlAlchemy(session_factory_teste)
    repo_perf = RepositorioPerfisClassificacaoSqlAlchemy(session_factory_teste)
    repo_exec = RepositorioExecucoesClassificacaoSqlAlchemy(session_factory_teste)

    agora = datetime(2026, 11, 21, 15, 0, tzinfo=UTC)
    prova = repo_provas.salvar(Prova(exame="ENADE", curso="Engenharia de Computação", ano=2023))

    ing_processando = Ingestao(prova_id=prova.id, criada_em=agora)
    ing_processando.iniciar(agora)
    repo_ingestoes.salvar(ing_processando)

    ing_concluida = Ingestao(prova_id=prova.id, criada_em=agora)
    ing_concluida.iniciar(agora)
    ing_concluida.concluir(agora, MetadadosIngestao(total_questoes_extraidas=29))
    repo_ingestoes.salvar(ing_concluida)

    tax = repo_tax.salvar(
        Taxonomia(
            codigo="enade-ec",
            nome="ENADE EC",
            curso_referencia="Engenharia de Computação",
            disciplinas=[Disciplina(codigo="algoritmos", nome="Algoritmos")],
        )
    )
    perfil = repo_perf.salvar(
        PerfilClassificacao(
            codigo="v2-fronteiras",
            versao="v1",
            diretrizes_gerais="Diretrizes.",
            guia_fronteiras="Fronteiras.",
            template_prompt="Prompt.",
        )
    )
    exec_processando = ExecucaoClassificacao(
        taxonomia_id=tax.id,
        perfil_id=perfil.id,
        snapshot_taxonomia={"codigo": tax.codigo},
        snapshot_perfil={"codigo": perfil.codigo},
        escopo=EscopoExecucao.TODAS,
        total_itens=10,
    )
    exec_processando.iniciar(agora, total_itens=10)
    repo_exec.salvar(exec_processando)

    worker = _criar_worker(session_factory_teste, tmp_path)
    worker.iniciar()
    try:
        ing_rec = repo_ingestoes.buscar_por_id(ing_processando.id)
        ing_ok = repo_ingestoes.buscar_por_id(ing_concluida.id)
        exec_rec = repo_exec.buscar_por_id(exec_processando.id)

        assert ing_rec is not None
        assert ing_rec.status == StatusIngestao.INTERROMPIDA
        assert ing_rec.concluida_em is not None
        assert ing_rec.mensagem_erro is not None

        assert ing_ok is not None
        assert ing_ok.status == StatusIngestao.CONCLUIDA

        assert exec_rec is not None
        assert exec_rec.status == StatusExecucaoClassificacao.INTERROMPIDA
        assert exec_rec.concluida_em is not None
    finally:
        worker.parar()


def test_worker_local_executa_sequencialmente_1_tarefa_por_vez_e_expoe_status_ativo(
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    armazenamento = ArmazenamentoArquivosLocal(tmp_path)
    repo_provas = RepositorioProvasSqlAlchemy(session_factory_teste)
    repo_ingestoes = RepositorioIngestoesSqlAlchemy(session_factory_teste)

    prova1 = Prova(exame="ENADE", curso="Engenharia de Computação", ano=2019)
    prova1.caminho_pdf = armazenamento.salvar(f"provas/{prova1.id}/prova.pdf", b"%PDF-1.4 p1")
    repo_provas.salvar(prova1)
    ing1 = repo_ingestoes.salvar(Ingestao(prova_id=prova1.id))

    entrou_primeira = threading.Event()
    liberar_primeira = threading.Event()
    extrator = _FakeExtratorProvaControlado(ao_entrar=entrou_primeira, liberar=liberar_primeira)
    worker = _criar_worker(session_factory_teste, tmp_path, extrator_prova=extrator)

    classificacao_executada = threading.Event()

    def _exec_classificacao(atualizar_progresso: object) -> None:
        assert callable(atualizar_progresso)
        assert extrator.ativos_simultaneos == 0
        atualizar_progresso(3, 5)
        status_durante = worker.status_atual()
        assert status_durante.estado == "ocupado"
        assert status_durante.tipo == "classificacao"
        assert status_durante.alvo == "ENADE 2023"
        assert status_durante.processadas == 3
        assert status_durante.total == 5
        assert status_durante.tarefa_ativa == "Classificando ENADE 2023: 3/5"
        classificacao_executada.set()

    worker.iniciar()
    try:
        worker.enfileirar_ingestao(prova1.id, ing1.id)
        worker.enfileirar_classificacao(
            uuid4(),
            alvo="ENADE 2023",
            total=5,
            executor=_exec_classificacao,
        )

        assert entrou_primeira.wait(timeout=5.0)
        # Aguarda um instante para garantir que a 2a tarefa nao iniciou em paralelo
        time.sleep(0.05)
        assert not classificacao_executada.is_set()

        status_ing = worker.status_atual()
        assert status_ing.estado == "ocupado"
        assert status_ing.tipo == "ingestao"
        assert status_ing.alvo == "ENADE 2019"
        assert status_ing.total == len(prova1.faixa_ce or FaixaQuestoes(9, 35))

        liberar_primeira.set()
        worker.aguardar_ocioso(timeout=10.0)

        assert classificacao_executada.is_set()
        assert extrator.max_simultaneos == 1
        assert worker.status_atual().estado == "ocioso"
        assert worker.status_atual().tipo is None
        assert worker.status_atual().tarefa_ativa is None
    finally:
        liberar_primeira.set()
        worker.parar()


def test_worker_local_marca_erro_sem_derrubar_loop_e_permite_retentativa(
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    armazenamento = ArmazenamentoArquivosLocal(tmp_path)
    repo_provas = RepositorioProvasSqlAlchemy(session_factory_teste)
    repo_ingestoes = RepositorioIngestoesSqlAlchemy(session_factory_teste)

    prova_falha = Prova(exame="ENADE", curso="Engenharia de Computação", ano=2017)
    prova_falha.caminho_pdf = armazenamento.salvar(f"provas/{prova_falha.id}/prova.pdf", b"%PDF-1.4 falha")
    repo_provas.salvar(prova_falha)
    ing_falha = repo_ingestoes.salvar(Ingestao(prova_id=prova_falha.id))

    prova_ok = Prova(exame="ENADE", curso="Engenharia de Computação", ano=2023)
    prova_ok.caminho_pdf = armazenamento.salvar(f"provas/{prova_ok.id}/prova.pdf", b"%PDF-1.4 ok")
    repo_provas.salvar(prova_ok)
    ing_ok = repo_ingestoes.salvar(Ingestao(prova_id=prova_ok.id))

    erro_mapa: dict[str, Exception] = {str(prova_falha.id): RuntimeError("Falha simulada no Docling")}
    extrator = _FakeExtratorProvaControlado(erro_por_pdf=erro_mapa)
    worker = _criar_worker(session_factory_teste, tmp_path, extrator_prova=extrator)

    worker.iniciar()
    try:
        worker.enfileirar_ingestao(prova_falha.id, ing_falha.id)
        worker.enfileirar_ingestao(prova_ok.id, ing_ok.id)
        worker.aguardar_ocioso(timeout=10.0)

        ing_falha_db = repo_ingestoes.buscar_por_id(ing_falha.id)
        ing_ok_db = repo_ingestoes.buscar_por_id(ing_ok.id)
        assert ing_falha_db is not None
        assert ing_falha_db.status == StatusIngestao.ERRO
        assert ing_falha_db.mensagem_erro == "Falha simulada no Docling"
        assert ing_ok_db is not None
        assert ing_ok_db.status == StatusIngestao.CONCLUIDA

        # Limpa a falha simulada e retenta a mesma Ingestão em erro
        erro_mapa.clear()
        worker.enfileirar_ingestao(prova_falha.id, ing_falha.id)
        worker.aguardar_ocioso(timeout=10.0)

        ing_retentada = repo_ingestoes.buscar_por_id(ing_falha.id)
        assert ing_retentada is not None
        assert ing_retentada.status == StatusIngestao.CONCLUIDA
        assert ing_retentada.mensagem_erro is None
    finally:
        worker.parar()


def test_worker_local_hook_classificacao_encadeada_nao_falha_ingestao_concluida(
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    armazenamento = ArmazenamentoArquivosLocal(tmp_path)
    repo_provas = RepositorioProvasSqlAlchemy(session_factory_teste)
    repo_ingestoes = RepositorioIngestoesSqlAlchemy(session_factory_teste)

    tax_id = uuid4()
    perfil_id = uuid4()

    prova = Prova(exame="ENADE", curso="Engenharia de Computação", ano=2023)
    prova.caminho_pdf = armazenamento.salvar(f"provas/{prova.id}/prova.pdf", b"%PDF-1.4 hook")
    repo_provas.salvar(prova)
    ing = repo_ingestoes.salvar(
        Ingestao(
            prova_id=prova.id,
            metadados=MetadadosIngestao(
                taxonomia_id_encadeada=tax_id,
                perfil_id_encadeada=perfil_id,
                status_classificacao_encadeada="aguardando_ingestao",
            ),
        )
    )

    def _hook_com_erro(*, prova_id: UUID, taxonomia_id: UUID, perfil_id: UUID | None) -> UUID | None:
        raise RuntimeError("Erro simulado no agendamento LLM")

    worker = _criar_worker(session_factory_teste, tmp_path, classificacao_hook=_hook_com_erro)
    worker.iniciar()
    try:
        worker.enfileirar_ingestao(prova.id, ing.id)
        worker.aguardar_ocioso(timeout=10.0)

        ing_db = repo_ingestoes.buscar_por_id(ing.id)
        assert ing_db is not None
        assert ing_db.status == StatusIngestao.CONCLUIDA
        assert ing_db.metadados.taxonomia_id_encadeada == tax_id
        assert ing_db.metadados.status_classificacao_encadeada == "erro_agendamento"
    finally:
        worker.parar()


def test_lifespan_fastapi_executa_recuperacao_de_boot_automaticamente(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    repo_provas = RepositorioProvasSqlAlchemy(session_factory_teste)
    repo_ingestoes = RepositorioIngestoesSqlAlchemy(session_factory_teste)

    prova = repo_provas.salvar(Prova(exame="ENADE", curso="Engenharia de Computação", ano=2023))
    ing = Ingestao(prova_id=prova.id)
    ing.iniciar(datetime(2026, 11, 21, 12, 0, tzinfo=UTC))
    repo_ingestoes.salvar(ing)

    app = build_app(
        Settings(database_url=db_teste_url, data_dir=tmp_path),
        extrator_prova=_FakeExtratorProvaControlado(),
        extrator_gabarito=_FakeExtratorGabaritoVazio(),
    )
    with TestClient(app) as client:
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["worker"]["estado"] == "ocioso"

    ing_apos = repo_ingestoes.buscar_por_id(ing.id)
    assert ing_apos is not None
    assert ing_apos.status == StatusIngestao.INTERROMPIDA


def test_worker_local_drena_fila_ao_parar_com_tarefa_pendente_e_permite_reiniciar(
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    armazenamento = ArmazenamentoArquivosLocal(tmp_path)
    repo_provas = RepositorioProvasSqlAlchemy(session_factory_teste)
    repo_ingestoes = RepositorioIngestoesSqlAlchemy(session_factory_teste)

    prova1 = Prova(exame="ENADE", curso="Engenharia de Computação", ano=2019)
    prova1.caminho_pdf = armazenamento.salvar(f"provas/{prova1.id}/prova.pdf", b"%PDF-1.4 p1")
    repo_provas.salvar(prova1)
    ing1 = repo_ingestoes.salvar(Ingestao(prova_id=prova1.id))

    prova2 = Prova(exame="ENADE", curso="Engenharia de Computação", ano=2023)
    prova2.caminho_pdf = armazenamento.salvar(f"provas/{prova2.id}/prova.pdf", b"%PDF-1.4 p2")
    repo_provas.salvar(prova2)
    ing2 = repo_ingestoes.salvar(Ingestao(prova_id=prova2.id))

    entrou_primeira = threading.Event()
    liberar_primeira = threading.Event()
    extrator = _FakeExtratorProvaControlado(ao_entrar=entrou_primeira, liberar=liberar_primeira)
    worker = _criar_worker(session_factory_teste, tmp_path, extrator_prova=extrator)

    worker.iniciar()
    try:
        worker.enfileirar_ingestao(prova1.id, ing1.id)
        assert entrou_primeira.wait(timeout=5.0)

        worker.enfileirar_ingestao(prova2.id, ing2.id)

        parada_concluida = threading.Event()

        def _parar_worker() -> None:
            worker.parar(timeout=5.0)
            parada_concluida.set()

        thread_parada = threading.Thread(target=_parar_worker, daemon=True)
        thread_parada.start()
        deadline = time.monotonic() + 2.0
        while not worker._parando.is_set() and time.monotonic() < deadline:
            time.sleep(0.005)
        assert worker._parando.is_set()

        liberar_primeira.set()
        assert parada_concluida.wait(timeout=5.0)
        thread_parada.join(timeout=2.0)

        assert worker._fila.empty()
        assert worker._fila.unfinished_tasks == 0
        worker.aguardar_ocioso(timeout=1.0)
        assert worker.status_atual().estado == "ocioso"

        ing1_db = repo_ingestoes.buscar_por_id(ing1.id)
        ing2_db = repo_ingestoes.buscar_por_id(ing2.id)
        assert ing1_db is not None and ing1_db.status == StatusIngestao.CONCLUIDA
        assert ing2_db is not None and ing2_db.status == StatusIngestao.PENDENTE

        # Reinicia a mesma instância do WorkerLocal e executa nova tarefa
        worker.enfileirar_ingestao(prova2.id, ing2.id)
        worker.iniciar()
        worker.aguardar_ocioso(timeout=5.0)

        ing2_reiniciada = repo_ingestoes.buscar_por_id(ing2.id)
        assert ing2_reiniciada is not None
        assert ing2_reiniciada.status == StatusIngestao.CONCLUIDA
    finally:
        liberar_primeira.set()
        worker.parar()


def test_worker_local_loop_com_parando_ativo_drena_sentinela_e_permite_reiniciar(
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    armazenamento = ArmazenamentoArquivosLocal(tmp_path)
    repo_provas = RepositorioProvasSqlAlchemy(session_factory_teste)
    repo_ingestoes = RepositorioIngestoesSqlAlchemy(session_factory_teste)

    prova1 = Prova(exame="ENADE", curso="Engenharia de Computação", ano=2017)
    prova1.caminho_pdf = armazenamento.salvar(f"provas/{prova1.id}/prova.pdf", b"%PDF-1.4 p1")
    repo_provas.salvar(prova1)
    ing1 = repo_ingestoes.salvar(Ingestao(prova_id=prova1.id))

    prova2 = Prova(exame="ENADE", curso="Engenharia de Computação", ano=2019)
    prova2.caminho_pdf = armazenamento.salvar(f"provas/{prova2.id}/prova.pdf", b"%PDF-1.4 p2")
    repo_provas.salvar(prova2)
    ing2 = repo_ingestoes.salvar(Ingestao(prova_id=prova2.id))

    prova3 = Prova(exame="ENADE", curso="Engenharia de Computação", ano=2023)
    prova3.caminho_pdf = armazenamento.salvar(f"provas/{prova3.id}/prova.pdf", b"%PDF-1.4 p3")
    repo_provas.salvar(prova3)
    ing3 = repo_ingestoes.salvar(Ingestao(prova_id=prova3.id))

    worker = _criar_worker(session_factory_teste, tmp_path)

    # Reproduz o cenário exato em que _loop() encontra item pendente com _parando já ativo
    worker.enfileirar_ingestao(prova1.id, ing1.id)
    worker.enfileirar_ingestao(prova2.id, ing2.id)
    worker._parando.set()
    worker._fila.put(_SENTINELA_PARAR)
    worker._loop()

    assert worker._fila.empty()
    assert worker._fila.unfinished_tasks == 0
    worker.aguardar_ocioso(timeout=1.0)

    ing1_db = repo_ingestoes.buscar_por_id(ing1.id)
    ing2_db = repo_ingestoes.buscar_por_id(ing2.id)
    assert ing1_db is not None and ing1_db.status == StatusIngestao.PENDENTE
    assert ing2_db is not None and ing2_db.status == StatusIngestao.PENDENTE

    # Também garante que sentinela residual antes de iniciar() é drenada sem perder tarefas válidas
    worker._fila.put(_SENTINELA_PARAR)
    worker.enfileirar_ingestao(prova3.id, ing3.id)
    worker.iniciar()
    try:
        worker.aguardar_ocioso(timeout=5.0)
        ing3_db = repo_ingestoes.buscar_por_id(ing3.id)
        assert ing3_db is not None
        assert ing3_db.status == StatusIngestao.CONCLUIDA
    finally:
        worker.parar()
