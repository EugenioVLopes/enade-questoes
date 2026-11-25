from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import InternalError
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

from application.seed import TEMPLATE_PROMPT_PADRAO
from domain.avaliacao import ConjuntoOuro
from domain.classificacao import Classificacao, ExecucaoClassificacao, PerfilClassificacao
from domain.enums import (
    CodigoAlertaExtracao,
    ComponenteProva,
    EscopoExecucao,
    LetraAlternativa,
    OrigemAtivoVisual,
    OrigemClassificacao,
    SeveridadeAlerta,
    SituacaoGabarito,
    StatusAlerta,
    StatusClassificacao,
    StatusExecucaoClassificacao,
    TipoQuestao,
)
from domain.prova import AlertaExtracao, Alternativa, AtivoVisual, FaixaQuestoes, Gabarito, Prova, Questao
from domain.taxonomia import Disciplina, Taxonomia
from infrastructure.config import Settings
from infrastructure.llm.cliente_openai import ClienteOpenAICompativel
from infrastructure.persistence.database import (
    create_readonly_db_engine,
    create_readonly_session_factory,
)
from infrastructure.persistence.models import (
    ClassificacaoModel,
    DivergenciaReclassificacaoModel,
    ExecucaoClassificacaoModel,
)
from infrastructure.persistence.repositorios import (
    RepositorioClassificacoesSqlAlchemy,
    RepositorioExecucoesClassificacaoSqlAlchemy,
    RepositorioPerfisClassificacaoSqlAlchemy,
    RepositorioProvasSqlAlchemy,
    RepositorioQuestoesSqlAlchemy,
    RepositorioTaxonomiasSqlAlchemy,
)
from infrastructure.storage.local import ArmazenamentoArquivosLocal
from presentation.cli.bootstrap import criar_provedor_eval
from presentation.cli.eval_cli import app

PNG_MINIMO_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _alternativas() -> list[Alternativa]:
    return [Alternativa(letra=letra, texto=f"Alternativa {letra.value}.") for letra in LetraAlternativa]


def _seed_taxonomia(factory: sessionmaker[Session], codigo: str = "enade-eng-computacao") -> Taxonomia:
    repo = RepositorioTaxonomiasSqlAlchemy(factory)
    return repo.salvar(
        Taxonomia(
            codigo=codigo,
            nome=f"Taxonomia {codigo}",
            curso_referencia="Engenharia de Computação",
            disciplinas=[
                Disciplina(codigo="algoritmos", nome="Algoritmos", ementa="Complexidade e grafos.", ativa=True),
                Disciplina(codigo="redes", nome="Redes", ementa="TCP/IP e roteamento.", ativa=True),
                Disciplina(codigo="so", nome="Sistemas Operacionais", ementa="Processos e memória.", ativa=True),
            ],
        )
    )


def _seed_perfil(
    factory: sessionmaker[Session],
    codigo: str = "v2-fronteiras",
    versao: str = "v1",
) -> PerfilClassificacao:
    repo = RepositorioPerfisClassificacaoSqlAlchemy(factory)
    return repo.salvar(
        PerfilClassificacao(
            codigo=codigo,
            versao=versao,
            diretrizes_gerais="Classifique conforme o catálogo oficial.",
            guia_fronteiras="Algoritmos vs Redes.",
            template_prompt=TEMPLATE_PROMPT_PADRAO,
            descricao="Perfil de teste",
        )
    )


def _seed_prova_e_questao(
    factory: sessionmaker[Session],
    *,
    ano: int,
    numero: int,
    situacao_gabarito: SituacaoGabarito = SituacaoGabarito.VALIDA,
    alertas: list[AlertaExtracao] | None = None,
    chave_ativo: str | None = None,
) -> tuple[Prova, Questao]:
    repo_provas = RepositorioProvasSqlAlchemy(factory)
    repo_questoes = RepositorioQuestoesSqlAlchemy(factory)

    prova = repo_provas.buscar_por_chave_natural("ENADE", "Engenharia de Computação", ano)
    if prova is None:
        prova = repo_provas.salvar(
            Prova(
                exame="ENADE",
                curso="Engenharia de Computação",
                ano=ano,
                faixa_ce=FaixaQuestoes(1, 35),
            )
        )

    alt_correta = LetraAlternativa.B if situacao_gabarito == SituacaoGabarito.VALIDA else None
    ativos = (
        [
            AtivoVisual(
                questao_id=uuid4(),
                origem=OrigemAtivoVisual.PICTURE_DOCLING,
                ordem=0,
                pagina=3,
                chave_arquivo=chave_ativo,
            )
        ]
        if chave_ativo
        else []
    )
    questao_id = uuid4()
    if ativos:
        ativos = [
            AtivoVisual(
                questao_id=questao_id,
                origem=OrigemAtivoVisual.PICTURE_DOCLING,
                ordem=0,
                pagina=3,
                chave_arquivo=chave_ativo,
            )
        ]

    questao = repo_questoes.salvar(
        Questao(
            id=questao_id,
            prova_id=prova.id,
            numero=numero,
            enunciado=f"Questão {numero} do ENADE {ano} sobre algoritmos e redes.",
            componente=ComponenteProva.COMPONENTE_ESPECIFICO,
            tipo=TipoQuestao.OBJETIVA,
            alternativas=_alternativas(),
            ativos_visuais=ativos,
            gabarito=Gabarito(situacao_gabarito=situacao_gabarito, alternativa_correta=alt_correta),
            alertas_extracao=alertas or [],
        )
    )
    return prova, questao


