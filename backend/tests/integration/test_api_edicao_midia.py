"""Testes de integração da edição curada de conteúdo, alertas e Ativos Visuais."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from domain.enums import (
    CodigoAlertaExtracao,
    OrigemAtivoVisual,
)
from domain.prova import AlertaExtracao, AtivoVisual, Questao
from infrastructure.persistence.models import ClassificacaoModel, ExecucaoClassificacaoModel
from infrastructure.storage.local import ArmazenamentoArquivosLocal
from tests.integration._apoio_questoes import (
    Repos,
    alternativas_completas,
    classificar,
    contar,
    criar_app,
    criar_prova,
    criar_questao,
    criar_repos,
    criar_taxonomia,
    jpeg_bytes,
    png_bytes,
)

ENUNCIADO_BOM = "Considere o protocolo de roteamento dinâmico OSPF aplicado em redes corporativas."
ENUNCIADO_COM_FORMULA = "Calcule o valor da expressão <!-- formula-not-decoded --> considerando o circuito."


def _alertas_por_codigo(detalhe: dict[str, object]) -> dict[str, dict[str, object]]:
    return {a["codigo"]: a for a in detalhe["alertas_extracao"]}  # type: ignore[index, union-attr]


def _prioritaria_vigente(repos: Repos, questao: Questao, taxonomia_id: UUID) -> bool:
    vigente = repos.classificacoes.buscar_vigente(questao.id, taxonomia_id)
    assert vigente is not None
    return vigente.revisao_prioritaria


def test_patch_questao_fecha_e_reabre_alertas_estruturais_sem_enfileirar_execucao(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos = criar_repos(session_factory_teste)
    tax = criar_taxonomia(repos)
    prova = criar_prova(repos, 2023)
    questao = criar_questao(
        repos,
        prova,
        10,
        ENUNCIADO_COM_FORMULA,
        alternativas=alternativas_completas()[:4],
        alertas=(CodigoAlertaExtracao.FORMULA_NAO_DECODIFICADA, CodigoAlertaExtracao.ALTERNATIVAS_INCOMPLETAS),
    )
    classificar(repos, questao, tax, "redes", confianca=0.9, prioritaria=True)
    execucoes_antes = contar(repos, ExecucaoClassificacaoModel)
    classificacoes_antes = contar(repos, ClassificacaoModel)
    assert questao.editada_manualmente is False

    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        url = f"/api/v1/questoes/{questao.id}"
        params = {"taxonomia_id": str(tax.id)}

        resp = client.patch(
            url,
            params=params,
            json={
                "enunciado": ENUNCIADO_BOM,
                "alternativas": [{"letra": "E", "texto": "Quinta alternativa criada pelo revisor."}]
                + [{"letra": a.letra.value, "texto": a.texto} for a in alternativas_completas()[:4]],
            },
        )
        assert resp.status_code == 200, resp.text
        corpo = resp.json()
        assert corpo["enunciado"] == ENUNCIADO_BOM
        assert [a["letra"] for a in corpo["alternativas"]] == ["A", "B", "C", "D", "E"]
        assert corpo["alternativas"][4]["texto"] == "Quinta alternativa criada pelo revisor."
        assert corpo["editada_manualmente"] is True
        alertas = _alertas_por_codigo(corpo)
        assert alertas["formula_nao_decodificada"]["status"] == "resolvido"
        assert alertas["formula_nao_decodificada"]["resolvido_em"] is not None
        assert alertas["alternativas_incompletas"]["status"] == "resolvido"
        # sem outro gatilho (confiança 0.9), a prioridade persistida da classificação pendente cai
        assert corpo["classificacao_vigente"]["revisao_prioritaria"] is False
        assert _prioritaria_vigente(repos, questao, tax.id) is False

        # busca textual enxerga o novo enunciado (trigger de busca_tsv)
        achados = client.get("/api/v1/questoes", params={"q": "corporativas"}).json()
        assert [i["id"] for i in achados["itens"]] == [str(questao.id)]

        # quebrar de novo: remover E e reintroduzir o marcador reabre os alertas
        resp = client.patch(
            url,
            params=params,
            json={
                "enunciado": ENUNCIADO_COM_FORMULA,
                "alternativas": [{"letra": a.letra.value, "texto": a.texto} for a in alternativas_completas()[:4]],
            },
        )
        assert resp.status_code == 200, resp.text
        reaberto = _alertas_por_codigo(resp.json())
        assert reaberto["formula_nao_decodificada"]["status"] == "aberto"
        assert reaberto["formula_nao_decodificada"]["resolvido_em"] is None
        assert reaberto["alternativas_incompletas"]["status"] == "aberto"
        assert resp.json()["classificacao_vigente"]["revisao_prioritaria"] is True
        assert _prioritaria_vigente(repos, questao, tax.id) is True

        # edição de gabarito
        resp = client.patch(url, json={"gabarito": {"situacao_gabarito": "valida", "alternativa_correta": "D"}})
        assert resp.status_code == 200, resp.text
        assert resp.json()["gabarito"] == {"situacao_gabarito": "valida", "alternativa_correta": "D"}
        resp = client.patch(url, json={"gabarito": {"situacao_gabarito": "anulada"}})
        assert resp.json()["gabarito"] == {"situacao_gabarito": "anulada", "alternativa_correta": None}

    # nenhuma Execução de Classificação enfileirada e nenhuma classificação criada
    assert contar(repos, ExecucaoClassificacaoModel) == execucoes_antes
    assert contar(repos, ClassificacaoModel) == classificacoes_antes


def test_patch_questao_validacoes(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos = criar_repos(session_factory_teste)
    prova = criar_prova(repos, 2023)
    questao = criar_questao(repos, prova, 10, ENUNCIADO_BOM)

    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        url = f"/api/v1/questoes/{questao.id}"
        assert client.patch(url, json={}).status_code == 422
        assert client.patch(url, json={"gabarito": {"situacao_gabarito": "valida"}}).status_code == 422
        assert (
            client.patch(
                url, json={"gabarito": {"situacao_gabarito": "anulada", "alternativa_correta": "A"}}
            ).status_code
            == 422
        )
        assert client.patch(url, json={"alternativas": [{"letra": "Z", "texto": "x"}]}).status_code == 422
        assert (
            client.patch(
                url, json={"alternativas": [{"letra": "A", "texto": "x"}, {"letra": "A", "texto": "y"}]}
            ).status_code
            == 422
        )
        assert client.patch(f"/api/v1/questoes/{uuid4()}", json={"enunciado": ENUNCIADO_BOM}).status_code == 404
        # nada foi alterado pelas tentativas inválidas
        atual = client.get(url).json()
        assert atual["editada_manualmente"] is False
        assert atual["enunciado"] == ENUNCIADO_BOM
        assert [a["letra"] for a in atual["alternativas"]] == ["A", "B", "C", "D", "E"]


def test_patch_alerta_resolve_inspecao_e_recalcula_prioridade(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos = criar_repos(session_factory_teste)
    tax = criar_taxonomia(repos)
    prova = criar_prova(repos, 2023)
    unico = criar_questao(repos, prova, 10, ENUNCIADO_BOM, alertas=(CodigoAlertaExtracao.PDF_VIA_OCR,))
    com_outro = criar_questao(repos, prova, 11, ENUNCIADO_BOM, alertas=(CodigoAlertaExtracao.PDF_VIA_OCR,))
    estrutural = criar_questao(
        repos, prova, 12, ENUNCIADO_BOM, alertas=(CodigoAlertaExtracao.ALTERNATIVAS_INCOMPLETAS,)
    )
    classificar(repos, unico, tax, "redes", confianca=0.9, prioritaria=True)
    # outro gatilho: confiança baixa mantém a prioridade após resolver o OCR
    classificar(repos, com_outro, tax, "redes", confianca=0.4, prioritaria=True)

    def alerta_de(q: Questao) -> AlertaExtracao:
        salva = repos.questoes.buscar_por_id(q.id)
        assert salva is not None
        return salva.alertas_extracao[0]

    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        tax_id = str(tax.id)
        filtro = {"taxonomia_id": tax_id, "revisao_prioritaria": "true"}
        assert {i["id"] for i in client.get("/api/v1/questoes", params=filtro).json()["itens"]} == {
            str(unico.id),
            str(com_outro.id),
            str(estrutural.id),  # sem classificação, mas com alerta crítico aberto
        }
        assert {
            i["id"] for i in client.get("/api/v1/questoes", params={"com_alerta_extracao": "true"}).json()["itens"]
        } == {
            str(unico.id),
            str(com_outro.id),
            str(estrutural.id),
        }

        resp = client.patch(
            f"/api/v1/questoes/{unico.id}/alertas/{alerta_de(unico).id}",
            params={"taxonomia_id": tax_id},
            json={"status": "resolvido"},
        )
        assert resp.status_code == 200, resp.text
        corpo = resp.json()
        assert corpo["editada_manualmente"] is True
        assert corpo["alertas_extracao"][0]["status"] == "resolvido"
        assert corpo["alertas_extracao"][0]["resolvido_em"] is not None
        assert corpo["classificacao_vigente"]["revisao_prioritaria"] is False

        resp = client.patch(
            f"/api/v1/questoes/{com_outro.id}/alertas/{alerta_de(com_outro).id}", json={"status": "resolvido"}
        )
        assert resp.status_code == 200, resp.text
        assert _prioritaria_vigente(repos, com_outro, tax.id) is True  # confiança 0.4 continua sendo gatilho

        # `unico` saiu de com_alerta_extracao=true e de revisao_prioritaria=true (gatilho único resolvido)
        listados = client.get("/api/v1/questoes", params={"com_alerta_extracao": "true"}).json()
        assert [i["id"] for i in listados["itens"]] == [str(estrutural.id)]
        prioritarias = client.get("/api/v1/questoes", params=filtro).json()
        # permanecem: com_outro (confiança baixa) e estrutural (alerta crítico aberto sem classificação)
        assert {i["id"] for i in prioritarias["itens"]} == {str(com_outro.id), str(estrutural.id)}

        # idempotente para alerta já resolvido
        assert (
            client.patch(
                f"/api/v1/questoes/{unico.id}/alertas/{alerta_de(unico).id}", json={"status": "resolvido"}
            ).status_code
            == 200
        )
        # alerta estrutural -> 422; alerta de outra questão -> 404; alerta inexistente -> 404; status inválido -> 422
        alerta_estrutural = alerta_de(estrutural)
        assert (
            client.patch(
                f"/api/v1/questoes/{estrutural.id}/alertas/{alerta_estrutural.id}", json={"status": "resolvido"}
            ).status_code
            == 422
        )
        assert (
            client.patch(
                f"/api/v1/questoes/{unico.id}/alertas/{alerta_estrutural.id}", json={"status": "resolvido"}
            ).status_code
            == 404
        )
        assert (
            client.patch(f"/api/v1/questoes/{unico.id}/alertas/{uuid4()}", json={"status": "resolvido"}).status_code
            == 404
        )
        assert (
            client.patch(
                f"/api/v1/questoes/{estrutural.id}/alertas/{alerta_estrutural.id}", json={"status": "aberto"}
            ).status_code
            == 422
        )


def _arquivos(raiz: Path) -> set[str]:
    return {str(p.relative_to(raiz)) for p in raiz.rglob("*") if p.is_file()}


def test_ativos_visuais_crud_manual_com_armazenamento(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos = criar_repos(session_factory_teste)
    prova = criar_prova(repos, 2023)
    questao = criar_questao(repos, prova, 10, ENUNCIADO_BOM)
    raiz = tmp_path / "dados"
    armazenamento = ArmazenamentoArquivosLocal(raiz)
    nome_original = "o"

    # ativo extraído automaticamente, com arquivo já gravado
    original = AtivoVisual(origem=OrigemAtivoVisual.PICTURE_DOCLING, ordem=0, pagina=1)
    original.chave_arquivo = f"provas/{prova.id}/ativos/{original.id}.png"
    armazenamento.salvar(original.chave_arquivo, png_bytes((1, 2, 3)))
    questao_db = repos.questoes.buscar_por_id(questao.id)
    assert questao_db is not None
    questao_db.ativos_visuais.append(original)
    repos.questoes.salvar(questao_db)
    assert nome_original and armazenamento.existe(original.chave_arquivo)

    with TestClient(criar_app(db_teste_url, tmp_path / "app", armazenamento)) as client:
        base = f"/api/v1/questoes/{questao.id}/ativos-visuais"
        assert client.get(f"/api/v1/questoes/{questao.id}").json()["editada_manualmente"] is False

        # POST PNG
        png = png_bytes((200, 10, 10))
        resp = client.post(base, files={"arquivo": ("figura.png", png, "image/png")}, data={"alternativa_letra": "C"})
        assert resp.status_code == 201, resp.text
        novo = resp.json()
        assert novo["origem"] == "upload_manual"
        assert novo["alternativa_letra"] == "C"
        assert novo["ordem"] == 1
        assert novo["url_arquivo"] == f"/api/v1/ativos-visuais/{novo['id']}/arquivo"
        chave_novo = f"provas/{prova.id}/ativos/{novo['id']}.png"
        assert armazenamento.existe(chave_novo)
        entrega = client.get(novo["url_arquivo"])
        assert entrega.status_code == 200
        assert entrega.headers["content-type"] == "image/png"
        assert entrega.content == png
        assert client.get(f"/api/v1/questoes/{questao.id}").json()["editada_manualmente"] is True

        # POST JPEG é convertido para PNG, com ordem explícita
        resp = client.post(base, files={"arquivo": ("foto.jpg", jpeg_bytes(), "image/jpeg")}, data={"ordem": "5"})
        assert resp.status_code == 201, resp.text
        jpeg_resp = resp.json()
        assert jpeg_resp["ordem"] == 5
        assert jpeg_resp["alternativa_letra"] is None
        assert client.get(jpeg_resp["url_arquivo"]).content.startswith(b"\x89PNG\r\n\x1a\n")

        # entradas inválidas: 422 e nenhum arquivo órfão
        antes = _arquivos(raiz)
        for nome, conteudo in (
            ("texto.txt", b"isto nao e uma imagem"),
            ("vazio.png", b""),
            (
                "gif.gif",
                b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            ),
            ("enorme.png", b"0" * (10 * 1024 * 1024 + 1)),
        ):
            resp = client.post(base, files={"arquivo": (nome, conteudo, "image/png")})
            assert resp.status_code == 422, (nome, resp.text)
        assert (
            client.post(
                base, files={"arquivo": ("a.png", png, "image/png")}, data={"alternativa_letra": "Z"}
            ).status_code
            == 422
        )
        assert _arquivos(raiz) == antes
        assert (
            client.post(
                f"/api/v1/questoes/{uuid4()}/ativos-visuais", files={"arquivo": ("a.png", png, "image/png")}
            ).status_code
            == 404
        )
        assert _arquivos(raiz) == antes

        # detalhe lista os ativos ordenados por `ordem`
        detalhe = client.get(f"/api/v1/questoes/{questao.id}").json()
        assert [(a["id"], a["ordem"]) for a in detalhe["ativos_visuais"]] == [
            (str(original.id), 0),
            (novo["id"], 1),
            (jpeg_resp["id"], 5),
        ]

        # PATCH: reordenar e mudar alternativa
        resp = client.patch(f"/api/v1/ativos-visuais/{novo['id']}", data={"ordem": "9", "alternativa_letra": "A"})
        assert resp.status_code == 200, resp.text
        assert (resp.json()["ordem"], resp.json()["alternativa_letra"]) == (9, "A")
        resp = client.patch(f"/api/v1/ativos-visuais/{novo['id']}", data={"remover_alternativa_letra": "true"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["alternativa_letra"] is None
        assert resp.json()["ordem"] == 9  # preservado
        ordem = [a["id"] for a in client.get(f"/api/v1/questoes/{questao.id}").json()["ativos_visuais"]]
        assert ordem == [str(original.id), jpeg_resp["id"], novo["id"]]

        # PATCH inválidos
        assert client.patch(f"/api/v1/ativos-visuais/{novo['id']}", data={}).status_code == 422
        assert (
            client.patch(
                f"/api/v1/ativos-visuais/{novo['id']}",
                data={"alternativa_letra": "A", "remover_alternativa_letra": "true"},
            ).status_code
            == 422
        )
        assert client.patch(f"/api/v1/ativos-visuais/{uuid4()}", data={"ordem": "1"}).status_code == 404
        arquivos_antes_substituicao = _arquivos(raiz)
        resp = client.patch(
            f"/api/v1/ativos-visuais/{original.id}", files={"arquivo": ("x.txt", b"nao e imagem", "text/plain")}
        )
        assert resp.status_code == 422
        assert _arquivos(raiz) == arquivos_antes_substituicao
        assert armazenamento.existe(original.chave_arquivo)

        # PATCH substitui a imagem do ativo extraído: arquivo antigo removido, origem vira upload_manual
        nova_png = png_bytes((9, 200, 9))
        resp = client.patch(
            f"/api/v1/ativos-visuais/{original.id}", files={"arquivo": ("n.png", nova_png, "image/png")}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["origem"] == "upload_manual"
        assert resp.json()["ordem"] == 0
        assert not armazenamento.existe(original.chave_arquivo)
        assert client.get(resp.json()["url_arquivo"]).content == nova_png
        assert len(_arquivos(raiz)) == len(arquivos_antes_substituicao)

        # DELETE remove registro e arquivo
        assert client.delete(f"/api/v1/ativos-visuais/{novo['id']}").status_code == 204
        assert not armazenamento.existe(chave_novo)
        assert client.get(f"/api/v1/ativos-visuais/{novo['id']}/arquivo").status_code == 404
        assert client.delete(f"/api/v1/ativos-visuais/{novo['id']}").status_code == 404
        restantes = [a["id"] for a in client.get(f"/api/v1/questoes/{questao.id}").json()["ativos_visuais"]]
        assert restantes == [str(original.id), jpeg_resp["id"]]
        assert len(_arquivos(raiz)) == 2


def test_delete_ativo_marca_questao_como_editada(
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
        assert client.delete(f"/api/v1/ativos-visuais/{ativo.id}").status_code == 204
        detalhe = client.get(f"/api/v1/questoes/{questao.id}").json()
        assert detalhe["ativos_visuais"] == []
        assert detalhe["editada_manualmente"] is True
    assert not armazenamento.existe(ativo.chave_arquivo)
