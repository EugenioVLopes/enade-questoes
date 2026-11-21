"""Composition root da aplicação FastAPI."""

from __future__ import annotations

from fastapi import FastAPI

from application.health import HealthUseCase
from application.midia import ObterAtivoVisualArquivoUseCase, ObterPaginaProvaImagemUseCase
from application.ports.armazenamento import ArmazenamentoArquivos
from application.ports.extracao import ExtratorGabarito, ExtratorProva, RenderizadorPaginaPdf
from application.provas import (
    AtualizarGabaritoUseCase,
    CriarProvaUseCase,
    ListarProvasUseCase,
    ObterProvaUseCase,
    ReprocessarProvaUseCase,
)
from application.worker import ClassificacaoEncadeadaHook, WorkerLocal
from infrastructure.config import Settings
from infrastructure.extracao import (
    ExtratorGabaritoPdfPlumber,
    ExtratorProvaDocling,
    RenderizadorPaginaPdfPypdfium2,
)
from infrastructure.persistence.database import (
    SqlAlchemyDatabaseProbe,
    create_db_engine,
    create_session_factory,
)
from infrastructure.persistence.repositorios import (
    RepositorioAtivosVisuaisSqlAlchemy,
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

    armazenamento_inst = armazenamento or ArmazenamentoArquivosLocal(resolved_settings.resolved_data_dir)
    extrator_prova_inst = extrator_prova or ExtratorProvaDocling()
    extrator_gabarito_inst = extrator_gabarito or ExtratorGabaritoPdfPlumber()
    renderizador_inst = renderizador or RenderizadorPaginaPdfPypdfium2()

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
        on_shutdown=engine.dispose,
    )


app = build_app()