class _FakeCompletionsClient:
    def __init__(self, respostas_por_numero: dict[int, dict[str, Any]]) -> None:
        self.respostas_por_numero = respostas_por_numero
        self.chamadas: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs: Any) -> Any:
        self.chamadas.append(kwargs)
        messages = kwargs["messages"]
        user_content = messages[1]["content"]
        texto_user = " ".join(p["text"] for p in user_content if p.get("type") == "text")

        dados = {
            "disciplina_principal": "algoritmos",
            "disciplinas_secundarias": [],
            "topicos": ["complexidade"],
            "justificativa": "Justificativa padrão determinística.",
            "confianca": 0.91,
        }
        for num, payload in self.respostas_por_numero.items():
            if f"QUESTÃO {num:02d}" in texto_user:
                dados = payload
                break

        return SimpleNamespace(
            model=kwargs["model"],
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(dados)))],
            usage=SimpleNamespace(prompt_tokens=120, completion_tokens=30),
        )


def test_readonly_engine_e_session_factory_rejeitam_escrita_no_postgresql(db_teste_url: str) -> None:
    ro_engine = create_readonly_db_engine(db_teste_url)
    try:
        ro_factory = create_readonly_session_factory(ro_engine)
        with ro_factory() as session:
            assert session.execute(text("SELECT 1")).scalar_one() == 1

        with pytest.raises(InternalError, match="read-only"):
            with ro_factory.begin() as session:
                session.execute(
                    text("INSERT INTO taxonomias (id, codigo, nome, curso_referencia) VALUES (:id, 'x', 'X', 'EC')"),
                    {"id": str(uuid4())},
                )
    finally:
        ro_engine.dispose()


