from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from application.ports import (
    RepositorioAtivosVisuais,
    RepositorioClassificacoes,
    RepositorioDivergenciasReclassificacao,
    RepositorioExecucoesClassificacao,
    RepositorioIngestoes,
    RepositorioPerfisClassificacao,
    RepositorioProvas,
    RepositorioQuestoes,
    RepositorioTaxonomias,
)
from domain.classificacao import (
    Classificacao,
    DivergenciaReclassificacao,
    ExecucaoClassificacao,
    PerfilClassificacao,
)
from domain.enums import (
    CodigoAlertaExtracao,
    EscopoExecucao,
    LetraAlternativa,
    OrigemAtivoVisual,
    OrigemClassificacao,
    ResolucaoDivergencia,
    SituacaoGabarito,
    StatusAlerta,
    StatusClassificacao,
    StatusDivergencia,
    StatusExecucaoClassificacao,
    StatusIngestao,
    TipoQuestao,
)
from domain.exceptions import ErroInvarianteDominio, ErroValidacaoDominio
from domain.prova import (
    AlertaExtracao,
    Alternativa,
    AtivoVisual,
    BoundingBox,
    FaixaQuestoes,
    Gabarito,
    Ingestao,
    MetadadosIngestao,
    Prova,
    Questao,
)
from domain.taxonomia import Disciplina, Taxonomia
from infrastructure.persistence import (
    RepositorioAtivosVisuaisSqlAlchemy,
    RepositorioClassificacoesSqlAlchemy,
    RepositorioDivergenciasReclassificacaoSqlAlchemy,
    RepositorioExecucoesClassificacaoSqlAlchemy,
    RepositorioIngestoesSqlAlchemy,
    RepositorioPerfisClassificacaoSqlAlchemy,
    RepositorioProvasSqlAlchemy,
    RepositorioQuestoesSqlAlchemy,
    RepositorioTaxonomiasSqlAlchemy,
    create_db_engine,
)
from tests.integration.conftest import construir_alembic_config

TABELAS_ESPERADAS = {
    "provas",
    "ingestoes",
    "questoes",
    "alternativas",
    "ativos_visuais",
    "alertas_extracao",
    "taxonomias",
    "disciplinas",
    "perfis_classificacao",
    "execucoes_classificacao",
    "classificacoes",
    "divergencias_reclassificacao",
}


def _criar_contexto_classificacao(
    session_factory: sessionmaker[Session],
) -> tuple[Prova, Questao, Taxonomia, PerfilClassificacao, ExecucaoClassificacao]:
    repo_provas = RepositorioProvasSqlAlchemy(session_factory)
    repo_questoes = RepositorioQuestoesSqlAlchemy(session_factory)
    repo_tax = RepositorioTaxonomiasSqlAlchemy(session_factory)
    repo_perfis = RepositorioPerfisClassificacaoSqlAlchemy(session_factory)
    repo_exec = RepositorioExecucoesClassificacaoSqlAlchemy(session_factory)

    prova = repo_provas.salvar(Prova(exame="ENADE", curso="Engenharia de Computação", ano=2023))
    questao = repo_questoes.salvar(
        Questao(
            prova_id=prova.id,
            numero=10,
            enunciado="Questão base para classificação.",
            alternativas=[Alternativa(LetraAlternativa.A, "Opção A"), Alternativa(LetraAlternativa.B, "Opção B")],
            gabarito=Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.A),
        )
    )
    taxonomia = repo_tax.salvar(
        Taxonomia(
            codigo="enade-ec",
            nome="ENADE EC",
            curso_referencia="Engenharia de Computação",
            disciplinas=[
                Disciplina("redes-e-comunicacoes", "Redes", "OSPF e TCP/IP"),
                Disciplina("algoritmos-e-estruturas-de-dados", "Algoritmos", "Complexidade e grafos"),
                Disciplina("sistemas-operacionais", "Sistemas Operacionais", "Escalonamento"),
            ],
        )
    )
    perfil = repo_perfis.salvar(
        PerfilClassificacao(
            codigo="perfil-teste",
            versao="v1",
            diretrizes_gerais="Classifique com precisão.",
            guia_fronteiras="Redes x Algoritmos",
            template_prompt="Questão: {enunciado}",
        )
    )
    execucao = repo_exec.salvar(
        ExecucaoClassificacao(
            taxonomia_id=taxonomia.id,
            perfil_id=perfil.id,
            snapshot_taxonomia=taxonomia.snapshot_dict(),
            snapshot_perfil=perfil.snapshot_dict(),
            escopo=EscopoExecucao.TODAS,
        )
    )
    return prova, questao, taxonomia, perfil, execucao


