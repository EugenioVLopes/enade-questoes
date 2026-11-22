"""Composition root da aplicação FastAPI."""

from __future__ import annotations

from fastapi import FastAPI

from application.classificacao import ClassificarQuestaoService
from application.execucoes_classificacao import (
    CriarExecucaoClassificacaoUseCase,
    DetalharExecucaoClassificacaoUseCase,
    ExecutarLoteClassificacaoService,
    HookClassificacaoEncadeada,
    ListarExecucoesClassificacaoUseCase,
    RetomarExecucaoClassificacaoUseCase,
)
from application.health import HealthUseCase
from application.midia import ObterAtivoVisualArquivoUseCase, ObterPaginaProvaImagemUseCase
from application.ports.armazenamento import ArmazenamentoArquivos
from application.ports.classificacao import ClassificadorMultimodal
from application.ports.extracao import ExtratorGabarito, ExtratorProva, RenderizadorPaginaPdf
from application.provas import (
    AtualizarGabaritoUseCase,
    CriarProvaUseCase,
    ListarProvasUseCase,
    ObterProvaUseCase,
    ReprocessarProvaUseCase,
)
from application.questoes import (
    AdicionarAtivoVisualUseCase,
    AtualizarAtivoVisualUseCase,
    ConsultarQuestoesUseCase,
    DetalharQuestaoUseCase,
    EditarConteudoQuestaoUseCase,
    RemoverAtivoVisualUseCase,
    ResolverAlertaExtracaoUseCase,
)
from application.revisao import (
    AprovarClassificacaoUseCase,
    CorrigirClassificacaoUseCase,
    ResolverDivergenciaUseCase,
)
from application.taxonomias import (
    AdicionarDisciplinaUseCase,
    AtualizarDisciplinaUseCase,
    AtualizarTaxonomiaUseCase,
    CriarPerfilClassificacaoUseCase,
    CriarTaxonomiaUseCase,
    DetalharTaxonomiaUseCase,
    ListarPerfisClassificacaoUseCase,
    ListarTaxonomiasUseCase,
)
from application.worker import ClassificacaoEncadeadaHook, WorkerLocal
from infrastructure.config import Settings
from infrastructure.extracao import (
    ExtratorGabaritoPdfPlumber,
    ExtratorProvaDocling,
    RenderizadorPaginaPdfPypdfium2,
)
from infrastructure.imagem import NormalizadorImagemPillow
from infrastructure.llm import criar_classificador_multimodal
from infrastructure.persistence.consulta_questoes import ConsultaQuestoesSqlAlchemy
from infrastructure.persistence.database import (
    SqlAlchemyDatabaseProbe,
    create_db_engine,
    create_session_factory,
)
from infrastructure.persistence.repositorios import (
    RepositorioAtivosVisuaisSqlAlchemy,
    RepositorioClassificacoesSqlAlchemy,
    RepositorioDivergenciasReclassificacaoSqlAlchemy,
    RepositorioExecucoesClassificacaoSqlAlchemy,
    RepositorioIngestoesSqlAlchemy,
    RepositorioPerfisClassificacaoSqlAlchemy,
    RepositorioProvasSqlAlchemy,
    RepositorioQuestoesSqlAlchemy,
    RepositorioTaxonomiasSqlAlchemy,
)
from infrastructure.storage.local import ArmazenamentoArquivosLocal
from presentation.api.app import create_app


