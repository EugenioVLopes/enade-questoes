"""Composition root da aplicação FastAPI."""

from __future__ import annotations

from fastapi import FastAPI

from application.health import HealthUseCase
from infrastructure.config import Settings
from infrastructure.persistence.database import SqlAlchemyDatabaseProbe, create_db_engine
from presentation.api.app import create_app


def build_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    engine = create_db_engine(resolved_settings.database_url)
    db_probe = SqlAlchemyDatabaseProbe(engine)
    health_use_case = HealthUseCase(db_probe=db_probe)
    return create_app(health_use_case=health_use_case)


app = build_app()
