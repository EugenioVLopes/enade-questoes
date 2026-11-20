from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class WorkerHealthResponse(BaseModel):
    estado: Literal["ocioso", "ocupado"]
    tarefa_ativa: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degradado"]
    banco_dados: Literal["conectado", "indisponivel"]
    worker: WorkerHealthResponse
