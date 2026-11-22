"""Entradas textuais da API de Questões: surrogates isolados e limites de tamanho/quantidade viram 422."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from infrastructure.persistence.models import ClassificacaoModel
from tests.integration._apoio_questoes import (
    ENUNCIADO_BOM,
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

JSON_CT = {"content-type": "application/json"}
SURROGATE_CRU = b"\xed\xa0\x80"  # U+D800 codificado "à força" em UTF-8: inválido, mas decodificável com surrogatepass


def _corpo(parcial: dict[str, Any]) -> bytes:
    """Serializa preservando surrogates como escapes JSON (`\\ud800`)."""
    return json.dumps(parcial, ensure_ascii=True).encode("ascii")


_CORRECAO = {"disciplina_principal": "redes", "disciplinas_secundarias": [], "topicos": [], "justificativa": "ok"}

CASOS_QUESTAO = {
    "enunciado-d800": {"enunciado": "ab\ud800cd"},
    "enunciado-dc00-no-inicio": {"enunciado": "\udc00 inicio"},
    "alternativa-dfff": {"alternativas": [{"letra": "A", "texto": "texto \udfff"}]},
}
CASOS_CORRECAO = {
    "justificativa-d800": {"justificativa": "x\ud800y"},
    "justificativa-dc00-no-fim": {"justificativa": "fim\udc00"},
    "secundaria": {"disciplinas_secundarias": ["algo\ud800ritmos"]},
    "topico": {"topicos": ["t\ud800x"]},
    "principal": {"disciplina_principal": "re\ud800des"},
}


def _montar(session_factory: sessionmaker[Session]) -> tuple[Repos, Any, Any, Any, Any, Any]:
    repos = criar_repos(session_factory)
    tax = criar_taxonomia(repos)
    prova = criar_prova(repos, 2023)
    q_corrigir = criar_questao(repos, prova, 10, ENUNCIADO_BOM)
    classificar(repos, q_corrigir, tax, "algoritmos")
    q_resolver = criar_questao(repos, prova, 11, ENUNCIADO_BOM)
    vigente = classificar(repos, q_resolver, tax, "algoritmos")
    divergencia = abrir_divergencia(repos, q_resolver, tax, criar_execucao(repos, tax), vigente)
    return repos, tax, q_corrigir, q_resolver, divergencia, vigente


def _nada_persistido(repos: Repos, total_antes: int, divergencia: Any, questao: Any) -> None:
    assert contar(repos, ClassificacaoModel) == total_antes
    assert repos.divergencias.buscar_por_id(divergencia.id).status.value == "aberta"  # type: ignore[union-attr]
    salva = repos.questoes.buscar_por_id(questao.id)
    assert salva is not None
    assert salva.enunciado == ENUNCIADO_BOM
    assert salva.versao == questao.versao


@pytest.mark.parametrize("alteracao", CASOS_QUESTAO.values(), ids=CASOS_QUESTAO.keys())
def test_patch_questao_com_surrogate_isolado_retorna_422_sem_alterar(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path, alteracao: dict[str, Any]
) -> None:
    repos, _, q_corrigir, _, divergencia, _ = _montar(session_factory_teste)
    total_antes = contar(repos, ClassificacaoModel)
    with TestClient(criar_app(db_teste_url, tmp_path), raise_server_exceptions=False) as client:
        resp = client.patch(f"/api/v1/questoes/{q_corrigir.id}", content=_corpo(alteracao), headers=JSON_CT)
        assert resp.status_code == 422, resp.text
    _nada_persistido(repos, total_antes, divergencia, q_corrigir)


def test_patch_questao_com_bytes_utf8_de_surrogate_cru_retorna_422_sem_alterar(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos, _, q_corrigir, _, divergencia, _ = _montar(session_factory_teste)
    total_antes = contar(repos, ClassificacaoModel)
    crus = {
        "enunciado": b'{"enunciado": "ab' + SURROGATE_CRU + b'cd"}',
        "alternativa": b'{"alternativas": [{"letra": "A", "texto": "x' + SURROGATE_CRU + b'"}]}',
    }
    with TestClient(criar_app(db_teste_url, tmp_path), raise_server_exceptions=False) as client:
        for corpo in crus.values():
            resp = client.patch(f"/api/v1/questoes/{q_corrigir.id}", content=corpo, headers=JSON_CT)
            assert resp.status_code in (400, 422), resp.text  # nunca 500 nem aceito
    _nada_persistido(repos, total_antes, divergencia, q_corrigir)


@pytest.mark.parametrize("alteracao", CASOS_CORRECAO.values(), ids=CASOS_CORRECAO.keys())
def test_corrigir_e_resolver_com_surrogate_isolado_retornam_422_sem_persistir(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path, alteracao: dict[str, Any]
) -> None:
    repos, tax, q_corrigir, q_resolver, divergencia, _ = _montar(session_factory_teste)
    total_antes = contar(repos, ClassificacaoModel)
    corpo = {**_CORRECAO, **alteracao}
    with TestClient(criar_app(db_teste_url, tmp_path), raise_server_exceptions=False) as client:
        resp = client.post(
            f"/api/v1/questoes/{q_corrigir.id}/classificacoes/{tax.id}/corrigir", content=_corpo(corpo), headers=JSON_CT
        )
        assert resp.status_code == 422, resp.text
        resp = client.post(
            f"/api/v1/questoes/{q_resolver.id}/divergencias/{divergencia.id}/resolver",
            content=_corpo({"resolucao": "editar_manualmente", "classificacao": corpo}),
            headers=JSON_CT,
        )
        assert resp.status_code == 422, resp.text
    _nada_persistido(repos, total_antes, divergencia, q_corrigir)


def test_corrigir_com_justificativa_em_bytes_utf8_de_surrogate_cru_nao_retorna_500(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos, tax, q_corrigir, _, divergencia, _ = _montar(session_factory_teste)
    total_antes = contar(repos, ClassificacaoModel)
    corpo = b'{"disciplina_principal": "redes", "justificativa": "x' + SURROGATE_CRU + b'y"}'
    with TestClient(criar_app(db_teste_url, tmp_path), raise_server_exceptions=False) as client:
        resp = client.post(
            f"/api/v1/questoes/{q_corrigir.id}/classificacoes/{tax.id}/corrigir", content=corpo, headers=JSON_CT
        )
    assert resp.status_code in (400, 422), resp.text
    _nada_persistido(repos, total_antes, divergencia, q_corrigir)


def test_mensagem_de_dominio_nao_ecoa_surrogate_e_nao_quebra_o_handler(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    """Defesa em profundidade: mesmo que um valor com surrogate chegue ao caso de uso, a resposta é 422 serializável."""
    from application.revisao import _validar_codigos_ativos
    from domain.exceptions import ErroValidacaoDominio

    repos = criar_repos(session_factory_teste)
    tax = criar_taxonomia(repos)
    with pytest.raises(ErroValidacaoDominio) as erro:
        _validar_codigos_ativos(tax, ["algo\ud800"])
    str(erro.value).encode("utf-8")  # não levanta UnicodeEncodeError


# ---------------------------------------------------------------------------
# Limites de quantidade e de tamanho: 422 rápido, sem processamento quadrático
# ---------------------------------------------------------------------------


def test_corrigir_rejeita_mais_de_20_topicos_e_100_mil_topicos_rapidamente(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos, tax, q_corrigir, _, divergencia, _ = _montar(session_factory_teste)
    total_antes = contar(repos, ClassificacaoModel)
    url = f"/api/v1/questoes/{q_corrigir.id}/classificacoes/{tax.id}/corrigir"
    with TestClient(criar_app(db_teste_url, tmp_path), raise_server_exceptions=False) as client:
        resp = client.post(url, json={**_CORRECAO, "topicos": [f"topico-{i}" for i in range(21)]})
        assert resp.status_code == 422, resp.text
        enorme = {**_CORRECAO, "topicos": [f"t{i}" for i in range(100_000)]}
        inicio = time.monotonic()
        resp = client.post(url, json=enorme)
        duracao = time.monotonic() - inicio
        assert resp.status_code == 422, resp.text[:200]
        assert duracao < 2.0, duracao
        resp = client.post(url, json={**_CORRECAO, "topicos": [f"topico-{i}" for i in range(20)]})
        assert resp.status_code == 201, resp.text
    assert contar(repos, ClassificacaoModel) == total_antes + 1
    assert repos.divergencias.buscar_por_id(divergencia.id).status.value == "aberta"  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "alteracao",
    [
        {"disciplinas_secundarias": ["algoritmos", "sistemas-operacionais", "redes"]},
        {"disciplinas_secundarias": ["a"] * 100_000},
        {"topicos": ["x" * 201]},
        {"justificativa": "j" * 5_001},
        {"disciplina_principal": "d" * 201},
    ],
    ids=["tres-secundarias", "cem-mil-secundarias", "topico-longo", "justificativa-longa", "principal-longa"],
)
def test_corrigir_e_resolver_rejeitam_limites_de_tamanho(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path, alteracao: dict[str, Any]
) -> None:
    repos, tax, q_corrigir, q_resolver, divergencia, _ = _montar(session_factory_teste)
    total_antes = contar(repos, ClassificacaoModel)
    corpo = {**_CORRECAO, **alteracao}
    with TestClient(criar_app(db_teste_url, tmp_path), raise_server_exceptions=False) as client:
        inicio = time.monotonic()
        resp = client.post(f"/api/v1/questoes/{q_corrigir.id}/classificacoes/{tax.id}/corrigir", json=corpo)
        assert resp.status_code == 422, resp.text[:200]
        resp = client.post(
            f"/api/v1/questoes/{q_resolver.id}/divergencias/{divergencia.id}/resolver",
            json={"resolucao": "editar_manualmente", "classificacao": corpo},
        )
        assert resp.status_code == 422, resp.text[:200]
        assert time.monotonic() - inicio < 2.0
    _nada_persistido(repos, total_antes, divergencia, q_corrigir)


@pytest.mark.parametrize(
    "alteracao",
    [
        {"enunciado": "e" * 20_001},
        {"alternativas": [{"letra": "A", "texto": "t" * 5_001}]},
        {"alternativas": [{"letra": "A", "texto": "a"}] * 6},
        {"alternativas": [{"letra": "A", "texto": "a"}] * 100_000},
    ],
    ids=["enunciado-longo", "alternativa-longa", "seis-alternativas", "cem-mil-alternativas"],
)
def test_patch_questao_rejeita_limites_de_tamanho_e_quantidade(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path, alteracao: dict[str, Any]
) -> None:
    repos, _, q_corrigir, _, divergencia, _ = _montar(session_factory_teste)
    total_antes = contar(repos, ClassificacaoModel)
    with TestClient(criar_app(db_teste_url, tmp_path), raise_server_exceptions=False) as client:
        inicio = time.monotonic()
        resp = client.patch(f"/api/v1/questoes/{q_corrigir.id}", json=alteracao)
        assert resp.status_code == 422, resp.text[:200]
        assert time.monotonic() - inicio < 2.0
        # nos limites exatos a edição é aceita
        resp = client.patch(f"/api/v1/questoes/{q_corrigir.id}", json={"enunciado": "e" * 20_000})
        assert resp.status_code == 200, resp.text[:200]
    assert contar(repos, ClassificacaoModel) == total_antes
    assert repos.divergencias.buscar_por_id(divergencia.id).status.value == "aberta"  # type: ignore[union-attr]
