"""Schema inicial PostgreSQL 16 (12 tabelas, busca combinada e integridade).

Revision ID: 0001_schema_inicial
Revises:
Create Date: 2026-11-21 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_schema_inicial"
down_revision: str | None = None
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE TEXT SEARCH CONFIGURATION pt_unaccent (COPY = pg_catalog.portuguese)")
    op.execute(
        "ALTER TEXT SEARCH CONFIGURATION pt_unaccent "
        "ALTER MAPPING FOR hword, hword_part, word WITH unaccent, portuguese_stem"
    )

    op.create_table(
        "provas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("exame", sa.Text(), nullable=False),
        sa.Column("curso", sa.Text(), nullable=False),
        sa.Column("ano", sa.Integer(), nullable=False),
        sa.Column("questao_inicio", sa.Integer(), nullable=False),
        sa.Column("questao_fim", sa.Integer(), nullable=False),
        sa.Column("caminho_pdf", sa.Text(), nullable=True),
        sa.Column("caminho_gabarito", sa.Text(), nullable=True),
        sa.Column("caminho_extracao_bruta", sa.Text(), nullable=True),
        sa.Column(
            "criada_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "atualizada_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("ano >= 1900", name="ck_provas_ano_minimo"),
        sa.CheckConstraint("questao_inicio >= 1", name="ck_provas_questao_inicio_positiva"),
        sa.CheckConstraint("questao_fim >= questao_inicio", name="ck_provas_questao_fim_valida"),
        sa.UniqueConstraint("exame", "curso", "ano", name="uq_provas_exame_curso_ano"),
    )
    op.create_index(
        "uq_provas_upper_exame_curso_ano",
        "provas",
        [sa.text("upper(exame)"), "curso", "ano"],
        unique=True,
    )

    op.create_table(
        "ingestoes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "prova_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("mensagem_erro", sa.Text(), nullable=True),
        sa.Column(
            "metadados",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("iniciada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("concluida_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "criada_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('pendente', 'processando', 'concluida', 'erro', 'interrompida')",
            name="ck_ingestoes_status",
        ),
    )
    op.create_index("ix_ingestoes_prova_criada_desc", "ingestoes", ["prova_id", sa.text("criada_em DESC")])
    op.create_index("ix_ingestoes_status", "ingestoes", ["status"])

    op.create_table(
        "questoes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "prova_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("componente", sa.Text(), nullable=False),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("enunciado", sa.Text(), nullable=False),
        sa.Column(
            "paginas",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("situacao_gabarito", sa.Text(), nullable=False),
        sa.Column("alternativa_correta", sa.Text(), nullable=True),
        sa.Column(
            "editada_manualmente",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("busca_tsv", postgresql.TSVECTOR(), nullable=True),
        sa.CheckConstraint("numero >= 1", name="ck_questoes_numero_positivo"),
        sa.CheckConstraint("componente IN ('componente_especifico')", name="ck_questoes_componente"),
        sa.CheckConstraint("tipo IN ('objetiva', 'discursiva')", name="ck_questoes_tipo"),
        sa.CheckConstraint(
            "situacao_gabarito IN ('valida', 'anulada', 'pendente')",
            name="ck_questoes_situacao_gabarito",
        ),
        sa.CheckConstraint(
            "alternativa_correta IS NULL OR alternativa_correta IN ('A', 'B', 'C', 'D', 'E')",
            name="ck_questoes_alternativa_correta",
        ),
        sa.CheckConstraint(
            "(situacao_gabarito = 'valida' AND alternativa_correta IS NOT NULL) "
            "OR (situacao_gabarito IN ('anulada', 'pendente') AND alternativa_correta IS NULL)",
            name="ck_questoes_gabarito_coerente",
        ),
        sa.UniqueConstraint("prova_id", "numero", name="uq_questoes_prova_numero"),
    )
    op.create_index("ix_questoes_busca_tsv", "questoes", ["busca_tsv"], postgresql_using="gin")
    op.create_index(
        "ix_questoes_enunciado_trgm",
        "questoes",
        ["enunciado"],
        postgresql_using="gin",
        postgresql_ops={"enunciado": "gin_trgm_ops"},
    )

    op.create_table(
        "alternativas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "questao_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("questoes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("letra", sa.Text(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.CheckConstraint("letra IN ('A', 'B', 'C', 'D', 'E')", name="ck_alternativas_letra"),
        sa.UniqueConstraint("questao_id", "letra", name="uq_alternativas_questao_letra"),
    )
    op.create_index(
        "ix_alternativas_texto_trgm",
        "alternativas",
        ["texto"],
        postgresql_using="gin",
        postgresql_ops={"texto": "gin_trgm_ops"},
    )

    op.create_table(
        "ativos_visuais",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "questao_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("questoes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("origem", sa.Text(), nullable=False),
        sa.Column("alternativa_letra", sa.Text(), nullable=True),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("pagina", sa.Integer(), nullable=True),
        sa.Column("bbox", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("chave_arquivo", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "origem IN ('picture_docling', 'formula_recorte', 'upload_manual')",
            name="ck_ativos_visuais_origem",
        ),
        sa.CheckConstraint(
            "alternativa_letra IS NULL OR alternativa_letra IN ('A', 'B', 'C', 'D', 'E')",
            name="ck_ativos_visuais_alternativa_letra",
        ),
        sa.CheckConstraint("ordem >= 0", name="ck_ativos_visuais_ordem"),
        sa.CheckConstraint("pagina IS NULL OR pagina >= 1", name="ck_ativos_visuais_pagina"),
        sa.CheckConstraint(
            "origem = 'upload_manual' OR pagina IS NOT NULL",
            name="ck_ativos_visuais_pagina_obrigatoria",
        ),
    )
    op.create_index("ix_ativos_visuais_questao_ordem", "ativos_visuais", ["questao_id", "ordem", "id"])

    op.create_table(
        "alertas_extracao",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "questao_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("questoes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("severidade", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("mensagem", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("resolvido_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "codigo IN ('formula_nao_decodificada', 'alternativas_incompletas', "
            "'pdf_via_ocr', 'enunciado_suspeito', 'fonte_symbol_detectada', 'gabarito_ausente_na_prova')",
            name="ck_alertas_extracao_codigo",
        ),
        sa.CheckConstraint("severidade IN ('critico', 'informativo')", name="ck_alertas_extracao_severidade"),
        sa.CheckConstraint("status IN ('aberto', 'resolvido')", name="ck_alertas_extracao_status"),
        sa.CheckConstraint(
            "(status = 'aberto' AND resolvido_em IS NULL) OR (status = 'resolvido' AND resolvido_em IS NOT NULL)",
            name="ck_alertas_extracao_coerencia_status",
        ),
        sa.UniqueConstraint("questao_id", "codigo", name="uq_alertas_extracao_questao_codigo"),
    )
    op.create_index("ix_alertas_extracao_questao_status", "alertas_extracao", ["questao_id", "status"])

    op.create_table(
        "taxonomias",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("codigo", sa.Text(), nullable=False, unique=True),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column("curso_referencia", sa.Text(), nullable=False, server_default=sa.text("''")),
    )

    op.create_table(
        "disciplinas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "taxonomia_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomias.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("nome", sa.Text(), nullable=False),
        sa.Column("ementa", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.UniqueConstraint("taxonomia_id", "codigo", name="uq_disciplinas_taxonomia_codigo"),
    )
    op.create_index("ix_disciplinas_taxonomia_ativa", "disciplinas", ["taxonomia_id", "ativa"])
    op.create_index("ix_disciplinas_taxonomia_ordem", "disciplinas", ["taxonomia_id", "ordem", "codigo"])

    op.create_table(
        "perfis_classificacao",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("versao", sa.Text(), nullable=False),
        sa.Column("diretrizes_gerais", sa.Text(), nullable=False),
        sa.Column("guia_fronteiras", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("template_prompt", sa.Text(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("codigo", "versao", name="uq_perfis_classificacao_codigo_versao"),
    )

    op.create_table(
        "execucoes_classificacao",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "taxonomia_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomias.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "perfil_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("perfis_classificacao.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("snapshot_taxonomia", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("snapshot_perfil", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("escopo", sa.Text(), nullable=False),
        sa.Column("incluir_revisadas", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("total_itens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("processadas", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("divergencias_abertas", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "erros_por_questao",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("cache_hits", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "criada_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("iniciada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("concluida_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "escopo IN ('todas', 'prova_id', 'pendentes', 'disciplina_arquivada', 'questao_ids')",
            name="ck_execucoes_escopo",
        ),
        sa.CheckConstraint(
            "status IN ('pendente', 'processando', 'concluida', 'concluida_com_erros', 'interrompida', 'erro')",
            name="ck_execucoes_status",
        ),
        sa.CheckConstraint(
            "total_itens >= 0 AND processadas >= 0 AND divergencias_abertas >= 0 "
            "AND cache_hits >= 0 AND prompt_tokens >= 0 AND completion_tokens >= 0",
            name="ck_execucoes_contadores",
        ),
    )
    op.create_index("ix_execucoes_classificacao_status", "execucoes_classificacao", ["status"])
    op.create_index(
        "ix_execucoes_classificacao_taxonomia_criada",
        "execucoes_classificacao",
        ["taxonomia_id", sa.text("criada_em DESC")],
    )

    op.create_table(
        "classificacoes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "questao_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("questoes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "taxonomia_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomias.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "execucao_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("execucoes_classificacao.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "substitui_classificacao_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("classificacoes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("disciplina_principal", sa.Text(), nullable=False),
        sa.Column(
            "disciplinas_secundarias",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "topicos",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("justificativa", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("confianca", sa.Float(), nullable=False),
        sa.Column("origem", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("vigente", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("revisao_prioritaria", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "alertas_validacao",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "criada_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("revisada_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("confianca >= 0.0 AND confianca <= 1.0", name="ck_classificacoes_confianca"),
        sa.CheckConstraint("origem IN ('automatica', 'humana')", name="ck_classificacoes_origem"),
        sa.CheckConstraint("status IN ('pendente_revisao', 'aprovada')", name="ck_classificacoes_status"),
    )
    op.create_index(
        "uq_classificacoes_vigente_por_questao_taxonomia",
        "classificacoes",
        ["questao_id", "taxonomia_id"],
        unique=True,
        postgresql_where=sa.text("vigente = true"),
    )
    op.create_index(
        "ix_classificacoes_fila_revisao",
        "classificacoes",
        ["taxonomia_id", "status", "revisao_prioritaria", "confianca"],
        postgresql_where=sa.text("vigente = true"),
    )
    op.create_index(
        "ix_classificacoes_historico",
        "classificacoes",
        ["questao_id", "taxonomia_id", sa.text("criada_em DESC")],
    )
    op.create_index(
        "ix_classificacoes_disciplinas_secundarias_gin",
        "classificacoes",
        ["disciplinas_secundarias"],
        postgresql_using="gin",
    )
    op.create_index("ix_classificacoes_topicos_gin", "classificacoes", ["topicos"], postgresql_using="gin")
    op.create_index(
        "ix_classificacoes_topicos_tsv",
        "classificacoes",
        [sa.text("jsonb_to_tsvector('pt_unaccent', topicos, '[\"string\"]')")],
        postgresql_using="gin",
    )

    op.create_table(
        "divergencias_reclassificacao",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "questao_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("questoes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "taxonomia_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("taxonomias.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "execucao_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("execucoes_classificacao.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "classificacao_vigente_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("classificacoes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "classificacao_candidata_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("classificacoes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("disciplina_principal_candidata", sa.Text(), nullable=False),
        sa.Column(
            "disciplinas_secundarias_candidatas",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "topicos_candidatos",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("justificativa_candidata", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("confianca_candidata", sa.Float(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("resolucao", sa.Text(), nullable=True),
        sa.Column(
            "criada_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("resolvida_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "confianca_candidata >= 0.0 AND confianca_candidata <= 1.0",
            name="ck_divergencias_confianca_candidata",
        ),
        sa.CheckConstraint("status IN ('aberta', 'resolvida')", name="ck_divergencias_status"),
        sa.CheckConstraint(
            "resolucao IS NULL OR resolucao IN ('aceitar_candidata', 'manter_humana', 'editar_manualmente')",
            name="ck_divergencias_resolucao",
        ),
        sa.CheckConstraint(
            "(status = 'aberta' AND resolucao IS NULL AND resolvida_em IS NULL) "
            "OR (status = 'resolvida' AND resolucao IS NOT NULL AND resolvida_em IS NOT NULL)",
            name="ck_divergencias_coerencia_status",
        ),
    )
    op.create_index("ix_divergencias_taxonomia_status", "divergencias_reclassificacao", ["taxonomia_id", "status"])
    op.create_index(
        "ix_divergencias_questao_taxonomia",
        "divergencias_reclassificacao",
        ["questao_id", "taxonomia_id"],
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_questoes_atualizar_busca_tsv()
        RETURNS TRIGGER AS $$
        DECLARE
            texto_alternativas TEXT;
        BEGIN
            SELECT coalesce(string_agg(texto, ' ' ORDER BY letra), '')
            INTO texto_alternativas
            FROM alternativas
            WHERE questao_id = NEW.id;

            NEW.busca_tsv :=
                setweight(to_tsvector('pt_unaccent', coalesce(NEW.enunciado, '')), 'A') ||
                setweight(to_tsvector('pt_unaccent', coalesce(texto_alternativas, '')), 'B');
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_questoes_atualizar_busca_tsv
        BEFORE INSERT OR UPDATE OF enunciado ON questoes
        FOR EACH ROW
        EXECUTE FUNCTION fn_questoes_atualizar_busca_tsv();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_alternativas_atualizar_busca_tsv()
        RETURNS TRIGGER AS $$
        DECLARE
            alvo_questao_id UUID;
        BEGIN
            alvo_questao_id := COALESCE(NEW.questao_id, OLD.questao_id);
            UPDATE questoes q
            SET busca_tsv =
                setweight(to_tsvector('pt_unaccent', coalesce(q.enunciado, '')), 'A') ||
                setweight(
                    to_tsvector(
                        'pt_unaccent',
                        coalesce(
                            (
                                SELECT string_agg(a.texto, ' ' ORDER BY a.letra)
                                FROM alternativas a
                                WHERE a.questao_id = q.id
                            ),
                            ''
                        )
                    ),
                    'B'
                )
            WHERE q.id = alvo_questao_id;

            IF TG_OP = 'UPDATE' AND OLD.questao_id IS DISTINCT FROM NEW.questao_id THEN
                UPDATE questoes q
                SET busca_tsv =
                    setweight(to_tsvector('pt_unaccent', coalesce(q.enunciado, '')), 'A') ||
                    setweight(
                        to_tsvector(
                            'pt_unaccent',
                            coalesce(
                                (
                                    SELECT string_agg(a.texto, ' ' ORDER BY a.letra)
                                    FROM alternativas a
                                    WHERE a.questao_id = q.id
                                ),
                                ''
                            )
                        ),
                        'B'
                    )
                WHERE q.id = OLD.questao_id;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_alternativas_atualizar_busca_tsv
        AFTER INSERT OR UPDATE OF texto, letra, questao_id OR DELETE ON alternativas
        FOR EACH ROW
        EXECUTE FUNCTION fn_alternativas_atualizar_busca_tsv();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_alternativas_atualizar_busca_tsv ON alternativas")
    op.execute("DROP TRIGGER IF EXISTS trg_questoes_atualizar_busca_tsv ON questoes")
    op.execute("DROP FUNCTION IF EXISTS fn_alternativas_atualizar_busca_tsv()")
    op.execute("DROP FUNCTION IF EXISTS fn_questoes_atualizar_busca_tsv()")

    op.drop_table("divergencias_reclassificacao")
    op.drop_table("classificacoes")
    op.drop_table("execucoes_classificacao")
    op.drop_table("perfis_classificacao")
    op.drop_table("disciplinas")
    op.drop_table("taxonomias")
    op.drop_table("alertas_extracao")
    op.drop_table("ativos_visuais")
    op.drop_table("alternativas")
    op.drop_table("questoes")
    op.drop_table("ingestoes")
    op.drop_table("provas")

    op.execute("DROP TEXT SEARCH CONFIGURATION IF EXISTS pt_unaccent")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS unaccent")
