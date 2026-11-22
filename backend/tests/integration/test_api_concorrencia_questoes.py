"""Concorrência sobre Questões e Classificações: recálculo de prioridade e lock otimista por versão."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from application.exceptions import ConflitoRecursoError
from application.questoes import (
    recalcular_revisao_prioritaria_pendentes,
)
from domain.classificacao import Classificacao, criar_classificacao_humana
from domain.enums import (
    CodigoAlertaExtracao,
    ResolucaoDivergencia,
    StatusClassificacao,
)
from infrastructure.persistence.models import ClassificacaoModel
from infrastructure.storage.local import ArmazenamentoArquivosLocal
from tests.integration._apoio_questoes import (
    ENUNCIADO_BOM,
    RepoComGancho,
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
    png_bytes,
)

# ---------------------------------------------------------------------------
# Recálculo de prioridade não reverte aprovação concorrente
# ---------------------------------------------------------------------------


def test_recalculo_de_prioridade_nao_reverte_aprovacao_concorrente(
    db_teste_url: str, session_factory_teste: sessionmaker[Session]
) -> None:
    repos = criar_repos(session_factory_teste)
    tax = criar_taxonomia(repos)
    questao = criar_questao(repos, criar_prova(repos, 2023), 10, ENUNCIADO_BOM)
    # confiança alta e sem alertas: o recálculo quer derrubar a prioridade (True -> False)
    ia = classificar(repos, questao, tax, "redes", confianca=0.9, prioritaria=True)

    def aprovar_concorrentemente() -> None:
        vigente = repos.classificacoes.buscar_vigente(questao.id, tax.id)
        assert vigente is not None
        from datetime import UTC, datetime

        vigente.aprovar(datetime.now(UTC))
        repos.classificacoes.salvar(vigente)

    proxy = RepoComGancho(repos.classificacoes, "listar_vigentes_por_questao", aprovar_concorrentemente)
    recalcular_revisao_prioritaria_pendentes(questao, proxy)  # type: ignore[arg-type]

    final = repos.classificacoes.buscar_por_id(ia.id)
    assert final is not None
    assert final.status == StatusClassificacao.APROVADA
    assert final.revisada_em is not None
    # a prioridade persistida da aprovada não é tocada
    assert final.revisao_prioritaria is True


def test_recalculo_atualiza_apenas_a_coluna_de_prioridade_quando_ainda_pendente(
    db_teste_url: str, session_factory_teste: sessionmaker[Session]
) -> None:
    repos = criar_repos(session_factory_teste)
    tax = criar_taxonomia(repos)
    questao = criar_questao(repos, criar_prova(repos, 2023), 10, ENUNCIADO_BOM)
    ia = classificar(repos, questao, tax, "redes", confianca=0.9, prioritaria=True)
    assert recalcular_revisao_prioritaria_pendentes(questao, repos.classificacoes) == 1
    atual = repos.classificacoes.buscar_por_id(ia.id)
    assert atual is not None
    assert atual.revisao_prioritaria is False
    assert atual.status == StatusClassificacao.PENDENTE_REVISAO
    assert repos.classificacoes.atualizar_revisao_prioritaria(ia.id, False) is False  # sem mudança


# ---------------------------------------------------------------------------
# Lock otimista na Questão
# ---------------------------------------------------------------------------


def test_repositorio_rejeita_salvar_questao_lida_antes_de_alteracao_concorrente(
    db_teste_url: str, session_factory_teste: sessionmaker[Session]
) -> None:
    repos = criar_repos(session_factory_teste)
    questao = criar_questao(repos, criar_prova(repos, 2023), 10, ENUNCIADO_BOM)
    assert questao.versao == 1

    lida_a = repos.questoes.buscar_por_id(questao.id)
    lida_b = repos.questoes.buscar_por_id(questao.id)
    assert lida_a is not None and lida_b is not None
    assert (lida_a.versao, lida_b.versao) == (1, 1)

    lida_a.enunciado = "Enunciado vencedor gravado primeiro pelo outro revisor."
    salva_a = repos.questoes.salvar(lida_a)
    assert salva_a.versao == 2

    lida_b.enunciado = "Enunciado perdedor que sobrescreveria o anterior sem lock."
    with pytest.raises(ConflitoRecursoError):
        repos.questoes.salvar(lida_b)

    final = repos.questoes.buscar_por_id(questao.id)
    assert final is not None
    assert final.enunciado == "Enunciado vencedor gravado primeiro pelo outro revisor."
    assert final.versao == 2


def test_patch_enunciado_com_escrita_concorrente_entre_leitura_e_gravacao_retorna_409(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos = criar_repos(session_factory_teste)
    questao = criar_questao(repos, criar_prova(repos, 2023), 10, ENUNCIADO_BOM)
    app = criar_app(db_teste_url, tmp_path)
    use_case = app.state.editar_questao_use_case

    def outro_revisor_edita() -> None:
        outra = repos.questoes.buscar_por_id(questao.id)
        assert outra is not None
        outra.enunciado = "Enunciado do outro revisor, gravado entre a leitura e a gravação."
        repos.questoes.salvar(outra)

    use_case._repo_questoes = RepoComGancho(use_case._repo_questoes, "buscar_por_id", outro_revisor_edita)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.patch(
            f"/api/v1/questoes/{questao.id}", json={"enunciado": "Enunciado do primeiro revisor, mais antigo."}
        )
        assert resp.status_code == 409, resp.text
    final = repos.questoes.buscar_por_id(questao.id)
    assert final is not None
    assert final.enunciado == "Enunciado do outro revisor, gravado entre a leitura e a gravação."


def test_patch_questao_com_versao_antiga_retorna_409_e_versao_atual_funciona(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos = criar_repos(session_factory_teste)
    questao = criar_questao(repos, criar_prova(repos, 2023), 10, ENUNCIADO_BOM)
    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        url = f"/api/v1/questoes/{questao.id}"
        detalhe = client.get(url).json()
        assert detalhe["versao"] == 1

        resp = client.patch(url, json={"enunciado": "Primeira edição válida do enunciado.", "versao": 1})
        assert resp.status_code == 200, resp.text
        assert resp.json()["versao"] == 2

        resp = client.patch(url, json={"enunciado": "Edição com versão velha que deve ser barrada.", "versao": 1})
        assert resp.status_code == 409, resp.text
        assert client.get(url).json()["enunciado"] == "Primeira edição válida do enunciado."

        resp = client.patch(url, json={"enunciado": "Edição com versão zero é inválida.", "versao": 0})
        assert resp.status_code == 422
        resp = client.patch(url, json={"enunciado": "Edição com a versão corrente.", "versao": 2})
        assert resp.status_code == 200, resp.text


def test_alerta_e_ativo_com_escrita_concorrente_retornam_409(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos = criar_repos(session_factory_teste)
    prova = criar_prova(repos, 2023)
    questao = criar_questao(repos, prova, 10, ENUNCIADO_BOM, alertas=(CodigoAlertaExtracao.PDF_VIA_OCR,))
    armazenamento = ArmazenamentoArquivosLocal(tmp_path / "dados")
    app = criar_app(db_teste_url, tmp_path / "app", armazenamento)

    def outro_revisor_edita() -> None:
        outra = repos.questoes.buscar_por_id(questao.id)
        assert outra is not None
        outra.enunciado = "Enunciado concorrente que não pode ser sobrescrito por ninguém."
        repos.questoes.salvar(outra)

    alerta_id = questao.alertas_extracao[0].id
    resolver = app.state.resolver_alerta_use_case
    resolver._repo_questoes = RepoComGancho(resolver._repo_questoes, "buscar_por_id", outro_revisor_edita)
    adicionar = app.state.adicionar_ativo_visual_use_case
    gancho_ativo = RepoComGancho(adicionar._repo_questoes, "buscar_por_id", lambda: None)
    adicionar._repo_questoes = gancho_ativo

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.patch(f"/api/v1/questoes/{questao.id}/alertas/{alerta_id}", json={"status": "resolvido"})
        assert resp.status_code == 409, resp.text
        intermediaria = repos.questoes.buscar_por_id(questao.id)
        assert intermediaria is not None
        assert intermediaria.alertas_extracao[0].status.value == "aberto"
        assert intermediaria.enunciado.startswith("Enunciado concorrente")

        # POST de ativo: a leitura ocorre, outro revisor grava, o salvar falha com 409 e não deixa arquivo órfão
        gancho_ativo._gancho = outro_revisor_edita
        gancho_ativo._disparado = False
        resp = client.post(
            f"/api/v1/questoes/{questao.id}/ativos-visuais", files={"arquivo": ("a.png", png_bytes(), "image/png")}
        )
        assert resp.status_code == 409, resp.text
    arquivos = [p for p in (tmp_path / "dados").rglob("*") if p.is_file()]
    assert arquivos == []
    assert repos.questoes.buscar_por_id(questao.id).ativos_visuais == []  # type: ignore[union-attr]


def test_reprocessamento_e_salvar_lote_preservam_versao_e_funcionam_com_lock(
    db_teste_url: str, session_factory_teste: sessionmaker[Session]
) -> None:
    repos = criar_repos(session_factory_teste)
    questao = criar_questao(repos, criar_prova(repos, 2023), 10, ENUNCIADO_BOM)
    atuais = repos.questoes.listar_por_prova(questao.prova_id)
    repos.questoes.salvar_lote(atuais)
    assert repos.questoes.buscar_por_id(questao.id).versao == 2  # type: ignore[union-attr]
    # nova leitura -> novo lote funciona; lote com cópia velha conflita
    repos.questoes.salvar_lote(repos.questoes.listar_por_prova(questao.prova_id))
    with pytest.raises(ConflitoRecursoError):
        repos.questoes.salvar_lote(atuais)


# ---------------------------------------------------------------------------
# Aprovar concorrente com corrigir / resolver: 409 sem regravar a linha antiga
# ---------------------------------------------------------------------------


def _corrigir_pelo_repositorio(repos: Repos, ia: Classificacao) -> Classificacao:
    nova = criar_classificacao_humana(
        questao_id=ia.questao_id,
        taxonomia_id=ia.taxonomia_id,
        disciplina_principal="algoritmos",
        topicos=("grafos",),
        justificativa="Correção concorrente.",
        agora=datetime.now(UTC),
        substitui_classificacao_id=ia.id,
    )
    return repos.classificacoes.registrar_substituicao(ia, nova)


@pytest.mark.parametrize("concorrente", ["corrigir", "aceitar_candidata"])
def test_aprovar_com_vigente_trocada_entre_leitura_e_gravacao_retorna_409(
    concorrente: str, db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos = criar_repos(session_factory_teste)
    tax = criar_taxonomia(repos)
    questao = criar_questao(repos, criar_prova(repos, 2023), 10, ENUNCIADO_BOM)
    ia = classificar(repos, questao, tax, "redes", confianca=0.9)
    divergencia = abrir_divergencia(repos, questao, tax, criar_execucao(repos, tax), ia, candidata="algoritmos")
    app = criar_app(db_teste_url, tmp_path)
    use_case = app.state.aprovar_classificacao_use_case
    trocas: list[Classificacao] = []

    def vigente_trocada() -> None:
        if concorrente == "corrigir":
            trocas.append(_corrigir_pelo_repositorio(repos, ia))
        else:
            repos.divergencias.resolver_atomicamente(
                divergencia.id, ResolucaoDivergencia.ACEITAR_CANDIDATA, datetime.now(UTC)
            )
            trocas.append(repos.classificacoes.buscar_vigente(questao.id, tax.id))  # type: ignore[arg-type]

    use_case._repo_classificacoes = RepoComGancho(use_case._repo_classificacoes, "buscar_vigente", vigente_trocada)
    total_antes = contar(repos, ClassificacaoModel)
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(f"/api/v1/questoes/{questao.id}/classificacoes/{tax.id}/aprovar")
    assert resp.status_code == 409, resp.text

    nova = trocas[0]
    vigente = repos.classificacoes.buscar_vigente(questao.id, tax.id)
    assert vigente is not None and vigente.id == nova.id and vigente.id != ia.id
    assert vigente.disciplina_principal == "algoritmos"
    assert contar(repos, ClassificacaoModel) == total_antes + 1  # só a substituta; nada foi regravado
    antiga = repos.classificacoes.buscar_por_id(ia.id)
    assert antiga is not None
    assert antiga.vigente is False
    assert antiga.status == StatusClassificacao.PENDENTE_REVISAO
    assert antiga.revisada_em is None
    assert antiga.disciplina_principal == "redes"
    assert antiga.confianca == 0.9
