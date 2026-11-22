"""Complementos de API de Questões: moldura da consulta, edição de alertas e mídia e aprovação."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from domain.enums import (
    LetraAlternativa,
    OrigemAtivoVisual,
    SituacaoGabarito,
)
from domain.prova import AtivoVisual, Gabarito, Prova
from infrastructure.persistence.models import ClassificacaoModel
from infrastructure.storage.local import ArmazenamentoArquivosLocal
from tests.integration._apoio_questoes import (
    ENUNCIADO_BOM,
    alternativas_completas,
    classificar,
    criar_app,
    criar_prova,
    criar_questao,
    criar_repos,
    criar_taxonomia,
    png_bytes,
)

# ---------------------------------------------------------------------------
# Disciplina arquivada e consulta
# ---------------------------------------------------------------------------


def test_listar_com_disciplina_arquivada_usa_predicado_compartilhado(
    db_teste_url: str, session_factory_teste: sessionmaker[Session]
) -> None:
    repos = criar_repos(session_factory_teste)
    tax = criar_taxonomia(repos)
    prova = criar_prova(repos, 2023)
    q_arq = criar_questao(repos, prova, 1, ENUNCIADO_BOM)
    q_sec = criar_questao(repos, prova, 2, ENUNCIADO_BOM)
    q_ok = criar_questao(repos, prova, 3, ENUNCIADO_BOM)
    classificar(repos, q_arq, tax, "legada")
    classificar(repos, q_sec, tax, "redes", secundarias=("legada",))
    classificar(repos, q_ok, tax, "redes")
    achadas = {q.id for q in repos.questoes.listar_com_disciplina_arquivada(tax.id)}
    assert achadas == {q_arq.id, q_sec.id}


# ---------------------------------------------------------------------------
# Edição, mídia, consulta e aprovação
# ---------------------------------------------------------------------------


def test_patch_questao_abre_e_fecha_enunciado_suspeito_e_gabarito_ausente(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos = criar_repos(session_factory_teste)
    prova = repos.provas.salvar(
        Prova(exame="ENADE", curso="Engenharia de Computação", ano=2023, caminho_gabarito="provas/x/gabarito.pdf")
    )
    questao = criar_questao(repos, prova, 10, ENUNCIADO_BOM, gabarito=Gabarito(SituacaoGabarito.PENDENTE))
    assert questao.alertas_extracao == []

    def alertas(corpo: dict[str, Any]) -> dict[str, str]:
        return {a["codigo"]: a["status"] for a in corpo["alertas_extracao"]}

    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        url = f"/api/v1/questoes/{questao.id}"
        resp = client.patch(url, json={"enunciado": "x y ?"})
        assert resp.status_code == 200, resp.text
        estado = alertas(resp.json())
        assert estado["enunciado_suspeito"] == "aberto"
        assert estado["gabarito_ausente_na_prova"] == "aberto"

        resp = client.patch(url, json={"enunciado": ENUNCIADO_BOM})
        assert alertas(resp.json())["enunciado_suspeito"] == "resolvido"
        assert alertas(resp.json())["gabarito_ausente_na_prova"] == "aberto"

        resp = client.patch(url, json={"gabarito": {"situacao_gabarito": "valida", "alternativa_correta": "C"}})
        assert resp.status_code == 200, resp.text
        final = alertas(resp.json())
        assert final["gabarito_ausente_na_prova"] == "resolvido"
        assert final["enunciado_suspeito"] == "resolvido"


def test_patch_ativo_marca_questao_como_editada(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos = criar_repos(session_factory_teste)
    prova = criar_prova(repos, 2023)
    questao = criar_questao(repos, prova, 10, ENUNCIADO_BOM)
    armazenamento = ArmazenamentoArquivosLocal(tmp_path / "dados")
    ativo = AtivoVisual(origem=OrigemAtivoVisual.PICTURE_DOCLING, ordem=0, pagina=1)
    ativo.chave_arquivo = f"provas/{prova.id}/ativos/{ativo.id}.png"
    armazenamento.salvar(ativo.chave_arquivo, png_bytes())
    salva = repos.questoes.buscar_por_id(questao.id)
    assert salva is not None
    salva.ativos_visuais.append(ativo)
    repos.questoes.salvar(salva)
    assert repos.questoes.buscar_por_id(questao.id).editada_manualmente is False  # type: ignore[union-attr]

    with TestClient(criar_app(db_teste_url, tmp_path / "app", armazenamento)) as client:
        resp = client.patch(f"/api/v1/ativos-visuais/{ativo.id}", data={"ordem": "3"})
        assert resp.status_code == 200, resp.text
        assert client.get(f"/api/v1/questoes/{questao.id}").json()["editada_manualmente"] is True


def test_consulta_com_q_ordena_por_relevancia_antes_de_ano_e_numero(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos = criar_repos(session_factory_teste)
    recente = criar_prova(repos, 2023)
    antiga = criar_prova(repos, 2019)
    alts = alternativas_completas()
    alts[1] = type(alts[1])(letra=LetraAlternativa.B, texto="Configure o protocolo OSPF na interface de borda.")
    so_alternativa = criar_questao(
        repos, recente, 1, "Descreva a convergência de rotas em uma rede corporativa extensa.", alternativas=alts
    )
    no_enunciado = criar_questao(
        repos, antiga, 9, "Explique o funcionamento do protocolo OSPF em redes de grande porte."
    )
    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        itens = client.get("/api/v1/questoes", params={"q": "OSPF"}).json()["itens"]
        # sem relevância, (2023, 1) viria antes de (2019, 9); com peso A do enunciado a ordem inverte
        assert [i["id"] for i in itens] == [str(no_enunciado.id), str(so_alternativa.id)]


def test_aprovar_nao_altera_revisao_prioritaria_persistida(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos = criar_repos(session_factory_teste)
    tax = criar_taxonomia(repos)
    questao = criar_questao(repos, criar_prova(repos, 2023), 10, ENUNCIADO_BOM)
    ia = classificar(repos, questao, tax, "redes", confianca=0.3, prioritaria=True)
    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        resp = client.post(f"/api/v1/questoes/{questao.id}/classificacoes/{tax.id}/aprovar")
        assert resp.status_code == 200, resp.text
    with session_factory_teste() as session:
        linha = session.scalar(select(ClassificacaoModel).where(ClassificacaoModel.id == ia.id))
        assert linha is not None
        assert linha.status == "aprovada"
        assert linha.revisao_prioritaria is True
