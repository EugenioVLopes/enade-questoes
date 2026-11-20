from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from application.health import HealthUseCase
from presentation.api.v1.health import router as health_router


def create_app(health_use_case: HealthUseCase) -> FastAPI:
    app = FastAPI(
        title="Enade Questões API",
        version="0.1.0",
        description="API local do sistema de ingestão, classificação e revisão de questões do ENADE.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.health_use_case = health_use_case
    app.include_router(health_router)
    return app
