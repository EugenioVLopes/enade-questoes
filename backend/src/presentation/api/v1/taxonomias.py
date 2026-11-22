from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from application.taxonomias import (
    AdicionarDisciplinaUseCase,
    AtualizarDisciplinaUseCase,
    AtualizarTaxonomiaUseCase,
    CriarTaxonomiaUseCase,
    DetalharTaxonomiaUseCase,
    DisciplinaComImpactoDTO,
    DisciplinaInput,
    ListarTaxonomiasUseCase,
    TaxonomiaComImpactoDTO,
)
from presentation.api.schemas import (
    DisciplinaAtualizarRequest,
    DisciplinaCriarRequest,
    DisciplinaResponse,
    ErroDetalheResponse,
    ListaTaxonomiasResponse,
    TaxonomiaAtualizarRequest,
    TaxonomiaCriarRequest,
    TaxonomiaResponse,
)

router = APIRouter(prefix="/api/v1/taxonomias", tags=["taxonomias"])
disciplinas_router = APIRouter(prefix="/api/v1/disciplinas", tags=["taxonomias"])


def _resolver_state(request: Request, attr: str) -> object:
    valor = getattr(request.app.state, attr, None)
    if valor is None:
        raise RuntimeError(f"Dependência '{attr}' não configurada em app.state.")
    return valor


def get_listar_taxonomias_use_case(request: Request) -> ListarTaxonomiasUseCase:
    return cast(ListarTaxonomiasUseCase, _resolver_state(request, "listar_taxonomias_use_case"))


def get_detalhar_taxonomia_use_case(request: Request) -> DetalharTaxonomiaUseCase:
    return cast(DetalharTaxonomiaUseCase, _resolver_state(request, "detalhar_taxonomia_use_case"))


def get_criar_taxonomia_use_case(request: Request) -> CriarTaxonomiaUseCase:
    return cast(CriarTaxonomiaUseCase, _resolver_state(request, "criar_taxonomia_use_case"))


def get_atualizar_taxonomia_use_case(request: Request) -> AtualizarTaxonomiaUseCase:
    return cast(AtualizarTaxonomiaUseCase, _resolver_state(request, "atualizar_taxonomia_use_case"))


def get_adicionar_disciplina_use_case(request: Request) -> AdicionarDisciplinaUseCase:
    return cast(AdicionarDisciplinaUseCase, _resolver_state(request, "adicionar_disciplina_use_case"))


def get_atualizar_disciplina_use_case(request: Request) -> AtualizarDisciplinaUseCase:
    return cast(AtualizarDisciplinaUseCase, _resolver_state(request, "atualizar_disciplina_use_case"))


def _serializar_disciplina(taxonomia_id: UUID, dto: DisciplinaComImpactoDTO) -> DisciplinaResponse:
    disc = dto.disciplina
    return DisciplinaResponse(
        id=disc.id,
        taxonomia_id=taxonomia_id,
        codigo=disc.codigo,
        nome=disc.nome,
        ementa=disc.ementa,
        ativa=disc.ativa,
        classificacoes_vigentes_impactadas=dto.classificacoes_vigentes_impactadas,
    )


def _serializar_taxonomia(dto: TaxonomiaComImpactoDTO) -> TaxonomiaResponse:
    tax = dto.taxonomia
    return TaxonomiaResponse(
        id=tax.id,
        codigo=tax.codigo,
        nome=tax.nome,
        curso_referencia=tax.curso_referencia,
        disciplinas=[_serializar_disciplina(tax.id, item) for item in dto.disciplinas],
    )


@router.get(
    "",
    response_model=ListaTaxonomiasResponse,
    summary="Lista todas as Taxonomias com suas Disciplinas e impacto em classificações vigentes",
)
def listar_taxonomias(
    use_case: Annotated[ListarTaxonomiasUseCase, Depends(get_listar_taxonomias_use_case)],
) -> ListaTaxonomiasResponse:
    itens = [_serializar_taxonomia(item) for item in use_case.execute()]
    return ListaTaxonomiasResponse(itens=itens, total=len(itens))


