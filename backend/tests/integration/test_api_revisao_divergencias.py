"""Testes de integração de aprovar, corrigir e resolver divergências (revisão humana)."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from domain.classificacao import ExecucaoClassificacao
from domain.enums import OrigemClassificacao, StatusClassificacao, StatusDivergencia
from domain.prova import Prova
from domain.taxonomia import Taxonomia
from infrastructure.persistence.models import ClassificacaoModel, DivergenciaReclassificacaoModel
from tests.integration._apoio_questoes import (
    Repos,
    abrir_divergencia,
    classificar,
    contar,
    criar_app,
    criar_execucao,
    criar_prova,
    criar_questao,
    criar_repos,
    criar_taxonomia,
)


def _preparar(session_factory: sessionmaker[Session]) -> tuple[Repos, Taxonomia, ExecucaoClassificacao, Prova]:
    repos = criar_repos(session_factory)
    taxonomia = criar_taxonomia(repos)
    execucao = criar_execucao(repos, taxonomia)
    prova = criar_prova(repos, 2023)
    return repos, taxonomia, execucao, prova


def _linhas(repos: Repos, questao_id: UUID) -> list[ClassificacaoModel]:
    with repos.session_factory() as session:
        return list(
            session.scalars(
                select(ClassificacaoModel)
                .where(ClassificacaoModel.questao_id == questao_id)
                .order_by(ClassificacaoModel.criada_em, ClassificacaoModel.id)
            )
        )


def test_aprovar_atualiza_registro_da_ia_in_place(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos, tax, _, prova = _preparar(session_factory_teste)
    questao = criar_questao(repos, prova, 10, "Questão a ser aprovada pelo revisor humano.")
    ia = classificar(repos, questao, tax, "redes", topicos=("roteamento-ospf",), confianca=0.62, prioritaria=True)
    total_antes = contar(repos, ClassificacaoModel)

    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        resp = client.post(f"/api/v1/questoes/{questao.id}/classificacoes/{tax.id}/aprovar")
        assert resp.status_code == 200, resp.text
        corpo = resp.json()
        assert corpo["id"] == str(ia.id)
        assert corpo["origem"] == "automatica"
        assert corpo["status"] == "aprovada"
        assert corpo["revisada_em"] is not None
        assert corpo["vigente"] is True
        assert corpo["confianca"] == pytest.approx(0.62)

        assert contar(repos, ClassificacaoModel) == total_antes
        (linha,) = _linhas(repos, questao.id)
        assert linha.id == ia.id
        assert linha.origem == "automatica"
        assert linha.status == "aprovada"
        assert linha.revisada_em is not None
        assert linha.disciplina_principal == "redes"
        assert linha.topicos == ["roteamento-ospf"]

        # aprovar de novo -> 409 (já aprovada); sem classificação -> 404; questão inexistente -> 404
        assert client.post(f"/api/v1/questoes/{questao.id}/classificacoes/{tax.id}/aprovar").status_code == 409
        outra = criar_questao(repos, prova, 11, "Questão sem classificação alguma registrada.")
        assert client.post(f"/api/v1/questoes/{outra.id}/classificacoes/{tax.id}/aprovar").status_code == 404
        assert client.post(f"/api/v1/questoes/{uuid4()}/classificacoes/{tax.id}/aprovar").status_code == 404


def test_corrigir_cria_humana_e_preserva_a_predicao_da_ia(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos, tax, _, prova = _preparar(session_factory_teste)
    questao = criar_questao(repos, prova, 10, "Questão a ser corrigida pelo revisor humano.")
    ia = classificar(
        repos,
        questao,
        tax,
        "redes",
        secundarias=("algoritmos",),
        topicos=("roteamento-ospf",),
        confianca=0.55,
    )

    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        url = f"/api/v1/questoes/{questao.id}/classificacoes/{tax.id}/corrigir"

        # inválidos: não criam linha nova
        invalidos = [
            {"disciplina_principal": "legada"},  # arquivada
            {"disciplina_principal": "inexistente"},
            {"disciplina_principal": "redes", "disciplinas_secundarias": ["redes"]},  # igual à principal
            {"disciplina_principal": "redes", "disciplinas_secundarias": ["algoritmos", "algoritmos"]},
            {
                "disciplina_principal": "redes",
                "disciplinas_secundarias": ["algoritmos", "sistemas-operacionais", "legada"],
            },
            {"disciplina_principal": "redes", "disciplinas_secundarias": ["legada"]},
            {"disciplina_principal": "redes", "topicos": ["!!!"]},
            {"disciplina_principal": ""},
        ]
        for corpo in invalidos:
            resp = client.post(url, json=corpo)
            assert resp.status_code == 422, (corpo, resp.text)
        assert len(_linhas(repos, questao.id)) == 1

        resp = client.post(
            url,
            json={
                "disciplina_principal": "sistemas-operacionais",
                "disciplinas_secundarias": ["redes", "algoritmos"],
                "topicos": ["Escalonamento de Processos", "escalonamento-de-processos", "Deadlock"],
                "justificativa": "  Ajuste do revisor.  ",
            },
        )
        assert resp.status_code == 201, resp.text
        nova = resp.json()
        assert nova["id"] != str(ia.id)
        assert nova["origem"] == "humana"
        assert nova["status"] == "aprovada"
        assert nova["vigente"] is True
        assert nova["substitui_classificacao_id"] == str(ia.id)
        assert nova["disciplina_principal"] == "sistemas-operacionais"
        assert nova["disciplinas_secundarias"] == ["redes", "algoritmos"]
        assert nova["topicos"] == ["escalonamento-de-processos", "deadlock"]
        assert nova["justificativa"] == "Ajuste do revisor."
        assert nova["revisada_em"] is not None

        linhas = _linhas(repos, questao.id)
        assert len(linhas) == 2
        original = next(linha for linha in linhas if linha.id == ia.id)
        assert original.vigente is False
        assert original.origem == "automatica"
        assert original.status == "pendente_revisao"
        assert original.disciplina_principal == "redes"
        assert original.disciplinas_secundarias == ["algoritmos"]
        assert original.topicos == ["roteamento-ospf"]
        assert original.confianca == pytest.approx(0.55)
        assert original.justificativa == "Justificativa original da IA."
        assert original.revisada_em is None
        assert sum(1 for linha in linhas if linha.vigente) == 1

        # taxonomia inexistente -> 404 (sem vigente passou a criar a humana inicial: ver teste dedicado)
        assert (
            client.post(
                f"/api/v1/questoes/{questao.id}/classificacoes/{uuid4()}/corrigir",
                json={"disciplina_principal": "redes"},
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/v1/questoes/{uuid4()}/classificacoes/{tax.id}/corrigir",
                json={"disciplina_principal": "redes"},
            ).status_code
            == 404
        )


def test_corrigir_sem_vigente_cria_humana_inicial_sem_substituicao(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos, tax, _, prova = _preparar(session_factory_teste)
    questao = criar_questao(repos, prova, 12, "Questão sem classificação, classificada manualmente.")
    url = f"/api/v1/questoes/{questao.id}/classificacoes/{tax.id}/corrigir"

    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        for corpo in (
            {"disciplina_principal": "legada"},  # arquivada
            {"disciplina_principal": "inexistente"},
            {"disciplina_principal": "redes", "disciplinas_secundarias": ["redes"]},
        ):
            assert client.post(url, json=corpo).status_code == 422, corpo
        assert _linhas(repos, questao.id) == []

        resp = client.post(
            url,
            json={
                "disciplina_principal": "redes",
                "disciplinas_secundarias": ["algoritmos"],
                "topicos": ["Roteamento OSPF"],
                "justificativa": "Classificação manual.",
            },
        )
        assert resp.status_code == 201, resp.text
        corpo = resp.json()
        assert corpo["origem"] == "humana"
        assert corpo["status"] == "aprovada"
        assert corpo["vigente"] is True
        assert corpo["substitui_classificacao_id"] is None
        assert corpo["execucao_id"] is None
        assert corpo["disciplina_principal"] == "redes"
        assert corpo["disciplinas_secundarias"] == ["algoritmos"]
        (linha,) = _linhas(repos, questao.id)
        assert linha.vigente is True

        # agora há vigente: a próxima correção substitui (não cria segunda vigente)
        resp2 = client.post(url, json={"disciplina_principal": "algoritmos"})
        assert resp2.status_code == 201, resp2.text
        assert resp2.json()["substitui_classificacao_id"] == corpo["id"]
        linhas = _linhas(repos, questao.id)
        assert len(linhas) == 2
        assert sum(1 for item in linhas if item.vigente) == 1


def test_corrigir_sem_vigente_com_divergencia_aberta_retorna_409(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos, tax, execucao, prova = _preparar(session_factory_teste)
    questao = criar_questao(repos, prova, 13, "Questão com divergência aberta e sem correção prévia.")
    vigente = classificar(
        repos, questao, tax, "redes", status=StatusClassificacao.APROVADA, origem=OrigemClassificacao.HUMANA
    )
    abrir_divergencia(repos, questao, tax, execucao, vigente)
    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        resp = client.post(
            f"/api/v1/questoes/{questao.id}/classificacoes/{tax.id}/corrigir",
            json={"disciplina_principal": "algoritmos"},
        )
        assert resp.status_code == 409


def test_corrigir_sem_vigente_em_corrida_com_outra_vigente_retorna_409_e_nao_500(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos, tax, _, prova = _preparar(session_factory_teste)
    questao = criar_questao(repos, prova, 14, "Questão cuja vigente surge durante a correção.")
    classificar(repos, questao, tax, "redes", status=StatusClassificacao.APROVADA, origem=OrigemClassificacao.HUMANA)
    # Simula a corrida: a leitura do caso de uso não enxerga a vigente que já existe no banco.
    monkeypatch.setattr(type(repos.classificacoes), "buscar_vigente", lambda self, questao_id, taxonomia_id: None)
    with TestClient(criar_app(db_teste_url, tmp_path), raise_server_exceptions=False) as client:
        resp = client.post(
            f"/api/v1/questoes/{questao.id}/classificacoes/{tax.id}/corrigir",
            json={"disciplina_principal": "algoritmos"},
        )
        assert resp.status_code == 409, resp.text
    assert sum(1 for item in _linhas(repos, questao.id) if item.vigente) == 1


def test_corrigir_com_divergencia_aberta_exige_endpoint_resolver(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos, tax, execucao, prova = _preparar(session_factory_teste)
    questao = criar_questao(repos, prova, 10, "Questão com divergência aberta na taxonomia.")
    vigente = classificar(
        repos,
        questao,
        tax,
        "redes",
        status=StatusClassificacao.APROVADA,
        origem=OrigemClassificacao.HUMANA,
    )
    abrir_divergencia(repos, questao, tax, execucao, vigente)
    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        resp = client.post(
            f"/api/v1/questoes/{questao.id}/classificacoes/{tax.id}/corrigir",
            json={"disciplina_principal": "algoritmos"},
        )
        assert resp.status_code == 409
        assert len(_linhas(repos, questao.id)) == 1


def _divergencia_status(repos: Repos, divergencia_id: UUID) -> str:
    with repos.session_factory() as session:
        return str(
            session.scalar(
                select(DivergenciaReclassificacaoModel.status).where(
                    DivergenciaReclassificacaoModel.id == divergencia_id
                )
            )
        )


def test_resolver_manter_humana_aceitar_candidata_e_erros(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos, tax, execucao, prova = _preparar(session_factory_teste)
    q_manter = criar_questao(repos, prova, 10, "Questão cuja classificação humana será mantida.")
    q_aceitar = criar_questao(repos, prova, 11, "Questão cuja candidata da reexecução será aceita.")
    v_manter = classificar(
        repos, q_manter, tax, "algoritmos", status=StatusClassificacao.APROVADA, origem=OrigemClassificacao.HUMANA
    )
    v_aceitar = classificar(
        repos, q_aceitar, tax, "algoritmos", status=StatusClassificacao.APROVADA, origem=OrigemClassificacao.HUMANA
    )
    d_manter = abrir_divergencia(repos, q_manter, tax, execucao, v_manter)
    d_aceitar = abrir_divergencia(repos, q_aceitar, tax, execucao, v_aceitar, candidata="redes")

    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        # divergência de outra questão no path -> 404; inexistente -> 404; resolução inválida -> 422
        assert (
            client.post(
                f"/api/v1/questoes/{q_aceitar.id}/divergencias/{d_manter.id}/resolver",
                json={"resolucao": "manter_humana"},
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/v1/questoes/{q_manter.id}/divergencias/{uuid4()}/resolver", json={"resolucao": "manter_humana"}
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/v1/questoes/{uuid4()}/divergencias/{d_manter.id}/resolver", json={"resolucao": "manter_humana"}
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/v1/questoes/{q_manter.id}/divergencias/{d_manter.id}/resolver", json={"resolucao": "descartar"}
            ).status_code
            == 422
        )
        # classificação extra só é aceita em editar_manualmente; editar_manualmente sem classificação -> 422
        assert (
            client.post(
                f"/api/v1/questoes/{q_manter.id}/divergencias/{d_manter.id}/resolver",
                json={"resolucao": "manter_humana", "classificacao": {"disciplina_principal": "redes"}},
            ).status_code
            == 422
        )
        assert (
            client.post(
                f"/api/v1/questoes/{q_manter.id}/divergencias/{d_manter.id}/resolver",
                json={"resolucao": "editar_manualmente"},
            ).status_code
            == 422
        )
        assert _divergencia_status(repos, d_manter.id) == "aberta"

        total_antes = contar(repos, ClassificacaoModel)
        resp = client.post(
            f"/api/v1/questoes/{q_manter.id}/divergencias/{d_manter.id}/resolver", json={"resolucao": "manter_humana"}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["divergencia"]["status"] == "resolvida"
        assert resp.json()["divergencia"]["resolucao"] == "manter_humana"
        assert resp.json()["divergencia"]["resolvida_em"] is not None
        assert resp.json()["classificacao_vigente"]["id"] == str(v_manter.id)
        assert contar(repos, ClassificacaoModel) == total_antes

        # segunda resolução da mesma divergência -> 409
        assert (
            client.post(
                f"/api/v1/questoes/{q_manter.id}/divergencias/{d_manter.id}/resolver",
                json={"resolucao": "manter_humana"},
            ).status_code
            == 409
        )

        resp = client.post(
            f"/api/v1/questoes/{q_aceitar.id}/divergencias/{d_aceitar.id}/resolver",
            json={"resolucao": "aceitar_candidata"},
        )
        assert resp.status_code == 200, resp.text
        vigente = resp.json()["classificacao_vigente"]
        assert vigente["id"] != str(v_aceitar.id)
        assert vigente["disciplina_principal"] == "redes"
        assert vigente["origem"] == "automatica"
        assert vigente["status"] == "aprovada"
        assert vigente["substitui_classificacao_id"] == str(v_aceitar.id)
        assert contar(repos, ClassificacaoModel) == total_antes + 1
        antiga = repos.classificacoes.buscar_por_id(v_aceitar.id)
        assert antiga is not None
        assert antiga.vigente is False


def test_resolver_editar_manualmente_cria_humana_e_fecha_divergencia(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos, tax, execucao, prova = _preparar(session_factory_teste)
    questao = criar_questao(repos, prova, 10, "Questão cuja divergência será resolvida por edição manual.")
    vigente = classificar(
        repos, questao, tax, "algoritmos", status=StatusClassificacao.APROVADA, origem=OrigemClassificacao.HUMANA
    )
    div = abrir_divergencia(repos, questao, tax, execucao, vigente)
    total_antes = contar(repos, ClassificacaoModel)

    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        resp = client.post(
            f"/api/v1/questoes/{questao.id}/divergencias/{div.id}/resolver",
            json={
                "resolucao": "editar_manualmente",
                "classificacao": {
                    "disciplina_principal": "redes",
                    "disciplinas_secundarias": ["sistemas-operacionais"],
                    "topicos": ["Roteamento OSPF"],
                    "justificativa": "Decisão do revisor.",
                },
            },
        )
        assert resp.status_code == 200, resp.text
        corpo = resp.json()
        assert corpo["divergencia"]["status"] == "resolvida"
        assert corpo["divergencia"]["resolucao"] == "editar_manualmente"
        nova = corpo["classificacao_vigente"]
        assert nova["origem"] == "humana"
        assert nova["status"] == "aprovada"
        assert nova["vigente"] is True
        assert nova["substitui_classificacao_id"] == str(vigente.id)
        assert nova["disciplina_principal"] == "redes"
        assert nova["topicos"] == ["roteamento-ospf"]
        assert contar(repos, ClassificacaoModel) == total_antes + 1
        assert _divergencia_status(repos, div.id) == StatusDivergencia.RESOLVIDA.value
        antiga = repos.classificacoes.buscar_por_id(vigente.id)
        assert antiga is not None
        assert antiga.vigente is False
        assert antiga.disciplina_principal == "algoritmos"


def test_resolver_editar_manualmente_validacao_invalida_nao_altera_nada(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos, tax, execucao, prova = _preparar(session_factory_teste)
    questao = criar_questao(repos, prova, 10, "Questão cuja edição manual inválida deve ser rejeitada.")
    vigente = classificar(
        repos, questao, tax, "algoritmos", status=StatusClassificacao.APROVADA, origem=OrigemClassificacao.HUMANA
    )
    div = abrir_divergencia(repos, questao, tax, execucao, vigente)
    total_antes = contar(repos, ClassificacaoModel)

    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        for classificacao in (
            {"disciplina_principal": "legada"},
            {"disciplina_principal": "redes", "disciplinas_secundarias": ["redes"]},
        ):
            resp = client.post(
                f"/api/v1/questoes/{questao.id}/divergencias/{div.id}/resolver",
                json={"resolucao": "editar_manualmente", "classificacao": classificacao},
            )
            assert resp.status_code == 422, resp.text
    assert _divergencia_status(repos, div.id) == "aberta"
    assert contar(repos, ClassificacaoModel) == total_antes
    atual = repos.classificacoes.buscar_vigente(questao.id, tax.id)
    assert atual is not None
    assert atual.id == vigente.id


def test_resolver_editar_manualmente_falha_dentro_da_transacao_faz_rollback_completo(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falha real após o UPDATE vigente=false e dentro de `resolver_atomicamente` desfaz toda a transação."""
    repos, tax, execucao, prova = _preparar(session_factory_teste)
    questao = criar_questao(repos, prova, 10, "Questão cuja transação de resolução vai falhar no meio.")
    vigente = classificar(
        repos, questao, tax, "algoritmos", status=StatusClassificacao.APROVADA, origem=OrigemClassificacao.HUMANA
    )
    div = abrir_divergencia(repos, questao, tax, execucao, vigente)
    total_antes = contar(repos, ClassificacaoModel)

    original_add = Session.add
    vigentes_no_momento_da_falha: list[int] = []

    def add_com_falha(self: Session, instance: object, *args: object, **kwargs: object) -> None:
        if isinstance(instance, ClassificacaoModel):
            # neste ponto o UPDATE vigente=false da anterior já foi emitido (flush) na mesma transação
            vigentes_no_momento_da_falha.append(
                self.scalar(
                    select(func.count()).select_from(ClassificacaoModel).where(ClassificacaoModel.vigente.is_(True))
                )
                or 0
            )
            raise RuntimeError("falha simulada no INSERT da nova classificação")
        original_add(self, instance, *args, **kwargs)

    monkeypatch.setattr(Session, "add", add_com_falha)
    with TestClient(criar_app(db_teste_url, tmp_path), raise_server_exceptions=False) as client:
        resp = client.post(
            f"/api/v1/questoes/{questao.id}/divergencias/{div.id}/resolver",
            json={"resolucao": "editar_manualmente", "classificacao": {"disciplina_principal": "redes"}},
        )
    monkeypatch.undo()

    assert resp.status_code == 500, resp.text
    # a falha ocorreu depois do UPDATE vigente=false, dentro da transação (nenhuma vigente visível nela)
    assert vigentes_no_momento_da_falha == [0]
    assert _divergencia_status(repos, div.id) == "aberta"
    assert contar(repos, ClassificacaoModel) == total_antes
    atual = repos.classificacoes.buscar_vigente(questao.id, tax.id)
    assert atual is not None
    assert atual.id == vigente.id
    assert atual.vigente is True
    assert atual.disciplina_principal == "algoritmos"
