from __future__ import annotations

from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, Form, Header, Path, Query, Request, Response, UploadFile, status

from application.midia import ObterPaginaProvaImagemUseCase
from application.provas import (
    AtualizarGabaritoUseCase,
    CriarProvaUseCase,
    DetalheProva,
    ListarProvasUseCase,
    ObterProvaUseCase,
    ReprocessarProvaUseCase,
)
from presentation.api.schemas import (
    ClassificacaoEncadeadaResponse,
    ConflitoProvaResponse,
    ContagemAlertasResponse,
    ContagemQuestoesResponse,
    ErroDetalheResponse,
    IngestaoResumoResponse,
    ListaProvasResponse,
    MetadadosIngestaoResponse,
    ProvaDetalheResponse,
    ProvaIngestaoAceitaResponse,
    ReprocessarProvaAceitaResponse,
    ReprocessarProvaRequest,
    ResumoAtualizacaoGabaritoResponse,
)
from presentation.api.v1._http_cache import responder_png_com_cache

router = APIRouter(prefix="/api/v1/provas", tags=["provas"])

type StatusIngestaoLiteral = Literal["pendente", "processando", "concluida", "erro", "interrompida"]


def _resolver_state(request: Request, attr: str) -> object:
    valor = getattr(request.app.state, attr, None)
    if valor is None:
        raise RuntimeError(f"Dependência '{attr}' não configurada em app.state.")
    return valor


def get_criar_prova_use_case(request: Request) -> CriarProvaUseCase:
    return cast(CriarProvaUseCase, _resolver_state(request, "criar_prova_use_case"))


def get_listar_provas_use_case(request: Request) -> ListarProvasUseCase:
    return cast(ListarProvasUseCase, _resolver_state(request, "listar_provas_use_case"))


def get_obter_prova_use_case(request: Request) -> ObterProvaUseCase:
    return cast(ObterProvaUseCase, _resolver_state(request, "obter_prova_use_case"))


def get_atualizar_gabarito_use_case(request: Request) -> AtualizarGabaritoUseCase:
    return cast(AtualizarGabaritoUseCase, _resolver_state(request, "atualizar_gabarito_use_case"))


def get_reprocessar_prova_use_case(request: Request) -> ReprocessarProvaUseCase:
    return cast(ReprocessarProvaUseCase, _resolver_state(request, "reprocessar_prova_use_case"))


def get_obter_pagina_prova_use_case(request: Request) -> ObterPaginaProvaImagemUseCase:
    return cast(ObterPaginaProvaImagemUseCase, _resolver_state(request, "obter_pagina_prova_use_case"))