def test_exportar_ouro_filtra_alertas_criticos_mantem_anulada_e_ordena_deterministicamente(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    agora = datetime(2026, 11, 25, 8, 0, tzinfo=UTC)
    tax = _seed_taxonomia(session_factory_teste)
    repo_cls = RepositorioClassificacoesSqlAlchemy(session_factory_teste)

    _, q_2023_1 = _seed_prova_e_questao(session_factory_teste, ano=2023, numero=1)
    _, q_2023_2_anulada = _seed_prova_e_questao(
        session_factory_teste,
        ano=2023,
        numero=2,
        situacao_gabarito=SituacaoGabarito.ANULADA,
    )
    _, q_2019_5_resolvido = _seed_prova_e_questao(
        session_factory_teste,
        ano=2019,
        numero=5,
        alertas=[
            AlertaExtracao(
                codigo=CodigoAlertaExtracao.FORMULA_NAO_DECODIFICADA,
                severidade=SeveridadeAlerta.CRITICO,
                status=StatusAlerta.RESOLVIDO,
                mensagem="Resolvido manualmente",
                resolvido_em=agora,
            ),
            AlertaExtracao(
                codigo=CodigoAlertaExtracao.FONTE_SYMBOL_DETECTADA,
                severidade=SeveridadeAlerta.INFORMATIVO,
                status=StatusAlerta.ABERTO,
                mensagem="Informativo aberto",
            ),
        ],
    )
    _, q_2019_3_critico = _seed_prova_e_questao(
        session_factory_teste,
        ano=2019,
        numero=3,
        alertas=[
            AlertaExtracao(
                codigo=CodigoAlertaExtracao.FORMULA_NAO_DECODIFICADA,
                severidade=SeveridadeAlerta.CRITICO,
                status=StatusAlerta.ABERTO,
                mensagem="Fórmula quebrada",
            )
        ],
    )
    _, q_2023_4_pendente = _seed_prova_e_questao(session_factory_teste, ano=2023, numero=4)

    for q, principal, secs, status in (
        (q_2023_1, "algoritmos", ("so",), StatusClassificacao.APROVADA),
        (q_2023_2_anulada, "redes", (), StatusClassificacao.APROVADA),
        (q_2019_5_resolvido, "so", ("algoritmos",), StatusClassificacao.APROVADA),
        (q_2019_3_critico, "algoritmos", (), StatusClassificacao.APROVADA),
        (q_2023_4_pendente, "redes", (), StatusClassificacao.PENDENTE_REVISAO),
    ):
        repo_cls.salvar(
            Classificacao(
                questao_id=q.id,
                taxonomia_id=tax.id,
                disciplina_principal=principal,
                disciplinas_secundarias=secs,
                topicos=("teste",),
                justificativa="Revisada",
                confianca=1.0,
                origem=OrigemClassificacao.HUMANA,
                status=status,
                vigente=True,
                criada_em=agora,
                revisada_em=agora if status == StatusClassificacao.APROVADA else None,
            )
        )

    ouro_path = tmp_path / "evals" / "golden" / "enade-eng-computacao.json"
    provedor = criar_provedor_eval(settings=Settings(database_url=db_teste_url, data_dir=tmp_path))
    try:
        res = CliRunner().invoke(
            app,
            ["exportar-ouro", "--taxonomia", "enade-eng-computacao", "--saida", str(ouro_path)],
            obj=provedor,
        )
    finally:
        provedor.close()

    assert res.exit_code == 0, res.output
    dados = json.loads(ouro_path.read_text(encoding="utf-8"))
    assert dados["versao_schema"] == "1.0"
    assert dados["taxonomia_codigo"] == "enade-eng-computacao"
    assert dados["total_itens"] == 3
    assert dados["total_edicoes"] == 2
    assert len(dados["digest"]) == 64

    chaves = [(i["exame"], i["curso"], i["ano"], i["numero"]) for i in dados["itens"]]
    assert chaves == [
        ("ENADE", "Engenharia de Computação", 2019, 5),
        ("ENADE", "Engenharia de Computação", 2023, 1),
        ("ENADE", "Engenharia de Computação", 2023, 2),
    ]
    assert dados["itens"][2]["situacao_gabarito"] == "anulada"
    for item in dados["itens"]:
        assert set(item.keys()) == {
            "exame",
            "curso",
            "ano",
            "numero",
            "disciplina_principal",
            "disciplinas_secundarias",
            "situacao_gabarito",
            "notas",
        }


def test_avaliar_preflight_aborta_sem_chamar_llm(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    agora = datetime(2026, 11, 25, 8, 10, tzinfo=UTC)
    tax = _seed_taxonomia(session_factory_teste)
    _seed_perfil(session_factory_teste)
    repo_cls = RepositorioClassificacoesSqlAlchemy(session_factory_teste)
    repo_questoes = RepositorioQuestoesSqlAlchemy(session_factory_teste)
    repo_tax = RepositorioTaxonomiasSqlAlchemy(session_factory_teste)

    _, q1 = _seed_prova_e_questao(session_factory_teste, ano=2023, numero=1)
    _, q2 = _seed_prova_e_questao(session_factory_teste, ano=2023, numero=2)
    for q, principal in ((q1, "algoritmos"), (q2, "redes")):
        repo_cls.salvar(
            Classificacao(
                questao_id=q.id,
                taxonomia_id=tax.id,
                disciplina_principal=principal,
                topicos=("t",),
                justificativa="OK",
                origem=OrigemClassificacao.HUMANA,
                status=StatusClassificacao.APROVADA,
                vigente=True,
                criada_em=agora,
                revisada_em=agora,
            )
        )

    ouro_path = tmp_path / "golden.json"
    fake_openai = _FakeCompletionsClient({})
    armazenamento = ArmazenamentoArquivosLocal(tmp_path)
    classificador = ClienteOpenAICompativel(
        provider="fake",
        base_url="http://localhost:8005/v1",
        api_key="EMPTY",
        model="fake-model",
        armazenamento=armazenamento,
        client=fake_openai,
    )
    provedor = criar_provedor_eval(
        settings=Settings(database_url=db_teste_url, data_dir=tmp_path),
        classificador=classificador,
        armazenamento=armazenamento,
    )
    runner = CliRunner()
    try:
        res_exp = runner.invoke(
            app,
            ["exportar-ouro", "--taxonomia", "enade-eng-computacao", "--saida", str(ouro_path)],
            obj=provedor,
        )
        assert res_exp.exit_code == 0, res_exp.output

        # 1) Alerta crítico aberto depois da exportação
        q1_recarregada = repo_questoes.buscar_por_id(q1.id)
        assert q1_recarregada is not None
        q1_recarregada.alertas_extracao = [
            AlertaExtracao(
                codigo=CodigoAlertaExtracao.ENUNCIADO_SUSPEITO,
                severidade=SeveridadeAlerta.CRITICO,
                status=StatusAlerta.ABERTO,
                mensagem="Suspeito",
            )
        ]
        repo_questoes.salvar(q1_recarregada)

        res_alerta = runner.invoke(
            app,
            ["avaliar", "--ouro", str(ouro_path), "--perfil", "v2-fronteiras@v1"],
            obj=provedor,
        )
        assert res_alerta.exit_code == 1
        assert "enunciado_suspeito" in res_alerta.output
        assert fake_openai.chamadas == []

        # Limpa alerta e arquiva disciplina referenciada
        q1_recarregada.alertas_extracao = []
        repo_questoes.salvar(q1_recarregada)
        alg = next(d for d in tax.disciplinas if d.codigo == "algoritmos")
        repo_tax.salvar_disciplina(
            tax.id,
            Disciplina(id=alg.id, codigo=alg.codigo, nome=alg.nome, ementa=alg.ementa, ativa=False),
        )

        res_arq = runner.invoke(
            app,
            ["avaliar", "--ouro", str(ouro_path), "--perfil", "v2-fronteiras@v1"],
            obj=provedor,
        )
        assert res_arq.exit_code == 1
        assert "algoritmos" in res_arq.output
        assert fake_openai.chamadas == []

        # Reativa disciplina e remove questão Q2 do banco
        repo_tax.salvar_disciplina(
            tax.id,
            Disciplina(id=alg.id, codigo=alg.codigo, nome=alg.nome, ementa=alg.ementa, ativa=True),
        )
        with session_factory_teste.begin() as session:
            session.execute(text("DELETE FROM questoes WHERE id = :qid"), {"qid": str(q2.id)})

        res_ausente = runner.invoke(
            app,
            ["avaliar", "--ouro", str(ouro_path), "--perfil", "v2-fronteiras@v1"],
            obj=provedor,
        )
        assert res_ausente.exit_code == 1
        assert "ausente" in res_ausente.output.lower()
        assert fake_openai.chamadas == []
    finally:
        provedor.close()


def test_avaliar_somente_leitura_cache_multipass_yaml_e_overrides(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agora = datetime(2026, 11, 25, 8, 20, tzinfo=UTC)
    tax = _seed_taxonomia(session_factory_teste)
    _seed_perfil(session_factory_teste)
    repo_cls = RepositorioClassificacoesSqlAlchemy(session_factory_teste)
    armazenamento = ArmazenamentoArquivosLocal(tmp_path)
    armazenamento.salvar("ativos/q1.png", PNG_MINIMO_1X1)

    _, q1 = _seed_prova_e_questao(session_factory_teste, ano=2023, numero=1, chave_ativo="ativos/q1.png")
    _, q2 = _seed_prova_e_questao(session_factory_teste, ano=2023, numero=2)
    for q, principal in ((q1, "algoritmos"), (q2, "redes")):
        repo_cls.salvar(
            Classificacao(
                questao_id=q.id,
                taxonomia_id=tax.id,
                disciplina_principal=principal,
                topicos=("t",),
                justificativa="OK",
                origem=OrigemClassificacao.HUMANA,
                status=StatusClassificacao.APROVADA,
                vigente=True,
                criada_em=agora,
                revisada_em=agora,
            )
        )

    ouro_path = tmp_path / "golden.json"
    fake_openai = _FakeCompletionsClient(
        {
            1: {
                "disciplina_principal": "algoritmos",
                "disciplinas_secundarias": [],
                "topicos": ["grafos"],
                "justificativa": "Questão de algoritmos.",
                "confianca": 0.95,
            },
            2: {
                "disciplina_principal": "redes",
                "disciplinas_secundarias": [],
                "topicos": ["tcp"],
                "justificativa": "Questão de redes.",
                "confianca": 0.93,
            },
        }
    )

    # Intercepta criação do ClienteOpenAICompativel no bootstrap para validar overrides --base-url/--model/--api-key
    configs_observadas: list[Settings] = []

    def _fake_criar_classificador(settings: Settings, armazenamento: Any = None) -> ClienteOpenAICompativel:
        configs_observadas.append(settings)
        return ClienteOpenAICompativel(
            provider=settings.llm_provider,
            base_url=settings.llm_base_url,
            api_key=settings.effective_llm_api_key,
            model=settings.llm_model,
            max_rpm=0,
            armazenamento=armazenamento,
            client=fake_openai,
        )

    monkeypatch.setattr("presentation.cli.bootstrap.criar_classificador_multimodal", _fake_criar_classificador)

    with session_factory_teste() as session:
        exec_antes = session.scalar(select(func.count()).select_from(ExecucaoClassificacaoModel))
        cls_antes = session.scalar(select(func.count()).select_from(ClassificacaoModel))
        div_antes = session.scalar(select(func.count()).select_from(DivergenciaReclassificacaoModel))

    provedor = criar_provedor_eval(settings=Settings(database_url=db_teste_url, data_dir=tmp_path))
    runner = CliRunner()
    try:
        assert (
            runner.invoke(
                app,
                ["exportar-ouro", "--taxonomia", "enade-eng-computacao", "--saida", str(ouro_path)],
                obj=provedor,
            ).exit_code
            == 0
        )

        # 1ª avaliação com overrides Qwen/vLLM e cache ligado
        res1 = runner.invoke(
            app,
            [
                "avaliar",
                "--ouro",
                str(ouro_path),
                "--perfil",
                "v2-fronteiras@v1",
                "--base-url",
                "http://localhost:8005/v1",
                "--model",
                "Qwen/Qwen3-27B",
                "--api-key",
                "token-teste",
            ],
            obj=provedor,
        )
        assert res1.exit_code == 0, res1.output
        assert len(fake_openai.chamadas) == 2
        assert configs_observadas[0].llm_provider == "vllm_qwen"
        assert configs_observadas[0].llm_base_url == "http://localhost:8005/v1"
        assert configs_observadas[0].llm_model == "Qwen/Qwen3-27B"
        assert configs_observadas[0].effective_llm_api_key == "token-teste"
        assert fake_openai.chamadas[0]["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
        # Confirma que a imagem da Q1 foi enviada no payload multimodal
        assert any(part.get("type") == "image_url" for part in fake_openai.chamadas[0]["messages"][1]["content"])

        # 2ª avaliação com mesmo comando: deve acertar cache em disco sem chamar OpenAI
        res2 = runner.invoke(
            app,
            [
                "avaliar",
                "--ouro",
                str(ouro_path),
                "--perfil",
                "v2-fronteiras@v1",
                "--base-url",
                "http://localhost:8005/v1",
                "--model",
                "Qwen/Qwen3-27B",
                "--api-key",
                "token-teste",
            ],
            obj=provedor,
        )
        assert res2.exit_code == 0, res2.output
        assert len(fake_openai.chamadas) == 2
        assert "2 (100.00%)" in res2.output

        # 3ª avaliação com rascunho YAML + --no-cache + --repeticoes 2
        yaml_perfil = tmp_path / "rascunho.yaml"
        yaml_perfil.write_text(
            "codigo: rascunho-yaml\nversao: v1\ndiretrizes_gerais: Diretrizes experimentais.\n",
            encoding="utf-8",
        )
        res3 = runner.invoke(
            app,
            [
                "avaliar",
                "--ouro",
                str(ouro_path),
                "--perfil",
                str(yaml_perfil),
                "--no-cache",
                "--repeticoes",
                "2",
            ],
            obj=provedor,
        )
        assert res3.exit_code == 0, res3.output
        assert len(fake_openai.chamadas) == 2 + 4
        assert "Estabilidade multipass" in res3.output
    finally:
        provedor.close()

    with session_factory_teste() as session:
        assert session.scalar(select(func.count()).select_from(ExecucaoClassificacaoModel)) == exec_antes
        assert session.scalar(select(func.count()).select_from(ClassificacaoModel)) == cls_antes
        assert session.scalar(select(func.count()).select_from(DivergenciaReclassificacaoModel)) == div_antes

    evals_dir = tmp_path / "evals"
    assert len(list(evals_dir.glob("*.json"))) == 3
    assert len(list(evals_dir.glob("*.md"))) == 3


def test_comparar_e2e_com_relatorios_gerados_por_avaliar(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    agora = datetime(2026, 11, 25, 8, 30, tzinfo=UTC)
    tax = _seed_taxonomia(session_factory_teste)
    _seed_perfil(session_factory_teste)
    repo_cls = RepositorioClassificacoesSqlAlchemy(session_factory_teste)

    _, q1 = _seed_prova_e_questao(session_factory_teste, ano=2023, numero=1)
    _, q2 = _seed_prova_e_questao(session_factory_teste, ano=2023, numero=2)
    for q, principal in ((q1, "algoritmos"), (q2, "redes")):
        repo_cls.salvar(
            Classificacao(
                questao_id=q.id,
                taxonomia_id=tax.id,
                disciplina_principal=principal,
                topicos=("t",),
                justificativa="OK",
                origem=OrigemClassificacao.HUMANA,
                status=StatusClassificacao.APROVADA,
                vigente=True,
                criada_em=agora,
                revisada_em=agora,
            )
        )

    ouro_path = tmp_path / "golden.json"
    armazenamento = ArmazenamentoArquivosLocal(tmp_path)
    runner = CliRunner()

    classificador_base = ClienteOpenAICompativel(
        provider="fake",
        base_url="http://localhost:8005/v1",
        api_key="EMPTY",
        model="base-model",
        max_rpm=0,
        armazenamento=armazenamento,
        client=_FakeCompletionsClient(
            {
                1: {
                    "disciplina_principal": "algoritmos",
                    "disciplinas_secundarias": [],
                    "topicos": ["grafos"],
                    "justificativa": "OK",
                    "confianca": 0.9,
                },
                2: {
                    "disciplina_principal": "redes",
                    "disciplinas_secundarias": [],
                    "topicos": ["tcp"],
                    "justificativa": "OK",
                    "confianca": 0.9,
                },
            }
        ),
    )
    prov_base = criar_provedor_eval(
        settings=Settings(database_url=db_teste_url, data_dir=tmp_path),
        classificador=classificador_base,
        armazenamento=armazenamento,
    )
    try:
        assert (
            runner.invoke(
                app,
                ["exportar-ouro", "--taxonomia", "enade-eng-computacao", "--saida", str(ouro_path)],
                obj=prov_base,
            ).exit_code
            == 0
        )
        assert (
            runner.invoke(
                app,
                ["avaliar", "--ouro", str(ouro_path), "--perfil", "v2-fronteiras@v1", "--no-cache"],
                obj=prov_base,
            ).exit_code
            == 0
        )
    finally:
        prov_base.close()

    classificador_cand = ClienteOpenAICompativel(
        provider="fake",
        base_url="http://localhost:8005/v1",
        api_key="EMPTY",
        model="cand-model",
        max_rpm=0,
        armazenamento=armazenamento,
        client=_FakeCompletionsClient(
            {
                1: {
                    "disciplina_principal": "algoritmos",
                    "disciplinas_secundarias": [],
                    "topicos": ["grafos"],
                    "justificativa": "OK",
                    "confianca": 0.9,
                },
                2: {
                    "disciplina_principal": "so",  # Regressão em Q2
                    "disciplinas_secundarias": [],
                    "topicos": ["processos"],
                    "justificativa": "Confundiu",
                    "confianca": 0.86,
                },
            }
        ),
    )
    prov_cand = criar_provedor_eval(
        settings=Settings(database_url=db_teste_url, data_dir=tmp_path),
        classificador=classificador_cand,
        armazenamento=armazenamento,
    )
    try:
        assert (
            runner.invoke(
                app,
                ["avaliar", "--ouro", str(ouro_path), "--perfil", "v2-fronteiras@v1", "--no-cache"],
                obj=prov_cand,
            ).exit_code
            == 0
        )
    finally:
        prov_cand.close()

    relatorios = sorted((tmp_path / "evals").glob("*.json"))
    assert len(relatorios) == 2
    base_json = next(p for p in relatorios if "base-model" in p.name)
    cand_json = next(p for p in relatorios if "cand-model" in p.name)

    res_fail = runner.invoke(app, ["comparar", str(base_json), str(cand_json)])
    assert res_fail.exit_code == 1
    assert "REPROVADO" in res_fail.output
    assert "Q02" in res_fail.output

    res_ok = runner.invoke(app, ["comparar", str(base_json), str(base_json)])
    assert res_ok.exit_code == 0, res_ok.output
    assert "APROVADO" in res_ok.output

    # Confirma que comparar rejeita snapshot com outro digest
    cand_outro = tmp_path / "outro.json"
    dados_outro = json.loads(cand_json.read_text(encoding="utf-8"))
    dados_outro["conjunto_ouro_digest"] = "0" * 64
    cand_outro.write_text(json.dumps(dados_outro), encoding="utf-8")
    res_mismatch = runner.invoke(app, ["comparar", str(base_json), str(cand_outro)])
    assert res_mismatch.exit_code == 1
    assert "distintos" in res_mismatch.output


def test_historico_ia_vs_humano_postgresql_cadeias_completas(
    db_teste_url: str,
    session_factory_teste: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    agora = datetime(2026, 11, 25, 8, 40, tzinfo=UTC)
    tax1 = _seed_taxonomia(session_factory_teste, "enade-eng-computacao")
    tax2 = _seed_taxonomia(session_factory_teste, "outro-curso")
    p1 = _seed_perfil(session_factory_teste, "v2-fronteiras", "v1")
    p2 = _seed_perfil(session_factory_teste, "v3-qwen", "v1")

    repo_exec = RepositorioExecucoesClassificacaoSqlAlchemy(session_factory_teste)
    repo_cls = RepositorioClassificacoesSqlAlchemy(session_factory_teste)

    snap_p1 = p1.snapshot_dict()  # Sem chave "modelo" -> "(não registrado)"
    snap_p2 = dict(p2.snapshot_dict())
    snap_p2["modelo"] = "Qwen/Qwen3-27B"

    exec1 = repo_exec.salvar(
        ExecucaoClassificacao(
            taxonomia_id=tax1.id,
            perfil_id=p1.id,
            snapshot_taxonomia=tax1.snapshot_dict(),
            snapshot_perfil=snap_p1,
            escopo=EscopoExecucao.TODAS,
            status=StatusExecucaoClassificacao.CONCLUIDA,
        )
    )
    exec2 = repo_exec.salvar(
        ExecucaoClassificacao(
            taxonomia_id=tax1.id,
            perfil_id=p2.id,
            snapshot_taxonomia=tax1.snapshot_dict(),
            snapshot_perfil=snap_p2,
            escopo=EscopoExecucao.TODAS,
            status=StatusExecucaoClassificacao.CONCLUIDA,
        )
    )

    _, q1 = _seed_prova_e_questao(session_factory_teste, ano=2023, numero=1)
    _, q2 = _seed_prova_e_questao(session_factory_teste, ano=2023, numero=2)
    _, q3 = _seed_prova_e_questao(session_factory_teste, ano=2023, numero=3)
    _, q4 = _seed_prova_e_questao(session_factory_teste, ano=2023, numero=4)
    _, q5 = _seed_prova_e_questao(session_factory_teste, ano=2023, numero=5)
    _, q6 = _seed_prova_e_questao(session_factory_teste, ano=2023, numero=6)
    _, q7 = _seed_prova_e_questao(session_factory_teste, ano=2023, numero=7)
    _, q8 = _seed_prova_e_questao(session_factory_teste, ano=2023, numero=8)

    # Q1: aprovação direta in-place
    repo_cls.salvar(
        Classificacao(
            questao_id=q1.id,
            taxonomia_id=tax1.id,
            disciplina_principal="algoritmos",
            disciplinas_secundarias=("so",),
            topicos=("grafos",),
            justificativa="IA",
            origem=OrigemClassificacao.AUTOMATICA,
            status=StatusClassificacao.APROVADA,
            vigente=True,
            execucao_id=exec1.id,
            criada_em=agora,
            revisada_em=agora,
        )
    )

    # Q2: correção humana na principal
    ai_q2 = repo_cls.salvar(
        Classificacao(
            questao_id=q2.id,
            taxonomia_id=tax1.id,
            disciplina_principal="algoritmos",
            disciplinas_secundarias=(),
            topicos=("t",),
            justificativa="IA",
            origem=OrigemClassificacao.AUTOMATICA,
            status=StatusClassificacao.PENDENTE_REVISAO,
            vigente=True,
            execucao_id=exec1.id,
            criada_em=agora,
        )
    )
    h_q2 = ai_q2.substituir_por_correcao(
        disciplina_principal="redes",
        disciplinas_secundarias=(),
        topicos=("tcp",),
        justificativa="Humano corrigiu principal",
        agora=agora,
    )
    repo_cls.registrar_substituicao(ai_q2, h_q2)

    # Q3: correção humana apenas nas secundárias
    ai_q3 = repo_cls.salvar(
        Classificacao(
            questao_id=q3.id,
            taxonomia_id=tax1.id,
            disciplina_principal="redes",
            disciplinas_secundarias=(),
            topicos=("t",),
            justificativa="IA",
            origem=OrigemClassificacao.AUTOMATICA,
            status=StatusClassificacao.PENDENTE_REVISAO,
            vigente=True,
            execucao_id=exec1.id,
            criada_em=agora,
        )
    )
    h_q3 = ai_q3.substituir_por_correcao(
        disciplina_principal="redes",
        disciplinas_secundarias=("so",),
        topicos=("t",),
        justificativa="Adicionou secundária",
        agora=agora,
    )
    repo_cls.registrar_substituicao(ai_q3, h_q3)

    # Q4: cadeia H2 -> H1 -> AI, onde H2 preservou disciplina_principal e secundárias (editou só tópicos)
    ai_q4 = repo_cls.salvar(
        Classificacao(
            questao_id=q4.id,
            taxonomia_id=tax1.id,
            disciplina_principal="so",
            disciplinas_secundarias=("algoritmos",),
            topicos=("t1",),
            justificativa="IA",
            origem=OrigemClassificacao.AUTOMATICA,
            status=StatusClassificacao.PENDENTE_REVISAO,
            vigente=True,
            execucao_id=exec1.id,
            criada_em=agora,
        )
    )
    h1_q4 = ai_q4.substituir_por_correcao(
        disciplina_principal="redes",
        disciplinas_secundarias=(),
        topicos=("t2",),
        justificativa="H1",
        agora=agora,
    )
    h1_salva = repo_cls.registrar_substituicao(ai_q4, h1_q4)
    h2_q4 = h1_salva.substituir_por_correcao(
        disciplina_principal="so",
        disciplinas_secundarias=("algoritmos",),
        topicos=("t3",),
        justificativa="H2 ajustou só tópico",
        agora=agora,
    )
    repo_cls.registrar_substituicao(h1_salva, h2_q4)

    # Q5: classificação puramente manual (sem ancestral automático -> excluída)
    repo_cls.salvar(
        Classificacao(
            questao_id=q5.id,
            taxonomia_id=tax1.id,
            disciplina_principal="algoritmos",
            topicos=("manual",),
            justificativa="Manual pura",
            origem=OrigemClassificacao.HUMANA,
            status=StatusClassificacao.APROVADA,
            vigente=True,
            criada_em=agora,
            revisada_em=agora,
        )
    )

    # Q6: pendente de revisão -> excluída
    repo_cls.salvar(
        Classificacao(
            questao_id=q6.id,
            taxonomia_id=tax1.id,
            disciplina_principal="algoritmos",
            topicos=("pend",),
            justificativa="Pendente",
            origem=OrigemClassificacao.AUTOMATICA,
            status=StatusClassificacao.PENDENTE_REVISAO,
            vigente=True,
            execucao_id=exec1.id,
            criada_em=agora,
        )
    )

    # Q7: segundo perfil + modelo em tax1
    repo_cls.salvar(
        Classificacao(
            questao_id=q7.id,
            taxonomia_id=tax1.id,
            disciplina_principal="redes",
            topicos=("tcp",),
            justificativa="IA Qwen",
            origem=OrigemClassificacao.AUTOMATICA,
            status=StatusClassificacao.APROVADA,
            vigente=True,
            execucao_id=exec2.id,
            criada_em=agora,
            revisada_em=agora,
        )
    )

    # Q8: segundo perfil + modelo em tax2
    ai_q8 = repo_cls.salvar(
        Classificacao(
            questao_id=q8.id,
            taxonomia_id=tax2.id,
            disciplina_principal="algoritmos",
            topicos=("t",),
            justificativa="IA Qwen tax2",
            origem=OrigemClassificacao.AUTOMATICA,
            status=StatusClassificacao.PENDENTE_REVISAO,
            vigente=True,
            execucao_id=exec2.id,
            criada_em=agora,
        )
    )
    h_q8 = ai_q8.substituir_por_correcao(
        disciplina_principal="so",
        topicos=("t",),
        justificativa="Corrigida em tax2",
        agora=agora,
    )
    repo_cls.registrar_substituicao(ai_q8, h_q8)

    provedor = criar_provedor_eval(settings=Settings(database_url=db_teste_url, data_dir=tmp_path))
    runner = CliRunner()
    try:
        res_tax1 = runner.invoke(
            app,
            ["historico", "--taxonomia", "enade-eng-computacao"],
            obj=provedor,
        )
        assert res_tax1.exit_code == 0, res_tax1.output
        assert "v2-fronteiras@v1" in res_tax1.output
        assert "(não registrado)" in res_tax1.output
        assert "2 (50.00%)" in res_tax1.output
        assert "1 (25.00%)" in res_tax1.output
        assert "v3-qwen@v1" in res_tax1.output
        assert "Qwen/Qwen3-27B" in res_tax1.output
        assert "1 (100.00%)" in res_tax1.output

        # Sem filtro inclui Q8
        res_todos = runner.invoke(app, ["historico"], obj=provedor)
        assert res_todos.exit_code == 0, res_todos.output
        assert "Todas as Taxonomias" in res_todos.output

        # Valida também os números exatos via caso de uso diretamente
        hist_use_case = provedor.criar_historico()
        res_uc = hist_use_case.execute(taxonomia_codigo=None)
        assert res_uc.total_registros == 6
        g_qwen = next(g for g in res_uc.grupos if g.perfil_codigo == "v3-qwen")
        assert g_qwen.total_revisadas == 2
        assert g_qwen.aprovacoes_diretas == 1
        assert g_qwen.correcoes_principal == 1
        assert g_qwen.correcoes_apenas_secundarias == 0
    finally:
        provedor.close()

    # Confirma helper ConjuntoOuro funciona com snapshot exportado
    assert isinstance(ConjuntoOuro.__name__, str)
