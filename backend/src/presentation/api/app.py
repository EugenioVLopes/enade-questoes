from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from application.exceptions import (
    ArquivoPdfAusenteError,
    ConflitoEstadoIngestaoError,
    ConflitoProvaExistenteError,
    ConflitoRecursoError,
    RecursoNaoEncontradoError,
)
from application.execucoes_classificacao import (
    CriarExecucaoClassificacaoUseCase,
    DetalharExecucaoClassificacaoUseCase,
    ListarExecucoesClassificacaoUseCase,
    RetomarExecucaoClassificacaoUseCase,
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
from application.worker import WorkerLocal
from domain.exceptions import (
    ErroInvarianteDominio,
    ErroValidacaoDominio,
    FaixaQuestoesIndisponivelError,
)
from presentation.api.v1.ativos_visuais import router as ativos_visuais_router
from presentation.api.v1.execucoes_classificacao import router as execucoes_classificacao_router
from presentation.api.v1.health import router as health_router
from presentation.api.v1.perfis_classificacao import router as perfis_classificacao_router
from presentation.api.v1.provas import router as provas_router
from presentation.api.v1.questoes import router as questoes_router
from presentation.api.v1.taxonomias import (
    disciplinas_router,
)
from presentation.api.v1.taxonomias import (
    router as taxonomias_router,
)

INDICE_VIGENTE_UNICA = "uq_classificacoes_vigente_por_questao_taxonomia"


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
    listar_taxonomias_use_case: ListarTaxonomiasUseCase | None = None,
    detalhar_taxonomia_use_case: DetalharTaxonomiaUseCase | None = None,
    criar_taxonomia_use_case: CriarTaxonomiaUseCase | None = None,
    atualizar_taxonomia_use_case: AtualizarTaxonomiaUseCase | None = None,
    adicionar_disciplina_use_case: AdicionarDisciplinaUseCase | None = None,
    atualizar_disciplina_use_case: AtualizarDisciplinaUseCase | None = None,
    listar_perfis_use_case: ListarPerfisClassificacaoUseCase | None = None,
    criar_perfil_use_case: CriarPerfilClassificacaoUseCase | None = None,
    criar_execucao_use_case: CriarExecucaoClassificacaoUseCase | None = None,
    listar_execucoes_use_case: ListarExecucoesClassificacaoUseCase | None = None,
    detalhar_execucao_use_case: DetalharExecucaoClassificacaoUseCase | None = None,
    retomar_execucao_use_case: RetomarExecucaoClassificacaoUseCase | None = None,
    consultar_questoes_use_case: ConsultarQuestoesUseCase | None = None,
    detalhar_questao_use_case: DetalharQuestaoUseCase | None = None,
    aprovar_classificacao_use_case: AprovarClassificacaoUseCase | None = None,
    corrigir_classificacao_use_case: CorrigirClassificacaoUseCase | None = None,
    resolver_divergencia_use_case: ResolverDivergenciaUseCase | None = None,
    editar_questao_use_case: EditarConteudoQuestaoUseCase | None = None,
    resolver_alerta_use_case: ResolverAlertaExtracaoUseCase | None = None,
    adicionar_ativo_visual_use_case: AdicionarAtivoVisualUseCase | None = None,
    atualizar_ativo_visual_use_case: AtualizarAtivoVisualUseCase | None = None,
    remover_ativo_visual_use_case: RemoverAtivoVisualUseCase | None = None,
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

    @app.exception_handler(RequestValidationError)
    def _tratar_validacao_requisicao(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # Mesmo formato do FastAPI, sem ecoar `input`/`ctx`: entradas profundamente aninhadas estourariam o encoder.
        detalhes = [
            {"loc": list(erro["loc"]), "msg": str(erro["msg"]), "type": str(erro["type"])} for erro in exc.errors()
        ]
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": detalhes})

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

    @app.exception_handler(ConflitoRecursoError)
    def _tratar_conflito_recurso(_request: Request, exc: ConflitoRecursoError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

    @app.exception_handler(ErroInvarianteDominio)
    def _tratar_invariante(_request: Request, exc: ErroInvarianteDominio) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

    @app.exception_handler(IntegrityError)
    def _tratar_conflito_vigente(_request: Request, exc: IntegrityError) -> JSONResponse:
        if INDICE_VIGENTE_UNICA not in str(exc.orig):
            raise exc
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "A Questão já possui Classificação vigente; recarregue e tente novamente."},
        )

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
    app.state.listar_taxonomias_use_case = listar_taxonomias_use_case
    app.state.detalhar_taxonomia_use_case = detalhar_taxonomia_use_case
    app.state.criar_taxonomia_use_case = criar_taxonomia_use_case
    app.state.atualizar_taxonomia_use_case = atualizar_taxonomia_use_case
    app.state.adicionar_disciplina_use_case = adicionar_disciplina_use_case
    app.state.atualizar_disciplina_use_case = atualizar_disciplina_use_case
    app.state.listar_perfis_use_case = listar_perfis_use_case
    app.state.criar_perfil_use_case = criar_perfil_use_case
    app.state.criar_execucao_use_case = criar_execucao_use_case
    app.state.listar_execucoes_use_case = listar_execucoes_use_case
    app.state.detalhar_execucao_use_case = detalhar_execucao_use_case
    app.state.retomar_execucao_use_case = retomar_execucao_use_case
    app.state.consultar_questoes_use_case = consultar_questoes_use_case
    app.state.detalhar_questao_use_case = detalhar_questao_use_case
    app.state.aprovar_classificacao_use_case = aprovar_classificacao_use_case
    app.state.corrigir_classificacao_use_case = corrigir_classificacao_use_case
    app.state.resolver_divergencia_use_case = resolver_divergencia_use_case
    app.state.editar_questao_use_case = editar_questao_use_case
    app.state.resolver_alerta_use_case = resolver_alerta_use_case
    app.state.adicionar_ativo_visual_use_case = adicionar_ativo_visual_use_case
    app.state.atualizar_ativo_visual_use_case = atualizar_ativo_visual_use_case
    app.state.remover_ativo_visual_use_case = remover_ativo_visual_use_case

    app.include_router(health_router)
    app.include_router(provas_router)
    app.include_router(questoes_router)
    app.include_router(ativos_visuais_router)
    app.include_router(taxonomias_router)
    app.include_router(disciplinas_router)
    app.include_router(perfis_classificacao_router)
    app.include_router(execucoes_classificacao_router)
    return app
