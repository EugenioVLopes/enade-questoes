from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response

from application.midia import ObterAtivoVisualArquivoUseCase
from presentation.api.schemas import ErroDetalheResponse
from presentation.api.v1._http_cache import responder_png_com_cache

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
