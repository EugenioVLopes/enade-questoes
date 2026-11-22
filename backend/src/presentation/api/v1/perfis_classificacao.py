from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, status

from application.taxonomias import (
    CriarPerfilClassificacaoUseCase,
    ListarPerfisClassificacaoUseCase,
)
from domain.classificacao import PerfilClassificacao
from presentation.api.schemas import (
    ErroDetalheResponse,
    ListaPerfisClassificacaoResponse,
    PerfilClassificacaoCriarRequest,
    PerfilClassificacaoResponse,
)

router = APIRouter(prefix="/api/v1/perfis-classificacao", tags=["perfis-classificacao"])


def _resolver_state(request: Request, attr: str) -> object:
    valor = getattr(request.app.state, attr, None)
    if valor is None:
        raise RuntimeError(f"Dependência '{attr}' não configurada em app.state.")
    return valor


def get_listar_perfis_use_case(request: Request) -> ListarPerfisClassificacaoUseCase:
    return cast(ListarPerfisClassificacaoUseCase, _resolver_state(request, "listar_perfis_use_case"))


def get_criar_perfil_use_case(request: Request) -> CriarPerfilClassificacaoUseCase:
    return cast(CriarPerfilClassificacaoUseCase, _resolver_state(request, "criar_perfil_use_case"))


def _serializar_perfil(perfil: PerfilClassificacao) -> PerfilClassificacaoResponse:
    return PerfilClassificacaoResponse(
        id=perfil.id,
        codigo=perfil.codigo,
        versao=perfil.versao,
        diretrizes_gerais=perfil.diretrizes_gerais,
        guia_fronteiras=perfil.guia_fronteiras,
        template_prompt=perfil.template_prompt,
        descricao=perfil.descricao,
        criado_em=perfil.criado_em,
    )


@router.get(
    "",
    response_model=ListaPerfisClassificacaoResponse,
    summary="Lista todas as versões imutáveis de Perfil de Classificação",
)
def listar_perfis_classificacao(
    use_case: Annotated[ListarPerfisClassificacaoUseCase, Depends(get_listar_perfis_use_case)],
) -> ListaPerfisClassificacaoResponse:
    itens = [_serializar_perfil(perfil) for perfil in use_case.execute()]
    return ListaPerfisClassificacaoResponse(itens=itens, total=len(itens))


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=PerfilClassificacaoResponse,
    responses={
        404: {"model": ErroDetalheResponse},
        409: {"model": ErroDetalheResponse},
        422: {"model": ErroDetalheResponse},
    },
    summary="Cria uma nova versão imutável de Perfil de Classificação (opcionalmente clonando perfil base)",
)
def criar_perfil_classificacao(
    payload: PerfilClassificacaoCriarRequest,
    use_case: Annotated[CriarPerfilClassificacaoUseCase, Depends(get_criar_perfil_use_case)],
) -> PerfilClassificacaoResponse:
    criado = use_case.execute(
        versao=payload.versao,
        codigo=payload.codigo,
        perfil_base_id=payload.perfil_base_id,
        diretrizes_gerais=payload.diretrizes_gerais,
        guia_fronteiras=payload.guia_fronteiras,
        template_prompt=payload.template_prompt,
        descricao=payload.descricao,
    )
    return _serializar_perfil(criado)
