"""Modelos ORM SQLAlchemy 2 para o schema PostgreSQL 16 do Enade Questões."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarativa SQLAlchemy 2 para os modelos de persistência."""


class ProvaModel(Base):
    __tablename__ = "provas"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    exame: Mapped[str] = mapped_column(Text, nullable=False)
    curso: Mapped[str] = mapped_column(Text, nullable=False)
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    questao_inicio: Mapped[int] = mapped_column(Integer, nullable=False)
    questao_fim: Mapped[int] = mapped_column(Integer, nullable=False)
    caminho_pdf: Mapped[str | None] = mapped_column(Text, nullable=True)
    caminho_gabarito: Mapped[str | None] = mapped_column(Text, nullable=True)
    caminho_extracao_bruta: Mapped[str | None] = mapped_column(Text, nullable=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    atualizada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("ano >= 1900", name="ck_provas_ano_minimo"),
        CheckConstraint("questao_inicio >= 1", name="ck_provas_questao_inicio_positiva"),
        CheckConstraint("questao_fim >= questao_inicio", name="ck_provas_questao_fim_valida"),
        UniqueConstraint("exame", "curso", "ano", name="uq_provas_exame_curso_ano"),
        Index("uq_provas_upper_exame_curso_ano", func.upper(exame), curso, ano, unique=True),
    )


class IngestaoModel(Base):
    __tablename__ = "ingestoes"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    prova_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("provas.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    mensagem_erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadados: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    iniciada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "status IN ('pendente', 'processando', 'concluida', 'erro', 'interrompida')",
            name="ck_ingestoes_status",
        ),
        Index("ix_ingestoes_prova_criada_desc", "prova_id", text("criada_em DESC")),
        Index("ix_ingestoes_status", "status"),
    )


class QuestaoModel(Base):
    __tablename__ = "questoes"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    prova_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("provas.id", ondelete="CASCADE"),
        nullable=False,
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    componente: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    enunciado: Mapped[str] = mapped_column(Text, nullable=False)
    paginas: Mapped[list[int]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    situacao_gabarito: Mapped[str] = mapped_column(Text, nullable=False)
    alternativa_correta: Mapped[str | None] = mapped_column(Text, nullable=True)
    editada_manualmente: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    versao: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    busca_tsv: Mapped[Any] = mapped_column(TSVECTOR, nullable=True)

    alternativas: Mapped[list[AlternativaModel]] = relationship(
        back_populates="questao",
        cascade="all, delete-orphan",
        order_by="AlternativaModel.letra",
    )
    ativos_visuais: Mapped[list[AtivoVisualModel]] = relationship(
        back_populates="questao",
        cascade="all, delete-orphan",
        order_by="(AtivoVisualModel.ordem, AtivoVisualModel.id)",
    )
    alertas_extracao: Mapped[list[AlertaExtracaoModel]] = relationship(
        back_populates="questao",
        cascade="all, delete-orphan",
        order_by="AlertaExtracaoModel.codigo",
    )

    __table_args__ = (
        CheckConstraint("numero >= 1", name="ck_questoes_numero_positivo"),
        CheckConstraint("componente IN ('componente_especifico')", name="ck_questoes_componente"),
        CheckConstraint("tipo IN ('objetiva', 'discursiva')", name="ck_questoes_tipo"),
        CheckConstraint("situacao_gabarito IN ('valida', 'anulada', 'pendente')", name="ck_questoes_situacao_gabarito"),
        CheckConstraint(
            "alternativa_correta IS NULL OR alternativa_correta IN ('A', 'B', 'C', 'D', 'E')",
            name="ck_questoes_alternativa_correta",
        ),
        CheckConstraint(
            "(situacao_gabarito = 'valida' AND alternativa_correta IS NOT NULL) "
            "OR (situacao_gabarito IN ('anulada', 'pendente') AND alternativa_correta IS NULL)",
            name="ck_questoes_gabarito_coerente",
        ),
        UniqueConstraint("prova_id", "numero", name="uq_questoes_prova_numero"),
        Index("ix_questoes_busca_tsv", "busca_tsv", postgresql_using="gin"),
        Index(
            "ix_questoes_enunciado_trgm",
            "enunciado",
            postgresql_using="gin",
            postgresql_ops={"enunciado": "gin_trgm_ops"},
        ),
    )


class AlternativaModel(Base):
    __tablename__ = "alternativas"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    questao_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("questoes.id", ondelete="CASCADE"),
        nullable=False,
    )
    letra: Mapped[str] = mapped_column(Text, nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)

    questao: Mapped[QuestaoModel] = relationship(back_populates="alternativas")

    __table_args__ = (
        CheckConstraint("letra IN ('A', 'B', 'C', 'D', 'E')", name="ck_alternativas_letra"),
        UniqueConstraint("questao_id", "letra", name="uq_alternativas_questao_letra"),
        Index(
            "ix_alternativas_texto_trgm",
            "texto",
            postgresql_using="gin",
            postgresql_ops={"texto": "gin_trgm_ops"},
        ),
    )