def build_app(
    settings: Settings | None = None,
    *,
    extrator_prova: ExtratorProva | None = None,
    extrator_gabarito: ExtratorGabarito | None = None,
    renderizador: RenderizadorPaginaPdf | None = None,
    armazenamento: ArmazenamentoArquivos | None = None,
    classificacao_hook: ClassificacaoEncadeadaHook | None = None,
    classificador: ClassificadorMultimodal | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings()
    engine = create_db_engine(resolved_settings.database_url)
    session_factory = create_session_factory(engine)
    db_probe = SqlAlchemyDatabaseProbe(engine)

    repo_provas = RepositorioProvasSqlAlchemy(session_factory)
    repo_ingestoes = RepositorioIngestoesSqlAlchemy(session_factory)
    repo_questoes = RepositorioQuestoesSqlAlchemy(session_factory)
    repo_ativos = RepositorioAtivosVisuaisSqlAlchemy(session_factory)
    repo_taxonomias = RepositorioTaxonomiasSqlAlchemy(session_factory)
    repo_perfis = RepositorioPerfisClassificacaoSqlAlchemy(session_factory)
    repo_execucoes = RepositorioExecucoesClassificacaoSqlAlchemy(session_factory)
    repo_classificacoes = RepositorioClassificacoesSqlAlchemy(session_factory)
    repo_divergencias = RepositorioDivergenciasReclassificacaoSqlAlchemy(session_factory)

    armazenamento_inst = armazenamento or ArmazenamentoArquivosLocal(resolved_settings.resolved_data_dir)
    extrator_prova_inst = extrator_prova or ExtratorProvaDocling()
    extrator_gabarito_inst = extrator_gabarito or ExtratorGabaritoPdfPlumber()
    renderizador_inst = renderizador or RenderizadorPaginaPdfPypdfium2()
    classificador_inst = (
        classificador
        if classificador is not None
        else criar_classificador_multimodal(resolved_settings, armazenamento=armazenamento_inst)
    )

    worker = WorkerLocal(
        repo_provas=repo_provas,
        repo_ingestoes=repo_ingestoes,
        repo_questoes=repo_questoes,
        repo_execucoes=repo_execucoes,
        armazenamento=armazenamento_inst,
        extrator_prova=extrator_prova_inst,
        extrator_gabarito=extrator_gabarito_inst,
        classificacao_hook=classificacao_hook,
    )

    health_use_case = HealthUseCase(
        db_probe=db_probe,
        worker_status_provider=worker.status_atual,
    )
    criar_prova_use_case = CriarProvaUseCase(
        repo_provas=repo_provas,
        repo_ingestoes=repo_ingestoes,
        repo_taxonomias=repo_taxonomias,
        repo_perfis=repo_perfis,
        armazenamento=armazenamento_inst,
        worker=worker,
    )
    listar_provas_use_case = ListarProvasUseCase(
        repo_provas=repo_provas,
        repo_ingestoes=repo_ingestoes,
        repo_questoes=repo_questoes,
        repo_execucoes=repo_execucoes,
    )
    obter_prova_use_case = ObterProvaUseCase(
        repo_provas=repo_provas,
        repo_ingestoes=repo_ingestoes,
        repo_questoes=repo_questoes,
        repo_execucoes=repo_execucoes,
    )
    atualizar_gabarito_use_case = AtualizarGabaritoUseCase(
        repo_provas=repo_provas,
        repo_ingestoes=repo_ingestoes,
        repo_questoes=repo_questoes,
        armazenamento=armazenamento_inst,
        extrator_gabarito=extrator_gabarito_inst,
    )
    reprocessar_prova_use_case = ReprocessarProvaUseCase(
        repo_provas=repo_provas,
        repo_ingestoes=repo_ingestoes,
        armazenamento=armazenamento_inst,
        worker=worker,
    )
    obter_pagina_prova_use_case = ObterPaginaProvaImagemUseCase(
        repo_provas=repo_provas,
        armazenamento=armazenamento_inst,
        renderizador=renderizador_inst,
    )
    obter_ativo_visual_use_case = ObterAtivoVisualArquivoUseCase(
        repo_ativos=repo_ativos,
        armazenamento=armazenamento_inst,
    )

    listar_taxonomias_use_case = ListarTaxonomiasUseCase(repo_taxonomias)
    detalhar_taxonomia_use_case = DetalharTaxonomiaUseCase(repo_taxonomias)
    criar_taxonomia_use_case = CriarTaxonomiaUseCase(repo_taxonomias)
    atualizar_taxonomia_use_case = AtualizarTaxonomiaUseCase(repo_taxonomias)
    adicionar_disciplina_use_case = AdicionarDisciplinaUseCase(repo_taxonomias)
    atualizar_disciplina_use_case = AtualizarDisciplinaUseCase(repo_taxonomias)

    listar_perfis_use_case = ListarPerfisClassificacaoUseCase(repo_perfis)
    criar_perfil_use_case = CriarPerfilClassificacaoUseCase(repo_perfis)

    criar_execucao_use_case = CriarExecucaoClassificacaoUseCase(
        repo_taxonomias=repo_taxonomias,
        repo_perfis=repo_perfis,
        repo_provas=repo_provas,
        repo_questoes=repo_questoes,
        repo_execucoes=repo_execucoes,
        worker=worker,
    )
    listar_execucoes_use_case = ListarExecucoesClassificacaoUseCase(repo_execucoes)
    detalhar_execucao_use_case = DetalharExecucaoClassificacaoUseCase(repo_execucoes)
    retomar_execucao_use_case = RetomarExecucaoClassificacaoUseCase(
        repo_execucoes=repo_execucoes,
        repo_provas=repo_provas,
        worker=worker,
    )

    consulta_questoes = ConsultaQuestoesSqlAlchemy(session_factory)
    normalizador_imagem = NormalizadorImagemPillow()
    ativos_deps = {
        "repo_questoes": repo_questoes,
        "repo_ativos": repo_ativos,
        "armazenamento": armazenamento_inst,
        "normalizador": normalizador_imagem,
    }
    consultar_questoes_use_case = ConsultarQuestoesUseCase(consulta=consulta_questoes, repo_taxonomias=repo_taxonomias)
    detalhar_questao_use_case = DetalharQuestaoUseCase(
        repo_questoes=repo_questoes,
        repo_provas=repo_provas,
        repo_taxonomias=repo_taxonomias,
        repo_classificacoes=repo_classificacoes,
        consulta=consulta_questoes,
    )
    aprovar_classificacao_use_case = AprovarClassificacaoUseCase(
        repo_questoes=repo_questoes, repo_classificacoes=repo_classificacoes
    )
    corrigir_classificacao_use_case = CorrigirClassificacaoUseCase(
        repo_questoes=repo_questoes,
        repo_taxonomias=repo_taxonomias,
        repo_classificacoes=repo_classificacoes,
        consulta=consulta_questoes,
    )
    resolver_divergencia_use_case = ResolverDivergenciaUseCase(
        repo_questoes=repo_questoes,
        repo_taxonomias=repo_taxonomias,
        repo_classificacoes=repo_classificacoes,
        repo_divergencias=repo_divergencias,
    )
    editar_questao_use_case = EditarConteudoQuestaoUseCase(
        repo_questoes=repo_questoes, repo_provas=repo_provas, repo_classificacoes=repo_classificacoes
    )
    resolver_alerta_use_case = ResolverAlertaExtracaoUseCase(
        repo_questoes=repo_questoes, repo_classificacoes=repo_classificacoes
    )
    adicionar_ativo_visual_use_case = AdicionarAtivoVisualUseCase(**ativos_deps)
    atualizar_ativo_visual_use_case = AtualizarAtivoVisualUseCase(**ativos_deps)
    remover_ativo_visual_use_case = RemoverAtivoVisualUseCase(**ativos_deps)

    classificar_questao_service = ClassificarQuestaoService(
        classificador_inst,
        armazenamento=armazenamento_inst,
    )
    executar_lote_service = ExecutarLoteClassificacaoService(
        repo_execucoes=repo_execucoes,
        repo_questoes=repo_questoes,
        repo_provas=repo_provas,
        repo_classificacoes=repo_classificacoes,
        repo_divergencias=repo_divergencias,
        classificar_questao=classificar_questao_service,
    )
    hook_efetivo = (
        classificacao_hook
        if classificacao_hook is not None
        else HookClassificacaoEncadeada(
            repo_perfis=repo_perfis,
            criar_execucao=criar_execucao_use_case,
        )
    )
    worker.configurar_classificacao(hook=hook_efetivo, executor=executar_lote_service)

    return create_app(
        health_use_case=health_use_case,
        worker=worker,
        criar_prova_use_case=criar_prova_use_case,
        listar_provas_use_case=listar_provas_use_case,
        obter_prova_use_case=obter_prova_use_case,
        atualizar_gabarito_use_case=atualizar_gabarito_use_case,
        reprocessar_prova_use_case=reprocessar_prova_use_case,
        obter_pagina_prova_use_case=obter_pagina_prova_use_case,
        obter_ativo_visual_use_case=obter_ativo_visual_use_case,
        listar_taxonomias_use_case=listar_taxonomias_use_case,
        detalhar_taxonomia_use_case=detalhar_taxonomia_use_case,
        criar_taxonomia_use_case=criar_taxonomia_use_case,
        atualizar_taxonomia_use_case=atualizar_taxonomia_use_case,
        adicionar_disciplina_use_case=adicionar_disciplina_use_case,
        atualizar_disciplina_use_case=atualizar_disciplina_use_case,
        listar_perfis_use_case=listar_perfis_use_case,
        criar_perfil_use_case=criar_perfil_use_case,
        criar_execucao_use_case=criar_execucao_use_case,
        listar_execucoes_use_case=listar_execucoes_use_case,
        detalhar_execucao_use_case=detalhar_execucao_use_case,
        retomar_execucao_use_case=retomar_execucao_use_case,
        consultar_questoes_use_case=consultar_questoes_use_case,
        detalhar_questao_use_case=detalhar_questao_use_case,
        aprovar_classificacao_use_case=aprovar_classificacao_use_case,
        corrigir_classificacao_use_case=corrigir_classificacao_use_case,
        resolver_divergencia_use_case=resolver_divergencia_use_case,
        editar_questao_use_case=editar_questao_use_case,
        resolver_alerta_use_case=resolver_alerta_use_case,
        adicionar_ativo_visual_use_case=adicionar_ativo_visual_use_case,
        atualizar_ativo_visual_use_case=atualizar_ativo_visual_use_case,
        remover_ativo_visual_use_case=remover_ativo_visual_use_case,
        on_shutdown=engine.dispose,
    )


app = build_app()