def test_repositorios_concretos_satisfazem_protocolos_de_aplicacao(
    session_factory_teste: sessionmaker[Session],
) -> None:
    pares = (
        (RepositorioProvasSqlAlchemy(session_factory_teste), RepositorioProvas),
        (RepositorioIngestoesSqlAlchemy(session_factory_teste), RepositorioIngestoes),
        (RepositorioQuestoesSqlAlchemy(session_factory_teste), RepositorioQuestoes),
        (RepositorioAtivosVisuaisSqlAlchemy(session_factory_teste), RepositorioAtivosVisuais),
        (RepositorioTaxonomiasSqlAlchemy(session_factory_teste), RepositorioTaxonomias),
        (RepositorioPerfisClassificacaoSqlAlchemy(session_factory_teste), RepositorioPerfisClassificacao),
        (RepositorioExecucoesClassificacaoSqlAlchemy(session_factory_teste), RepositorioExecucoesClassificacao),
        (RepositorioClassificacoesSqlAlchemy(session_factory_teste), RepositorioClassificacoes),
        (
            RepositorioDivergenciasReclassificacaoSqlAlchemy(session_factory_teste),
            RepositorioDivergenciasReclassificacao,
        ),
    )
    for instancia, protocolo in pares:
        assert isinstance(instancia, protocolo)


def test_alembic_downgrade_base_e_upgrade_head_em_postgresql_16_limpo(db_teste_url: str) -> None:
    cfg = construir_alembic_config(db_teste_url)
    command.downgrade(cfg, "base")

    engine = create_db_engine(db_teste_url)
    try:
        with engine.connect() as conn:
            tabelas_apos_downgrade = {
                row[0]
                for row in conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).fetchall()
            }
            assert TABELAS_ESPERADAS.isdisjoint(tabelas_apos_downgrade)

        command.upgrade(cfg, "head")

        with engine.connect() as conn:
            extensoes = {row[0] for row in conn.execute(text("SELECT extname FROM pg_extension")).fetchall()}
            assert {"unaccent", "pg_trgm"}.issubset(extensoes)

            ts_configs = {
                row[0]
                for row in conn.execute(
                    text("SELECT cfgname FROM pg_ts_config WHERE cfgname = 'pt_unaccent'")
                ).fetchall()
            }
            assert ts_configs == {"pt_unaccent"}

            tabelas = {
                row[0]
                for row in conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).fetchall()
            }
            assert TABELAS_ESPERADAS.issubset(tabelas)
    finally:
        engine.dispose()


def test_repositorio_provas_e_unicidade_chave_natural(session_factory_teste: sessionmaker[Session]) -> None:
    repo = RepositorioProvasSqlAlchemy(session_factory_teste)

    prova = Prova(
        exame="enade",
        curso="Engenharia de Computação",
        ano=2025,
        faixa_ce=FaixaQuestoes(12, 40),
        caminho_pdf="storage/provas/2025/prova.pdf",
    )
    salva = repo.salvar(prova)
    assert salva.faixa_ce == FaixaQuestoes(12, 40)

    encontrada = repo.buscar_por_chave_natural("  ENADE ", "Engenharia de Computação", 2025)
    assert encontrada is not None
    assert encontrada.id == prova.id
    assert encontrada.faixa_ce == FaixaQuestoes(12, 40)

    assert repo.buscar_por_id(prova.id) is not None
    assert len(repo.listar()) == 1

    duplicada_case = Prova(
        exame="ENADE",
        curso="Engenharia de Computação",
        ano=2025,
        faixa_ce=FaixaQuestoes(12, 40),
    )
    with pytest.raises(IntegrityError):
        repo.salvar(duplicada_case)


def test_repositorio_ingestoes_e_interrupcao_em_lote(session_factory_teste: sessionmaker[Session]) -> None:
    repo_provas = RepositorioProvasSqlAlchemy(session_factory_teste)
    repo_ing = RepositorioIngestoesSqlAlchemy(session_factory_teste)
    prova = repo_provas.salvar(Prova(exame="ENADE", curso="Engenharia de Computação", ano=2023))

    t0 = datetime(2026, 11, 21, 10, 0, tzinfo=UTC)
    ing_concluida = Ingestao(prova_id=prova.id, criada_em=t0)
    ing_concluida.iniciar(t0)
    ing_concluida.concluir(
        t0 + timedelta(seconds=10),
        MetadadosIngestao(
            total_questoes_extraidas=29,
            imagens_detectadas=4,
            imagens_filtradas_margem=1,
            formulas_recortadas=2,
            usou_ocr=False,
            paginas_fonte_symbol=(3, 7),
            gabarito_enviado=True,
        ),
    )
    repo_ing.salvar(ing_concluida)

    ing_processando = Ingestao(prova_id=prova.id, criada_em=t0 + timedelta(minutes=1))
    ing_processando.iniciar(t0 + timedelta(minutes=1))
    repo_ing.salvar(ing_processando)

    ultima = repo_ing.buscar_ultima_por_prova(prova.id)
    assert ultima is not None
    assert ultima.id == ing_processando.id
    assert len(repo_ing.listar_por_prova(prova.id)) == 2

    interrompidas = repo_ing.marcar_em_processamento_como_interrompidas(
        t0 + timedelta(minutes=2),
        "Worker reiniciado após queda.",
    )
    assert interrompidas == 1

    ing_proc_atualizada = repo_ing.buscar_por_id(ing_processando.id)
    ing_conc_atualizada = repo_ing.buscar_por_id(ing_concluida.id)
    assert ing_proc_atualizada is not None
    assert ing_proc_atualizada.status == StatusIngestao.INTERROMPIDA
    assert ing_proc_atualizada.mensagem_erro == "Worker reiniciado após queda."
    assert ing_conc_atualizada is not None
    assert ing_conc_atualizada.status == StatusIngestao.CONCLUIDA
    assert ing_conc_atualizada.metadados.paginas_fonte_symbol == (3, 7)