class AtivoVisualModel(Base):
    __tablename__ = "ativos_visuais"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    questao_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("questoes.id", ondelete="CASCADE"),
        nullable=False,
    )
    origem: Mapped[str] = mapped_column(Text, nullable=False)
    alternativa_letra: Mapped[str | None] = mapped_column(Text, nullable=True)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    pagina: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox: Mapped[dict[str, float] | None] = mapped_column(JSONB, nullable=True)
    chave_arquivo: Mapped[str | None] = mapped_column(Text, nullable=True)

    questao: Mapped[QuestaoModel] = relationship(back_populates="ativos_visuais")

    __table_args__ = (
        CheckConstraint(
            "origem IN ('picture_docling', 'formula_recorte', 'upload_manual')",
            name="ck_ativos_visuais_origem",
        ),
        CheckConstraint(
            "alternativa_letra IS NULL OR alternativa_letra IN ('A', 'B', 'C', 'D', 'E')",
            name="ck_ativos_visuais_alternativa_letra",
        ),
        CheckConstraint("ordem >= 0", name="ck_ativos_visuais_ordem"),
        CheckConstraint("pagina IS NULL OR pagina >= 1", name="ck_ativos_visuais_pagina"),
        CheckConstraint(
            "origem = 'upload_manual' OR pagina IS NOT NULL",
            name="ck_ativos_visuais_pagina_obrigatoria",
        ),
        Index("ix_ativos_visuais_questao_ordem", "questao_id", "ordem", "id"),
    )


class AlertaExtracaoModel(Base):
    __tablename__ = "alertas_extracao"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    questao_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("questoes.id", ondelete="CASCADE"),
        nullable=False,
    )
    codigo: Mapped[str] = mapped_column(Text, nullable=False)
    severidade: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    mensagem: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    resolvido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    questao: Mapped[QuestaoModel] = relationship(back_populates="alertas_extracao")

    __table_args__ = (
        CheckConstraint(
            "codigo IN ('formula_nao_decodificada', 'alternativas_incompletas', "
            "'pdf_via_ocr', 'enunciado_suspeito', 'fonte_symbol_detectada', 'gabarito_ausente_na_prova')",
            name="ck_alertas_extracao_codigo",
        ),
        CheckConstraint("severidade IN ('critico', 'informativo')", name="ck_alertas_extracao_severidade"),
        CheckConstraint("status IN ('aberto', 'resolvido')", name="ck_alertas_extracao_status"),
        CheckConstraint(
            "(status = 'aberto' AND resolvido_em IS NULL) OR (status = 'resolvido' AND resolvido_em IS NOT NULL)",
            name="ck_alertas_extracao_coerencia_status",
        ),
        UniqueConstraint("questao_id", "codigo", name="uq_alertas_extracao_questao_codigo"),
        Index("ix_alertas_extracao_questao_status", "questao_id", "status"),
    )


class TaxonomiaModel(Base):
    __tablename__ = "taxonomias"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    codigo: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    curso_referencia: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))

    disciplinas: Mapped[list[DisciplinaModel]] = relationship(
        back_populates="taxonomia",
        cascade="all, delete-orphan",
        order_by="(DisciplinaModel.ordem, DisciplinaModel.codigo)",
    )


class DisciplinaModel(Base):
    __tablename__ = "disciplinas"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    taxonomia_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("taxonomias.id", ondelete="CASCADE"),
        nullable=False,
    )
    codigo: Mapped[str] = mapped_column(Text, nullable=False)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    ementa: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    taxonomia: Mapped[TaxonomiaModel] = relationship(back_populates="disciplinas")

    __table_args__ = (
        UniqueConstraint("taxonomia_id", "codigo", name="uq_disciplinas_taxonomia_codigo"),
        Index("ix_disciplinas_taxonomia_ativa", "taxonomia_id", "ativa"),
        Index("ix_disciplinas_taxonomia_ordem", "taxonomia_id", "ordem", "codigo"),
    )


class PerfilClassificacaoModel(Base):
    __tablename__ = "perfis_classificacao"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    codigo: Mapped[str] = mapped_column(Text, nullable=False)
    versao: Mapped[str] = mapped_column(Text, nullable=False)
    diretrizes_gerais: Mapped[str] = mapped_column(Text, nullable=False)
    guia_fronteiras: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    template_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (UniqueConstraint("codigo", "versao", name="uq_perfis_classificacao_codigo_versao"),)


