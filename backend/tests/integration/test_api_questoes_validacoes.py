"""Validações de entrada das rotas de Questões e Ativos Visuais."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from starlette.datastructures import UploadFile

from application.questoes import (
    TAMANHO_MAXIMO_IMAGEM_BYTES,
)
from domain.enums import (
    LetraAlternativa,
    OrigemAtivoVisual,
)
from domain.exceptions import ErroValidacaoDominio
from domain.prova import AtivoVisual
from infrastructure.persistence.models import ClassificacaoModel
from infrastructure.storage.local import ArmazenamentoArquivosLocal
from tests.integration._apoio_questoes import (
    ENUNCIADO_BOM,
    abrir_divergencia,
    alternativas_completas,
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
# Listagem: entradas inválidas nunca resultam em 500
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "params",
    [
        {"q": "\x00"},
        {"q": "abc\x00def"},
        {"topico": "a\x00b", "com_taxonomia": "1"},
        {"ano": "99999999999999999999"},
        {"ano": "1899"},
        {"ano": "2101"},
        {"ano": "0"},
        {"pagina": str(10**20)},
        {"pagina": str(2**63 - 1)},
        {"pagina": "100001"},
    ],
)
def test_listagem_entradas_extremas_retornam_422_e_nao_500(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path, params: dict[str, str]
) -> None:
    taxonomia = criar_taxonomia(criar_repos(session_factory_teste))
    consulta = {k: v for k, v in params.items() if k != "com_taxonomia"}
    if "com_taxonomia" in params:
        # com `taxonomia_id` válido, o 422 só pode vir da regra de NUL (e não da dependência de taxonomia)
        consulta["taxonomia_id"] = str(taxonomia.id)
    with TestClient(criar_app(db_teste_url, tmp_path), raise_server_exceptions=False) as client:
        resp = client.get("/api/v1/questoes", params=consulta)
        assert resp.status_code == 422, (params, resp.status_code, resp.text)
        if any("\x00" in valor for valor in params.values()):
            assert "NUL" in resp.text
        assert client.get("/api/v1/questoes", params={"ano": "2023", "pagina": "100000"}).status_code == 200


# ---------------------------------------------------------------------------
# Exclusão mútua de alternativa_letra e remover_alternativa_letra no caso de uso
# ---------------------------------------------------------------------------


def test_caso_de_uso_atualizar_ativo_rejeita_letra_e_remocao_simultaneas(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos = criar_repos(session_factory_teste)
    prova = criar_prova(repos, 2023)
    questao = criar_questao(repos, prova, 10, ENUNCIADO_BOM)
    app = criar_app(db_teste_url, tmp_path)
    use_case = app.state.atualizar_ativo_visual_use_case
    with pytest.raises(ErroValidacaoDominio):
        use_case.execute(uuid4(), alternativa_letra=LetraAlternativa.A, remover_alternativa_letra=True)
    assert repos.questoes.buscar_por_id(questao.id) is not None


# ---------------------------------------------------------------------------
# PATCH de Questão: enunciado e alternativas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("enunciado", ["", "   ", "\n\t "])
def test_patch_enunciado_vazio_ou_so_espacos_retorna_422_sem_alterar(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path, enunciado: str
) -> None:
    repos = criar_repos(session_factory_teste)
    questao = criar_questao(repos, criar_prova(repos, 2023), 10, ENUNCIADO_BOM)
    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        resp = client.patch(f"/api/v1/questoes/{questao.id}", json={"enunciado": enunciado})
        assert resp.status_code == 422, resp.text
    persistida = repos.questoes.buscar_por_id(questao.id)
    assert persistida is not None
    assert persistida.enunciado == ENUNCIADO_BOM
    assert persistida.editada_manualmente is False


def test_patch_alternativas_vazias_em_objetiva_retorna_422_e_remocao_parcial_continua_valida(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos = criar_repos(session_factory_teste)
    questao = criar_questao(repos, criar_prova(repos, 2023), 10, ENUNCIADO_BOM)
    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        url = f"/api/v1/questoes/{questao.id}"
        resp = client.patch(url, json={"alternativas": []})
        assert resp.status_code == 422, resp.text
        persistida = repos.questoes.buscar_por_id(questao.id)
        assert persistida is not None
        assert len(persistida.alternativas) == 5

        parcial = [{"letra": a.letra.value, "texto": a.texto} for a in alternativas_completas()[:4]]
        resp = client.patch(url, json={"alternativas": parcial})
        assert resp.status_code == 200, resp.text
        codigos = {a["codigo"]: a["status"] for a in resp.json()["alertas_extracao"]}
        assert codigos["alternativas_incompletas"] == "aberto"


def test_dominio_discursiva_aceita_alternativas_vazias() -> None:
    from domain.enums import TipoQuestao
    from domain.prova import Questao

    discursiva = Questao(
        prova_id=uuid4(),
        numero=1,
        enunciado=ENUNCIADO_BOM,
        tipo=TipoQuestao.DISCURSIVA,
        alternativas=alternativas_completas(),
    )
    discursiva.editar_conteudo(alternativas=[])
    assert discursiva.alternativas == []
    with pytest.raises(ErroValidacaoDominio):
        discursiva.editar_conteudo(enunciado="  ")


# ---------------------------------------------------------------------------
# Upload: nunca lê além do limite + 1
# ---------------------------------------------------------------------------


def test_upload_le_no_maximo_limite_mais_um_byte(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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

    tamanhos: list[int | None] = []
    original = UploadFile.read

    async def espiao(self: UploadFile, size: int = -1) -> bytes:
        tamanhos.append(size)
        return await original(self, size)

    monkeypatch.setattr(UploadFile, "read", espiao)
    grande = b"0" * (TAMANHO_MAXIMO_IMAGEM_BYTES + 5_000)
    with TestClient(criar_app(db_teste_url, tmp_path / "app", armazenamento)) as client:
        resp = client.post(
            f"/api/v1/questoes/{questao.id}/ativos-visuais", files={"arquivo": ("g.png", grande, "image/png")}
        )
        assert resp.status_code == 422, resp.text
        resp = client.patch(f"/api/v1/ativos-visuais/{ativo.id}", files={"arquivo": ("g.png", grande, "image/png")})
        assert resp.status_code == 422, resp.text
    assert tamanhos == [TAMANHO_MAXIMO_IMAGEM_BYTES + 1, TAMANHO_MAXIMO_IMAGEM_BYTES + 1]


# ---------------------------------------------------------------------------
# Caractere NUL: rejeitado na borda com 422 em todo campo de texto gravado
# ---------------------------------------------------------------------------

_CORRECAO_BASE = {"disciplina_principal": "redes", "disciplinas_secundarias": [], "topicos": [], "justificativa": "ok"}


@pytest.mark.parametrize(
    "alteracao",
    [
        {"justificativa": "x\x00y"},
        {"topicos": ["a\x00b"]},
        {"disciplina_principal": "re\x00des"},
        {"disciplinas_secundarias": ["algo\x00ritmos"]},
    ],
    ids=["justificativa", "topicos", "principal", "secundarias"],
)
def test_nul_na_classificacao_humana_retorna_422_em_corrigir_e_em_resolver(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
    alteracao: dict[str, object],
) -> None:
    repos = criar_repos(session_factory_teste)
    tax = criar_taxonomia(repos)
    execucao = criar_execucao(repos, tax)
    prova = criar_prova(repos, 2023)
    q_corrigir = criar_questao(repos, prova, 10, ENUNCIADO_BOM)
    classificar(repos, q_corrigir, tax, "algoritmos")
    q_resolver = criar_questao(repos, prova, 11, ENUNCIADO_BOM)
    vigente = classificar(repos, q_resolver, tax, "algoritmos")
    divergencia = abrir_divergencia(repos, q_resolver, tax, execucao, vigente)
    total_antes = contar(repos, ClassificacaoModel)
    corpo = {**_CORRECAO_BASE, **alteracao}

    with TestClient(criar_app(db_teste_url, tmp_path), raise_server_exceptions=False) as client:
        resp = client.post(f"/api/v1/questoes/{q_corrigir.id}/classificacoes/{tax.id}/corrigir", json=corpo)
        assert resp.status_code == 422, resp.text
        assert "NUL" in resp.text
        resp = client.post(
            f"/api/v1/questoes/{q_resolver.id}/divergencias/{divergencia.id}/resolver",
            json={"resolucao": "editar_manualmente", "classificacao": corpo},
        )
        assert resp.status_code == 422, resp.text
        assert "NUL" in resp.text

    assert contar(repos, ClassificacaoModel) == total_antes
    assert repos.divergencias.buscar_por_id(divergencia.id).status.value == "aberta"  # type: ignore[union-attr]


def test_patch_questao_com_nul_no_enunciado_retorna_422_sem_alterar(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos = criar_repos(session_factory_teste)
    questao = criar_questao(repos, criar_prova(repos, 2023), 10, ENUNCIADO_BOM)
    with TestClient(criar_app(db_teste_url, tmp_path), raise_server_exceptions=False) as client:
        resp = client.patch(f"/api/v1/questoes/{questao.id}", json={"enunciado": "abc\x00def"})
        assert resp.status_code == 422, resp.text
        assert "NUL" in resp.text
    salva = repos.questoes.buscar_por_id(questao.id)
    assert salva is not None
    assert salva.enunciado == ENUNCIADO_BOM
    assert salva.versao == questao.versao


def test_patch_questao_com_nul_no_texto_de_alternativa_retorna_422_sem_alterar(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos = criar_repos(session_factory_teste)
    questao = criar_questao(repos, criar_prova(repos, 2023), 10, ENUNCIADO_BOM)
    with TestClient(criar_app(db_teste_url, tmp_path), raise_server_exceptions=False) as client:
        resp = client.patch(
            f"/api/v1/questoes/{questao.id}", json={"alternativas": [{"letra": "A", "texto": "x\x00y"}]}
        )
        assert resp.status_code == 422, resp.text
        assert "NUL" in resp.text
    salva = repos.questoes.buscar_por_id(questao.id)
    assert salva is not None
    assert [a.texto for a in salva.alternativas] == [a.texto for a in questao.alternativas]


# ---------------------------------------------------------------------------
# Corpo JSON profundamente aninhado: 422 no formato do FastAPI, sem RecursionError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("profundidade", [1000, 3000])
def test_patch_questao_com_json_muito_aninhado_retorna_422_e_nao_500(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path, profundidade: int
) -> None:
    repos = criar_repos(session_factory_teste)
    questao = criar_questao(repos, criar_prova(repos, 2023), 10, ENUNCIADO_BOM)
    corpo = '{"enunciado": ' + "[" * profundidade + "]" * profundidade + "}"
    with TestClient(criar_app(db_teste_url, tmp_path), raise_server_exceptions=False) as client:
        resp = client.patch(
            f"/api/v1/questoes/{questao.id}", content=corpo, headers={"content-type": "application/json"}
        )
        assert resp.status_code == 422, resp.text[:300]
        detalhe = resp.json()["detail"]
        assert isinstance(detalhe, list)
        assert detalhe[0]["loc"] == ["body", "enunciado"]
        assert set(detalhe[0]) == {"loc", "msg", "type"}


def test_erro_de_validacao_mantem_formato_loc_msg_type(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        resp = client.get("/api/v1/questoes", params={"pagina": "abc"})
    assert resp.status_code == 422
    erro = resp.json()["detail"][0]
    assert erro["loc"] == ["query", "pagina"]
    assert erro["type"] == "int_parsing"
    assert isinstance(erro["msg"], str)