def _serializar_detalhe_prova(detalhe: DetalheProva) -> ProvaDetalheResponse:
    prova = detalhe.prova
    faixa = prova.faixa_ce
    if faixa is None:
        raise RuntimeError(f"Prova '{prova.id}' sem faixa_ce definida.")

    ultima_ingestao_resp: IngestaoResumoResponse | None = None
    if detalhe.ultima_ingestao is not None:
        ing = detalhe.ultima_ingestao
        meta = ing.metadados
        ultima_ingestao_resp = IngestaoResumoResponse(
            id=ing.id,
            status=cast(StatusIngestaoLiteral, ing.status.value),
            mensagem_erro=ing.mensagem_erro,
            iniciada_em=ing.iniciada_em,
            concluida_em=ing.concluida_em,
            criada_em=ing.criada_em,
            metadados=MetadadosIngestaoResponse(
                total_questoes_extraidas=meta.total_questoes_extraidas,
                imagens_detectadas=meta.imagens_detectadas,
                imagens_filtradas_margem=meta.imagens_filtradas_margem,
                formulas_recortadas=meta.formulas_recortadas,
                usou_ocr=meta.usou_ocr,
                paginas_fonte_symbol=list(meta.paginas_fonte_symbol),
                gabarito_enviado=meta.gabarito_enviado,
            ),
        )

    return ProvaDetalheResponse(
        id=prova.id,
        exame=prova.exame,
        curso=prova.curso,
        ano=prova.ano,
        questao_inicio=faixa.inicio,
        questao_fim=faixa.fim,
        possui_gabarito=prova.caminho_gabarito is not None,
        criada_em=prova.criada_em,
        atualizada_em=prova.atualizada_em,
        ultima_ingestao=ultima_ingestao_resp,
        questoes=ContagemQuestoesResponse(
            total=detalhe.questoes.total,
            editadas_manualmente=detalhe.questoes.editadas_manualmente,
            gabarito_validas=detalhe.questoes.gabarito_validas,
            gabarito_anuladas=detalhe.questoes.gabarito_anuladas,
            gabarito_pendentes=detalhe.questoes.gabarito_pendentes,
        ),
        alertas=ContagemAlertasResponse(
            abertos=detalhe.alertas.abertos,
            criticos_abertos=detalhe.alertas.criticos_abertos,
            questoes_com_alerta_aberto=detalhe.alertas.questoes_com_alerta_aberto,
        ),
        classificacao_encadeada=ClassificacaoEncadeadaResponse(
            solicitada=detalhe.classificacao_encadeada.solicitada,
            taxonomia_id=detalhe.classificacao_encadeada.taxonomia_id,
            perfil_id=detalhe.classificacao_encadeada.perfil_id,
            execucao_id=detalhe.classificacao_encadeada.execucao_id,
            status=detalhe.classificacao_encadeada.status,
        ),
    )


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ProvaIngestaoAceitaResponse,
    responses={
        404: {"model": ErroDetalheResponse},
        409: {"model": ConflitoProvaResponse},
        422: {"model": ErroDetalheResponse},
    },
    summary="Cadastra uma Prova (PDF obrigatório e Gabarito opcional) e enfileira sua Ingestão",
)
async def criar_prova(
    use_case: Annotated[CriarProvaUseCase, Depends(get_criar_prova_use_case)],
    arquivo_prova: Annotated[UploadFile, File(...)],
    curso: Annotated[str, Form(...)],
    ano: Annotated[int, Form(...)],
    exame: Annotated[str, Form()] = "ENADE",
    arquivo_gabarito: Annotated[UploadFile | None, File()] = None,
    questao_inicio: Annotated[int | None, Form()] = None,
    questao_fim: Annotated[int | None, Form()] = None,
    taxonomia_id: Annotated[UUID | None, Form()] = None,
    perfil_id: Annotated[UUID | None, Form()] = None,
) -> ProvaIngestaoAceitaResponse:
    conteudo_prova = await arquivo_prova.read()
    conteudo_gabarito = await arquivo_gabarito.read() if arquivo_gabarito is not None else None

    resultado = use_case.execute(
        exame=exame,
        curso=curso,
        ano=ano,
        conteudo_prova_pdf=conteudo_prova,
        conteudo_gabarito_pdf=conteudo_gabarito,
        questao_inicio=questao_inicio,
        questao_fim=questao_fim,
        taxonomia_id=taxonomia_id,
        perfil_id=perfil_id,
    )
    faixa = resultado.prova.faixa_ce
    if faixa is None:
        raise RuntimeError(f"Prova '{resultado.prova.id}' sem faixa_ce definida.")

    return ProvaIngestaoAceitaResponse(
        prova_id=resultado.prova.id,
        ingestao_id=resultado.ingestao.id,
        status=cast(StatusIngestaoLiteral, resultado.ingestao.status.value),
        exame=resultado.prova.exame,
        curso=resultado.prova.curso,
        ano=resultado.prova.ano,
        questao_inicio=faixa.inicio,
        questao_fim=faixa.fim,
        possui_gabarito=resultado.prova.caminho_gabarito is not None,
    )