class ExecucaoClassificacaoModel(Base):
    __tablename__ = "execucoes_classificacao"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    taxonomia_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("taxonomias.id", ondelete="RESTRICT"),
        nullable=False,
    )
    perfil_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("perfis_classificacao.id", ondelete="RESTRICT"),
        nullable=False,
    )
    snapshot_taxonomia: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    snapshot_perfil: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    escopo: Mapped[str] = mapped_column(Text, nullable=False)
    incluir_revisadas: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    total_itens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    processadas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    divergencias_abertas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    erros_por_questao: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    cache_hits: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    iniciada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escopo_prova_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("provas.id", ondelete="SET NULL"),
        nullable=True,
    )
    escopo_questao_ids: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    questao_ids_alvo: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    questao_ids_concluidas: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )

    __table_args__ = (
        CheckConstraint(
            "escopo IN ('todas', 'prova_id', 'pendentes', 'disciplina_arquivada', 'questao_ids')",
            name="ck_execucoes_escopo",
        ),
        CheckConstraint(
            "status IN ('pendente', 'processando', 'concluida', 'concluida_com_erros', 'interrompida', 'erro')",
            name="ck_execucoes_status",
        ),
        CheckConstraint(
            "total_itens >= 0 AND processadas >= 0 AND divergencias_abertas >= 0 "
            "AND cache_hits >= 0 AND prompt_tokens >= 0 AND completion_tokens >= 0",
            name="ck_execucoes_contadores",
        ),
        Index("ix_execucoes_classificacao_status", "status"),
        Index("ix_execucoes_classificacao_taxonomia_criada", "taxonomia_id", text("criada_em DESC")),
    )


class ClassificacaoModel(Base):
    __tablename__ = "classificacoes"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    questao_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("questoes.id", ondelete="CASCADE"),
        nullable=False,
    )
    taxonomia_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("taxonomias.id", ondelete="CASCADE"),
        nullable=False,
    )
    execucao_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("execucoes_classificacao.id", ondelete="SET NULL"),
        nullable=True,
    )
    substitui_classificacao_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("classificacoes.id", ondelete="SET NULL"),
        nullable=True,
    )
    disciplina_principal: Mapped[str] = mapped_column(Text, nullable=False)
    disciplinas_secundarias: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    topicos: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    justificativa: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    confianca: Mapped[float] = mapped_column(Float, nullable=False)
    origem: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    vigente: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    revisao_prioritaria: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    alertas_validacao: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    revisada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("confianca >= 0.0 AND confianca <= 1.0", name="ck_classificacoes_confianca"),
        CheckConstraint("origem IN ('automatica', 'humana')", name="ck_classificacoes_origem"),
        CheckConstraint("status IN ('pendente_revisao', 'aprovada')", name="ck_classificacoes_status"),
        Index(
            "uq_classificacoes_vigente_por_questao_taxonomia",
            "questao_id",
            "taxonomia_id",
            unique=True,
            postgresql_where=text("vigente = true"),
        ),
        Index(
            "ix_classificacoes_fila_revisao",
            "taxonomia_id",
            "status",
            "revisao_prioritaria",
            "confianca",
            postgresql_where=text("vigente = true"),
        ),
        Index("ix_classificacoes_historico", "questao_id", "taxonomia_id", text("criada_em DESC")),
        Index("ix_classificacoes_disciplinas_secundarias_gin", "disciplinas_secundarias", postgresql_using="gin"),
        Index("ix_classificacoes_topicos_gin", "topicos", postgresql_using="gin"),
        Index(
            "ix_classificacoes_topicos_trgm",
            text("(topicos::text) gin_trgm_ops"),
            postgresql_using="gin",
        ),
        Index(
            "ix_classificacoes_topicos_tsv",
            text("jsonb_to_tsvector('pt_unaccent', topicos, '[\"string\"]')"),
            postgresql_using="gin",
        ),
    )


class DivergenciaReclassificacaoModel(Base):
    __tablename__ = "divergencias_reclassificacao"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    questao_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("questoes.id", ondelete="CASCADE"),
        nullable=False,
    )
    taxonomia_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("taxonomias.id", ondelete="CASCADE"),
        nullable=False,
    )
    execucao_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("execucoes_classificacao.id", ondelete="CASCADE"),
        nullable=False,
    )
    classificacao_vigente_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("classificacoes.id", ondelete="CASCADE"),
        nullable=False,
    )
    classificacao_candidata_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("classificacoes.id", ondelete="SET NULL"),
        nullable=True,
    )
    disciplina_principal_candidata: Mapped[str] = mapped_column(Text, nullable=False)
    disciplinas_secundarias_candidatas: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    topicos_candidatos: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    justificativa_candidata: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    confianca_candidata: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    resolucao: Mapped[str | None] = mapped_column(Text, nullable=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resolvida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "confianca_candidata >= 0.0 AND confianca_candidata <= 1.0",
            name="ck_divergencias_confianca_candidata",
        ),
        CheckConstraint("status IN ('aberta', 'resolvida')", name="ck_divergencias_status"),
        CheckConstraint(
            "resolucao IS NULL OR resolucao IN ('aceitar_candidata', 'manter_humana', 'editar_manualmente')",
            name="ck_divergencias_resolucao",
        ),
        CheckConstraint(
            "(status = 'aberta' AND resolucao IS NULL AND resolvida_em IS NULL) "
            "OR (status = 'resolvida' AND resolucao IS NOT NULL AND resolvida_em IS NOT NULL)",
            name="ck_divergencias_coerencia_status",
        ),
        Index("ix_divergencias_taxonomia_status", "taxonomia_id", "status"),
        Index("ix_divergencias_questao_taxonomia", "questao_id", "taxonomia_id"),
    )
