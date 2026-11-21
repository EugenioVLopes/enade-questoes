from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from application.exceptions import (
    ArquivoPdfAusenteError,
    ConflitoEstadoIngestaoError,
    ConflitoProvaExistenteError,
    RecursoNaoEncontradoError,
)
from application.health import HealthUseCase
from application.midia import ObterAtivoVisualArquivoUseCase, ObterPaginaProvaImagemUseCase
from application.provas import (
    AtualizarGabaritoUseCase,
    CriarProvaUseCase,
    ListarProvasUseCase,
    ObterProvaUseCase,
    ReprocessarProvaUseCase,
)
from application.worker import WorkerLocal
from domain.exceptions import (
    ErroInvarianteDominio,
    ErroValidacaoDominio,
    FaixaQuestoesIndisponivelError,
)
from presentation.api.v1.ativos_visuais import router as ativos_visuais_router
from presentation.api.v1.health import router as health_router
from presentation.api.v1.provas import router as provas_router


def create_app(
    health_use_case: HealthUseCase,
    *,
    worker: WorkerLocal | None = None,
    criar_prova_use_case: CriarProvaUseCase | None = None,
    listar_provas_use_case: ListarProvasUseCase | None = None,
    obter_prova_use_case: ObterProvaUseCase | None = None,
    atualizar_gabarito_use_case: AtualizarGabaritoUseCase | None = None,
    reprocessar_prova_use_case: ReprocessarProvaUseCase | None = None,
    obter_pagina_prova_use_case: ObterPaginaProvaImagemUseCase | None = None,
    obter_ativo_visual_use_case: ObterAtivoVisualArquivoUseCase | None = None,
    on_shutdown: Callable[[], None] | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app_inst: FastAPI) -> AsyncIterator[None]:
        worker_inst: WorkerLocal | None = getattr(app_inst.state, "worker", None)
        if worker_inst is not None:
            worker_inst.iniciar()
        try:
            yield
        finally:
            if worker_inst is not None:
                worker_inst.parar()
            if on_shutdown is not None:
                on_shutdown()

    app = FastAPI(
        title="Enade Questões API",
        version="0.1.0",
        description="API local do sistema de ingestão, classificação e revisão de questões do ENADE.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RecursoNaoEncontradoError)
    def _tratar_nao_encontrado(_request: Request, exc: RecursoNaoEncontradoError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

    @app.exception_handler(ConflitoProvaExistenteError)
    def _tratar_conflito_prova(_request: Request, exc: ConflitoProvaExistenteError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": str(exc),
                "prova_id": str(exc.prova_id),
                "exame": exc.exame,
                "curso": exc.curso,
                "ano": exc.ano,
            },
        )

    @app.exception_handler(ConflitoEstadoIngestaoError)
    def _tratar_conflito_ingestao(_request: Request, exc: ConflitoEstadoIngestaoError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

    @app.exception_handler(ErroInvarianteDominio)
    def _tratar_invariante(_request: Request, exc: ErroInvarianteDominio) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

    @app.exception_handler(ArquivoPdfAusenteError)
    def _tratar_pdf_ausente(_request: Request, exc: ArquivoPdfAusenteError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(exc)})

    @app.exception_handler(ErroValidacaoDominio)
    def _tratar_validacao_dominio(_request: Request, exc: ErroValidacaoDominio) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(exc)})

    @app.exception_handler(FaixaQuestoesIndisponivelError)
    def _tratar_faixa_indisponivel(_request: Request, exc: FaixaQuestoesIndisponivelError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": str(exc)})

    app.state.health_use_case = health_use_case
    app.state.worker = worker
    app.state.criar_prova_use_case = criar_prova_use_case
    app.state.listar_provas_use_case = listar_provas_use_case
    app.state.obter_prova_use_case = obter_prova_use_case
    app.state.atualizar_gabarito_use_case = atualizar_gabarito_use_case
    app.state.reprocessar_prova_use_case = reprocessar_prova_use_case
    app.state.obter_pagina_prova_use_case = obter_pagina_prova_use_case
    app.state.obter_ativo_visual_use_case = obter_ativo_visual_use_case

    app.include_router(health_router)
    app.include_router(provas_router)
    app.include_router(ativos_visuais_router)
    return app
