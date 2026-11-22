"""Testes de integração de Execuções de Classificação, WorkerLocal, Retomada e Encadeamento pós-Ingestão."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pypdfium2 as pdfium
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session, sessionmaker

from application.exceptions import ErroClassificadorLLMError
from application.ports.classificacao import (
    ClassificadorMultimodal,
    IdentidadeClassificador,
    ResultadoChamada,
)
from application.ports.extracao import (
    AlternativaExtraida,
    AtivoVisualExtraido,
    ItemGabaritoExtraido,
    QuestaoExtraida,
    ResultadoExtracaoGabarito,
    ResultadoExtracaoProva,
)
from application.seed import (
    CODIGO_PERFIL_PADRAO,
    DESCRICAO_PERFIL_PADRAO,
    DIRETRIZES_GERAIS_PADRAO,
    GUIA_FRONTEIRAS_PADRAO,
    TEMPLATE_PROMPT_PADRAO,
    VERSAO_PERFIL_PADRAO,
)
from domain.classificacao import Classificacao, ExecucaoClassificacao, PerfilClassificacao
from domain.enums import (
    EscopoExecucao,
    LetraAlternativa,
    OrigemAtivoVisual,
    OrigemClassificacao,
    SituacaoGabarito,
    StatusClassificacao,
    StatusDivergencia,
    StatusExecucaoClassificacao,
    TipoQuestao,
)
from domain.prova import Alternativa, BoundingBox, FaixaQuestoes, Gabarito, MetadadosIngestao, Prova, Questao
from domain.taxonomia import Disciplina, Taxonomia
from infrastructure.config import Settings
from infrastructure.persistence.repositorios import (
    RepositorioClassificacoesSqlAlchemy,
    RepositorioDivergenciasReclassificacaoSqlAlchemy,
    RepositorioExecucoesClassificacaoSqlAlchemy,
    RepositorioPerfisClassificacaoSqlAlchemy,
    RepositorioProvasSqlAlchemy,
    RepositorioQuestoesSqlAlchemy,
    RepositorioTaxonomiasSqlAlchemy,
)
from presentation.api.v1.execucoes_classificacao import _serializar_snapshot_resumo
from presentation.main import build_app


def _gerar_png_bytes(cor: tuple[int, int, int] = (20, 90, 180)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (36, 24), color=cor).save(buf, format="PNG")
    return buf.getvalue()


def _gerar_pdf_bytes_valido(num_paginas: int = 1) -> bytes:
    doc = pdfium.PdfDocument.new()
    try:
        for _ in range(num_paginas):
            doc.new_page(width=200, height=280)
        buf = BytesIO()
        doc.save(buf)
        return buf.getvalue()
    finally:
        doc.close()


def _alternativas_validas() -> list[Alternativa]:
    return [Alternativa(letra=letra, texto=f"Texto alternativa {letra.value}.") for letra in LetraAlternativa]


class _FakeClassificadorMultimodal:
    def __init__(
        self,
        comportamento_por_numero: dict[int, dict[str, Any] | ResultadoChamada | Exception] | None = None,
    ) -> None:
        self.comportamento_por_numero: dict[int, dict[str, Any] | ResultadoChamada | Exception] = (
            dict(comportamento_por_numero) if comportamento_por_numero else {}
        )
        self.falhar_sempre: Exception | None = None
        self.chamadas: list[dict[str, Any]] = []

    @property
    def identidade(self) -> IdentidadeClassificador:
        return IdentidadeClassificador(
            provider="fake",
            model="fake-multimodal-v1",
            base_url="http://fake.local",
        )

    def classificar_estruturado(
        self,
        *,
        system: str,
        user: str,
        imagens_png: Sequence[bytes],
        schema: Mapping[str, Any],
        nome_schema: str,
        max_tokens: int = 4096,
        usar_cache: bool = True,
    ) -> ResultadoChamada:
        self.chamadas.append(
            {
                "system": system,
                "user": user,
                "imagens_png": list(imagens_png),
                "schema": dict(schema),
                "nome_schema": nome_schema,
            }
        )
        if self.falhar_sempre is not None:
            raise self.falhar_sempre

        for num, acao in self.comportamento_por_numero.items():
            if f"QUESTÃO {num:02d}" in user or f"Questão {num}" in user:
                if isinstance(acao, Exception):
                    raise acao
                if isinstance(acao, ResultadoChamada):
                    return acao
                return ResultadoChamada(
                    dados_brutos=acao,
                    prompt_tokens=110,
                    completion_tokens=25,
                    latencia_ms=4.0,
                    from_cache=False,
                    cache_key=f"cache-q{num}",
                )

        return ResultadoChamada(
            dados_brutos={
                "disciplina_principal": "algoritmos",
                "disciplinas_secundarias": [],
                "topicos": ["Análise Assintótica"],
                "justificativa": "Justificativa determinística padrão.",
                "confianca": 0.91,
            },
            prompt_tokens=90,
            completion_tokens=20,
            latencia_ms=2.0,
            from_cache=True,
            cache_key="cache-default",
        )


class _FakeExtratorProva:
    def extrair(self, caminho_pdf: Path, faixa_ce: FaixaQuestoes) -> ResultadoExtracaoProva:
        alternativas = tuple(
            AlternativaExtraida(letra=letra, texto=f"Opção {letra.value}.") for letra in LetraAlternativa
        )
        questoes = (
            QuestaoExtraida(
                numero=10,
                enunciado="Questão 10 com figura sobre grafos e algoritmos.",
                paginas=(1,),
                alternativas=alternativas,
                ativos_visuais=(
                    AtivoVisualExtraido(
                        origem=OrigemAtivoVisual.PICTURE_DOCLING,
                        conteudo_png=_gerar_png_bytes((10, 120, 200)),
                        ordem=0,
                        pagina=1,
                        bbox=BoundingBox(10.0, 20.0, 90.0, 80.0),
                    ),
                ),
            ),
            QuestaoExtraida(
                numero=11,
                enunciado="Questão 11 sobre protocolos de roteamento em redes.",
                paginas=(1,),
                alternativas=alternativas,
                ativos_visuais=(),
            ),
        )
        return ResultadoExtracaoProva(
            questoes=questoes,
            extracao_bruta_json='{"pages": [1]}',
            metadados=MetadadosIngestao(total_questoes_extraidas=2),
        )


class _FakeExtratorGabarito:
    def extrair(self, caminho_pdf: Path) -> ResultadoExtracaoGabarito:
        return ResultadoExtracaoGabarito(
            itens=(
                ItemGabaritoExtraido(10, TipoQuestao.OBJETIVA, Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.A)),
                ItemGabaritoExtraido(11, TipoQuestao.OBJETIVA, Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.C)),
            )
        )


def _semeia_taxonomia_e_perfil(
    session_factory: sessionmaker[Session],
    *,
    codigo_tax: str = "enade-ec",
    codigo_perfil: str = CODIGO_PERFIL_PADRAO,
    versao_perfil: str = VERSAO_PERFIL_PADRAO,
) -> tuple[Taxonomia, PerfilClassificacao]:
    repo_tax = RepositorioTaxonomiasSqlAlchemy(session_factory)
    repo_perfil = RepositorioPerfisClassificacaoSqlAlchemy(session_factory)
    tax = repo_tax.salvar(
        Taxonomia(
            codigo=codigo_tax,
            nome="ENADE Engenharia de Computação",
            curso_referencia="Engenharia de Computação",
            disciplinas=[
                Disciplina(codigo="algoritmos", nome="Algoritmos", ementa="Complexidade e grafos", ativa=True),
                Disciplina(codigo="redes", nome="Redes", ementa="Protocolos TCP/IP e roteamento", ativa=True),
                Disciplina(codigo="banco-de-dados", nome="Banco de Dados", ementa="SQL e normalização", ativa=True),
                Disciplina(codigo="legada", nome="Disciplina Legada", ementa="Ementa antiga", ativa=False),
            ],
        )
    )
    perfil = repo_perfil.salvar(
        PerfilClassificacao(
            codigo=codigo_perfil,
            versao=versao_perfil,
            diretrizes_gerais=DIRETRIZES_GERAIS_PADRAO,
            guia_fronteiras=GUIA_FRONTEIRAS_PADRAO,
            template_prompt=TEMPLATE_PROMPT_PADRAO,
            descricao=DESCRICAO_PERFIL_PADRAO,
        )
    )
    return tax, perfil


def test_execucao_e2e_escopos_e_snapshots_congelados(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    fake_llm = _FakeClassificadorMultimodal(
        {
            10: ResultadoChamada(
                dados_brutos={
                    "disciplina_principal": "algoritmos",
                    "disciplinas_secundarias": ["redes"],
                    "topicos": ["Grafos"],
                    "justificativa": "Q10 exige grafos e análise de tráfego.",
                    "confianca": 0.92,
                },
                prompt_tokens=150,
                completion_tokens=30,
                latencia_ms=5.0,
                from_cache=False,
                cache_key="q10-key",
            ),
            11: ResultadoChamada(
                dados_brutos={
                    "disciplina_principal": "redes",
                    "disciplinas_secundarias": [],
                    "topicos": ["OSPF"],
                    "justificativa": "Q11 trata de roteamento OSPF.",
                    "confianca": 0.88,
                },
                prompt_tokens=140,
                completion_tokens=25,
                latencia_ms=3.0,
                from_cache=True,
                cache_key="q11-key",
            ),
            12: ResultadoChamada(
                dados_brutos={
                    "disciplina_principal": "banco-de-dados",
                    "disciplinas_secundarias": [],
                    "topicos": ["SQL"],
                    "justificativa": "Q12 exige consulta SQL.",
                    "confianca": 0.95,
                },
                prompt_tokens=130,
                completion_tokens=20,
                latencia_ms=4.0,
                from_cache=False,
                cache_key="q12-key",
            ),
        }
    )
    assert isinstance(fake_llm, ClassificadorMultimodal)

    tax, perfil = _semeia_taxonomia_e_perfil(session_factory_teste)
    tax_outra = RepositorioTaxonomiasSqlAlchemy(session_factory_teste).salvar(
        Taxonomia(
            codigo="outra-tax",
            nome="Outra Taxonomia",
            disciplinas=[Disciplina(codigo="algoritmos", nome="Algoritmos")],
        )
    )
    tax_sem_ativas = RepositorioTaxonomiasSqlAlchemy(session_factory_teste).salvar(
        Taxonomia(
            codigo="tax-vazia",
            nome="Taxonomia Sem Ativas",
            disciplinas=[Disciplina(codigo="desativada", nome="Desativada", ativa=False)],
        )
    )

    repo_provas = RepositorioProvasSqlAlchemy(session_factory_teste)
    repo_questoes = RepositorioQuestoesSqlAlchemy(session_factory_teste)
    repo_classif = RepositorioClassificacoesSqlAlchemy(session_factory_teste)

    prova1 = repo_provas.salvar(
        Prova(exame="ENADE", curso="Engenharia de Computação", ano=2023, faixa_ce=FaixaQuestoes(10, 38))
    )
    prova2 = repo_provas.salvar(
        Prova(exame="ENADE", curso="Engenharia de Computação", ano=2019, faixa_ce=FaixaQuestoes(9, 35))
    )
    q10 = repo_questoes.salvar(
        Questao(prova_id=prova1.id, numero=10, enunciado="Enunciado Q10", alternativas=_alternativas_validas())
    )
    q11 = repo_questoes.salvar(
        Questao(prova_id=prova1.id, numero=11, enunciado="Enunciado Q11", alternativas=_alternativas_validas())
    )
    q12 = repo_questoes.salvar(
        Questao(prova_id=prova2.id, numero=12, enunciado="Enunciado Q12", alternativas=_alternativas_validas())
    )

    app = build_app(
        Settings(database_url=db_teste_url, data_dir=tmp_path / "app_data"),
        classificador=fake_llm,
    )

    with TestClient(app) as client:
        # Validações 404 e 422 antes de disparar
        assert (
            client.post(
                "/api/v1/execucoes-classificacao",
                json={"taxonomia_id": str(uuid4()), "perfil_id": str(perfil.id), "escopo": "todas"},
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/api/v1/execucoes-classificacao",
                json={"taxonomia_id": str(tax.id), "perfil_id": str(uuid4()), "escopo": "todas"},
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/api/v1/execucoes-classificacao",
                json={"taxonomia_id": str(tax_sem_ativas.id), "perfil_id": str(perfil.id), "escopo": "todas"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/execucoes-classificacao",
                json={"taxonomia_id": str(tax.id), "perfil_id": str(perfil.id), "escopo": "prova_id"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/execucoes-classificacao",
                json={"taxonomia_id": str(tax.id), "perfil_id": str(perfil.id), "escopo": "questao_ids"},
            ).status_code
            == 422
        )

        # 1. Escopo 'prova_id' -> 202 Accepted
        resp_post = client.post(
            "/api/v1/execucoes-classificacao",
            json={
                "taxonomia_id": str(tax.id),
                "perfil_id": str(perfil.id),
                "escopo": "prova_id",
                "prova_id": str(prova1.id),
            },
        )
        assert resp_post.status_code == 202
        aceita = resp_post.json()
        exec_prova1_id = UUID(aceita["execucao_id"])
        assert aceita["status"] == "pendente"
        assert aceita["total_itens"] == 2

        # Editar a taxonomia imediatamente (arquivar 'redes' + adicionar 'ia') NÃO deve quebrar o snapshot congelado
        redes_disc = next(d for d in tax.disciplinas if d.codigo == "redes")
        client.patch(f"/api/v1/disciplinas/{redes_disc.id}", json={"ativa": False})
        client.post(
            f"/api/v1/taxonomias/{tax.id}/disciplinas",
            json={"codigo": "ia", "nome": "Inteligência Artificial"},
        )

        app.state.worker.aguardar_ocioso(timeout=10.0)

        detalhe = client.get(f"/api/v1/execucoes-classificacao/{exec_prova1_id}").json()
        assert detalhe["status"] == "concluida"
        assert detalhe["total_itens"] == 2
        assert detalhe["processadas"] == 2
        assert detalhe["total_erros"] == 0
        assert detalhe["erros_por_questao"] == {}
        assert detalhe["divergencias_abertas"] == 0
        assert detalhe["cache_hits"] == 1
        assert detalhe["prompt_tokens"] == 290
        assert detalhe["completion_tokens"] == 55
        assert detalhe["snapshot_resumo"]["taxonomia"]["total_disciplinas"] == 3
        assert detalhe["snapshot_resumo"]["perfil"]["versao"] == VERSAO_PERFIL_PADRAO
        # Snapshot congelado continha apenas as 3 disciplinas ativas originais (sem 'legada' nem 'ia')
        codigos_snap = [d["codigo"] for d in detalhe["snapshot_taxonomia"]["disciplinas"]]
        assert codigos_snap == ["algoritmos", "redes", "banco-de-dados"]
        assert set(detalhe["questao_ids_alvo"]) == {str(q10.id), str(q11.id)}
        assert set(detalhe["questao_ids_concluidas"]) == {str(q10.id), str(q11.id)}

        # Classificações gravadas no PostgreSQL como automatica + pendente_revisao + vigente
        c10 = repo_classif.buscar_vigente(q10.id, tax.id)
        c11 = repo_classif.buscar_vigente(q11.id, tax.id)
        assert c10 is not None and c10.disciplina_principal == "algoritmos"
        assert c10.origem == OrigemClassificacao.AUTOMATICA
        assert c10.status == StatusClassificacao.PENDENTE_REVISAO
        assert c11 is not None and c11.disciplina_principal == "redes"

        # Reativa 'redes' e aprova Q10 para testar os demais escopos
        # ('pendentes', 'disciplina_arquivada', 'questao_ids', 'todas')
        c10.aprovar(datetime.now(UTC))
        repo_classif.salvar(c10)

        # Q10 tem secundária='redes' e Q11 tem principal='redes'; ao arquivar 'redes',
        # escopo 'disciplina_arquivada' deve mirar Q10 e Q11 (e não Q12)
        client.patch(f"/api/v1/disciplinas/{redes_disc.id}", json={"ativa": False})
        resp_arq = client.post(
            "/api/v1/execucoes-classificacao",
            json={
                "taxonomia_id": str(tax.id),
                "perfil_id": str(perfil.id),
                "escopo": "disciplina_arquivada",
            },
        )
        assert resp_arq.status_code == 202
        exec_arq_id = UUID(resp_arq.json()["execucao_id"])
        app.state.worker.aguardar_ocioso(timeout=10.0)
        det_arq = client.get(f"/api/v1/execucoes-classificacao/{exec_arq_id}").json()
        assert set(det_arq["questao_ids_alvo"]) == {str(q10.id), str(q11.id)}

        # Reativa 'redes' novamente para escopos seguintes
        client.patch(f"/api/v1/disciplinas/{redes_disc.id}", json={"ativa": True})

        # Escopo 'pendentes': Q10 já está aprovada -> deve mirar Q11 (pendente_revisao) e Q12 (sem classificação)
        resp_pend = client.post(
            "/api/v1/execucoes-classificacao",
            json={
                "taxonomia_id": str(tax.id),
                "perfil_id": str(perfil.id),
                "escopo": "pendentes",
            },
        )
        assert resp_pend.status_code == 202
        exec_pend_id = UUID(resp_pend.json()["execucao_id"])
        app.state.worker.aguardar_ocioso(timeout=10.0)
        det_pend = client.get(f"/api/v1/execucoes-classificacao/{exec_pend_id}").json()
        assert set(det_pend["questao_ids_alvo"]) == {str(q11.id), str(q12.id)}

        # Escopo 'questao_ids': mira somente Q12
        resp_qids = client.post(
            "/api/v1/execucoes-classificacao",
            json={
                "taxonomia_id": str(tax.id),
                "perfil_id": str(perfil.id),
                "escopo": "questao_ids",
                "questao_ids": [str(q12.id)],
            },
        )
        assert resp_qids.status_code == 202
        exec_qids_id = UUID(resp_qids.json()["execucao_id"])
        app.state.worker.aguardar_ocioso(timeout=10.0)
        det_qids = client.get(f"/api/v1/execucoes-classificacao/{exec_qids_id}").json()
        assert det_qids["questao_ids_alvo"] == [str(q12.id)]

        # Escopo 'todas': mira Q10, Q11 e Q12
        resp_todas = client.post(
            "/api/v1/execucoes-classificacao",
            json={
                "taxonomia_id": str(tax.id),
                "perfil_id": str(perfil.id),
                "escopo": "todas",
            },
        )
        assert resp_todas.status_code == 202
        exec_todas_id = UUID(resp_todas.json()["execucao_id"])
        app.state.worker.aguardar_ocioso(timeout=10.0)
        det_todas = client.get(f"/api/v1/execucoes-classificacao/{exec_todas_id}").json()
        assert set(det_todas["questao_ids_alvo"]) == {str(q10.id), str(q11.id), str(q12.id)}

        # GET /api/v1/execucoes-classificacao com e sem filtro taxonomia_id
        lista_todas = client.get("/api/v1/execucoes-classificacao").json()
        assert lista_todas["total"] == 5
        lista_filtrada = client.get(f"/api/v1/execucoes-classificacao?taxonomia_id={tax_outra.id}").json()
        assert lista_filtrada["total"] == 0
        assert client.get(f"/api/v1/execucoes-classificacao/{uuid4()}").status_code == 404


def test_incluir_revisadas_false_pula_aprovadas_e_true_abre_divergencia_seletiva(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    tax, perfil = _semeia_taxonomia_e_perfil(session_factory_teste)
    repo_provas = RepositorioProvasSqlAlchemy(session_factory_teste)
    repo_questoes = RepositorioQuestoesSqlAlchemy(session_factory_teste)
    repo_classif = RepositorioClassificacoesSqlAlchemy(session_factory_teste)
    repo_div = RepositorioDivergenciasReclassificacaoSqlAlchemy(session_factory_teste)

    prova = repo_provas.salvar(
        Prova(exame="ENADE", curso="Engenharia de Computação", ano=2023, faixa_ce=FaixaQuestoes(10, 38))
    )
    q10 = repo_questoes.salvar(
        Questao(prova_id=prova.id, numero=10, enunciado="Enunciado Q10.", alternativas=_alternativas_validas())
    )
    q11 = repo_questoes.salvar(
        Questao(prova_id=prova.id, numero=11, enunciado="Enunciado Q11.", alternativas=_alternativas_validas())
    )
    q12 = repo_questoes.salvar(
        Questao(prova_id=prova.id, numero=12, enunciado="Enunciado Q12.", alternativas=_alternativas_validas())
    )

    # Parte 1: incluir_revisadas = false
    c10_hum = repo_classif.salvar(
        Classificacao(
            questao_id=q10.id,
            taxonomia_id=tax.id,
            disciplina_principal="algoritmos",
            disciplinas_secundarias=("redes",),
            topicos=("Grafos",),
            justificativa="Aprovada por humano.",
            confianca=1.0,
            origem=OrigemClassificacao.HUMANA,
            status=StatusClassificacao.APROVADA,
            vigente=True,
        )
    )
    c11_pend = repo_classif.salvar(
        Classificacao(
            questao_id=q11.id,
            taxonomia_id=tax.id,
            disciplina_principal="redes",
            topicos=("HTTP",),
            justificativa="Sugestão antiga pendente.",
            confianca=0.6,
            origem=OrigemClassificacao.AUTOMATICA,
            status=StatusClassificacao.PENDENTE_REVISAO,
            vigente=True,
        )
    )
    # Q12 sem classificação

    fake_llm = _FakeClassificadorMultimodal(
        {
            10: {
                "disciplina_principal": "redes",
                "disciplinas_secundarias": [],
                "topicos": ["TCP"],
                "justificativa": "Não deve ser chamado quando incluir_revisadas=false.",
                "confianca": 0.99,
            },
            11: {
                "disciplina_principal": "algoritmos",
                "disciplinas_secundarias": ["redes"],
                "topicos": ["Ordenação"],
                "justificativa": "Nova classificação Q11.",
                "confianca": 0.9,
            },
            12: {
                "disciplina_principal": "banco-de-dados",
                "disciplinas_secundarias": [],
                "topicos": ["SQL"],
                "justificativa": "Classificação inicial Q12.",
                "confianca": 0.93,
            },
        }
    )

    app = build_app(
        Settings(database_url=db_teste_url, data_dir=tmp_path / "app_data"),
        classificador=fake_llm,
    )

    with TestClient(app) as client:
        resp_false = client.post(
            "/api/v1/execucoes-classificacao",
            json={
                "taxonomia_id": str(tax.id),
                "perfil_id": str(perfil.id),
                "escopo": "todas",
                "incluir_revisadas": False,
            },
        )
        assert resp_false.status_code == 202
        exec_false_id = UUID(resp_false.json()["execucao_id"])
        app.state.worker.aguardar_ocioso(timeout=10.0)

        # Q10 aprovada foi pulada sem chamar LLM
        assert len(fake_llm.chamadas) == 2
        assert all("QUESTÃO 10" not in c["user"] for c in fake_llm.chamadas)

        c10_atual = repo_classif.buscar_vigente(q10.id, tax.id)
        assert c10_atual is not None and c10_atual.id == c10_hum.id and c10_atual.vigente is True

        c11_antiga = repo_classif.buscar_por_id(c11_pend.id)
        c11_nova = repo_classif.buscar_vigente(q11.id, tax.id)
        assert c11_antiga is not None and c11_antiga.vigente is False
        assert c11_nova is not None and c11_nova.substitui_classificacao_id == c11_pend.id
        assert c11_nova.disciplina_principal == "algoritmos"

        c12_nova = repo_classif.buscar_vigente(q12.id, tax.id)
        assert c12_nova is not None and c12_nova.disciplina_principal == "banco-de-dados"
        assert client.get(f"/api/v1/execucoes-classificacao/{exec_false_id}").json()["divergencias_abertas"] == 0

        # Parte 2: incluir_revisadas = true com todas aprovadas
        # Q10: ('algoritmos', ('redes',)) -> LLM devolve mesma principal/secundárias -> SEM divergência
        # Q11: ('algoritmos', ('redes', 'banco-de-dados')) -> secundárias reordenadas -> SEM divergência
        # Q12: aprovada ('banco-de-dados', ()) -> LLM devolve principal 'redes' -> ABRE divergência
        c11_aprovada = repo_classif.registrar_substituicao(
            c11_nova,
            Classificacao(
                questao_id=q11.id,
                taxonomia_id=tax.id,
                substitui_classificacao_id=c11_nova.id,
                disciplina_principal="algoritmos",
                disciplinas_secundarias=("redes", "banco-de-dados"),
                topicos=("Grafos",),
                justificativa="Revisada por humano.",
                confianca=1.0,
                origem=OrigemClassificacao.HUMANA,
                status=StatusClassificacao.APROVADA,
                vigente=True,
            ),
        )
        c12_nova.aprovar(datetime.now(UTC))
        repo_classif.salvar(c12_nova)

        fake_llm.chamadas.clear()
        fake_llm.comportamento_por_numero = {
            10: {
                "disciplina_principal": "algoritmos",
                "disciplinas_secundarias": ["redes"],
                "topicos": ["Tópico Novo Concordante"],
                "justificativa": "Concorda com humana.",
                "confianca": 0.95,
            },
            11: {
                "disciplina_principal": "algoritmos",
                "disciplinas_secundarias": ["banco-de-dados", "redes"],
                "topicos": ["Índices em Grafos"],
                "justificativa": "Secundárias em outra ordem (mesmo conjunto).",
                "confianca": 0.89,
            },
            12: {
                "disciplina_principal": "redes",
                "disciplinas_secundarias": [],
                "topicos": ["DNS"],
                "justificativa": "Mudou a disciplina principal.",
                "confianca": 0.94,
            },
        }

        resp_true = client.post(
            "/api/v1/execucoes-classificacao",
            json={
                "taxonomia_id": str(tax.id),
                "perfil_id": str(perfil.id),
                "escopo": "todas",
                "incluir_revisadas": True,
            },
        )
        assert resp_true.status_code == 202
        exec_true_id = UUID(resp_true.json()["execucao_id"])
        app.state.worker.aguardar_ocioso(timeout=10.0)

        assert len(fake_llm.chamadas) == 3
        det_true = client.get(f"/api/v1/execucoes-classificacao/{exec_true_id}").json()
        assert det_true["status"] == "concluida"
        assert det_true["divergencias_abertas"] == 1

        # Todas as 3 vigentes humanas preservadas intactas
        assert repo_classif.buscar_vigente(q10.id, tax.id).id == c10_hum.id  # type: ignore[union-attr]
        assert repo_classif.buscar_vigente(q11.id, tax.id).id == c11_aprovada.id  # type: ignore[union-attr]
        assert repo_classif.buscar_vigente(q12.id, tax.id).id == c12_nova.id  # type: ignore[union-attr]

        # Histórico concordante gravado com vigente=False para Q10 e Q11
        hist_q10 = repo_classif.listar_historico(q10.id, tax.id)
        hist_q11 = repo_classif.listar_historico(q11.id, tax.id)
        assert any(h.execucao_id == exec_true_id and h.vigente is False for h in hist_q10)
        assert any(h.execucao_id == exec_true_id and h.vigente is False for h in hist_q11)

        # Apenas 1 Divergência aberta (para Q12)
        divs = repo_div.listar(taxonomia_id=tax.id, status=StatusDivergencia.ABERTA)
        assert len(divs) == 1
        assert divs[0].questao_id == q12.id
        assert divs[0].disciplina_principal_candidata == "redes"


def test_retomar_execucao_concluida_com_erros_e_interrompida(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    tax, perfil = _semeia_taxonomia_e_perfil(session_factory_teste)
    repo_provas = RepositorioProvasSqlAlchemy(session_factory_teste)
    repo_questoes = RepositorioQuestoesSqlAlchemy(session_factory_teste)
    repo_execucoes = RepositorioExecucoesClassificacaoSqlAlchemy(session_factory_teste)

    prova = repo_provas.salvar(
        Prova(exame="ENADE", curso="Engenharia de Computação", ano=2023, faixa_ce=FaixaQuestoes(10, 38))
    )
    q10 = repo_questoes.salvar(
        Questao(prova_id=prova.id, numero=10, enunciado="Enunciado Q10.", alternativas=_alternativas_validas())
    )
    q11 = repo_questoes.salvar(
        Questao(prova_id=prova.id, numero=11, enunciado="Enunciado Q11.", alternativas=_alternativas_validas())
    )
    q12 = repo_questoes.salvar(
        Questao(prova_id=prova.id, numero=12, enunciado="Enunciado Q12.", alternativas=_alternativas_validas())
    )

    fake_llm = _FakeClassificadorMultimodal(
        {
            11: ErroClassificadorLLMError("Timeout simulado no LLM para Q11."),
        }
    )

    app = build_app(
        Settings(database_url=db_teste_url, data_dir=tmp_path / "app_data"),
        classificador=fake_llm,
    )

    with TestClient(app) as client:
        # 1. Execução com falha parcial em Q11 -> concluida_com_erros
        resp_post = client.post(
            "/api/v1/execucoes-classificacao",
            json={"taxonomia_id": str(tax.id), "perfil_id": str(perfil.id), "escopo": "todas"},
        )
        assert resp_post.status_code == 202
        exec_id = UUID(resp_post.json()["execucao_id"])
        app.state.worker.aguardar_ocioso(timeout=10.0)

        det_erro = client.get(f"/api/v1/execucoes-classificacao/{exec_id}").json()
        assert det_erro["status"] == "concluida_com_erros"
        assert det_erro["processadas"] == 3
        assert det_erro["total_erros"] == 1
        assert str(q11.id) in det_erro["erros_por_questao"]
        assert set(det_erro["questao_ids_concluidas"]) == {str(q10.id), str(q12.id)}

        # Corrige resposta de Q11 e retoma -> processa SOMENTE Q11
        fake_llm.chamadas.clear()
        fake_llm.comportamento_por_numero[11] = {
            "disciplina_principal": "redes",
            "disciplinas_secundarias": [],
            "topicos": ["TCP"],
            "justificativa": "Q11 retomada com sucesso.",
            "confianca": 0.9,
        }

        resp_retomar = client.post(f"/api/v1/execucoes-classificacao/{exec_id}/retomar")
        assert resp_retomar.status_code == 202
        assert resp_retomar.json()["status"] == "pendente"
        app.state.worker.aguardar_ocioso(timeout=10.0)

        assert len(fake_llm.chamadas) == 1
        assert "QUESTÃO 11" in fake_llm.chamadas[0]["user"]

        det_ok = client.get(f"/api/v1/execucoes-classificacao/{exec_id}").json()
        assert det_ok["status"] == "concluida"
        assert det_ok["total_erros"] == 0
        assert det_ok["erros_por_questao"] == {}
        assert det_ok["processadas"] == 3
        assert set(det_ok["questao_ids_concluidas"]) == {str(q10.id), str(q11.id), str(q12.id)}

        # Retomar execução em estados não retomáveis (concluida, pendente, processando, erro) -> 409;
        # ID inexistente -> 404
        assert client.post(f"/api/v1/execucoes-classificacao/{exec_id}/retomar").status_code == 409
        assert client.post(f"/api/v1/execucoes-classificacao/{uuid4()}/retomar").status_code == 404

        for status_nao_retomavel in (
            StatusExecucaoClassificacao.PENDENTE,
            StatusExecucaoClassificacao.PROCESSANDO,
            StatusExecucaoClassificacao.ERRO,
        ):
            exec_nao_retomavel = repo_execucoes.salvar(
                ExecucaoClassificacao(
                    taxonomia_id=tax.id,
                    perfil_id=perfil.id,
                    snapshot_taxonomia=tax.snapshot_dict(),
                    snapshot_perfil=perfil.snapshot_dict(),
                    escopo=EscopoExecucao.TODAS,
                    status=status_nao_retomavel,
                )
            )
            assert client.post(f"/api/v1/execucoes-classificacao/{exec_nao_retomavel.id}/retomar").status_code == 409

        # 2. Execução em estado 'interrompida' -> retoma processando somente pendentes
        exec_interrompida = repo_execucoes.salvar(
            ExecucaoClassificacao(
                taxonomia_id=tax.id,
                perfil_id=perfil.id,
                snapshot_taxonomia=tax.snapshot_dict(),
                snapshot_perfil=perfil.snapshot_dict(),
                escopo=EscopoExecucao.TODAS,
                status=StatusExecucaoClassificacao.INTERROMPIDA,
                total_itens=2,
                processadas=1,
                questao_ids_alvo=(q10.id, q11.id),
                questao_ids_concluidas=(q10.id,),
            )
        )
        fake_llm.chamadas.clear()
        resp_retomar_int = client.post(f"/api/v1/execucoes-classificacao/{exec_interrompida.id}/retomar")
        assert resp_retomar_int.status_code == 202
        app.state.worker.aguardar_ocioso(timeout=10.0)

        assert len(fake_llm.chamadas) == 1
        assert "QUESTÃO 11" in fake_llm.chamadas[0]["user"]
        det_int = client.get(f"/api/v1/execucoes-classificacao/{exec_interrompida.id}").json()
        assert det_int["status"] == "concluida"
        assert set(det_int["questao_ids_concluidas"]) == {str(q10.id), str(q11.id)}


def test_encadeamento_pos_ingestao_e_isolamento_falha_llm(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    tax, perfil_padrao = _semeia_taxonomia_e_perfil(session_factory_teste)
    repo_perfil = RepositorioPerfisClassificacaoSqlAlchemy(session_factory_teste)
    perfil_alt = repo_perfil.salvar(
        PerfilClassificacao(
            codigo="custom",
            versao="v1",
            diretrizes_gerais=DIRETRIZES_GERAIS_PADRAO,
            guia_fronteiras=GUIA_FRONTEIRAS_PADRAO,
            template_prompt=TEMPLATE_PROMPT_PADRAO,
            descricao="Perfil alternativo explícito",
        )
    )
    repo_questoes = RepositorioQuestoesSqlAlchemy(session_factory_teste)
    repo_classif = RepositorioClassificacoesSqlAlchemy(session_factory_teste)

    fake_llm = _FakeClassificadorMultimodal(
        {
            10: {
                "disciplina_principal": "algoritmos",
                "disciplinas_secundarias": [],
                "topicos": ["Grafos"],
                "justificativa": "Q10 encadeada com ativo visual.",
                "confianca": 0.92,
            },
            11: {
                "disciplina_principal": "redes",
                "disciplinas_secundarias": [],
                "topicos": ["Roteamento"],
                "justificativa": "Q11 encadeada.",
                "confianca": 0.89,
            },
        }
    )

    app = build_app(
        Settings(database_url=db_teste_url, data_dir=tmp_path / "app_data"),
        extrator_prova=_FakeExtratorProva(),
        extrator_gabarito=_FakeExtratorGabarito(),
        classificador=fake_llm,
    )
    pdf_bytes = _gerar_pdf_bytes_valido(1)

    with TestClient(app) as client:
        # 1. Caminho feliz: POST /api/v1/provas com taxonomia_id (usa perfil padrão v2-fronteiras:v1)
        resp_ok = client.post(
            "/api/v1/provas",
            data={
                "exame": "ENADE",
                "curso": "Engenharia de Computação",
                "ano": "2023",
                "taxonomia_id": str(tax.id),
            },
            files={
                "arquivo_prova": ("prova_2023.pdf", pdf_bytes, "application/pdf"),
                "arquivo_gabarito": ("gab_2023.pdf", b"%PDF-1.4 gab", "application/pdf"),
            },
        )
        assert resp_ok.status_code == 202
        prova_ok_id = UUID(resp_ok.json()["prova_id"])
        app.state.worker.aguardar_ocioso(timeout=10.0)

        det_ok = client.get(f"/api/v1/provas/{prova_ok_id}").json()
        assert det_ok["ultima_ingestao"]["status"] == "concluida"
        assert det_ok["questoes"]["total"] == 2
        exec_encadeada_id = det_ok["classificacao_encadeada"]["execucao_id"]
        assert exec_encadeada_id is not None

        det_exec_ok = client.get(f"/api/v1/execucoes-classificacao/{exec_encadeada_id}").json()
        assert det_exec_ok["status"] == "concluida"
        assert det_exec_ok["perfil_id"] == str(perfil_padrao.id)
        assert det_exec_ok["processadas"] == 2

        # Confirma que a imagem PNG do AtivoVisual da Q10 foi enviada ao ClassificadorMultimodal
        chamada_q10 = next(c for c in fake_llm.chamadas if "QUESTÃO 10" in c["user"])
        assert len(chamada_q10["imagens_png"]) == 1
        assert bytes(chamada_q10["imagens_png"][0]).startswith(b"\x89PNG\r\n\x1a\n")

        questoes_ok = {q.numero: q for q in repo_questoes.listar_por_prova(prova_ok_id)}
        assert repo_classif.buscar_vigente(questoes_ok[10].id, tax.id).disciplina_principal == "algoritmos"  # type: ignore[union-attr]
        assert repo_classif.buscar_vigente(questoes_ok[11].id, tax.id).disciplina_principal == "redes"  # type: ignore[union-attr]

        # 2. Falha simulada do LLM NÃO invalida Prova, Questões nem Ingestão(concluida)
        fake_llm.chamadas.clear()
        fake_llm.falhar_sempre = ErroClassificadorLLMError("Provedor LLM indisponível.")

        resp_falha_llm = client.post(
            "/api/v1/provas",
            data={
                "exame": "ENADE",
                "curso": "Engenharia de Computação",
                "ano": "2019",
                "questao_inicio": "9",
                "questao_fim": "35",
                "taxonomia_id": str(tax.id),
                "perfil_id": str(perfil_alt.id),
            },
            files={"arquivo_prova": ("prova_2019.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp_falha_llm.status_code == 202
        prova_falha_id = UUID(resp_falha_llm.json()["prova_id"])
        app.state.worker.aguardar_ocioso(timeout=10.0)

        det_prova_falha = client.get(f"/api/v1/provas/{prova_falha_id}").json()
        assert det_prova_falha["ultima_ingestao"]["status"] == "concluida"
        assert det_prova_falha["questoes"]["total"] == 2
        exec_falha_id = det_prova_falha["classificacao_encadeada"]["execucao_id"]
        assert exec_falha_id is not None

        questoes_preservadas = repo_questoes.listar_por_prova(prova_falha_id)
        assert len(questoes_preservadas) == 2

        det_exec_falha = client.get(f"/api/v1/execucoes-classificacao/{exec_falha_id}").json()
        assert det_exec_falha["perfil_id"] == str(perfil_alt.id)
        assert det_exec_falha["status"] == "concluida_com_erros"
        assert det_exec_falha["total_erros"] == 2


def test_snapshot_resumo_tolera_campos_null_e_disciplinas_nao_sequencia(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    tax, perfil = _semeia_taxonomia_e_perfil(session_factory_teste)
    repo_execucoes = RepositorioExecucoesClassificacaoSqlAlchemy(session_factory_teste)

    exec_int_disciplinas = repo_execucoes.salvar(
        ExecucaoClassificacao(
            taxonomia_id=tax.id,
            perfil_id=perfil.id,
            snapshot_taxonomia={
                "id": str(tax.id),
                "codigo": None,
                "nome": None,
                "curso_referencia": None,
                "disciplinas": 123,
            },
            snapshot_perfil={
                "id": str(perfil.id),
                "codigo": None,
                "versao": None,
                "descricao": None,
            },
            escopo=EscopoExecucao.TODAS,
            status=StatusExecucaoClassificacao.CONCLUIDA,
        )
    )
    exec_str_disciplinas = repo_execucoes.salvar(
        ExecucaoClassificacao(
            taxonomia_id=tax.id,
            perfil_id=perfil.id,
            snapshot_taxonomia={
                "id": str(tax.id),
                "codigo": "enade-ec",
                "nome": "ENADE EC",
                "curso_referencia": None,
                "disciplinas": "texto-nao-lista",
            },
            snapshot_perfil={
                "id": str(perfil.id),
                "codigo": "v2-fronteiras",
                "versao": "v1",
                "descricao": None,
            },
            escopo=EscopoExecucao.TODAS,
            status=StatusExecucaoClassificacao.CONCLUIDA,
        )
    )

    resumo_direto = _serializar_snapshot_resumo(exec_int_disciplinas)
    assert resumo_direto.taxonomia.codigo == ""
    assert resumo_direto.taxonomia.nome == ""
    assert resumo_direto.taxonomia.curso_referencia == ""
    assert resumo_direto.taxonomia.total_disciplinas == 0
    assert resumo_direto.taxonomia.disciplinas_codigos == []
    assert resumo_direto.perfil.codigo == ""
    assert resumo_direto.perfil.versao == ""
    assert resumo_direto.perfil.descricao == ""

    app = build_app(
        Settings(database_url=db_teste_url, data_dir=tmp_path / "app_data"),
        classificador=_FakeClassificadorMultimodal(),
    )

    with TestClient(app) as client:
        resp_detalhe_int = client.get(f"/api/v1/execucoes-classificacao/{exec_int_disciplinas.id}")
        assert resp_detalhe_int.status_code == 200
        snap_int = resp_detalhe_int.json()["snapshot_resumo"]
        assert snap_int["taxonomia"]["codigo"] == ""
        assert snap_int["taxonomia"]["nome"] == ""
        assert snap_int["taxonomia"]["curso_referencia"] == ""
        assert snap_int["taxonomia"]["total_disciplinas"] == 0
        assert snap_int["taxonomia"]["disciplinas_codigos"] == []
        assert snap_int["perfil"]["codigo"] == ""
        assert snap_int["perfil"]["versao"] == ""
        assert snap_int["perfil"]["descricao"] == ""

        resp_detalhe_str = client.get(f"/api/v1/execucoes-classificacao/{exec_str_disciplinas.id}")
        assert resp_detalhe_str.status_code == 200
        snap_str = resp_detalhe_str.json()["snapshot_resumo"]
        assert snap_str["taxonomia"]["curso_referencia"] == ""
        assert snap_str["taxonomia"]["total_disciplinas"] == 0
        assert snap_str["taxonomia"]["disciplinas_codigos"] == []
        assert snap_str["perfil"]["descricao"] == ""

        resp_lista = client.get("/api/v1/execucoes-classificacao")
        assert resp_lista.status_code == 200
        assert resp_lista.json()["total"] == 2
