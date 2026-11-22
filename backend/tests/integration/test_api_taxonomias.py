"""Testes de integração dos endpoints /api/v1/taxonomias, /api/v1/disciplinas e /api/v1/perfis-classificacao."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from application.ports.classificacao import IdentidadeClassificador, ResultadoChamada
from domain.classificacao import Classificacao, ExecucaoClassificacao
from domain.enums import (
    EscopoExecucao,
    LetraAlternativa,
    OrigemClassificacao,
    StatusClassificacao,
    StatusExecucaoClassificacao,
)
from domain.prova import Alternativa, FaixaQuestoes, Prova, Questao
from infrastructure.config import Settings
from infrastructure.persistence.repositorios import (
    RepositorioClassificacoesSqlAlchemy,
    RepositorioExecucoesClassificacaoSqlAlchemy,
    RepositorioProvasSqlAlchemy,
    RepositorioQuestoesSqlAlchemy,
    RepositorioTaxonomiasSqlAlchemy,
)
from presentation.main import build_app


class _DummyClassificador:
    @property
    def identidade(self) -> IdentidadeClassificador:
        return IdentidadeClassificador(provider="fake", model="fake-v1", base_url="http://fake.local")

    def classificar_estruturado(
        self,
        *,
        system: str,
        user: str,
        imagens_png: object,
        schema: object,
        nome_schema: str,
        max_tokens: int = 4096,
        usar_cache: bool = True,
    ) -> ResultadoChamada:
        raise AssertionError("Classificador não deveria ser chamado nestes testes.")


def _alternativas_validas() -> list[Alternativa]:
    return [Alternativa(letra=letra, texto=f"Alternativa {letra.value}.") for letra in LetraAlternativa]


def test_crud_taxonomias_disciplinas_impacto_arquivamento_e_proibicao_exclusao(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    app = build_app(
        Settings(database_url=db_teste_url, data_dir=tmp_path / "app_data"),
        classificador=_DummyClassificador(),
    )

    repo_provas = RepositorioProvasSqlAlchemy(session_factory_teste)
    repo_questoes = RepositorioQuestoesSqlAlchemy(session_factory_teste)
    repo_classif = RepositorioClassificacoesSqlAlchemy(session_factory_teste)
    repo_tax = RepositorioTaxonomiasSqlAlchemy(session_factory_teste)

    with TestClient(app) as client:
        # 1. POST /api/v1/taxonomias -> 201 Created com disciplinas ordenadas
        resp_create = client.post(
            "/api/v1/taxonomias",
            json={
                "codigo": "enade-ec",
                "nome": "ENADE Engenharia de Computação",
                "curso_referencia": "Engenharia de Computação",
                "disciplinas": [
                    {"codigo": "algoritmos", "nome": "Algoritmos", "ementa": "Complexidade e estruturas"},
                    {"codigo": "redes", "nome": "Redes de Computadores", "ementa": "Protocolos TCP/IP"},
                ],
            },
        )
        assert resp_create.status_code == 201
        tax_data = resp_create.json()
        tax_id = UUID(tax_data["id"])
        assert tax_data["codigo"] == "enade-ec"
        assert [d["codigo"] for d in tax_data["disciplinas"]] == ["algoritmos", "redes"]
        assert all(d["classificacoes_vigentes_impactadas"] == 0 for d in tax_data["disciplinas"])

        # Duplicidade de código de taxonomia -> 409 Conflict
        resp_dup_tax = client.post(
            "/api/v1/taxonomias",
            json={"codigo": "enade-ec", "nome": "Outra Taxonomia"},
        )
        assert resp_dup_tax.status_code == 409

        # Validação de domínio -> 422
        assert client.post("/api/v1/taxonomias", json={"codigo": "   ", "nome": "X"}).status_code == 422

        # 2. GET /api/v1/taxonomias e GET /api/v1/taxonomias/{id}
        resp_list = client.get("/api/v1/taxonomias")
        assert resp_list.status_code == 200
        assert resp_list.json()["total"] == 1
        assert resp_list.json()["itens"][0]["id"] == str(tax_id)

        resp_detalhe = client.get(f"/api/v1/taxonomias/{tax_id}")
        assert resp_detalhe.status_code == 200
        assert resp_detalhe.json()["id"] == str(tax_id)
        assert client.get(f"/api/v1/taxonomias/{uuid4()}").status_code == 404

        # 3. PATCH /api/v1/taxonomias/{id} atualiza nome/curso_referencia e rejeita alterar codigo (422)
        resp_patch_tax = client.patch(
            f"/api/v1/taxonomias/{tax_id}",
            json={"nome": "ENADE Eng. Computação (Atualizada)", "curso_referencia": "Eng. Computação"},
        )
        assert resp_patch_tax.status_code == 200
        patched_tax = resp_patch_tax.json()
        assert patched_tax["codigo"] == "enade-ec"
        assert patched_tax["nome"] == "ENADE Eng. Computação (Atualizada)"
        assert patched_tax["curso_referencia"] == "Eng. Computação"
        assert [d["codigo"] for d in patched_tax["disciplinas"]] == ["algoritmos", "redes"]

        resp_patch_codigo = client.patch(
            f"/api/v1/taxonomias/{tax_id}",
            json={"codigo": "novo-codigo", "nome": "Outro"},
        )
        assert resp_patch_codigo.status_code == 422
        assert client.patch(f"/api/v1/taxonomias/{uuid4()}", json={"nome": "X"}).status_code == 404

        # 4. POST /api/v1/taxonomias/{id}/disciplinas -> 201 Created, 409 duplicado, 422 ordem negativa
        resp_add_disc = client.post(
            f"/api/v1/taxonomias/{tax_id}/disciplinas",
            json={"codigo": "banco-de-dados", "nome": "Banco de Dados", "ementa": "Modelo relacional e SQL"},
        )
        assert resp_add_disc.status_code == 201
        disc_bd = resp_add_disc.json()
        assert disc_bd["codigo"] == "banco-de-dados"
        assert disc_bd["taxonomia_id"] == str(tax_id)
        assert disc_bd["ativa"] is True
        assert disc_bd["classificacoes_vigentes_impactadas"] == 0

        assert (
            client.post(
                f"/api/v1/taxonomias/{tax_id}/disciplinas",
                json={"codigo": "redes", "nome": "Redes Duplicada"},
            ).status_code
            == 409
        )
        assert (
            client.post(
                f"/api/v1/taxonomias/{tax_id}/disciplinas",
                json={"codigo": "ia", "nome": "IA", "ordem": -1},
            ).status_code
            == 422
        )
        for ordem_invalida in (True, False, 1.5, "1"):
            assert (
                client.post(
                    f"/api/v1/taxonomias/{tax_id}/disciplinas",
                    json={"codigo": "ia", "nome": "IA", "ordem": ordem_invalida},
                ).status_code
                == 422
            )
        assert (
            client.post(
                f"/api/v1/taxonomias/{uuid4()}/disciplinas",
                json={"codigo": "ia", "nome": "IA"},
            ).status_code
            == 404
        )

        # 5. Semeia classificações vigentes (principal, secundária) e não-vigente para testar contagem de impacto
        prova = repo_provas.salvar(
            Prova(exame="ENADE", curso="Engenharia de Computação", ano=2023, faixa_ce=FaixaQuestoes(10, 38))
        )
        q10 = repo_questoes.salvar(
            Questao(
                prova_id=prova.id,
                numero=10,
                enunciado="Questão 10 sobre redes TCP.",
                alternativas=_alternativas_validas(),
            )
        )
        q11 = repo_questoes.salvar(
            Questao(
                prova_id=prova.id,
                numero=11,
                enunciado="Questão 11 sobre algoritmos distribuídos em redes.",
                alternativas=_alternativas_validas(),
            )
        )
        # Q10: não-vigente com principal='redes' (NÃO deve contar) + vigente com principal='redes' (CONTA)
        repo_classif.salvar(
            Classificacao(
                questao_id=q10.id,
                taxonomia_id=tax_id,
                disciplina_principal="redes",
                topicos=("TCP",),
                justificativa="Versão antiga não vigente.",
                confianca=0.7,
                origem=OrigemClassificacao.AUTOMATICA,
                status=StatusClassificacao.PENDENTE_REVISAO,
                vigente=False,
            )
        )
        repo_classif.salvar(
            Classificacao(
                questao_id=q10.id,
                taxonomia_id=tax_id,
                disciplina_principal="redes",
                topicos=("TCP",),
                justificativa="Vigente como principal.",
                confianca=0.9,
                origem=OrigemClassificacao.HUMANA,
                status=StatusClassificacao.APROVADA,
                vigente=True,
            )
        )
        # Q11: vigente com 'redes' como disciplina secundária (CONTA)
        repo_classif.salvar(
            Classificacao(
                questao_id=q11.id,
                taxonomia_id=tax_id,
                disciplina_principal="algoritmos",
                disciplinas_secundarias=("redes",),
                topicos=("Roteamento",),
                justificativa="Vigente com redes secundária.",
                confianca=0.85,
                origem=OrigemClassificacao.AUTOMATICA,
                status=StatusClassificacao.PENDENTE_REVISAO,
                vigente=True,
            )
        )

        redes_id = next(d["id"] for d in patched_tax["disciplinas"] if d["codigo"] == "redes")

        # Arquivar disciplina 'redes' (ativa=false) e verificar contagem exata (= 2)
        resp_arq = client.patch(
            f"/api/v1/disciplinas/{redes_id}",
            json={"ativa": False, "ementa": "Protocolos TCP/IP e camadas OSI"},
        )
        assert resp_arq.status_code == 200
        arq_body = resp_arq.json()
        assert arq_body["ativa"] is False
        assert arq_body["ementa"] == "Protocolos TCP/IP e camadas OSI"
        assert arq_body["classificacoes_vigentes_impactadas"] == 2

        # GET /taxonomias/{id} e GET /taxonomias mantêm disciplina arquivada e contagem atualizada
        det_apos_arq = client.get(f"/api/v1/taxonomias/{tax_id}").json()
        disc_map = {d["codigo"]: d for d in det_apos_arq["disciplinas"]}
        assert disc_map["redes"]["ativa"] is False
        assert disc_map["redes"]["classificacoes_vigentes_impactadas"] == 2
        assert disc_map["algoritmos"]["classificacoes_vigentes_impactadas"] == 1
        assert disc_map["banco-de-dados"]["classificacoes_vigentes_impactadas"] == 0

        # Reativar disciplina 'redes' (ativa=true)
        resp_reativar = client.patch(f"/api/v1/disciplinas/{redes_id}", json={"ativa": True})
        assert resp_reativar.status_code == 200
        assert resp_reativar.json()["ativa"] is True
        assert resp_reativar.json()["classificacoes_vigentes_impactadas"] == 2

        # Código imutável em disciplina (422), ordem booleana/não-inteira estrita (422) e ID inexistente (404)
        assert client.patch(f"/api/v1/disciplinas/{redes_id}", json={"codigo": "x"}).status_code == 422
        for ordem_invalida in (True, False, 1.5, "1"):
            assert (
                client.patch(
                    f"/api/v1/disciplinas/{redes_id}",
                    json={"ordem": ordem_invalida},
                ).status_code
                == 422
            )
        assert client.patch(f"/api/v1/disciplinas/{uuid4()}", json={"ativa": False}).status_code == 404

        # 6. Proibição de exclusão física (405 Method Not Allowed e registros intactos no PostgreSQL)
        assert client.delete(f"/api/v1/taxonomias/{tax_id}").status_code == 405
        assert client.delete(f"/api/v1/disciplinas/{redes_id}").status_code == 405

        tax_db = repo_tax.buscar_por_id(tax_id)
        assert tax_db is not None
        assert {d.codigo for d in tax_db.disciplinas} == {"algoritmos", "redes", "banco-de-dados"}


def test_perfis_classificacao_clonagem_unicidade_e_imutabilidade_snapshots(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    app = build_app(
        Settings(database_url=db_teste_url, data_dir=tmp_path / "app_data"),
        classificador=_DummyClassificador(),
    )
    repo_execucoes = RepositorioExecucoesClassificacaoSqlAlchemy(session_factory_teste)

    with TestClient(app) as client:
        tax = client.post(
            "/api/v1/taxonomias",
            json={
                "codigo": "enade-ec",
                "nome": "ENADE EC",
                "disciplinas": [
                    {"codigo": "algoritmos", "nome": "Algoritmos", "ementa": "Ementa original algoritmos"},
                    {"codigo": "redes", "nome": "Redes", "ementa": "Ementa original redes"},
                ],
            },
        ).json()
        tax_id = UUID(tax["id"])

        # 1. Criar Perfil v1
        resp_v1 = client.post(
            "/api/v1/perfis-classificacao",
            json={
                "codigo": "editorial-ec",
                "versao": "v1",
                "diretrizes_gerais": "Diretrizes originais v1.",
                "guia_fronteiras": "Fronteira A vs B.",
                "template_prompt": "SYSTEM:{diretrizes_gerais}\nUSER:{enunciado}",
                "descricao": "Descrição canônica v1",
            },
        )
        assert resp_v1.status_code == 201
        v1 = resp_v1.json()
        v1_id = UUID(v1["id"])
        assert v1["criado_em"] is not None

        # Duplicidade (codigo, versao) -> 409 Conflict
        assert (
            client.post(
                "/api/v1/perfis-classificacao",
                json={
                    "codigo": "editorial-ec",
                    "versao": "v1",
                    "diretrizes_gerais": "Outra",
                    "template_prompt": "Outro",
                },
            ).status_code
            == 409
        )

        # Validação de campos obrigatórios sem base -> 422
        assert (
            client.post(
                "/api/v1/perfis-classificacao",
                json={"codigo": "editorial-ec", "versao": "v0"},
            ).status_code
            == 422
        )

        # Registrar uma Execução passada vinculada a v1 e à Taxonomia original
        exec_passada = repo_execucoes.salvar(
            ExecucaoClassificacao(
                taxonomia_id=tax_id,
                perfil_id=v1_id,
                snapshot_taxonomia={
                    "id": str(tax_id),
                    "codigo": "enade-ec",
                    "nome": "ENADE EC",
                    "curso_referencia": "",
                    "disciplinas": [
                        {
                            "id": tax["disciplinas"][0]["id"],
                            "codigo": "algoritmos",
                            "nome": "Algoritmos",
                            "ementa": "Ementa original algoritmos",
                            "ativa": True,
                        },
                        {
                            "id": tax["disciplinas"][1]["id"],
                            "codigo": "redes",
                            "nome": "Redes",
                            "ementa": "Ementa original redes",
                            "ativa": True,
                        },
                    ],
                },
                snapshot_perfil={
                    "id": str(v1_id),
                    "codigo": "editorial-ec",
                    "versao": "v1",
                    "diretrizes_gerais": "Diretrizes originais v1.",
                    "guia_fronteiras": "Fronteira A vs B.",
                    "template_prompt": "SYSTEM:{diretrizes_gerais}\nUSER:{enunciado}",
                    "descricao": "Descrição canônica v1",
                },
                escopo=EscopoExecucao.TODAS,
                status=StatusExecucaoClassificacao.CONCLUIDA,
            )
        )

        # 2. Clonar v1 -> v2 omitindo codigo, guia_fronteiras, template_prompt e descricao (preserva descricao base!)
        resp_v2 = client.post(
            "/api/v1/perfis-classificacao",
            json={
                "versao": "v2",
                "perfil_base_id": str(v1_id),
                "diretrizes_gerais": "Diretrizes refinadas v2.",
            },
        )
        assert resp_v2.status_code == 201
        v2 = resp_v2.json()
        assert v2["id"] != v1["id"]
        assert v2["codigo"] == "editorial-ec"
        assert v2["versao"] == "v2"
        assert v2["diretrizes_gerais"] == "Diretrizes refinadas v2."
        assert v2["guia_fronteiras"] == "Fronteira A vs B."
        assert v2["template_prompt"] == "SYSTEM:{diretrizes_gerais}\nUSER:{enunciado}"
        assert v2["descricao"] == "Descrição canônica v1"

        # Base inexistente -> 404
        assert (
            client.post(
                "/api/v1/perfis-classificacao",
                json={"versao": "v3", "perfil_base_id": str(uuid4())},
            ).status_code
            == 404
        )

        # GET /api/v1/perfis-classificacao lista ordenado por (codigo, versao)
        resp_lista = client.get("/api/v1/perfis-classificacao")
        assert resp_lista.status_code == 200
        lista = resp_lista.json()
        assert lista["total"] == 2
        assert [(item["codigo"], item["versao"]) for item in lista["itens"]] == [
            ("editorial-ec", "v1"),
            ("editorial-ec", "v2"),
        ]

        # Clonar v1 -> v3 enviando explicitamente descricao="" e guia_fronteiras="" limpa no clone sem alterar v1
        resp_v3 = client.post(
            "/api/v1/perfis-classificacao",
            json={
                "versao": "v3",
                "perfil_base_id": str(v1_id),
                "descricao": "",
                "guia_fronteiras": "",
            },
        )
        assert resp_v3.status_code == 201
        v3 = resp_v3.json()
        assert v3["id"] != v1["id"]
        assert v3["codigo"] == "editorial-ec"
        assert v3["versao"] == "v3"
        assert v3["descricao"] == ""
        assert v3["guia_fronteiras"] == ""
        assert v3["diretrizes_gerais"] == "Diretrizes originais v1."
        assert v3["template_prompt"] == "SYSTEM:{diretrizes_gerais}\nUSER:{enunciado}"

        perfis_apos_v3 = {item["versao"]: item for item in client.get("/api/v1/perfis-classificacao").json()["itens"]}
        assert perfis_apos_v3["v1"]["descricao"] == "Descrição canônica v1"
        assert perfis_apos_v3["v1"]["guia_fronteiras"] == "Fronteira A vs B."
        assert perfis_apos_v3["v3"]["descricao"] == ""
        assert perfis_apos_v3["v3"]["guia_fronteiras"] == ""

        # 3. Alterar Taxonomia / arquivar disciplina após execução não muda snapshots congelados
        client.patch(f"/api/v1/taxonomias/{tax_id}", json={"nome": "ENADE EC Editado"})
        client.patch(f"/api/v1/disciplinas/{tax['disciplinas'][1]['id']}", json={"ativa": False})

        det_exec = client.get(f"/api/v1/execucoes-classificacao/{exec_passada.id}").json()
        assert det_exec["snapshot_perfil"]["versao"] == "v1"
        assert det_exec["snapshot_perfil"]["diretrizes_gerais"] == "Diretrizes originais v1."
        assert det_exec["snapshot_perfil"]["descricao"] == "Descrição canônica v1"
        assert det_exec["snapshot_taxonomia"]["nome"] == "ENADE EC"
        assert len(det_exec["snapshot_taxonomia"]["disciplinas"]) == 2
