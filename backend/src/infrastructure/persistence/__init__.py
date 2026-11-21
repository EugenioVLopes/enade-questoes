"""Adaptadores de persistência relacional (PostgreSQL / SQLAlchemy 2)."""

from infrastructure.persistence.database import (
    SqlAlchemyDatabaseProbe,
    create_db_engine,
    create_session_factory,
    ping_database,
)
from infrastructure.persistence.models import Base
from infrastructure.persistence.repositorios import (
    RepositorioAtivosVisuaisSqlAlchemy,
    RepositorioClassificacoesSqlAlchemy,
    RepositorioDivergenciasReclassificacaoSqlAlchemy,
    RepositorioExecucoesClassificacaoSqlAlchemy,
    RepositorioIngestoesSqlAlchemy,
    RepositorioPerfisClassificacaoSqlAlchemy,
    RepositorioProvasSqlAlchemy,
    RepositorioQuestoesSqlAlchemy,
    RepositorioTaxonomiasSqlAlchemy,
)

__all__ = [
    "Base",
    "RepositorioAtivosVisuaisSqlAlchemy",
    "RepositorioClassificacoesSqlAlchemy",
    "RepositorioDivergenciasReclassificacaoSqlAlchemy",
    "RepositorioExecucoesClassificacaoSqlAlchemy",
    "RepositorioIngestoesSqlAlchemy",
    "RepositorioPerfisClassificacaoSqlAlchemy",
    "RepositorioProvasSqlAlchemy",
    "RepositorioQuestoesSqlAlchemy",
    "RepositorioTaxonomiasSqlAlchemy",
    "SqlAlchemyDatabaseProbe",
    "create_db_engine",
    "create_session_factory",
    "ping_database",
]