def test_repositorios_questoes_e_ativos_visuais_reconciliacao_e_constraints(
    session_factory_teste: sessionmaker[Session],
) -> None:
    repo_provas = RepositorioProvasSqlAlchemy(session_factory_teste)
    repo_questoes = RepositorioQuestoesSqlAlchemy(session_factory_teste)
    repo_ativos = RepositorioAtivosVisuaisSqlAlchemy(session_factory_teste)

    prova = repo_provas.salvar(Prova(exame="ENADE", curso="Engenharia de Computação", ano=2023))
    agora = datetime(2026, 11, 21, 11, 0, tzinfo=UTC)

    q10 = Questao(
        prova_id=prova.id,
        numero=10,
        enunciado="Enunciado inicial da questão 10.",
        tipo=TipoQuestao.OBJETIVA,
        paginas=(5, 6),
        alternativas=[
            Alternativa(LetraAlternativa.A, "Alternativa A inicial"),
            Alternativa(LetraAlternativa.B, "Alternativa B inicial"),
        ],
        ativos_visuais=[
            AtivoVisual(
                origem=OrigemAtivoVisual.PICTURE_DOCLING,
                ordem=0,
                pagina=5,
                bbox=BoundingBox(0.1, 0.2, 0.8, 0.6),
                chave_arquivo="storage/provas/p/ativos/1.png",
            )
        ],
        gabarito=Gabarito(SituacaoGabarito.PENDENTE),
        alertas_extracao=[
            AlertaExtracao(
                codigo=CodigoAlertaExtracao.ALTERNATIVAS_INCOMPLETAS,
                mensagem="Faltam alternativas C, D, E",
            )
        ],
    )
    q11 = Questao(
        prova_id=prova.id,
        numero=11,
        enunciado="Questão 11 anulada.",
        paginas=(7,),
        gabarito=Gabarito(SituacaoGabarito.ANULADA),
    )

    salvas = repo_questoes.salvar_lote([q10, q11])
    assert [q.numero for q in salvas] == [10, 11]
    assert repo_questoes.buscar_por_prova_e_numero(prova.id, 10) is not None
    assert len(repo_questoes.listar_por_prova(prova.id)) == 2

    # Edição manual substitui alternativas por novas instâncias (novos UUIDs) e resolve alerta
    q10.editar_conteudo(
        enunciado="Enunciado corrigido manualmente.",
        alternativas=[
            Alternativa(LetraAlternativa.A, "Nova A"),
            Alternativa(LetraAlternativa.B, "Nova B"),
            Alternativa(LetraAlternativa.C, "Nova C"),
        ],
        gabarito=Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.C),
    )
    q10.alertas_extracao[0].resolver(agora)
    q10_atualizada = repo_questoes.salvar(q10)
    assert q10_atualizada.editada_manualmente is True
    assert q10_atualizada.gabarito == Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.C)
    assert [a.letra for a in q10_atualizada.alternativas] == [
        LetraAlternativa.A,
        LetraAlternativa.B,
        LetraAlternativa.C,
    ]
    assert q10_atualizada.alertas_extracao[0].status == StatusAlerta.RESOLVIDO

    # AtivoVisual standalone requer questao_id
    ativo_sem_questao = AtivoVisual(origem=OrigemAtivoVisual.UPLOAD_MANUAL, ordem=1)
    with pytest.raises(ErroValidacaoDominio):
        repo_ativos.salvar(ativo_sem_questao)

    ativo_manual = AtivoVisual(
        origem=OrigemAtivoVisual.UPLOAD_MANUAL,
        ordem=1,
        alternativa_letra=LetraAlternativa.C,
        chave_arquivo=f"storage/provas/{prova.id}/ativos/manual.png",
        questao_id=q10.id,
    )
    repo_ativos.salvar(ativo_manual)
    ativos_q10 = repo_ativos.listar_por_questao(q10.id)
    assert len(ativos_q10) == 2
    assert ativos_q10[1].id == ativo_manual.id
    repo_ativos.remover(ativo_manual.id)
    assert repo_ativos.buscar_por_id(ativo_manual.id) is None

    # Unicidade (prova_id, numero) no banco
    with pytest.raises(IntegrityError):
        repo_questoes.salvar(Questao(prova_id=prova.id, numero=10, enunciado="Duplicada"))


