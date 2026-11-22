"""Predicados SQL compartilhados entre repositórios e consultas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import exists, func, or_, select

from infrastructure.persistence.models import DisciplinaModel


def classificacao_usa_disciplina_arquivada(classificacao: Any, taxonomia_id: UUID) -> Any:
    """Verdadeiro quando a principal ou alguma secundária da Classificação é uma Disciplina arquivada."""
    return exists(
        select(DisciplinaModel.id).where(
            DisciplinaModel.taxonomia_id == taxonomia_id,
            DisciplinaModel.ativa.is_(False),
            or_(
                DisciplinaModel.codigo == classificacao.disciplina_principal,
                classificacao.disciplinas_secundarias.op("@>")(func.jsonb_build_array(DisciplinaModel.codigo)),
            ),
        )
    )