@router.get(
    "/{taxonomia_id}",
    response_model=TaxonomiaResponse,
    responses={404: {"model": ErroDetalheResponse}},
    summary="Obtém os detalhes de uma Taxonomia e todas as suas Disciplinas",
)
def detalhar_taxonomia(
    taxonomia_id: UUID,
    use_case: Annotated[DetalharTaxonomiaUseCase, Depends(get_detalhar_taxonomia_use_case)],
) -> TaxonomiaResponse:
    return _serializar_taxonomia(use_case.execute(taxonomia_id))


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=TaxonomiaResponse,
    responses={
        409: {"model": ErroDetalheResponse},
        422: {"model": ErroDetalheResponse},
    },
    summary="Cria uma nova Taxonomia com Disciplinas iniciais opcionais",
)
def criar_taxonomia(
    payload: TaxonomiaCriarRequest,
    use_case: Annotated[CriarTaxonomiaUseCase, Depends(get_criar_taxonomia_use_case)],
) -> TaxonomiaResponse:
    disciplinas_input = [
        DisciplinaInput(
            codigo=item.codigo,
            nome=item.nome,
            ementa=item.ementa,
            ativa=item.ativa,
        )
        for item in payload.disciplinas
    ]
    criada = use_case.execute(
        codigo=payload.codigo,
        nome=payload.nome,
        curso_referencia=payload.curso_referencia,
        disciplinas=disciplinas_input,
    )
    return _serializar_taxonomia(criada)


@router.patch(
    "/{taxonomia_id}",
    response_model=TaxonomiaResponse,
    responses={
        404: {"model": ErroDetalheResponse},
        422: {"model": ErroDetalheResponse},
    },
    summary="Atualiza nome e curso de referência de uma Taxonomia (código imutável)",
)
def atualizar_taxonomia(
    taxonomia_id: UUID,
    payload: TaxonomiaAtualizarRequest,
    use_case: Annotated[AtualizarTaxonomiaUseCase, Depends(get_atualizar_taxonomia_use_case)],
) -> TaxonomiaResponse:
    atualizada = use_case.execute(
        taxonomia_id,
        nome=payload.nome,
        curso_referencia=payload.curso_referencia,
    )
    return _serializar_taxonomia(atualizada)


@router.post(
    "/{taxonomia_id}/disciplinas",
    status_code=status.HTTP_201_CREATED,
    response_model=DisciplinaResponse,
    responses={
        404: {"model": ErroDetalheResponse},
        409: {"model": ErroDetalheResponse},
        422: {"model": ErroDetalheResponse},
    },
    summary="Adiciona uma Disciplina a uma Taxonomia existente",
)
def adicionar_disciplina(
    taxonomia_id: UUID,
    payload: DisciplinaCriarRequest,
    use_case: Annotated[AdicionarDisciplinaUseCase, Depends(get_adicionar_disciplina_use_case)],
) -> DisciplinaResponse:
    tid, dto = use_case.execute(
        taxonomia_id,
        codigo=payload.codigo,
        nome=payload.nome,
        ementa=payload.ementa,
        ativa=payload.ativa,
        ordem=payload.ordem,
    )
    return _serializar_disciplina(tid, dto)


@disciplinas_router.patch(
    "/{disciplina_id}",
    response_model=DisciplinaResponse,
    responses={
        404: {"model": ErroDetalheResponse},
        422: {"model": ErroDetalheResponse},
    },
    summary="Atualiza, arquiva ou reativa uma Disciplina expondo o impacto em classificações vigentes",
)
def atualizar_disciplina(
    disciplina_id: UUID,
    payload: DisciplinaAtualizarRequest,
    use_case: Annotated[AtualizarDisciplinaUseCase, Depends(get_atualizar_disciplina_use_case)],
) -> DisciplinaResponse:
    tid, dto = use_case.execute(
        disciplina_id,
        nome=payload.nome,
        ementa=payload.ementa,
        ativa=payload.ativa,
        ordem=payload.ordem,
    )
    return _serializar_disciplina(tid, dto)