def test_repositorios_taxonomia_perfil_e_execucao_snapshots_congelados(
    session_factory_teste: sessionmaker[Session],
) -> None:
    _, questao, taxonomia, perfil, execucao = _criar_contexto_classificacao(session_factory_teste)
    repo_tax = RepositorioTaxonomiasSqlAlchemy(session_factory_teste)
    repo_perfis = RepositorioPerfisClassificacaoSqlAlchemy(session_factory_teste)
    repo_exec = RepositorioExecucoesClassificacaoSqlAlchemy(session_factory_teste)
    repo_class = RepositorioClassificacoesSqlAlchemy(session_factory_teste)

    # Ordem das disciplinas preservada
    tax_lida = repo_tax.buscar_por_codigo("enade-ec")
    assert tax_lida is not None
    assert [d.codigo for d in tax_lida.disciplinas] == [
        "redes-e-comunicacoes",
        "algoritmos-e-estruturas-de-dados",
        "sistemas-operacionais",
    ]
    assert len(repo_tax.listar()) == 1

    # Perfil imutável e unicidade (codigo, versao)
    assert repo_perfis.buscar_por_codigo_e_versao("perfil-teste", "v1") is not None
    assert len(repo_perfis.listar()) == 1
    with pytest.raises(IntegrityError):
        repo_perfis.salvar(
            PerfilClassificacao(
                codigo="perfil-teste",
                versao="v1",
                diretrizes_gerais="Outro",
                guia_fronteiras="",
                template_prompt="Outro",
            )
        )
    perfil_alterado = PerfilClassificacao(
        id=perfil.id,
        codigo=perfil.codigo,
        versao=perfil.versao,
        diretrizes_gerais="Alterada",
        guia_fronteiras=perfil.guia_fronteiras,
        template_prompt=perfil.template_prompt,
    )
    with pytest.raises(ErroInvarianteDominio):
        repo_perfis.salvar(perfil_alterado)

    # ExecucaoClassificacao com MappingProxyType e frozenset descongelados em JSONB
    agora = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
    exec_congelada = ExecucaoClassificacao(
        taxonomia_id=taxonomia.id,
        perfil_id=perfil.id,
        snapshot_taxonomia=MappingProxyType({"tags": frozenset({"b", "a"}), "itens": (1, 2)}),
        snapshot_perfil=perfil.snapshot_dict(),
        escopo=EscopoExecucao.PENDENTES,
        status=StatusExecucaoClassificacao.PROCESSANDO,
        iniciada_em=agora,
    )
    repo_exec.salvar(exec_congelada)
    exec_lida = repo_exec.buscar_por_id(exec_congelada.id)
    assert exec_lida is not None
    assert isinstance(exec_lida.snapshot_taxonomia, MappingProxyType)
    assert exec_lida.snapshot_taxonomia["tags"] == ("a", "b")
    assert len(repo_exec.listar()) == 2

    interrompidas = repo_exec.marcar_em_processamento_como_interrompidas(agora + timedelta(minutes=5))
    assert interrompidas == 1
    exec_interrompida = repo_exec.buscar_por_id(exec_congelada.id)
    assert exec_interrompida is not None
    assert exec_interrompida.status == StatusExecucaoClassificacao.INTERROMPIDA

    # Contagem de classificações vigentes (principal OU secundária)
    repo_class.salvar(
        Classificacao(
            questao_id=questao.id,
            taxonomia_id=taxonomia.id,
            disciplina_principal="redes-e-comunicacoes",
            disciplinas_secundarias=("algoritmos-e-estruturas-de-dados",),
            topicos=("roteamento-ospf",),
            justificativa="Usa OSPF com algoritmo de Dijkstra.",
            confianca=0.92,
            vigente=True,
            execucao_id=execucao.id,
        )
    )
    repo_class.salvar(
        Classificacao(
            questao_id=questao.id,
            taxonomia_id=taxonomia.id,
            disciplina_principal="sistemas-operacionais",
            topicos=("historico-antigo",),
            justificativa="Histórico não vigente.",
            confianca=0.60,
            vigente=False,
            execucao_id=execucao.id,
        )
    )
    assert repo_tax.contar_classificacoes_vigentes_por_disciplina(taxonomia.id, "redes-e-comunicacoes") == 1
    assert repo_tax.contar_classificacoes_vigentes_por_disciplina(taxonomia.id, "algoritmos-e-estruturas-de-dados") == 1
    assert repo_tax.contar_classificacoes_vigentes_por_disciplina(taxonomia.id, "sistemas-operacionais") == 0


