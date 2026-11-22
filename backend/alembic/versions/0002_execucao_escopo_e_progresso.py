"""Adiciona escopo parametrizado e progresso retomável em execucoes_classificacao.

Revision ID: 0002_execucao_escopo_e_progresso
Revises: 0001_schema_inicial
Create Date: 2026-11-22 12:38:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_execucao_escopo_e_progresso"
down_revision: str | None = "0001_schema_inicial"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "execucoes_classificacao",
        sa.Column("escopo_prova_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_execucoes_classificacao_escopo_prova_id",
        "execucoes_classificacao",
        "provas",
        ["escopo_prova_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "execucoes_classificacao",
        sa.Column(
            "escopo_questao_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "execucoes_classificacao",
        sa.Column(
            "questao_ids_alvo",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "execucoes_classificacao",
        sa.Column(
            "questao_ids_concluidas",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("execucoes_classificacao", "questao_ids_concluidas")
    op.drop_column("execucoes_classificacao", "questao_ids_alvo")
    op.drop_column("execucoes_classificacao", "escopo_questao_ids")
    op.drop_constraint("fk_execucoes_classificacao_escopo_prova_id", "execucoes_classificacao", type_="foreignkey")
    op.drop_column("execucoes_classificacao", "escopo_prova_id")
