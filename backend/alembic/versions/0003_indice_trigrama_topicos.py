"""Adiciona índice GIN pg_trgm sobre os Tópicos das Classificações.

Revision ID: 0003_indice_trigrama_topicos
Revises: 0002_execucao_escopo_e_progresso
Create Date: 2026-11-22 15:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0003_indice_trigrama_topicos"
down_revision: str | None = "0002_execucao_escopo_e_progresso"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_classificacoes_topicos_trgm",
        "classificacoes",
        [sa.text("(topicos::text) gin_trgm_ops")],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_classificacoes_topicos_trgm", table_name="classificacoes")
