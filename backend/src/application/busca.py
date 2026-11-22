"""Helpers de busca compartilhados entre casos de uso da aplicação."""

from __future__ import annotations

from uuid import UUID

from application.exceptions import RecursoNaoEncontradoError
from application.ports.repositorios import RepositorioTaxonomias
from domain.taxonomia import Taxonomia


def buscar_taxonomia_ou_404(repo_taxonomias: RepositorioTaxonomias, taxonomia_id: UUID) -> Taxonomia:
    taxonomia = repo_taxonomias.buscar_por_id(taxonomia_id)
    if taxonomia is None:
        raise RecursoNaoEncontradoError(f"Taxonomia '{taxonomia_id}' não encontrada.")
    return taxonomia