def test_classificacoes_integridade_parcial_preservacao_historica_e_fila_revisao(
    session_factory_teste: sessionmaker[Session],
) -> None:
    repo_questoes = RepositorioQuestoesSqlAlchemy(session_factory_teste)
    repo_class = RepositorioClassificacoesSqlAlchemy(session_factory_teste)
    prova, q10, taxonomia, _, execucao = _criar_contexto_classificacao(session_factory_teste)

    q11 = repo_questoes.salvar(Questao(prova_id=prova.id, numero=11, enunciado="Segunda questão."))
    t0 = datetime(2026, 11, 21, 13, 0, tzinfo=UTC)

    ia_q10 = repo_class.salvar(
        Classificacao(
            questao_id=q10.id,
            taxonomia_id=taxonomia.id,
            disciplina_principal="redes-e-comunicacoes",
            topicos=("camada-rede",),
            justificativa="Classificação automática inicial.",
            confianca=0.68,
            origem=OrigemClassificacao.AUTOMATICA,
            status=StatusClassificacao.PENDENTE_REVISAO,
            vigente=True,
            revisao_prioritaria=True,
            execucao_id=execucao.id,
            alertas_validacao=("baixa_confianca",),
            criada_em=t0,
        )
    )

    # Índice único parcial impede duas vigentes para o mesmo (questao_id, taxonomia_id)
    with pytest.raises(IntegrityError):
        repo_class.salvar(
            Classificacao(
                questao_id=q10.id,
                taxonomia_id=taxonomia.id,
                disciplina_principal="algoritmos-e-estruturas-de-dados",
                vigente=True,
                criada_em=t0 + timedelta(seconds=5),
            )
        )

    # Substituição humana preserva IA no histórico com vigente=False e cria nova humana vigente=True
    humana_q10 = ia_q10.substituir_por_correcao(
        disciplina_principal="algoritmos-e-estruturas-de-dados",
        disciplinas_secundarias=("redes-e-comunicacoes",),
        topicos=("Algoritmo de Dijkstra",),
        justificativa="Foco principal na análise de complexidade do caminho mínimo.",
        agora=t0 + timedelta(minutes=1),
    )
    nova_salva = repo_class.registrar_substituicao(ia_q10, humana_q10)
    assert nova_salva.vigente is True
    assert nova_salva.origem == OrigemClassificacao.HUMANA
    assert nova_salva.substitui_classificacao_id == ia_q10.id

    vigente_atual = repo_class.buscar_vigente(q10.id, taxonomia.id)
    assert vigente_atual is not None
    assert vigente_atual.id == humana_q10.id
    assert len(repo_class.listar_vigentes_por_questao(q10.id)) == 1

    historico = repo_class.listar_historico(q10.id, taxonomia.id)
    assert [c.id for c in historico] == [humana_q10.id, ia_q10.id]
    assert historico[1].vigente is False
    assert historico[1].origem == OrigemClassificacao.AUTOMATICA
    assert historico[1].alertas_validacao == ("baixa_confianca",)

    # Fila de revisão: ordenação (revisao_prioritaria DESC, confianca ASC, ano DESC, numero ASC)
    c_q11 = repo_class.salvar(
        Classificacao(
            questao_id=q11.id,
            taxonomia_id=taxonomia.id,
            disciplina_principal="sistemas-operacionais",
            confianca=0.91,
            origem=OrigemClassificacao.AUTOMATICA,
            status=StatusClassificacao.PENDENTE_REVISAO,
            vigente=True,
            revisao_prioritaria=False,
            criada_em=t0 + timedelta(minutes=2),
        )
    )
    fila_pendentes = repo_class.listar_fila_revisao(
        taxonomia.id,
        status=StatusClassificacao.PENDENTE_REVISAO,
    )
    assert [c.id for c in fila_pendentes] == [c_q11.id]

    q12 = repo_questoes.salvar(Questao(prova_id=prova.id, numero=12, enunciado="Terceira questão."))
    c_q12_prio = repo_class.salvar(
        Classificacao(
            questao_id=q12.id,
            taxonomia_id=taxonomia.id,
            disciplina_principal="redes-e-comunicacoes",
            confianca=0.55,
            origem=OrigemClassificacao.AUTOMATICA,
            status=StatusClassificacao.PENDENTE_REVISAO,
            vigente=True,
            revisao_prioritaria=True,
            criada_em=t0 + timedelta(minutes=3),
        )
    )
    fila_prioritaria = repo_class.listar_fila_revisao(
        taxonomia.id,
        status=StatusClassificacao.PENDENTE_REVISAO,
        apenas_revisao_prioritaria=True,
    )
    assert [c.id for c in fila_prioritaria] == [c_q12_prio.id]
    fila_todos_pendentes = repo_class.listar_fila_revisao(taxonomia.id, status=StatusClassificacao.PENDENTE_REVISAO)
    assert [c.id for c in fila_todos_pendentes] == [c_q12_prio.id, c_q11.id]


