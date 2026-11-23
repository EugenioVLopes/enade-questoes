"""Testes de integração de GET /api/v1/questoes e GET /api/v1/questoes/{id} (busca, filtros, fila, contadores)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from domain.enums import (
    CodigoAlertaExtracao,
    LetraAlternativa,
    OrigemAtivoVisual,
    OrigemClassificacao,
    SituacaoGabarito,
    StatusAlerta,
    StatusClassificacao,
)
from domain.prova import AlertaExtracao, Alternativa, AtivoVisual, Gabarito, Questao
from domain.taxonomia import Disciplina, Taxonomia
from tests.integration._apoio_questoes import (
    T0,
    Repos,
    abrir_divergencia,
    alternativas_completas,
    classificar,
    criar_app,
    criar_execucao,
    criar_prova,
    criar_questao,
    criar_repos,
    criar_taxonomia,
)


@dataclass
class Cenario:
    repos: Repos
    taxonomia: Taxonomia
    q1: Questao
    q2: Questao
    q3: Questao
    q4: Questao
    q5: Questao
    q6: Questao


def _montar_cenario(session_factory: sessionmaker[Session]) -> Cenario:
    repos = criar_repos(session_factory)
    taxonomia = criar_taxonomia(repos)
    execucao = criar_execucao(repos, taxonomia)
    prova23 = criar_prova(repos, 2023)
    prova21 = criar_prova(repos, 2019)

    q1 = criar_questao(
        repos, prova23, 1, "Considere o protocolo OSPF para roteamento dinâmico em redes de computadores."
    )
    alts_q2 = alternativas_completas()
    alts_q2[2] = Alternativa(letra=LetraAlternativa.C, texto="Utilize VHDL para descrever o circuito sequencial.")
    q2 = criar_questao(
        repos,
        prova23,
        2,
        "Descreva a função de transferência de um filtro implementado em hardware.",
        alternativas=alts_q2,
    )
    q3 = criar_questao(repos, prova23, 3, "A funcao recursiva consome pilha de chamadas durante a execução.")
    q4 = criar_questao(
        repos,
        prova21,
        1,
        "Enunciado extraído por OCR sem classificação registrada ainda.",
        alertas=(CodigoAlertaExtracao.PDF_VIA_OCR,),
        gabarito=Gabarito(SituacaoGabarito.PENDENTE),
    )
    q5 = criar_questao(
        repos,
        prova21,
        2,
        "Questão classificada em disciplina arquivada com alerta informativo.",
        alertas=(CodigoAlertaExtracao.FONTE_SYMBOL_DETECTADA,),
    )
    q6 = repos.questoes.salvar(
        Questao(
            prova_id=prova21.id,
            numero=3,
            enunciado="Questão com alerta de OCR já resolvido pelo revisor humano.",
            alternativas=alternativas_completas(),
            alertas_extracao=[
                AlertaExtracao(codigo=CodigoAlertaExtracao.PDF_VIA_OCR, status=StatusAlerta.RESOLVIDO, resolvido_em=T0)
            ],
            gabarito=Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.B),
        )
    )

    c1 = classificar(repos, q1, taxonomia, "redes", topicos=("roteamento-ospf",), confianca=0.9)
    c2 = classificar(
        repos,
        q2,
        taxonomia,
        "algoritmos",
        secundarias=("redes",),
        topicos=("filtros-digitais",),
        confianca=0.5,
        prioritaria=True,
    )
    classificar(
        repos,
        q3,
        taxonomia,
        "sistemas-operacionais",
        topicos=("escalonamento-de-processos",),
        confianca=1.0,
        status=StatusClassificacao.APROVADA,
        origem=OrigemClassificacao.HUMANA,
    )
    classificar(repos, q5, taxonomia, "legada", topicos=("tema-legado",), confianca=0.8)
    abrir_divergencia(repos, q1, taxonomia, execucao, c1)
    abrir_divergencia(repos, q2, taxonomia, execucao, c2, candidata="sistemas-operacionais")
    return Cenario(repos, taxonomia, q1, q2, q3, q4, q5, q6)


def _ids(resp_json: dict[str, object]) -> list[str]:
    return [item["id"] for item in resp_json["itens"]]  # type: ignore[index, union-attr]


def _numeros(resp_json: dict[str, object]) -> list[tuple[int, int]]:
    return [(item["prova"]["ano"], item["numero"]) for item in resp_json["itens"]]  # type: ignore[index, union-attr]


def test_busca_textual_acentos_siglas_alternativas_e_topicos(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    cen = _montar_cenario(session_factory_teste)
    with TestClient(criar_app(db_teste_url, tmp_path)) as client:

        def buscar(termo: str) -> dict[str, object]:
            resp = client.get("/api/v1/questoes", params={"q": termo})
            assert resp.status_code == 200, resp.text
            return resp.json()

        # "função" (acentuada) casa "função" (q2) e "funcao" sem acento (q3) via stemming português + unaccent
        acentuada = buscar("função")
        assert set(_ids(acentuada)) == {str(cen.q2.id), str(cen.q3.id)}
        assert acentuada["total"] == 2
        # sem acento acha o texto acentuado e o não acentuado
        assert set(_ids(buscar("funcao"))) == {str(cen.q2.id), str(cen.q3.id)}

        # siglas técnicas
        assert _ids(buscar("OSPF")) == [str(cen.q1.id)]
        assert _ids(buscar("ospf")) == [str(cen.q1.id)]
        # termo presente só em alternativa
        assert _ids(buscar("VHDL")) == [str(cen.q2.id)]
        # termo presente só em Tópico da classificação vigente (kebab-case)
        assert _ids(buscar("escalonamento")) == [str(cen.q3.id)]
        # parte interna do Tópico via trigramas
        assert _ids(buscar("tema-legado")) == [str(cen.q5.id)]

        # delimitadores JSON dos Tópicos ('[' e ']') não casam: nenhum Tópico do cenário contém colchetes
        assert buscar("[")["total"] == 0
        assert buscar("]")["total"] == 0

        inexistente = buscar("zzxqwvk")
        assert inexistente["total"] == 0
        assert inexistente["itens"] == []


def test_filtros_combinados_secundarias_e_atributos(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    cen = _montar_cenario(session_factory_teste)
    tax_id = str(cen.taxonomia.id)
    disciplina_redes = next(d for d in cen.taxonomia.disciplinas if d.codigo == "redes")
    prova23 = cen.q1.prova_id
    with TestClient(criar_app(db_teste_url, tmp_path)) as client:

        def listar(**params: object) -> dict[str, object]:
            resp = client.get("/api/v1/questoes", params=params)
            assert resp.status_code == 200, resp.text
            return resp.json()

        # prova_id + disciplina_id: padrão inclui secundárias (q2 só tem redes como secundária)
        padrao = listar(prova_id=str(prova23), disciplina_id=str(disciplina_redes.id))
        assert _ids(padrao) == [str(cen.q1.id), str(cen.q2.id)]
        assert padrao["taxonomia_id"] == tax_id

        sem_secundarias = listar(
            prova_id=str(prova23), disciplina_id=str(disciplina_redes.id), incluir_secundarias="false"
        )
        assert _ids(sem_secundarias) == [str(cen.q1.id)]

        # prova diferente não tem redes
        assert listar(prova_id=str(cen.q4.prova_id), disciplina_id=str(disciplina_redes.id))["total"] == 0

        assert _ids(listar(ano=2019)) == [str(cen.q4.id), str(cen.q5.id), str(cen.q6.id)]
        assert _ids(listar(situacao_gabarito="pendente")) == [str(cen.q4.id)]
        assert _ids(listar(taxonomia_id=tax_id, topico="roteamento-ospf")) == [str(cen.q1.id)]
        assert _ids(listar(taxonomia_id=tax_id, status_revisao="aprovada")) == [str(cen.q3.id)]
        assert _ids(listar(taxonomia_id=tax_id, status_revisao="sem_classificacao")) == [
            str(cen.q4.id),
            str(cen.q6.id),
        ]
        assert _ids(listar(taxonomia_id=tax_id, status_revisao="pendente_revisao")) == [
            str(cen.q1.id),
            str(cen.q2.id),
            str(cen.q5.id),
        ]
        assert _ids(listar(taxonomia_id=tax_id, status_revisao="pendente")) == [
            str(cen.q1.id),
            str(cen.q2.id),
            str(cen.q4.id),
            str(cen.q5.id),
            str(cen.q6.id),
        ]
        assert _ids(listar(taxonomia_id=tax_id, com_divergencia="true")) == [str(cen.q1.id), str(cen.q2.id)]
        assert _ids(listar(taxonomia_id=tax_id, usa_disciplina_arquivada="true")) == [str(cen.q5.id)]
        # busca combinada com filtro de prova
        assert _ids(listar(q="OSPF", prova_id=str(cen.q4.prova_id))) == []


def test_com_alerta_extracao_considera_apenas_alertas_abertos(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    cen = _montar_cenario(session_factory_teste)
    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        com = client.get("/api/v1/questoes", params={"com_alerta_extracao": "true"}).json()
        # q4 (pdf_via_ocr aberto) e q5 (fonte_symbol aberto); q6 tem alerta resolvido e fica fora
        assert _ids(com) == [str(cen.q4.id), str(cen.q5.id)]
        assert {i["id"]: i["alertas_abertos"] for i in com["itens"]} == {
            str(cen.q4.id): ["pdf_via_ocr"],
            str(cen.q5.id): ["fonte_symbol_detectada"],
        }

        sem = client.get("/api/v1/questoes", params={"com_alerta_extracao": "false"}).json()
        assert _ids(sem) == [str(cen.q1.id), str(cen.q2.id), str(cen.q3.id), str(cen.q6.id)]
        item_q6 = next(i for i in sem["itens"] if i["id"] == str(cen.q6.id))
        assert item_q6["alertas_abertos"] == []


def test_contadores_paginacao_e_validacoes(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    cen = _montar_cenario(session_factory_teste)
    tax_id = str(cen.taxonomia.id)
    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        com_tax = client.get("/api/v1/questoes", params={"taxonomia_id": tax_id}).json()
        # pendentes: tudo menos q3 aprovada; divergências: q1 e q2; disciplina arquivada: q5
        assert com_tax["contadores"] == {"pendentes": 5, "divergencias": 2, "disciplina_arquivada": 1}
        assert com_tax["total"] == 6

        sem_tax = client.get("/api/v1/questoes").json()
        assert sem_tax["contadores"] is None
        assert sem_tax["taxonomia_id"] is None

        # ordem de consulta: ano desc, numero asc
        assert _numeros(sem_tax) == [(2023, 1), (2023, 2), (2023, 3), (2019, 1), (2019, 2), (2019, 3)]

        pagina2 = client.get("/api/v1/questoes", params={"pagina": 2, "tamanho_pagina": 2}).json()
        assert _numeros(pagina2) == [(2023, 3), (2019, 1)]
        assert (pagina2["total"], pagina2["pagina"], pagina2["tamanho_pagina"]) == (6, 2, 2)

        # filtros dependentes de taxonomia sem taxonomia_id -> 422
        assert client.get("/api/v1/questoes", params={"com_divergencia": "true"}).status_code == 422
        assert client.get("/api/v1/questoes", params={"ordenacao": "fila_revisao"}).status_code == 422
        assert client.get("/api/v1/questoes", params={"tamanho_pagina": 500}).status_code == 422
        assert client.get("/api/v1/questoes", params={"pagina": 0}).status_code == 422
        assert client.get("/api/v1/questoes", params={"taxonomia_id": str(uuid4())}).status_code == 404

        item_q2 = next(i for i in com_tax["itens"] if i["id"] == str(cen.q2.id))
        assert item_q2["classificacao"]["disciplina_principal"] == "algoritmos"
        assert item_q2["classificacao"]["disciplinas_secundarias"] == ["redes"]
        assert item_q2["tem_divergencia_aberta"] is True
        assert item_q2["revisao_prioritaria"] is True
        assert item_q2["trecho"].startswith("Descreva a função")


def test_fila_revisao_ordem_exata_e_prioridade_efetiva(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    repos = criar_repos(session_factory_teste)
    tax = criar_taxonomia(repos)
    p23 = criar_prova(repos, 2023)
    p22 = criar_prova(repos, 2018)
    p21 = criar_prova(repos, 2019)

    def nova(prova: object, numero: int, **kw: object) -> Questao:
        return criar_questao(repos, prova, numero, f"Enunciado da questão {numero} para a fila.", **kw)  # type: ignore[arg-type]

    qa = nova(
        p23,
        5,
    )
    qb = nova(p23, 4)
    qb2 = nova(p23, 2)
    qc = nova(p22, 1)
    qd = nova(p23, 1)
    qe = nova(p23, 3)  # aprovada com flag persistida True: não deve ser prioritária
    qf = nova(p21, 1)  # sem classificação e sem alerta
    qg = nova(p21, 2, alertas=(CodigoAlertaExtracao.PDF_VIA_OCR,))  # sem classificação, alerta crítico aberto

    classificar(repos, qa, tax, "redes", confianca=0.6, prioritaria=True)
    classificar(repos, qb, tax, "redes", confianca=0.3, prioritaria=True)
    classificar(repos, qb2, tax, "redes", confianca=0.3, prioritaria=True)
    classificar(repos, qc, tax, "redes", confianca=0.3, prioritaria=True)
    classificar(repos, qd, tax, "redes", confianca=0.1, prioritaria=False)
    classificar(repos, qe, tax, "redes", confianca=0.2, prioritaria=True, status=StatusClassificacao.APROVADA)

    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        fila = client.get("/api/v1/questoes", params={"taxonomia_id": str(tax.id), "ordenacao": "fila_revisao"}).json()
        esperado = [qb2.id, qb.id, qc.id, qa.id, qg.id, qd.id, qe.id, qf.id]
        assert _ids(fila) == [str(i) for i in esperado]
        assert [i["revisao_prioritaria"] for i in fila["itens"]] == [True] * 5 + [False] * 3

        so_prioritarias = client.get(
            "/api/v1/questoes",
            params={"taxonomia_id": str(tax.id), "revisao_prioritaria": "true", "ordenacao": "fila_revisao"},
        ).json()
        assert _ids(so_prioritarias) == [str(i) for i in esperado[:5]]
        nao_prioritarias = client.get(
            "/api/v1/questoes", params={"taxonomia_id": str(tax.id), "revisao_prioritaria": "false"}
        ).json()
        assert {i["id"] for i in nao_prioritarias["itens"]} == {str(qd.id), str(qe.id), str(qf.id)}


def test_listagem_expoe_possui_ativos_visuais(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    cen = _montar_cenario(session_factory_teste)
    q2 = cen.repos.questoes.buscar_por_id(cen.q2.id)
    assert q2 is not None
    q2.ativos_visuais = [AtivoVisual(origem=OrigemAtivoVisual.PICTURE_DOCLING, ordem=0, pagina=1)]
    cen.repos.questoes.salvar(q2)

    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        corpo = client.get("/api/v1/questoes").json()
    por_id = {i["id"]: i["possui_ativos_visuais"] for i in corpo["itens"]}
    assert por_id[str(cen.q2.id)] is True
    assert por_id[str(cen.q1.id)] is False
    assert sum(por_id.values()) == 1


def test_detalhe_questao_completo_e_erros(
    db_teste_url: str, session_factory_teste: sessionmaker[Session], tmp_path: Path
) -> None:
    cen = _montar_cenario(session_factory_teste)
    repos = cen.repos
    segunda = repos.taxonomias.salvar(
        Taxonomia(codigo="outra", nome="Outra", disciplinas=[Disciplina("matematica", "Matemática")])
    )
    classificar(repos, cen.q2, segunda, "matematica", topicos=("calculo",))

    # ativos fora de ordem de inserção e alertas aberto + resolvido
    q2 = repos.questoes.buscar_por_id(cen.q2.id)
    assert q2 is not None
    q2.ativos_visuais = [
        AtivoVisual(origem=OrigemAtivoVisual.UPLOAD_MANUAL, ordem=2, alternativa_letra=LetraAlternativa.B),
        AtivoVisual(origem=OrigemAtivoVisual.PICTURE_DOCLING, ordem=0, pagina=1),
        AtivoVisual(origem=OrigemAtivoVisual.FORMULA_RECORTE, ordem=1, pagina=2),
    ]
    q2.alertas_extracao = [
        AlertaExtracao(codigo=CodigoAlertaExtracao.PDF_VIA_OCR),
        AlertaExtracao(
            codigo=CodigoAlertaExtracao.FONTE_SYMBOL_DETECTADA, status=StatusAlerta.RESOLVIDO, resolvido_em=T0
        ),
    ]
    repos.questoes.salvar(q2)

    vigente_q2 = repos.classificacoes.buscar_vigente(cen.q2.id, cen.taxonomia.id)
    assert vigente_q2 is not None

    # histórico append-only de q3: a classificação aprovada original e a correção humana posterior
    original_q3 = repos.classificacoes.buscar_vigente(cen.q3.id, cen.taxonomia.id)
    assert original_q3 is not None
    correcao_q3 = original_q3.substituir_por_correcao(
        disciplina_principal="redes", justificativa="Correção posterior.", agora=T0 + timedelta(hours=1)
    )
    repos.classificacoes.registrar_substituicao(original_q3, correcao_q3)

    with TestClient(criar_app(db_teste_url, tmp_path)) as client:
        resp = client.get(f"/api/v1/questoes/{cen.q2.id}", params={"taxonomia_id": str(cen.taxonomia.id)})
        assert resp.status_code == 200, resp.text
        d = resp.json()
        assert d["prova"]["ano"] == 2023
        assert d["numero"] == 2
        assert [a["letra"] for a in d["alternativas"]] == ["A", "B", "C", "D", "E"]
        assert d["alternativas"][2]["texto"].startswith("Utilize VHDL")
        assert [a["ordem"] for a in d["ativos_visuais"]] == [0, 1, 2]
        assert [a["origem"] for a in d["ativos_visuais"]] == ["picture_docling", "formula_recorte", "upload_manual"]
        assert [a["alternativa_letra"] for a in d["ativos_visuais"]] == [None, None, "B"]
        assert all(a["url_arquivo"] == f"/api/v1/ativos-visuais/{a['id']}/arquivo" for a in d["ativos_visuais"])
        assert d["gabarito"] == {"situacao_gabarito": "valida", "alternativa_correta": "A"}
        por_codigo = {a["codigo"]: a for a in d["alertas_extracao"]}
        assert por_codigo["pdf_via_ocr"]["status"] == "aberto"
        assert por_codigo["pdf_via_ocr"]["resolvido_em"] is None
        assert por_codigo["fonte_symbol_detectada"]["status"] == "resolvido"
        assert por_codigo["fonte_symbol_detectada"]["resolvido_em"] is not None
        assert d["classificacao_vigente"]["id"] == str(vigente_q2.id)
        assert d["classificacao_vigente"]["disciplina_principal"] == "algoritmos"
        assert d["divergencia_aberta"]["classificacao_vigente_id"] == str(vigente_q2.id)
        assert d["divergencia_aberta"]["status"] == "aberta"
        assert [h["id"] for h in d["historico"]] == [str(vigente_q2.id)]
        h3 = client.get(f"/api/v1/questoes/{cen.q3.id}", params={"taxonomia_id": str(cen.taxonomia.id)}).json()
        assert [(h["id"], h["vigente"]) for h in h3["historico"]] == [
            (str(correcao_q3.id), True),
            (str(original_q3.id), False),
        ]
        assert h3["historico"][1]["disciplina_principal"] == "sistemas-operacionais"
        assert h3["classificacao_vigente"]["id"] == str(correcao_q3.id)
        assert len(d["outras_taxonomias"]) == 1
        assert d["outras_taxonomias"][0]["taxonomia_codigo"] == "outra"
        assert d["outras_taxonomias"][0]["classificacao"]["disciplina_principal"] == "matematica"
        assert d["disciplinas_arquivadas_em_uso"] == []

        # sem taxonomia: sem classificação vigente, mas outras_taxonomias traz as duas
        sem_tax = client.get(f"/api/v1/questoes/{cen.q2.id}").json()
        assert sem_tax["classificacao_vigente"] is None
        assert sem_tax["divergencia_aberta"] is None
        assert len(sem_tax["outras_taxonomias"]) == 2

        # questão que usa disciplina arquivada
        q5 = client.get(f"/api/v1/questoes/{cen.q5.id}", params={"taxonomia_id": str(cen.taxonomia.id)}).json()
        assert q5["disciplinas_arquivadas_em_uso"] == ["legada"]

        assert client.get(f"/api/v1/questoes/{uuid4()}").status_code == 404
        assert client.get(f"/api/v1/questoes/{cen.q2.id}", params={"taxonomia_id": str(uuid4())}).status_code == 404
