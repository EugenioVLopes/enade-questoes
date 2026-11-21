"""Ponto de entrada CLI do seed idempotente em PostgreSQL."""

from __future__ import annotations

from application.seed import ResultadoSeed, executar_seed_inicial
from infrastructure.config import Settings
from infrastructure.persistence.database import create_db_engine, create_session_factory
from infrastructure.persistence.repositorios import (
    RepositorioPerfisClassificacaoSqlAlchemy,
    RepositorioTaxonomiasSqlAlchemy,
)


def seed_banco_dados(database_url: str | None = None) -> ResultadoSeed:
    url = database_url or Settings().database_url
    engine = create_db_engine(url)
    try:
        session_factory = create_session_factory(engine)
        repo_taxonomias = RepositorioTaxonomiasSqlAlchemy(session_factory)
        repo_perfis = RepositorioPerfisClassificacaoSqlAlchemy(session_factory)
        return executar_seed_inicial(repo_taxonomias=repo_taxonomias, repo_perfis=repo_perfis)
    finally:
        engine.dispose()


def main() -> None:
    resultado = seed_banco_dados()
    status_tax = "criada" if resultado.taxonomia_criada else "mantida"
    status_perfil = "criado" if resultado.perfil_criado else "mantido"
    print(
        f"Seed concluído: taxonomia='{resultado.taxonomia.codigo}' ({status_tax}, "
        f"{len(resultado.taxonomia.ativas())} disciplinas ativas); "
        f"perfil='{resultado.perfil.codigo}:{resultado.perfil.versao}' ({status_perfil})."
    )


if __name__ == "__main__":
    main()