def test_divergencias_resolver_atomicamente_todos_os_caminhos_e_rollback(
    session_factory_teste: sessionmaker[Session],
) -> None:
    repo_questoes = RepositorioQuestoesSqlAlchemy(session_factory_teste)
    repo_class = RepositorioClassificacoesSqlAlchemy(session_factory_teste)
    repo_div = RepositorioDivergenciasReclassificacaoSqlAlchemy(session_factory_teste)

    prova, q10, taxonomia, _, execucao = _criar_contexto_classificacao(session_factory_teste)
    q11 = repo_questoes.salvar(Questao(prova_id=prova.id, numero=11, enunciado="Questão 11."))
    q12 = repo_questoes.salvar(Questao(prova_id=prova.id, numero=12, enunciado="Questão 12."))

    t0 = datetime(2026, 11, 21, 14, 0, tzinfo=UTC)

    def _criar_humana(questao: Questao) -> Classificacao:
        return repo_class.salvar(
            Classificacao(
                questao_id=questao.id,
                taxonomia_id=taxonomia.id,
                disciplina_principal="sistemas-operacionais",
                topicos=("escalonamento",),
                justificativa="Humana aprovada.",
                confianca=1.0,
                origem=OrigemClassificacao.HUMANA,
                status=StatusClassificacao.APROVADA,
                vigente=True,
                criada_em=t0,
                revisada_em=t0,
            )
        )

    vig_10 = _criar_humana(q10)
    vig_11 = _criar_humana(q11)
    vig_12 = _criar_humana(q12)

    div_manter = repo_div.salvar(
        DivergenciaReclassificacao(
            questao_id=q10.id,
            taxonomia_id=taxonomia.id,
            execucao_id=execucao.id,
            classificacao_vigente_id=vig_10.id,
            disciplina_principal_candidata="redes-e-comunicacoes",
            confianca_candidata=0.88,
            criada_em=t0,
        )
    )
    div_aceitar = repo_div.salvar(
        DivergenciaReclassificacao(
            questao_id=q11.id,
            taxonomia_id=taxonomia.id,
            execucao_id=execucao.id,
            classificacao_vigente_id=vig_11.id,
            disciplina_principal_candidata="redes-e-comunicacoes",
            disciplinas_secundarias_candidatas=("algoritmos-e-estruturas-de-dados",),
            topicos_candidatos=("roteamento-ospf",),
            justificativa_candidata="Candidata correta.",
            confianca_candidata=0.95,
            criada_em=t0,
        )
    )
    div_editar = repo_div.salvar(
        DivergenciaReclassificacao(
            questao_id=q12.id,
            taxonomia_id=taxonomia.id,
            execucao_id=execucao.id,
            classificacao_vigente_id=vig_12.id,
            disciplina_principal_candidata="redes-e-comunicacoes",
            confianca_candidata=0.82,
            criada_em=t0,
        )
    )

    assert len(repo_div.listar(taxonomia_id=taxonomia.id, status=StatusDivergencia.ABERTA)) == 3

    # Erro contratual faz rollback sem alterar nada
    with pytest.raises(ErroValidacaoDominio):
        repo_div.resolver_atomicamente(div_editar.id, ResolucaoDivergencia.EDITAR_MANUALMENTE, t0)
    with pytest.raises(ErroValidacaoDominio):
        repo_div.resolver_atomicamente(
            div_editar.id,
            ResolucaoDivergencia.EDITAR_MANUALMENTE,
            t0,
            nova_classificacao=Classificacao(
                questao_id=q12.id,
                taxonomia_id=taxonomia.id,
                disciplina_principal="algoritmos-e-estruturas-de-dados",
                origem=OrigemClassificacao.HUMANA,
                status=StatusClassificacao.APROVADA,
                vigente=False,
            ),
        )
    with pytest.raises(ErroValidacaoDominio):
        repo_div.resolver_atomicamente(
            div_editar.id,
            ResolucaoDivergencia.EDITAR_MANUALMENTE,
            t0,
            nova_classificacao=Classificacao(
                questao_id=q12.id,
                taxonomia_id=taxonomia.id,
                disciplina_principal="algoritmos-e-estruturas-de-dados",
                origem=OrigemClassificacao.HUMANA,
                status=StatusClassificacao.PENDENTE_REVISAO,
                vigente=True,
            ),
        )
    with pytest.raises(ErroValidacaoDominio):
        repo_div.resolver_atomicamente(
            div_manter.id,
            ResolucaoDivergencia.MANTER_HUMANA,
            t0,
            nova_classificacao=vig_10,
        )
    div_ainda_aberta = repo_div.buscar_por_id(div_editar.id)
    assert div_ainda_aberta is not None
    assert div_ainda_aberta.status == StatusDivergencia.ABERTA

    # 1. MANTER_HUMANA
    res_manter = repo_div.resolver_atomicamente(
        div_manter.id, ResolucaoDivergencia.MANTER_HUMANA, t0 + timedelta(minutes=1)
    )
    assert res_manter.status == StatusDivergencia.RESOLVIDA
    assert res_manter.resolucao == ResolucaoDivergencia.MANTER_HUMANA
    vig_10_apos = repo_class.buscar_vigente(q10.id, taxonomia.id)
    assert vig_10_apos is not None and vig_10_apos.id == vig_10.id

    # 2. ACEITAR_CANDIDATA (nova_classificacao=None)
    res_aceitar = repo_div.resolver_atomicamente(
        div_aceitar.id,
        ResolucaoDivergencia.ACEITAR_CANDIDATA,
        t0 + timedelta(minutes=2),
    )
    assert res_aceitar.status == StatusDivergencia.RESOLVIDA
    vig_11_apos = repo_class.buscar_vigente(q11.id, taxonomia.id)
    assert vig_11_apos is not None
    assert vig_11_apos.disciplina_principal == "redes-e-comunicacoes"
    assert vig_11_apos.substitui_classificacao_id == vig_11.id
    assert vig_11_apos.status == StatusClassificacao.APROVADA
    antiga_11 = repo_class.buscar_por_id(vig_11.id)
    assert antiga_11 is not None and antiga_11.vigente is False

    # 3. EDITAR_MANUALMENTE
    nova_manual = vig_12.substituir_por_correcao(
        disciplina_principal="algoritmos-e-estruturas-de-dados",
        topicos=("complexidade",),
        justificativa="Edição humana após divergência.",
        agora=t0 + timedelta(minutes=3),
    )
    res_editar = repo_div.resolver_atomicamente(
        div_editar.id,
        ResolucaoDivergencia.EDITAR_MANUALMENTE,
        t0 + timedelta(minutes=3),
        nova_classificacao=nova_manual,
    )
    assert res_editar.status == StatusDivergencia.RESOLVIDA
    vig_12_apos = repo_class.buscar_vigente(q12.id, taxonomia.id)
    assert vig_12_apos is not None and vig_12_apos.id == nova_manual.id
    assert len(repo_div.listar(taxonomia_id=taxonomia.id, status=StatusDivergencia.RESOLVIDA)) == 3


