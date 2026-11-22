from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, Request, Response, UploadFile, status

from application.midia import ObterAtivoVisualArquivoUseCase
from application.questoes import (
    TAMANHO_MAXIMO_IMAGEM_BYTES,
    AtualizarAtivoVisualUseCase,
    RemoverAtivoVisualUseCase,
)
from domain.enums import LetraAlternativa
from presentation.api.schemas import ErroDetalheResponse
from presentation.api.schemas_questoes import AtivoVisualResponse
from presentation.api.v1._http_cache import responder_png_com_cache
from presentation.api.v1.questoes import serializar_ativo

router = APIRouter(prefix="/api/v1/ativos-visuais", tags=["midia"])


def get_obter_ativo_visual_use_case(request: Request) -> ObterAtivoVisualArquivoUseCase:
    valor = getattr(request.app.state, "obter_ativo_visual_use_case", None)
    if valor is None:
        raise RuntimeError("Dependência 'obter_ativo_visual_use_case' não configurada em app.state.")
    return cast(ObterAtivoVisualArquivoUseCase, valor)


@router.get(
    "/{ativo_id}/arquivo",
    responses={
        200: {"content": {"image/png": {}}},
        304: {"description": "Not Modified"},
        404: {"model": ErroDetalheResponse},
    },
    summary="Entrega o arquivo PNG de um Ativo Visual via ArmazenamentoArquivos",
)
def obter_arquivo_ativo_visual(
    ativo_id: UUID,
    use_case: Annotated[ObterAtivoVisualArquivoUseCase, Depends(get_obter_ativo_visual_use_case)],
    if_none_match: Annotated[str | None, Header(alias="If-None-Match")] = None,
) -> Response:
    resultado = use_case.execute(ativo_id)
    return responder_png_com_cache(resultado, if_none_match)


def get_atualizar_ativo_visual_use_case(request: Request) -> AtualizarAtivoVisualUseCase:
    valor = getattr(request.app.state, "atualizar_ativo_visual_use_case", None)
    if valor is None:
        raise RuntimeError("Dependência 'atualizar_ativo_visual_use_case' não configurada em app.state.")
    return cast(AtualizarAtivoVisualUseCase, valor)


def get_remover_ativo_visual_use_case(request: Request) -> RemoverAtivoVisualUseCase:
    valor = getattr(request.app.state, "remover_ativo_visual_use_case", None)
    if valor is None:
        raise RuntimeError("Dependência 'remover_ativo_visual_use_case' não configurada em app.state.")
    return cast(RemoverAtivoVisualUseCase, valor)


@router.patch(
    "/{ativo_id}",
    response_model=AtivoVisualResponse,
    responses={404: {"model": ErroDetalheResponse}, 422: {"model": ErroDetalheResponse}},
    summary="Reordena, altera a alternativa associada ou substitui a imagem de um Ativo Visual",
)
async def atualizar_ativo_visual(
    ativo_id: UUID,
    use_case: Annotated[AtualizarAtivoVisualUseCase, Depends(get_atualizar_ativo_visual_use_case)],
    arquivo: Annotated[UploadFile | None, File()] = None,
    alternativa_letra: Annotated[LetraAlternativa | None, Form()] = None,
    remover_alternativa_letra: Annotated[bool, Form()] = False,
    ordem: Annotated[int | None, Form(ge=0, le=2_147_483_647)] = None,
) -> AtivoVisualResponse:
    conteudo = await arquivo.read(TAMANHO_MAXIMO_IMAGEM_BYTES + 1) if arquivo is not None else None
    ativo = use_case.execute(
        ativo_id,
        conteudo=conteudo,
        ordem=ordem,
        alternativa_letra=alternativa_letra,
        remover_alternativa_letra=remover_alternativa_letra,
    )
    return serializar_ativo(ativo)


@router.delete(
    "/{ativo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErroDetalheResponse}},
    summary="Remove um Ativo Visual e seu arquivo do armazenamento",
)
def remover_ativo_visual(
    ativo_id: UUID,
    use_case: Annotated[RemoverAtivoVisualUseCase, Depends(get_remover_ativo_visual_use_case)],
) -> Response:
    use_case.execute(ativo_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
