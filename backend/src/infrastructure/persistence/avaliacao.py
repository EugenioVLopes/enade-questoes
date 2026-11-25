"""Adaptadores concretos de persistência somente-leitura e snapshot para Avaliação Offline."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session, selectinload, sessionmaker

from application.exceptions import RecursoNaoEncontradoError
from application.ports.avaliacao import RegistroHistoricoClassificacao
from domain.avaliacao import ChaveQuestaoOuro, ConjuntoOuro, ItemConjuntoOuro
from domain.classificacao import PerfilClassificacao
from domain.enums import (
    CodigoAlertaExtracao,
    OrigemClassificacao,
    SeveridadeAlerta,
    SituacaoGabarito,
    StatusAlerta,
    StatusClassificacao,
)
from domain.exceptions import ErroValidacaoDominio
from domain.prova import AlertaExtracao, Prova, Questao
from domain.taxonomia import Taxonomia
from infrastructure.persistence.models import (
    ClassificacaoModel,
    ExecucaoClassificacaoModel,
    PerfilClassificacaoModel,
    ProvaModel,
    QuestaoModel,
    TaxonomiaModel,
)
from infrastructure.persistence.repositorios import (
    _para_dominio_classificacao,
    _para_dominio_perfil,
    _para_dominio_prova,
    _para_dominio_questao,
    _para_dominio_taxonomia,
)

VERSAO_SCHEMA_CONJUNTO_OURO = "1.0"


def _serializar_conjunto_ouro(conjunto: ConjuntoOuro) -> dict[str, Any]:
    edicoes_distintas = {(item.chave.exame, item.chave.curso, item.chave.ano) for item in conjunto.itens}
    return {
        "versao_schema": conjunto.versao_schema,
        "taxonomia_codigo": conjunto.taxonomia_codigo,
        "exportado_em": conjunto.exportado_em.isoformat(),
        "digest": conjunto.digest(),
        "total_itens": conjunto.total_itens,
        "total_edicoes": len(edicoes_distintas),
        "itens": [
            {
                "exame": item.chave.exame,
                "curso": item.chave.curso,
                "ano": item.chave.ano,
                "numero": item.chave.numero,
                "disciplina_principal": item.disciplina_principal,
                "disciplinas_secundarias": list(item.disciplinas_secundarias),
                "situacao_gabarito": item.situacao_gabarito.value,
                "notas": item.notas,
            }
            for item in conjunto.itens
        ],
    }


def _parse_datetime_iso(raw: Any, *, campo: str) -> datetime:
    if not isinstance(raw, str) or not raw.strip():
        raise ErroValidacaoDominio(f"Campo '{campo}' deve ser string ISO-8601 não vazia.")
    texto = raw.strip()
    if texto.endswith("Z"):
        texto = f"{texto[:-1]}+00:00"
    try:
        dt = datetime.fromisoformat(texto)
    except ValueError as err:
        raise ErroValidacaoDominio(f"Timestamp ISO inválido em '{campo}': {raw!r}.") from err
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


class RepositorioConjuntoOuroSqlAlchemy:
    """Implementação concreta de ``RepositorioConjuntoOuro`` (PostgreSQL somente-leitura + snapshot JSON)."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        versao_schema: str = VERSAO_SCHEMA_CONJUNTO_OURO,
    ) -> None:
        self._session_factory = session_factory
        self._versao_schema = versao_schema

    def exportar_elegiveis(self, taxonomia_codigo: str, agora: datetime) -> ConjuntoOuro:
        codigo_limpo = taxonomia_codigo.strip()
        if not codigo_limpo:
            raise ErroValidacaoDominio("Código da Taxonomia não pode ser vazio.")

        with self._session_factory() as session:
            tax_row = session.scalar(select(TaxonomiaModel).where(TaxonomiaModel.codigo == codigo_limpo))
            if tax_row is None:
                raise RecursoNaoEncontradoError(f"Taxonomia '{codigo_limpo}' não encontrada.")

            stmt = (
                select(ClassificacaoModel, QuestaoModel, ProvaModel)
                .join(QuestaoModel, ClassificacaoModel.questao_id == QuestaoModel.id)
                .join(ProvaModel, QuestaoModel.prova_id == ProvaModel.id)
                .options(selectinload(QuestaoModel.alertas_extracao))
                .where(
                    ClassificacaoModel.taxonomia_id == tax_row.id,
                    ClassificacaoModel.vigente.is_(True),
                    ClassificacaoModel.status == StatusClassificacao.APROVADA.value,
                )
            )
            linhas = session.execute(stmt).all()

        itens: list[ItemConjuntoOuro] = []
        for classif_row, questao_row, prova_row in linhas:
            classificacao = _para_dominio_classificacao(classif_row)
            alertas = [
                AlertaExtracao(
                    id=alerta.id,
                    codigo=CodigoAlertaExtracao(alerta.codigo),
                    severidade=SeveridadeAlerta(alerta.severidade),
                    status=StatusAlerta(alerta.status),
                    mensagem=alerta.mensagem,
                    resolvido_em=alerta.resolvido_em,
                )
                for alerta in questao_row.alertas_extracao
            ]
            if not ConjuntoOuro.item_elegivel(classificacao, alertas):
                continue

            chave = ChaveQuestaoOuro(
                exame=prova_row.exame,
                curso=prova_row.curso,
                ano=prova_row.ano,
                numero=questao_row.numero,
            )
            itens.append(
                ItemConjuntoOuro(
                    chave=chave,
                    disciplina_principal=classificacao.disciplina_principal,
                    disciplinas_secundarias=classificacao.disciplinas_secundarias,
                    situacao_gabarito=SituacaoGabarito(questao_row.situacao_gabarito),
                    notas="",
                )
            )

        return ConjuntoOuro(
            versao_schema=self._versao_schema,
            taxonomia_codigo=tax_row.codigo,
            exportado_em=agora,
            itens=tuple(itens),
        )

    def salvar_snapshot(self, conjunto: ConjuntoOuro, destino: str) -> str:
        caminho = Path(destino)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        conteudo = json.dumps(_serializar_conjunto_ouro(conjunto), ensure_ascii=False, indent=2) + "\n"
        conteudo_bytes = conteudo.encode("utf-8")

        fd, caminho_tmp = tempfile.mkstemp(prefix=".tmp-golden-", dir=caminho.parent)
        try:
            with os.fdopen(fd, "wb") as arquivo_tmp:
                arquivo_tmp.write(conteudo_bytes)
                arquivo_tmp.flush()
                os.fsync(arquivo_tmp.fileno())
            os.replace(caminho_tmp, caminho)
        except Exception:
            Path(caminho_tmp).unlink(missing_ok=True)
            raise

        return str(caminho)

    def carregar_snapshot(self, origem: str) -> ConjuntoOuro:
        caminho = Path(origem)
        if not caminho.is_file():
            raise RecursoNaoEncontradoError(f"Arquivo de Conjunto-Ouro não encontrado: '{origem}'.")

        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as err:
            raise ErroValidacaoDominio(f"Falha ao ler JSON de Conjunto-Ouro '{origem}': {err}") from err

        if not isinstance(dados, Mapping):
            raise ErroValidacaoDominio("Snapshot de Conjunto-Ouro deve ser um objeto JSON.")

        versao_schema = dados.get("versao_schema")
        taxonomia_codigo = dados.get("taxonomia_codigo")
        if not isinstance(versao_schema, str) or not isinstance(taxonomia_codigo, str):
            raise ErroValidacaoDominio("Snapshot de Conjunto-Ouro exige 'versao_schema' e 'taxonomia_codigo' (str).")

        exportado_em = _parse_datetime_iso(dados.get("exportado_em"), campo="exportado_em")

        raw_itens = dados.get("itens")
        if not isinstance(raw_itens, list):
            raise ErroValidacaoDominio("Snapshot de Conjunto-Ouro exige lista 'itens'.")

        itens: list[ItemConjuntoOuro] = []
        for idx, raw_item in enumerate(raw_itens):
            if not isinstance(raw_item, Mapping):
                raise ErroValidacaoDominio(f"Item #{idx} do Conjunto-Ouro deve ser um objeto JSON.")
            try:
                chave = ChaveQuestaoOuro(
                    exame=str(raw_item["exame"]),
                    curso=str(raw_item["curso"]),
                    ano=raw_item["ano"],
                    numero=raw_item["numero"],
                )
                itens.append(
                    ItemConjuntoOuro(
                        chave=chave,
                        disciplina_principal=str(raw_item["disciplina_principal"]),
                        disciplinas_secundarias=tuple(raw_item.get("disciplinas_secundarias") or ()),
                        situacao_gabarito=SituacaoGabarito(
                            raw_item.get("situacao_gabarito", SituacaoGabarito.VALIDA.value)
                        ),
                        notas=str(raw_item.get("notas") or ""),
                    )
                )
            except KeyError as err:
                raise ErroValidacaoDominio(
                    f"Campo obrigatório ausente no item #{idx} do Conjunto-Ouro: {err}."
                ) from err
            except (TypeError, ValueError) as err:
                raise ErroValidacaoDominio(f"Item #{idx} inválido no Conjunto-Ouro: {err}.") from err

        return ConjuntoOuro(
            versao_schema=versao_schema,
            taxonomia_codigo=taxonomia_codigo,
            exportado_em=exportado_em,
            itens=tuple(itens),
        )