def test_busca_textual_combinada_tsvector_portugues_e_termos_tecnicos(
    session_factory_teste: sessionmaker[Session],
) -> None:
    repo_provas = RepositorioProvasSqlAlchemy(session_factory_teste)
    repo_questoes = RepositorioQuestoesSqlAlchemy(session_factory_teste)
    repo_tax = RepositorioTaxonomiasSqlAlchemy(session_factory_teste)
    repo_class = RepositorioClassificacoesSqlAlchemy(session_factory_teste)

    prova = repo_provas.salvar(Prova(exame="ENADE", curso="Engenharia de Computação", ano=2023))
    tax = repo_tax.salvar(
        Taxonomia(
            codigo="enade-ec",
            nome="ENADE EC",
            disciplinas=[Disciplina("algoritmos", "Algoritmos"), Disciplina("redes", "Redes")],
        )
    )

    q_arvore = repo_questoes.salvar(
        Questao(
            prova_id=prova.id,
            numero=10,
            enunciado="Considere uma árvore binária de busca com ordenação eficiente em computação.",
            alternativas=[Alternativa(LetraAlternativa.A, "O algoritmo realiza rotação simples.")],
        )
    )
    q_ospf = repo_questoes.salvar(
        Questao(
            prova_id=prova.id,
            numero=11,
            enunciado="O protocolo de roteamento intra-domínio OSPF utiliza estado de enlace.",
            alternativas=[Alternativa(LetraAlternativa.A, "Calcula caminhos mínimos.")],
        )
    )
    q_vhdl = repo_questoes.salvar(
        Questao(
            prova_id=prova.id,
            numero=12,
            enunciado="Sobre descrição de hardware para síntese em FPGA:",
            alternativas=[Alternativa(LetraAlternativa.A, "O código em VHDL define um registrador síncrono.")],
        )
    )
    q_complexidade = repo_questoes.salvar(
        Questao(
            prova_id=prova.id,
            numero=13,
            enunciado="A complexidade de tempo do algoritmo Mergesort no pior caso é O(n log n).",
            alternativas=[Alternativa(LetraAlternativa.A, "Divide e conquista.")],
        )
    )
    q_distrator_log_n = repo_questoes.salvar(
        Questao(
            prova_id=prova.id,
            numero=14,
            enunciado="O sistema registra log de auditoria para n usuários simultâneos.",
            alternativas=[Alternativa(LetraAlternativa.A, "Armazena eventos em arquivo texto.")],
        )
    )

    # Tópico vigente em classificação (e histórico não vigente que NÃO deve vazar)
    repo_class.salvar(
        Classificacao(
            questao_id=q_arvore.id,
            taxonomia_id=tax.id,
            disciplina_principal="algoritmos",
            topicos=("busca-heuristica",),
            vigente=True,
        )
    )
    repo_class.salvar(
        Classificacao(
            questao_id=q_distrator_log_n.id,
            taxonomia_id=tax.id,
            disciplina_principal="redes",
            topicos=("topico-antigo-fantasma",),
            vigente=False,
        )
    )

    # 1. Acentuação e flexão em português (pt_unaccent)
    assert [q.id for q in repo_questoes.buscar_por_texto("ordenacao")] == [q_arvore.id]
    assert [q.id for q in repo_questoes.buscar_por_texto("computacao")] == [q_arvore.id]
    assert [q.id for q in repo_questoes.buscar_por_texto("arvores")] == [q_arvore.id]
    assert [q.id for q in repo_questoes.buscar_por_texto("algoritmos")] == [q_complexidade.id, q_arvore.id]

    # 2. Tópicos em classificacoes vigentes (sem vazar histórico não vigente)
    assert [q.id for q in repo_questoes.buscar_por_texto("heuristica", taxonomia_id=tax.id)] == [q_arvore.id]
    assert repo_questoes.buscar_por_texto("topico-antigo-fantasma", taxonomia_id=tax.id) == []

    # 3. Termos técnicos exatos em enunciado e alternativas
    assert [q.id for q in repo_questoes.buscar_por_texto("OSPF")] == [q_ospf.id]
    assert [q.id for q in repo_questoes.buscar_por_texto("VHDL")] == [q_vhdl.id]

    # 4. Símbolo técnico O(n log n) NÃO gera falso positivo em questão com 'log' e 'n' separados
    resultados_onlogn = repo_questoes.buscar_por_texto("O(n log n)")
    assert [q.id for q in resultados_onlogn] == [q_complexidade.id]
    assert q_distrator_log_n.id not in {q.id for q in resultados_onlogn}

    # 5. Garante que consulta vazia retorna [] e prova_id filtra corretamente
    assert repo_questoes.buscar_por_texto("   ") == []
    assert repo_questoes.buscar_por_texto("OSPF", prova_id=uuid4()) == []


