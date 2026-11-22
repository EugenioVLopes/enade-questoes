"""Adiciona coluna de versão (lock otimista) em questoes.

Revision ID: 0004_versao_questao
Revises: 0003_indice_trigrama_topicos
Create Date: 2026-11-22 18:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0004_versao_questao"
down_revision: str | None = "0003_indice_trigrama_topicos"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "questoes",
        sa.Column("versao", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )


def downgrade() -> None:
    op.drop_column("questoes", "versao")