class ConsultaAvaliacaoSqlAlchemy:
    """Adaptador de leitura somente-leitura para preflight, hidratação e histórico IA × Humano."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def buscar_taxonomia_por_codigo(self, codigo: str) -> Taxonomia | None:
        codigo_limpo = codigo.strip()
        if not codigo_limpo:
            return None
        with self._session_factory() as session:
            stmt = (
                select(TaxonomiaModel)
                .where(TaxonomiaModel.codigo == codigo_limpo)
                .options(selectinload(TaxonomiaModel.disciplinas))
            )
            row = session.scalar(stmt)
            return _para_dominio_taxonomia(row) if row is not None else None

    def buscar_perfil_por_codigo_versao(self, codigo: str, versao: str) -> PerfilClassificacao | None:
        codigo_limpo = codigo.strip()
        versao_limpa = versao.strip()
        if not codigo_limpo or not versao_limpa:
            return None
        with self._session_factory() as session:
            stmt = select(PerfilClassificacaoModel).where(
                PerfilClassificacaoModel.codigo == codigo_limpo,
                PerfilClassificacaoModel.versao == versao_limpa,
            )
            row = session.scalar(stmt)
            return _para_dominio_perfil(row) if row is not None else None

    def carregar_questoes_por_chaves(
        self,
        chaves: Sequence[ChaveQuestaoOuro],
    ) -> dict[ChaveQuestaoOuro, tuple[Prova, Questao]]:
        chaves_unicas = list(dict.fromkeys(chaves))
        if not chaves_unicas:
            return {}

        tuplas = [c.as_tuple() for c in chaves_unicas]
        with self._session_factory() as session:
            stmt = (
                select(QuestaoModel, ProvaModel)
                .join(ProvaModel, QuestaoModel.prova_id == ProvaModel.id)
                .options(
                    selectinload(QuestaoModel.alternativas),
                    selectinload(QuestaoModel.ativos_visuais),
                    selectinload(QuestaoModel.alertas_extracao),
                )
                .where(
                    tuple_(
                        func.upper(ProvaModel.exame),
                        ProvaModel.curso,
                        ProvaModel.ano,
                        QuestaoModel.numero,
                    ).in_(tuplas)
                )
            )
            linhas = session.execute(stmt).all()

        resultado: dict[ChaveQuestaoOuro, tuple[Prova, Questao]] = {}
        for questao_row, prova_row in linhas:
            prova = _para_dominio_prova(prova_row)
            questao = _para_dominio_questao(questao_row)
            chave = ChaveQuestaoOuro(
                exame=prova.exame,
                curso=prova.curso,
                ano=prova.ano,
                numero=questao.numero,
            )
            resultado[chave] = (prova, questao)
        return resultado

    def listar_registros_historico(
        self,
        taxonomia_codigo: str | None = None,
    ) -> list[RegistroHistoricoClassificacao]:
        with self._session_factory() as session:
            tax_id_filtro: UUID | None = None
            if taxonomia_codigo is not None and taxonomia_codigo.strip():
                codigo_limpo = taxonomia_codigo.strip()
                tax_row = session.scalar(select(TaxonomiaModel).where(TaxonomiaModel.codigo == codigo_limpo))
                if tax_row is None:
                    raise RecursoNaoEncontradoError(f"Taxonomia '{codigo_limpo}' não encontrada.")
                tax_id_filtro = tax_row.id
                tax_codigos = {tax_row.id: tax_row.codigo}
            else:
                tax_rows = session.scalars(select(TaxonomiaModel)).all()
                tax_codigos = {row.id: row.codigo for row in tax_rows}

            stmt_classif = select(ClassificacaoModel).order_by(
                ClassificacaoModel.criada_em.asc(),
                ClassificacaoModel.id.asc(),
            )
            if tax_id_filtro is not None:
                stmt_classif = stmt_classif.where(ClassificacaoModel.taxonomia_id == tax_id_filtro)
            classif_rows = session.scalars(stmt_classif).all()

            exec_ids = {row.execucao_id for row in classif_rows if row.execucao_id is not None}
            exec_snapshots: dict[UUID, Mapping[str, Any]] = {}
            if exec_ids:
                stmt_exec = select(ExecucaoClassificacaoModel).where(ExecucaoClassificacaoModel.id.in_(exec_ids))
                for exec_row in session.scalars(stmt_exec).all():
                    exec_snapshots[exec_row.id] = exec_row.snapshot_perfil or {}

        por_id = {row.id: row for row in classif_rows}
        registros: list[RegistroHistoricoClassificacao] = []

        for row in classif_rows:
            if not row.vigente or row.status != StatusClassificacao.APROVADA.value:
                continue

            ai_row: ClassificacaoModel | None = None
            if row.origem == OrigemClassificacao.AUTOMATICA.value:
                ai_row = row
            else:
                visitados: set[UUID] = {row.id}
                atual_id = row.substitui_classificacao_id
                while atual_id is not None and atual_id not in visitados:
                    visitados.add(atual_id)
                    ancestral = por_id.get(atual_id)
                    if ancestral is None:
                        break
                    if ancestral.origem == OrigemClassificacao.AUTOMATICA.value:
                        ai_row = ancestral
                        break
                    atual_id = ancestral.substitui_classificacao_id

            if ai_row is None:
                continue

            snapshot = exec_snapshots.get(ai_row.execucao_id, {}) if ai_row.execucao_id is not None else {}
            perfil_codigo = str(snapshot.get("codigo") or "(desconhecido)").strip() or "(desconhecido)"
            perfil_versao = str(snapshot.get("versao") or "").strip()
            modelo_bruto = snapshot.get("modelo") or snapshot.get("modelo_identidade") or snapshot.get("model") or ""
            modelo = str(modelo_bruto).strip() or "(não registrado)"

            registros.append(
                RegistroHistoricoClassificacao(
                    taxonomia_codigo=tax_codigos.get(row.taxonomia_id, str(row.taxonomia_id)),
                    perfil_codigo=perfil_codigo,
                    perfil_versao=perfil_versao,
                    modelo=modelo,
                    ia_disciplina_principal=ai_row.disciplina_principal,
                    ia_disciplinas_secundarias=tuple(ai_row.disciplinas_secundarias or ()),
                    final_disciplina_principal=row.disciplina_principal,
                    final_disciplinas_secundarias=tuple(row.disciplinas_secundarias or ()),
                )
            )

        return registros
