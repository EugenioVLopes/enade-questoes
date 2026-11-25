from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker


def create_db_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


def create_readonly_db_engine(database_url: str) -> Engine:
    """Cria ``Engine`` configurada em modo estritamente somente-leitura no PostgreSQL."""
    url = make_url(database_url)
    connect_args: dict[str, Any] = {}
    if url.get_backend_name() == "postgresql":
        connect_args["options"] = "-c default_transaction_read_only=on"
    engine = create_engine(database_url, pool_pre_ping=True, connect_args=connect_args)

    @event.listens_for(engine, "begin")
    def _enforcar_begin_somente_leitura(conn: Connection) -> None:
        if conn.dialect.name == "postgresql":
            conn.execute(text("SET TRANSACTION READ ONLY"))

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def create_readonly_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Cria ``sessionmaker`` sem autoflush e com ``SET TRANSACTION READ ONLY`` no PostgreSQL."""
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    @event.listens_for(factory, "after_begin")
    def _enforcar_sessao_somente_leitura(session: Session, transaction: Any, connection: Connection) -> None:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SET TRANSACTION READ ONLY"))

    return factory


def ping_database(engine: Engine) -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


class SqlAlchemyDatabaseProbe:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def ping(self) -> bool:
        return ping_database(self._engine)