@router.get(
    "",
    response_model=ListaProvasResponse,
    summary="Lista todas as Provas com estado da última Ingestão, questões e alertas",
)
def listar_provas(
    use_case: Annotated[ListarProvasUseCase, Depends(get_listar_provas_use_case)],
) -> ListaProvasResponse:
    itens = [_serializar_detalhe_prova(item) for item in use_case.execute()]
    return ListaProvasResponse(itens=itens, total=len(itens))


@router.get(
    "/{prova_id}",
    response_model=ProvaDetalheResponse,
    responses={404: {"model": ErroDetalheResponse}},
    summary="Obtém os detalhes, status de Ingestão e métricas de uma Prova",
)
def obter_prova(
    prova_id: UUID,
    use_case: Annotated[ObterProvaUseCase, Depends(get_obter_prova_use_case)],
) -> ProvaDetalheResponse:
    return _serializar_detalhe_prova(use_case.execute(prova_id))


@router.put(
    "/{prova_id}/gabarito",
    response_model=ResumoAtualizacaoGabaritoResponse,
    responses={
        404: {"model": ErroDetalheResponse},
        409: {"model": ErroDetalheResponse},
        422: {"model": ErroDetalheResponse},
    },
    summary="Atualiza o Gabarito oficial de uma Prova preservando classificações e edições manuais",
)
async def atualizar_gabarito(
    prova_id: UUID,
    use_case: Annotated[AtualizarGabaritoUseCase, Depends(get_atualizar_gabarito_use_case)],
    arquivo_gabarito: Annotated[UploadFile, File(...)],
) -> ResumoAtualizacaoGabaritoResponse:
    conteudo_gabarito = await arquivo_gabarito.read()
    resumo = use_case.execute(prova_id, conteudo_gabarito)
    return ResumoAtualizacaoGabaritoResponse(
        mantidas=resumo.mantidas,
        alteradas=resumo.alteradas,
        anuladas=resumo.anuladas,
        sem_correspondencia=list(resumo.sem_correspondencia),
        questoes_sem_gabarito=list(resumo.questoes_sem_gabarito),
    )


@router.post(
    "/{prova_id}/reprocessar",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ReprocessarProvaAceitaResponse,
    responses={
        404: {"model": ErroDetalheResponse},
        409: {"model": ErroDetalheResponse},
        422: {"model": ErroDetalheResponse},
    },
    summary="Reenfileira a extração de uma Prova conciliando questões por número oficial",
)
def reprocessar_prova(
    prova_id: UUID,
    use_case: Annotated[ReprocessarProvaUseCase, Depends(get_reprocessar_prova_use_case)],
    payload: Annotated[ReprocessarProvaRequest | None, Body()] = None,
) -> ReprocessarProvaAceitaResponse:
    sobrescrever_editadas = payload.sobrescrever_editadas if payload is not None else False
    resultado = use_case.execute(prova_id, sobrescrever_editadas=sobrescrever_editadas)
    return ReprocessarProvaAceitaResponse(
        prova_id=resultado.prova.id,
        ingestao_id=resultado.ingestao.id,
        status=cast(StatusIngestaoLiteral, resultado.ingestao.status.value),
        sobrescrever_editadas=resultado.sobrescrever_editadas,
    )


@router.get(
    "/{prova_id}/paginas/{pagina}/imagem",
    responses={
        200: {"content": {"image/png": {}}},
        304: {"description": "Not Modified"},
        404: {"model": ErroDetalheResponse},
        422: {"model": ErroDetalheResponse},
    },
    summary="Renderiza sob demanda uma página do PDF original da Prova em PNG",
)
def obter_pagina_prova_imagem(
    prova_id: UUID,
    pagina: Annotated[int, Path(ge=1)],
    use_case: Annotated[ObterPaginaProvaImagemUseCase, Depends(get_obter_pagina_prova_use_case)],
    dpi: Annotated[int, Query(ge=72, le=300)] = 150,
    if_none_match: Annotated[str | None, Header(alias="If-None-Match")] = None,
) -> Response:
    resultado = use_case.execute(prova_id, pagina, dpi=dpi)
    return responder_png_com_cache(resultado, if_none_match)
