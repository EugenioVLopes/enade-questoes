"""Gravações do sistema (reprocessamento e gabarito) convivendo com edições concorrentes do revisor."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session, sessionmaker

import application.provas as provas_mod
from application.exceptions import ConflitoRecursoError
from application.provas import AtualizarGabaritoUseCase
from application.worker import WorkerLocal
from domain.enums import LetraAlternativa, SituacaoGabarito, StatusIngestao
from domain.prova import Gabarito, Ingestao, MetadadosIngestao, Prova
from infrastructure.persistence.repositorios import (
    RepositorioExecucoesClassificacaoSqlAlchemy,
    RepositorioIngestoesSqlAlchemy,
    RepositorioProvasSqlAlchemy,
    RepositorioQuestoesSqlAlchemy,
)
from infrastructure.storage.local import ArmazenamentoArquivosLocal
from tests.integration._apoio_questoes import ENUNCIADO_BOM, RepoComGancho, Repos, criar_questao, criar_repos
from tests.integration.test_worker_local import _FakeExtratorGabaritoVazio, _FakeExtratorProvaControlado

ENUNCIADO_REVISOR = "Enunciado do revisor gravado durante o processamento da prova."
PDF = b"%PDF-1.4 conteudo"


def _preparar_prova(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
    *,
    q10_editada: bool = False,
    com_ausente_na_extracao: bool = False,
) -> tuple[Repos, ArmazenamentoArquivosLocal, Prova, RepositorioIngestoesSqlAlchemy]:
    repos = criar_repos(session_factory)
    armazenamento = ArmazenamentoArquivosLocal(tmp_path)
    prova = Prova(exame="ENADE", curso="Engenharia de Computação", ano=2019)
    prova.caminho_pdf = armazenamento.salvar(f"provas/{prova.id}/prova.pdf", PDF)
    repos.provas.salvar(prova)
    criar_questao(repos, prova, 9, ENUNCIADO_BOM)
    q10 = criar_questao(repos, prova, 10, ENUNCIADO_BOM)
    if q10_editada:
        q10.editada_manualmente = True
        repos.questoes.salvar(q10)
    if com_ausente_na_extracao:
        criar_questao(repos, prova, 11, ENUNCIADO_BOM)  # o extrator fake só devolve as questões 9 e 10
    return repos, armazenamento, prova, RepositorioIngestoesSqlAlchemy(session_factory)


def _revisor_edita(repos: Repos, prova_id: Any, numero: int) -> None:
    questao = next(q for q in repos.questoes.listar_por_prova(prova_id) if q.numero == numero)
    questao.editar_conteudo(enunciado=ENUNCIADO_REVISOR)
    questao.editada_manualmente = True
    repos.questoes.salvar(questao)


def _reprocessar_com_revisor_durante_extracao(
    session_factory: sessionmaker[Session],
    tmp_path: Path,
    *,
    numero_editado: int,
    sobrescrever_editadas: bool,
    q10_editada: bool = False,
    com_ausente_na_extracao: bool = False,
) -> tuple[Repos, Prova, Ingestao, dict[int, Any]]:
    repos, armazenamento, prova, repo_ingestoes = _preparar_prova(
        session_factory, tmp_path, q10_editada=q10_editada, com_ausente_na_extracao=com_ausente_na_extracao
    )
    ingestao = repo_ingestoes.salvar(Ingestao(prova_id=prova.id))
    # O gancho dispara logo após a leitura inicial do worker: a edição cai entre a leitura e a gravação.
    repo_questoes = RepoComGancho(
        repos.questoes, "listar_por_prova", lambda: _revisor_edita(repos, prova.id, numero_editado)
    )
    worker = WorkerLocal(
        repo_provas=RepositorioProvasSqlAlchemy(session_factory),
        repo_ingestoes=repo_ingestoes,
        repo_questoes=repo_questoes,  # type: ignore[arg-type]
        repo_execucoes=RepositorioExecucoesClassificacaoSqlAlchemy(session_factory),
        armazenamento=armazenamento,
        extrator_prova=_FakeExtratorProvaControlado(),
        extrator_gabarito=_FakeExtratorGabaritoVazio(),
    )
    worker.iniciar()
    try:
        worker.enfileirar_ingestao(prova.id, ingestao.id, sobrescrever_editadas=sobrescrever_editadas)
        worker.aguardar_ocioso(timeout=20)
    finally:
        worker.parar()
    final = repo_ingestoes.buscar_por_id(ingestao.id)
    assert final is not None
    return repos, prova, final, {q.numero: q for q in repos.questoes.listar_por_prova(prova.id)}


def test_reprocessamento_preserva_edicao_do_revisor_feita_durante_a_extracao(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    _, _, ingestao, questoes = _reprocessar_com_revisor_durante_extracao(
        session_factory_teste, tmp_path, numero_editado=9, sobrescrever_editadas=False
    )
    assert ingestao.status == StatusIngestao.CONCLUIDA, ingestao.mensagem_erro
    assert questoes[9].enunciado == ENUNCIADO_REVISOR
    assert questoes[9].editada_manualmente is True
    assert questoes[10].enunciado != ENUNCIADO_BOM  # a demais foi reprocessada
    assert "questão 10" in questoes[10].enunciado


def test_reprocessamento_com_sobrescrita_aplica_a_extracao_sobre_edicao_concorrente(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    _, _, ingestao, questoes = _reprocessar_com_revisor_durante_extracao(
        session_factory_teste, tmp_path, numero_editado=9, sobrescrever_editadas=True
    )
    assert ingestao.status == StatusIngestao.CONCLUIDA, ingestao.mensagem_erro
    assert "questão 9" in questoes[9].enunciado
    assert questoes[9].editada_manualmente is False
    assert "questão 10" in questoes[10].enunciado


def test_reprocessamento_nao_regrava_questao_ja_preservada_editada_durante_a_extracao(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    _, _, ingestao, questoes = _reprocessar_com_revisor_durante_extracao(
        session_factory_teste, tmp_path, numero_editado=10, sobrescrever_editadas=False, q10_editada=True
    )
    assert ingestao.status == StatusIngestao.CONCLUIDA, ingestao.mensagem_erro
    assert questoes[10].enunciado == ENUNCIADO_REVISOR
    assert questoes[10].editada_manualmente is True
    assert "questão 9" in questoes[9].enunciado


def test_reprocessamento_com_sobrescrita_preserva_edicao_concorrente_de_questao_ausente_da_extracao(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    # A questão 11 existe no banco, não vem na extração (a reconciliação a mantém como lida) e o revisor a edita
    # durante a extração: regravá-la com a cópia lida (sobrescrever_editadas=true) reverteria a edição.
    _, _, ingestao, questoes = _reprocessar_com_revisor_durante_extracao(
        session_factory_teste,
        tmp_path,
        numero_editado=11,
        sobrescrever_editadas=True,
        com_ausente_na_extracao=True,
    )
    assert ingestao.status == StatusIngestao.CONCLUIDA, ingestao.mensagem_erro
    assert questoes[11].enunciado == ENUNCIADO_REVISOR
    assert questoes[11].editada_manualmente is True
    assert "questão 9" in questoes[9].enunciado  # as extraídas continuam sobrescritas
    assert "questão 10" in questoes[10].enunciado


class _AntesDe:
    """Executa o gancho imediatamente antes de a chamada `metodo` ser delegada ao repositório."""

    def __init__(self, real: Any, metodo: str, gancho: Any) -> None:
        self._real = real
        self._metodo = metodo
        self._gancho = gancho

    def __getattr__(self, nome: str) -> Any:
        atributo = getattr(self._real, nome)
        if nome != self._metodo:
            return atributo

        def envolvido(*args: Any, **kwargs: Any) -> Any:
            self._gancho()
            return atributo(*args, **kwargs)

        return envolvido


def _preparar_gabarito(
    session_factory: sessionmaker[Session], tmp_path: Path
) -> tuple[Repos, ArmazenamentoArquivosLocal, Prova, RepositorioIngestoesSqlAlchemy, Ingestao]:
    repos, armazenamento, prova, repo_ingestoes = _preparar_prova(session_factory, tmp_path)
    q10 = next(q for q in repos.questoes.listar_por_prova(prova.id) if q.numero == 10)
    q10.gabarito = Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.B)
    repos.questoes.salvar(q10)
    ingestao = Ingestao(prova_id=prova.id)
    ingestao.iniciar(datetime.now(UTC))
    ingestao.concluir(datetime.now(UTC), MetadadosIngestao(total_questoes_extraidas=2))
    return repos, armazenamento, prova, repo_ingestoes, repo_ingestoes.salvar(ingestao)


def _caso_de_uso_gabarito(
    session_factory: sessionmaker[Session],
    repo_ingestoes: RepositorioIngestoesSqlAlchemy,
    repo_questoes: Any,
    armazenamento: ArmazenamentoArquivosLocal,
) -> AtualizarGabaritoUseCase:
    return AtualizarGabaritoUseCase(
        repo_provas=RepositorioProvasSqlAlchemy(session_factory),
        repo_ingestoes=repo_ingestoes,
        repo_questoes=repo_questoes,
        armazenamento=armazenamento,
        extrator_gabarito=_FakeExtratorGabaritoVazio(),
    )


def test_gabarito_aplicado_sobre_edicao_concorrente_do_revisor_sem_conflito(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos, armazenamento, prova, repo_ingestoes, ingestao = _preparar_gabarito(session_factory_teste, tmp_path)

    # A edição do revisor cai na janela entre ler e gravar as questões: logo após `listar_por_prova` (fluxo antigo,
    # que gerava 409) ou imediatamente antes da transação de `atualizar_por_prova` (fluxo atual).
    def revisor() -> None:
        _revisor_edita(repos, prova.id, 9)

    proxy = _AntesDe(RepoComGancho(repos.questoes, "listar_por_prova", revisor), "atualizar_por_prova", revisor)
    caso_de_uso = _caso_de_uso_gabarito(session_factory_teste, repo_ingestoes, proxy, armazenamento)

    resumo = caso_de_uso.execute(prova.id, b"%PDF-1.4 gabarito")

    questoes = {q.numero: q for q in repos.questoes.listar_por_prova(prova.id)}
    assert resumo.alteradas == 1
    assert questoes[10].gabarito.alternativa_correta == LetraAlternativa.A
    assert questoes[9].enunciado == ENUNCIADO_REVISOR
    assert questoes[9].editada_manualmente is True
    prova_final = repos.provas.buscar_por_id(prova.id)
    assert prova_final is not None
    assert prova_final.caminho_gabarito == f"provas/{prova.id}/gabarito.pdf"
    ingestao_final = repo_ingestoes.buscar_por_id(ingestao.id)
    assert ingestao_final is not None
    assert ingestao_final.metadados.gabarito_enviado is True


def test_gabarito_mantem_a_transacao_travada_contra_escrita_concorrente_do_revisor(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos, armazenamento, prova, repo_ingestoes, _ = _preparar_gabarito(session_factory_teste, tmp_path)
    lida_pelo_revisor = repos.questoes.buscar_por_id(
        next(q.id for q in repos.questoes.listar_por_prova(prova.id) if q.numero == 10)
    )
    assert lida_pelo_revisor is not None
    lida_pelo_revisor.editar_conteudo(enunciado=ENUNCIADO_REVISOR)
    resultado: dict[str, BaseException | None] = {"erro": None}

    def revisor_salva() -> None:
        try:
            repos.questoes.salvar(lida_pelo_revisor)
        except BaseException as erro:  # noqa: BLE001
            resultado["erro"] = erro

    threads: list[threading.Thread] = []
    original = provas_mod.aplicar_gabarito_na_prova

    def aplicar_e_dispara_revisor(*args: Any, **kwargs: Any) -> Any:
        # Dentro da transação do sistema (linhas travadas): a gravação do revisor só pode esperar o commit.
        thread = threading.Thread(target=revisor_salva)
        thread.start()
        threads.append(thread)
        return original(*args, **kwargs)

    monkeypatch.setattr(provas_mod, "aplicar_gabarito_na_prova", aplicar_e_dispara_revisor)
    caso_de_uso = _caso_de_uso_gabarito(session_factory_teste, repo_ingestoes, repos.questoes, armazenamento)

    caso_de_uso.execute(prova.id, b"%PDF-1.4 gabarito")
    threads[0].join(timeout=20)

    assert isinstance(resultado["erro"], ConflitoRecursoError)  # o revisor leu antes: lock otimista dele (D17)
    q10 = next(q for q in repos.questoes.listar_por_prova(prova.id) if q.numero == 10)
    assert q10.gabarito.alternativa_correta == LetraAlternativa.A
    assert q10.enunciado == ENUNCIADO_BOM


def test_falha_na_gravacao_das_questoes_nao_deixa_gabarito_pela_metade(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos, armazenamento, prova, repo_ingestoes, ingestao = _preparar_gabarito(session_factory_teste, tmp_path)
    chave = f"provas/{prova.id}/gabarito.pdf"
    armazenamento.salvar(chave, b"%PDF-1.4 gabarito-antigo")
    prova_com_gabarito = repos.provas.buscar_por_id(prova.id)
    assert prova_com_gabarito is not None
    prova_com_gabarito.caminho_gabarito = chave
    repos.provas.salvar(prova_com_gabarito)

    def falha(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("falha injetada na gravação das questões")

    monkeypatch.setattr(provas_mod, "aplicar_gabarito_na_prova", falha)
    caso_de_uso = _caso_de_uso_gabarito(session_factory_teste, repo_ingestoes, repos.questoes, armazenamento)

    with pytest.raises(RuntimeError, match="falha injetada"):
        caso_de_uso.execute(prova.id, b"%PDF-1.4 gabarito-novo")

    assert armazenamento.ler(chave) == b"%PDF-1.4 gabarito-antigo"
    ingestao_final = repo_ingestoes.buscar_por_id(ingestao.id)
    assert ingestao_final is not None
    assert ingestao_final.metadados.gabarito_enviado is False
    q10 = next(q for q in repos.questoes.listar_por_prova(prova.id) if q.numero == 10)
    assert q10.gabarito.alternativa_correta == LetraAlternativa.B


def test_falha_na_gravacao_sem_gabarito_anterior_remove_o_pdf_gravado(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos, armazenamento, prova, repo_ingestoes, _ = _preparar_gabarito(session_factory_teste, tmp_path)

    def falha(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("falha injetada na gravação das questões")

    monkeypatch.setattr(provas_mod, "aplicar_gabarito_na_prova", falha)
    caso_de_uso = _caso_de_uso_gabarito(session_factory_teste, repo_ingestoes, repos.questoes, armazenamento)

    with pytest.raises(RuntimeError):
        caso_de_uso.execute(prova.id, b"%PDF-1.4 gabarito-novo")

    assert not armazenamento.existe(f"provas/{prova.id}/gabarito.pdf")
    prova_final = repos.provas.buscar_por_id(prova.id)
    assert prova_final is not None
    assert prova_final.caminho_gabarito is None


@pytest.mark.parametrize("com_gabarito_anterior", [True, False], ids=["com-gabarito-anterior", "sem-gabarito-anterior"])
def test_falha_durante_a_gravacao_das_questoes_nao_deixa_nada_pela_metade(
    com_gabarito_anterior: bool,
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos, armazenamento, prova, repo_ingestoes, ingestao = _preparar_gabarito(session_factory_teste, tmp_path)
    chave = f"provas/{prova.id}/gabarito.pdf"
    if com_gabarito_anterior:
        armazenamento.salvar(chave, b"%PDF-1.4 gabarito-antigo")
        prova_com_gabarito = repos.provas.buscar_por_id(prova.id)
        assert prova_com_gabarito is not None
        prova_com_gabarito.caminho_gabarito = chave
        repos.provas.salvar(prova_com_gabarito)
    antes = {q.numero: q for q in repos.questoes.listar_por_prova(prova.id)}

    original = RepositorioQuestoesSqlAlchemy._upsert_em_sessao
    chamadas: list[int] = []

    def falha_na_segunda_gravacao(self: Any, session: Any, questao: Any, **kwargs: Any) -> Any:
        # A primeira questão já foi gravada dentro da transação quando a segunda falha: a falha é DURANTE a gravação.
        chamadas.append(questao.numero)
        if len(chamadas) == 2:
            raise RuntimeError("falha injetada durante a gravação das questões")
        return original(self, session, questao, **kwargs)

    monkeypatch.setattr(RepositorioQuestoesSqlAlchemy, "_upsert_em_sessao", falha_na_segunda_gravacao)
    caso_de_uso = _caso_de_uso_gabarito(session_factory_teste, repo_ingestoes, repos.questoes, armazenamento)

    with pytest.raises(RuntimeError, match="durante a gravação"):
        caso_de_uso.execute(prova.id, b"%PDF-1.4 gabarito-novo")

    assert chamadas == [9, 10]
    depois = {q.numero: q for q in repos.questoes.listar_por_prova(prova.id)}
    assert {n: q.versao for n, q in depois.items()} == {n: q.versao for n, q in antes.items()}
    assert depois[10].gabarito.alternativa_correta == LetraAlternativa.B
    assert depois[9].gabarito == antes[9].gabarito
    prova_final = repos.provas.buscar_por_id(prova.id)
    assert prova_final is not None
    ingestao_final = repo_ingestoes.buscar_por_id(ingestao.id)
    assert ingestao_final is not None
    assert ingestao_final.metadados.gabarito_enviado is False
    if com_gabarito_anterior:
        assert armazenamento.ler(chave) == b"%PDF-1.4 gabarito-antigo"
        assert prova_final.caminho_gabarito == chave
    else:
        assert not armazenamento.existe(chave)
        assert prova_final.caminho_gabarito is None
