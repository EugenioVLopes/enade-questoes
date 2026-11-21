from __future__ import annotations

from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from application.health import HealthUseCase
from presentation.api.schemas import HealthResponse, WorkerHealthResponse

router = APIRouter(prefix="/api/v1", tags=["operacao"])


def get_health_use_case(request: Request) -> HealthUseCase:
    return cast(HealthUseCase, request.app.state.health_use_case)


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse}},
    summary="Verifica a saúde do serviço, conectividade com PostgreSQL e worker local",
)
def health_check(
    use_case: Annotated[HealthUseCase, Depends(get_health_use_case)],
) -> JSONResponse:
    resultado = use_case.execute()
    estado_worker = cast(Literal["ocioso", "ocupado"], resultado.worker.estado)
    tipo_worker = cast(Literal["ingestao", "classificacao"] | None, resultado.worker.tipo)
    status_servico = cast(Literal["ok", "degradado"], resultado.status)
    status_banco = cast(Literal["conectado", "indisponivel"], resultado.banco_dados)

    payload = HealthResponse(
        status=status_servico,
        banco_dados=status_banco,
        worker=WorkerHealthResponse(
            estado=estado_worker,
            tarefa_ativa=resultado.worker.tarefa_ativa,
            tipo=tipo_worker,
            alvo=resultado.worker.alvo,
            processadas=resultado.worker.processadas,
            total=resultado.worker.total,
        ),
    )
    http_status = status.HTTP_200_OK if resultado.banco_dados == "conectado" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=http_status, content=payload.model_dump())