def test_busca_textual_precisao_simbolos_tecnicos_e_delimitadores_json(
    session_factory_teste: sessionmaker[Session],
) -> None:
    repo_provas = RepositorioProvasSqlAlchemy(session_factory_teste)
    repo_questoes = RepositorioQuestoesSqlAlchemy(session_factory_teste)
    repo_tax = RepositorioTaxonomiasSqlAlchemy(session_factory_teste)
    repo_class = RepositorioClassificacoesSqlAlchemy(session_factory_teste)

    prova = repo_provas.salvar(Prova(exame="ENADE", curso="Engenharia de Computação", ano=2023))
    tax = repo_tax.salvar(
        Taxonomia(
            codigo="enade-ec",
            nome="ENADE EC",
            disciplinas=[Disciplina("algoritmos", "Algoritmos"), Disciplina("sistemas", "Sistemas")],
        )
    )

    q_c_lang = repo_questoes.salvar(
        Questao(
            prova_id=prova.id,
            numero=1,
            enunciado="Qual a saída do código em linguagem C abaixo?",
            alternativas=[Alternativa(LetraAlternativa.A, "Compila sem erro.")],
        )
    )
    q_csharp = repo_questoes.salvar(
        Questao(
            prova_id=prova.id,
            numero=2,
            enunciado="Em C#, interfaces definem contratos para classes.",
            alternativas=[Alternativa(LetraAlternativa.A, "Permite herança múltipla de interfaces.")],
        )
    )
    q_path_win = repo_questoes.salvar(
        Questao(
            prova_id=prova.id,
            numero=3,
            enunciado=r"O arquivo de configuração fica em C:\temp\config.ini.",
            alternativas=[Alternativa(LetraAlternativa.A, "Usa barra invertida.")],
        )
    )
    q_path_colon = repo_questoes.salvar(
        Questao(
            prova_id=prova.id,
            numero=4,
            enunciado="O rótulo C:temp não representa diretório raiz válido.",
            alternativas=[Alternativa(LetraAlternativa.A, "Falta o separador.")],
        )
    )
    q_hifen_wildcards = repo_questoes.salvar(
        Questao(
            prova_id=prova.id,
            numero=5,
            enunciado="O princípio de ação-reação aplica-se com taxa de 50% e variável _x_.",
            alternativas=[Alternativa(LetraAlternativa.A, r"Caractere literal \n.")],
        )
    )
    q_colchete_topico = repo_questoes.salvar(
        Questao(
            prova_id=prova.id,
            numero=6,
            enunciado="Acesso indexado em vetor na memória contígua.",
            alternativas=[Alternativa(LetraAlternativa.A, "Tempo constante.")],
        )
    )

    repo_class.salvar(
        Classificacao(
            questao_id=q_c_lang.id,
            taxonomia_id=tax.id,
            disciplina_principal="algoritmos",
            topicos=("algoritmos",),
            vigente=True,
        )
    )
    repo_class.salvar(
        Classificacao(
            questao_id=q_csharp.id,
            taxonomia_id=tax.id,
            disciplina_principal="algoritmos",
            topicos=(),
            vigente=True,
        )
    )
    repo_class.salvar(
        Classificacao(
            questao_id=q_colchete_topico.id,
            taxonomia_id=tax.id,
            disciplina_principal="algoritmos",
            topicos=("array[0]",),
            vigente=True,
        )
    )

    # 1. C# NÃO deve dar falso positivo em questão com apenas "linguagem C"
    resultados_csharp = repo_questoes.buscar_por_texto("C#")
    assert [q.id for q in resultados_csharp] == [q_csharp.id]

    # 2. Delimitadores de JSONB ('[', ']', '"') não casam sintaxe de array em topicos
    resultados_colchete = repo_questoes.buscar_por_texto("[")
    assert [q.id for q in resultados_colchete] == [q_colchete_topico.id]
    assert [q.id for q in repo_questoes.buscar_por_texto("]")] == [q_colchete_topico.id]
    assert repo_questoes.buscar_por_texto('"') == []

    # 3. Barra invertida em caminho Windows não casa separador ":" via FTS
    resultados_path = repo_questoes.buscar_por_texto(r"C:\temp")
    assert [q.id for q in resultados_path] == [q_path_win.id]
    assert q_path_colon.id not in {q.id for q in resultados_path}

    # 4. Termo hifenizado em português e escape literal de %, _, \ continuam funcionando
    assert [q.id for q in repo_questoes.buscar_por_texto("acao")] == [q_hifen_wildcards.id]
    assert [q.id for q in repo_questoes.buscar_por_texto("50%")] == [q_hifen_wildcards.id]
    assert [q.id for q in repo_questoes.buscar_por_texto("_x_")] == [q_hifen_wildcards.id]
    assert [q.id for q in repo_questoes.buscar_por_texto(r"\n")] == [q_hifen_wildcards.id]
