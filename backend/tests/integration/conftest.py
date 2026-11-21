from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from infrastructure.config import Settings
from infrastructure.persistence.database import create_db_engine, create_session_factory

BACKEND_DIR = Path(__file__).resolve().parents[2]
TABELAS_TRUNCATE = (
    "divergencias_reclassificacao, classificacoes, execucoes_classificacao, "
    "perfis_classificacao, disciplinas, taxonomias, alertas_extracao, "
    "ativos_visuais, alternativas, questoes, ingestoes, provas"
)


def construir_alembic_config(database_url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


@pytest.fixture(scope="session")
def db_teste_url() -> Iterator[str]:
    base_url = make_url(Settings().database_url)
    nome_banco_teste = f"{base_url.database}_test"
    admin_url = base_url.set(database="postgres")
    test_url = base_url.set(database=nome_banco_teste)
    test_url_str = test_url.render_as_string(hide_password=False)

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) "
                    "FROM pg_stat_activity "
                    "WHERE datname = :nome_banco AND pid <> pg_backend_pid()"
                ),
                {"nome_banco": nome_banco_teste},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{nome_banco_teste}"'))
            conn.execute(text(f'CREATE DATABASE "{nome_banco_teste}"'))
    finally:
        admin_engine.dispose()

    cfg = construir_alembic_config(test_url_str)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

    yield test_url_str


@pytest.fixture()
def session_factory_teste(db_teste_url: str) -> Iterator[sessionmaker[Session]]:
    engine = create_db_engine(db_teste_url)
    factory = create_session_factory(engine)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {TABELAS_TRUNCATE} RESTART IDENTITY CASCADE"))
    try:
        yield factory
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {TABELAS_TRUNCATE} RESTART IDENTITY CASCADE"))
        engine.dispose()
