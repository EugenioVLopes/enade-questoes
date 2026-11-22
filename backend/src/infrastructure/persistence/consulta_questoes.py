"""Read model SQLAlchemy da consulta de Questões, fila de Revisão e contadores de abas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import and_, case, exists, false, func, or_, select
from sqlalchemy.orm import Session, aliased, selectinload, sessionmaker

from application.ports.consulta_questoes import (
    ContadoresRevisao,
    FiltroConsultaQuestoes,
    ItemConsultaQuestao,
    OrdenacaoConsulta,
    PaginaConsultaQuestoes,
    StatusRevisao,
)
from domain.classificacao import DivergenciaReclassificacao
from domain.enums import SeveridadeAlerta, StatusAlerta, StatusClassificacao, StatusDivergencia
from infrastructure.persistence.models import (
    AlertaExtracaoModel,
    ClassificacaoModel,
    DivergenciaReclassificacaoModel,
    ProvaModel,
    QuestaoModel,
)
from infrastructure.persistence.predicados import classificacao_usa_disciplina_arquivada
from infrastructure.persistence.repositorios import (
    _para_dominio_classificacao,
    _para_dominio_divergencia,
    _para_dominio_questao,
    condicao_busca_textual,
)


def _alerta_aberto(*, apenas_critico: bool) -> Any:
    criterios = [
        AlertaExtracaoModel.questao_id == QuestaoModel.id,
        AlertaExtracaoModel.status == StatusAlerta.ABERTO.value,
    ]
    if apenas_critico:
        criterios.append(AlertaExtracaoModel.severidade == SeveridadeAlerta.CRITICO.value)
    return exists(select(AlertaExtracaoModel.id).where(*criterios))


def _divergencia_aberta(taxonomia_id: UUID) -> Any:
    return exists(
        select(DivergenciaReclassificacaoModel.id).where(
            DivergenciaReclassificacaoModel.questao_id == QuestaoModel.id,
            DivergenciaReclassificacaoModel.taxonomia_id == taxonomia_id,
            DivergenciaReclassificacaoModel.status == StatusDivergencia.ABERTA.value,
        )
    )


class ConsultaQuestoesSqlAlchemy:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def consultar(self, filtro: FiltroConsultaQuestoes) -> PaginaConsultaQuestoes:
        classificacao = aliased(ClassificacaoModel, name="classificacao_vigente")
        taxonomia_id = filtro.taxonomia_id
        alerta_critico = _alerta_aberto(apenas_critico=True)

        if taxonomia_id is not None:
            # D2: aprovadas nunca são prioritárias; sem vigente, vale o alerta crítico aberto.
            prioridade = case(
                (classificacao.id.is_(None), alerta_critico),
                else_=and_(
                    classificacao.status == StatusClassificacao.PENDENTE_REVISAO.value,
                    classificacao.revisao_prioritaria.is_(True),
                ),
            )
            tem_divergencia = _divergencia_aberta(taxonomia_id)
            usa_arquivada = classificacao_usa_disciplina_arquivada(classificacao, taxonomia_id)
        else:
            prioridade = alerta_critico
            tem_divergencia = false()
            usa_arquivada = false()

        criterios: list[Any] = []
        relevancia: Any = None
        termo = (filtro.termo or "").strip()
        if termo:
            condicao, relevancia = condicao_busca_textual(termo, taxonomia_id=taxonomia_id)
            criterios.append(condicao)
        if filtro.prova_id is not None:
            criterios.append(QuestaoModel.prova_id == filtro.prova_id)
        if filtro.ano is not None:
            criterios.append(ProvaModel.ano == filtro.ano)
        if filtro.situacao_gabarito is not None:
            criterios.append(QuestaoModel.situacao_gabarito == filtro.situacao_gabarito.value)
        if filtro.com_alerta_extracao is not None:
            alerta_aberto = _alerta_aberto(apenas_critico=False)
            criterios.append(alerta_aberto if filtro.com_alerta_extracao else ~alerta_aberto)

        if taxonomia_id is not None:
            criterios.extend(self._criterios_classificacao(filtro, classificacao))
            if filtro.revisao_prioritaria is not None:
                criterios.append(prioridade.is_(filtro.revisao_prioritaria))
            if filtro.com_divergencia is not None:
                criterios.append(tem_divergencia if filtro.com_divergencia else ~tem_divergencia)
            if filtro.usa_disciplina_arquivada is not None:
                criterios.append(usa_arquivada if filtro.usa_disciplina_arquivada else ~usa_arquivada)

        def _aplicar_joins(stmt: Any) -> Any:
            stmt = stmt.join(ProvaModel, QuestaoModel.prova_id == ProvaModel.id)
            if taxonomia_id is not None:
                stmt = stmt.outerjoin(
                    classificacao,
                    and_(
                        classificacao.questao_id == QuestaoModel.id,
                        classificacao.taxonomia_id == taxonomia_id,
                        classificacao.vigente.is_(True),
                    ),
                )
            return stmt.where(*criterios)

        colunas: list[Any] = [
            QuestaoModel,
            ProvaModel.exame,
            ProvaModel.curso,
            ProvaModel.ano,
            prioridade.label("revisao_prioritaria"),
            tem_divergencia.label("tem_divergencia_aberta"),
            usa_arquivada.label("usa_disciplina_arquivada"),
        ]
        if taxonomia_id is not None:
            colunas.append(classificacao)

        stmt = _aplicar_joins(select(*colunas).select_from(QuestaoModel)).options(
            selectinload(QuestaoModel.alternativas),
            selectinload(QuestaoModel.ativos_visuais),
            selectinload(QuestaoModel.alertas_extracao),
        )

        ordenacao: list[Any] = []
        if filtro.ordenacao == OrdenacaoConsulta.FILA_REVISAO:
            ordenacao.append(prioridade.desc())
            if taxonomia_id is not None:
                ordenacao.append(classificacao.confianca.asc().nulls_last())
        elif relevancia is not None:
            ordenacao.append(relevancia.desc())
        ordenacao.extend([ProvaModel.ano.desc(), QuestaoModel.numero.asc()])
        if filtro.ordenacao == OrdenacaoConsulta.CONSULTA:
            ordenacao.extend([ProvaModel.exame.asc(), ProvaModel.curso.asc()])
        ordenacao.append(QuestaoModel.id.asc())
        stmt = stmt.order_by(*ordenacao).offset(filtro.deslocamento).limit(filtro.limite)

        contagem = select(func.count()).select_from(
            _aplicar_joins(select(QuestaoModel.id).select_from(QuestaoModel)).subquery()
        )

        with self._session_factory() as session:
            total = int(session.scalar(contagem) or 0)
            itens = tuple(
                ItemConsultaQuestao(
                    questao=_para_dominio_questao(row[0]),
                    prova_exame=row[1],
                    prova_curso=row[2],
                    prova_ano=row[3],
                    revisao_prioritaria=bool(row[4]),
                    tem_divergencia_aberta=bool(row[5]),
                    usa_disciplina_arquivada=bool(row[6]),
                    classificacao=(
                        _para_dominio_classificacao(row[7]) if len(row) > 7 and row[7] is not None else None
                    ),
                )
                for row in session.execute(stmt).all()
            )
        return PaginaConsultaQuestoes(itens=itens, total=total)

    @staticmethod
    def _criterios_classificacao(filtro: FiltroConsultaQuestoes, classificacao: Any) -> list[Any]:
        criterios: list[Any] = []
        if filtro.disciplina_codigo is not None:
            principal = classificacao.disciplina_principal == filtro.disciplina_codigo
            if filtro.incluir_secundarias:
                criterios.append(
                    or_(principal, classificacao.disciplinas_secundarias.contains([filtro.disciplina_codigo]))
                )
            else:
                criterios.append(principal)
        if filtro.topico is not None:
            criterios.append(classificacao.topicos.contains([filtro.topico]))

        status = filtro.status_revisao
        if status == StatusRevisao.SEM_CLASSIFICACAO:
            criterios.append(classificacao.id.is_(None))
        elif status == StatusRevisao.PENDENTE_REVISAO:
            criterios.append(classificacao.status == StatusClassificacao.PENDENTE_REVISAO.value)
        elif status == StatusRevisao.APROVADA:
            criterios.append(classificacao.status == StatusClassificacao.APROVADA.value)
        elif status == StatusRevisao.PENDENTE:
            criterios.append(
                or_(
                    classificacao.id.is_(None),
                    classificacao.status == StatusClassificacao.PENDENTE_REVISAO.value,
                )
            )
        return criterios

    def contar_abas_revisao(self, taxonomia_id: UUID) -> ContadoresRevisao:
        aprovada_vigente = exists(
            select(ClassificacaoModel.id).where(
                ClassificacaoModel.questao_id == QuestaoModel.id,
                ClassificacaoModel.taxonomia_id == taxonomia_id,
                ClassificacaoModel.vigente.is_(True),
                ClassificacaoModel.status == StatusClassificacao.APROVADA.value,
            )
        )
        arquivada = exists(
            select(ClassificacaoModel.id).where(
                ClassificacaoModel.questao_id == QuestaoModel.id,
                ClassificacaoModel.taxonomia_id == taxonomia_id,
                ClassificacaoModel.vigente.is_(True),
                classificacao_usa_disciplina_arquivada(ClassificacaoModel, taxonomia_id),
            )
        )
        with self._session_factory() as session:
            pendentes = session.scalar(select(func.count(QuestaoModel.id)).where(~aprovada_vigente))
            divergencias = session.scalar(
                select(func.count(func.distinct(DivergenciaReclassificacaoModel.questao_id))).where(
                    DivergenciaReclassificacaoModel.taxonomia_id == taxonomia_id,
                    DivergenciaReclassificacaoModel.status == StatusDivergencia.ABERTA.value,
                )
            )
            com_arquivada = session.scalar(select(func.count(QuestaoModel.id)).where(arquivada))
        return ContadoresRevisao(
            pendentes=int(pendentes or 0),
            divergencias=int(divergencias or 0),
            disciplina_arquivada=int(com_arquivada or 0),
        )

    def listar_divergencias_abertas_da_questao(self, questao_id: UUID) -> list[DivergenciaReclassificacao]:
        with self._session_factory() as session:
            stmt = (
                select(DivergenciaReclassificacaoModel)
                .where(
                    DivergenciaReclassificacaoModel.questao_id == questao_id,
                    DivergenciaReclassificacaoModel.status == StatusDivergencia.ABERTA.value,
                )
                .order_by(DivergenciaReclassificacaoModel.criada_em.desc(), DivergenciaReclassificacaoModel.id.asc())
            )
            return [_para_dominio_divergencia(row) for row in session.scalars(stmt).all()]
