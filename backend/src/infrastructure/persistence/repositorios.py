"""Repositórios concretos SQLAlchemy 2 e mappers domínio ↔ ORM."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import case, delete, exists, func, or_, select, text, true, update
from sqlalchemy.orm import Session, selectinload, sessionmaker

from domain.classificacao import (
    Classificacao,
    DivergenciaReclassificacao,
    ExecucaoClassificacao,
    PerfilClassificacao,
)
from domain.enums import (
    CodigoAlertaExtracao,
    ComponenteProva,
    EscopoExecucao,
    LetraAlternativa,
    OrigemAtivoVisual,
    OrigemClassificacao,
    ResolucaoDivergencia,
    SeveridadeAlerta,
    SituacaoGabarito,
    StatusAlerta,
    StatusClassificacao,
    StatusDivergencia,
    StatusExecucaoClassificacao,
    StatusIngestao,
    TipoQuestao,
)
from domain.exceptions import ErroInvarianteDominio, ErroValidacaoDominio
from domain.prova import (
    AlertaExtracao,
    Alternativa,
    AtivoVisual,
    BoundingBox,
    FaixaQuestoes,
    Gabarito,
    Ingestao,
    MetadadosIngestao,
    Prova,
    Questao,
)
from domain.taxonomia import Disciplina, Taxonomia
from infrastructure.persistence.models import (
    AlertaExtracaoModel,
    AlternativaModel,
    AtivoVisualModel,
    ClassificacaoModel,
    DisciplinaModel,
    DivergenciaReclassificacaoModel,
    ExecucaoClassificacaoModel,
    IngestaoModel,
    PerfilClassificacaoModel,
    ProvaModel,
    QuestaoModel,
    TaxonomiaModel,
)

_CARACTERES_TECNICOS_RE = re.compile(r"[()\[\]{}<>=+/*_~^#\\]")


def _agora_utc() -> datetime:
    return datetime.now(UTC)


def _descongelar_json(valor: Any) -> Any:
    if isinstance(valor, Mapping):
        return {str(chave): _descongelar_json(item) for chave, item in valor.items()}
    if isinstance(valor, list | tuple):
        return [_descongelar_json(item) for item in valor]
    if isinstance(valor, set | frozenset):
        return sorted((_descongelar_json(item) for item in valor), key=str)
    return valor


def _escapar_like(termo: str) -> str:
    return termo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---------------------------------------------------------------------------
# Mappers Domínio <-> ORM
# ---------------------------------------------------------------------------


def _para_dominio_prova(row: ProvaModel) -> Prova:
    return Prova(
        id=row.id,
        exame=row.exame,
        curso=row.curso,
        ano=row.ano,
        faixa_ce=FaixaQuestoes(inicio=row.questao_inicio, fim=row.questao_fim),
        caminho_pdf=row.caminho_pdf,
        caminho_gabarito=row.caminho_gabarito,
        caminho_extracao_bruta=row.caminho_extracao_bruta,
        criada_em=row.criada_em,
        atualizada_em=row.atualizada_em,
    )


def _parse_uuid_opcional(valor: Any) -> UUID | None:
    if valor is None or valor == "":
        return None
    return valor if isinstance(valor, UUID) else UUID(str(valor))


def _para_dominio_ingestao(row: IngestaoModel) -> Ingestao:
    raw_meta = row.metadados or {}
    status_encadeado_raw = raw_meta.get("status_classificacao_encadeada")
    metadados = MetadadosIngestao(
        total_questoes_extraidas=int(raw_meta.get("total_questoes_extraidas", 0)),
        imagens_detectadas=int(raw_meta.get("imagens_detectadas", 0)),
        imagens_filtradas_margem=int(raw_meta.get("imagens_filtradas_margem", 0)),
        formulas_recortadas=int(raw_meta.get("formulas_recortadas", 0)),
        usou_ocr=bool(raw_meta.get("usou_ocr", False)),
        paginas_fonte_symbol=tuple(int(p) for p in raw_meta.get("paginas_fonte_symbol", ())),
        gabarito_enviado=bool(raw_meta.get("gabarito_enviado", False)),
        taxonomia_id_encadeada=_parse_uuid_opcional(raw_meta.get("taxonomia_id_encadeada")),
        perfil_id_encadeada=_parse_uuid_opcional(raw_meta.get("perfil_id_encadeada")),
        execucao_classificacao_id=_parse_uuid_opcional(raw_meta.get("execucao_classificacao_id")),
        status_classificacao_encadeada=(str(status_encadeado_raw) if status_encadeado_raw is not None else None),
    )
    return Ingestao(
        id=row.id,
        prova_id=row.prova_id,
        status=StatusIngestao(row.status),
        mensagem_erro=row.mensagem_erro,
        metadados=metadados,
        iniciada_em=row.iniciada_em,
        concluida_em=row.concluida_em,
        criada_em=row.criada_em,
    )


def _para_dict_metadados_ingestao(metadados: MetadadosIngestao) -> dict[str, Any]:
    dados: dict[str, Any] = {
        "total_questoes_extraidas": metadados.total_questoes_extraidas,
        "imagens_detectadas": metadados.imagens_detectadas,
        "imagens_filtradas_margem": metadados.imagens_filtradas_margem,
        "formulas_recortadas": metadados.formulas_recortadas,
        "usou_ocr": metadados.usou_ocr,
        "paginas_fonte_symbol": list(metadados.paginas_fonte_symbol),
        "gabarito_enviado": metadados.gabarito_enviado,
    }
    if metadados.taxonomia_id_encadeada is not None:
        dados["taxonomia_id_encadeada"] = str(metadados.taxonomia_id_encadeada)
    if metadados.perfil_id_encadeada is not None:
        dados["perfil_id_encadeada"] = str(metadados.perfil_id_encadeada)
    if metadados.execucao_classificacao_id is not None:
        dados["execucao_classificacao_id"] = str(metadados.execucao_classificacao_id)
    if metadados.status_classificacao_encadeada is not None:
        dados["status_classificacao_encadeada"] = metadados.status_classificacao_encadeada
    return dados


def _para_dominio_ativo(row: AtivoVisualModel) -> AtivoVisual:
    bbox = (
        BoundingBox(
            x0=float(row.bbox["x0"]),
            y0=float(row.bbox["y0"]),
            x1=float(row.bbox["x1"]),
            y1=float(row.bbox["y1"]),
        )
        if row.bbox is not None
        else None
    )
    return AtivoVisual(
        id=row.id,
        questao_id=row.questao_id,
        origem=OrigemAtivoVisual(row.origem),
        ordem=row.ordem,
        alternativa_letra=LetraAlternativa(row.alternativa_letra) if row.alternativa_letra else None,
        pagina=row.pagina,
        bbox=bbox,
        chave_arquivo=row.chave_arquivo,
    )


def _para_dict_bbox(bbox: BoundingBox | None) -> dict[str, float] | None:
    if bbox is None:
        return None
    return {"x0": float(bbox.x0), "y0": float(bbox.y0), "x1": float(bbox.x1), "y1": float(bbox.y1)}


def _para_dominio_questao(row: QuestaoModel) -> Questao:
    alternativas = [
        Alternativa(id=alt.id, letra=LetraAlternativa(alt.letra), texto=alt.texto)
        for alt in sorted(row.alternativas, key=lambda item: item.letra)
    ]
    ativos = [
        _para_dominio_ativo(ativo) for ativo in sorted(row.ativos_visuais, key=lambda item: (item.ordem, item.id))
    ]
    alertas = [
        AlertaExtracao(
            id=alerta.id,
            codigo=CodigoAlertaExtracao(alerta.codigo),
            severidade=SeveridadeAlerta(alerta.severidade),
            status=StatusAlerta(alerta.status),
            mensagem=alerta.mensagem,
            resolvido_em=alerta.resolvido_em,
        )
        for alerta in sorted(row.alertas_extracao, key=lambda item: item.codigo)
    ]
    gabarito = Gabarito(
        situacao_gabarito=SituacaoGabarito(row.situacao_gabarito),
        alternativa_correta=LetraAlternativa(row.alternativa_correta) if row.alternativa_correta else None,
    )
    return Questao(
        id=row.id,
        prova_id=row.prova_id,
        numero=row.numero,
        enunciado=row.enunciado,
        componente=ComponenteProva(row.componente),
        tipo=TipoQuestao(row.tipo),
        paginas=tuple(int(p) for p in (row.paginas or ())),
        alternativas=alternativas,
        ativos_visuais=ativos,
        gabarito=gabarito,
        alertas_extracao=alertas,
        editada_manualmente=row.editada_manualmente,
    )


def _para_dominio_taxonomia(row: TaxonomiaModel) -> Taxonomia:
    disciplinas = [
        Disciplina(
            id=disc.id,
            codigo=disc.codigo,
            nome=disc.nome,
            ementa=disc.ementa,
            ativa=disc.ativa,
        )
        for disc in sorted(row.disciplinas, key=lambda item: (item.ordem, item.codigo))
    ]
    return Taxonomia(
        id=row.id,
        codigo=row.codigo,
        nome=row.nome,
        curso_referencia=row.curso_referencia,
        disciplinas=disciplinas,
    )


def _para_dominio_perfil(row: PerfilClassificacaoModel) -> PerfilClassificacao:
    return PerfilClassificacao(
        id=row.id,
        codigo=row.codigo,
        versao=row.versao,
        diretrizes_gerais=row.diretrizes_gerais,
        guia_fronteiras=row.guia_fronteiras,
        template_prompt=row.template_prompt,
        descricao=row.descricao,
        criado_em=row.criado_em,
    )


def _para_dominio_execucao(row: ExecucaoClassificacaoModel) -> ExecucaoClassificacao:
    return ExecucaoClassificacao(
        id=row.id,
        taxonomia_id=row.taxonomia_id,
        perfil_id=row.perfil_id,
        snapshot_taxonomia=row.snapshot_taxonomia,
        snapshot_perfil=row.snapshot_perfil,
        escopo=EscopoExecucao(row.escopo),
        incluir_revisadas=row.incluir_revisadas,
        status=StatusExecucaoClassificacao(row.status),
        total_itens=row.total_itens,
        processadas=row.processadas,
        divergencias_abertas=row.divergencias_abertas,
        erros_por_questao=dict(row.erros_por_questao or {}),
        cache_hits=row.cache_hits,
        prompt_tokens=row.prompt_tokens,
        completion_tokens=row.completion_tokens,
        criada_em=row.criada_em,
        iniciada_em=row.iniciada_em,
        concluida_em=row.concluida_em,
    )


def _para_dominio_classificacao(row: ClassificacaoModel) -> Classificacao:
    return Classificacao(
        id=row.id,
        questao_id=row.questao_id,
        taxonomia_id=row.taxonomia_id,
        disciplina_principal=row.disciplina_principal,
        disciplinas_secundarias=tuple(row.disciplinas_secundarias or ()),
        topicos=tuple(row.topicos or ()),
        justificativa=row.justificativa,
        confianca=row.confianca,
        origem=OrigemClassificacao(row.origem),
        status=StatusClassificacao(row.status),
        vigente=row.vigente,
        revisao_prioritaria=row.revisao_prioritaria,
        execucao_id=row.execucao_id,
        substitui_classificacao_id=row.substitui_classificacao_id,
        alertas_validacao=tuple(row.alertas_validacao or ()),
        criada_em=row.criada_em,
        revisada_em=row.revisada_em,
    )


def _para_modelo_classificacao(classificacao: Classificacao, *, criada_em_padrao: datetime) -> ClassificacaoModel:
    return ClassificacaoModel(
        id=classificacao.id,
        questao_id=classificacao.questao_id,
        taxonomia_id=classificacao.taxonomia_id,
        execucao_id=classificacao.execucao_id,
        substitui_classificacao_id=classificacao.substitui_classificacao_id,
        disciplina_principal=classificacao.disciplina_principal,
        disciplinas_secundarias=list(classificacao.disciplinas_secundarias),
        topicos=list(classificacao.topicos),
        justificativa=classificacao.justificativa,
        confianca=classificacao.confianca,
        origem=classificacao.origem.value,
        status=classificacao.status.value,
        vigente=classificacao.vigente,
        revisao_prioritaria=classificacao.revisao_prioritaria,
        alertas_validacao=list(classificacao.alertas_validacao),
        criada_em=classificacao.criada_em or criada_em_padrao,
        revisada_em=classificacao.revisada_em,
    )


def _para_dominio_divergencia(row: DivergenciaReclassificacaoModel) -> DivergenciaReclassificacao:
    return DivergenciaReclassificacao(
        id=row.id,
        questao_id=row.questao_id,
        taxonomia_id=row.taxonomia_id,
        execucao_id=row.execucao_id,
        classificacao_vigente_id=row.classificacao_vigente_id,
        disciplina_principal_candidata=row.disciplina_principal_candidata,
        disciplinas_secundarias_candidatas=tuple(row.disciplinas_secundarias_candidatas or ()),
        topicos_candidatos=tuple(row.topicos_candidatos or ()),
        justificativa_candidata=row.justificativa_candidata,
        confianca_candidata=row.confianca_candidata,
        classificacao_candidata_id=row.classificacao_candidata_id,
        status=StatusDivergencia(row.status),
        resolucao=ResolucaoDivergencia(row.resolucao) if row.resolucao else None,
        criada_em=row.criada_em,
        resolvida_em=row.resolvida_em,
    )


# ---------------------------------------------------------------------------
# Repositórios
# ---------------------------------------------------------------------------


class RepositorioProvasSqlAlchemy:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def salvar(self, prova: Prova) -> Prova:
        agora = _agora_utc()
        if prova.faixa_ce is None:
            raise ErroValidacaoDominio("Prova exige 'faixa_ce' definida para persistência.")
        with self._session_factory.begin() as session:
            row = session.get(ProvaModel, prova.id)
            if row is None:
                row = ProvaModel(
                    id=prova.id,
                    exame=prova.exame,
                    curso=prova.curso,
                    ano=prova.ano,
                    questao_inicio=prova.faixa_ce.inicio,
                    questao_fim=prova.faixa_ce.fim,
                    caminho_pdf=prova.caminho_pdf,
                    caminho_gabarito=prova.caminho_gabarito,
                    caminho_extracao_bruta=prova.caminho_extracao_bruta,
                    criada_em=prova.criada_em or agora,
                    atualizada_em=prova.atualizada_em or agora,
                )
                session.add(row)
            else:
                row.exame = prova.exame
                row.curso = prova.curso
                row.ano = prova.ano
                row.questao_inicio = prova.faixa_ce.inicio
                row.questao_fim = prova.faixa_ce.fim
                row.caminho_pdf = prova.caminho_pdf
                row.caminho_gabarito = prova.caminho_gabarito
                row.caminho_extracao_bruta = prova.caminho_extracao_bruta
                if prova.criada_em is not None:
                    row.criada_em = prova.criada_em
                row.atualizada_em = prova.atualizada_em or agora
            session.flush()
            return _para_dominio_prova(row)

    def buscar_por_id(self, prova_id: UUID) -> Prova | None:
        with self._session_factory() as session:
            row = session.get(ProvaModel, prova_id)
            return _para_dominio_prova(row) if row is not None else None

    def buscar_por_chave_natural(self, exame: str, curso: str, ano: int) -> Prova | None:
        exame_norm = exame.strip().upper()
        curso_norm = curso.strip()
        with self._session_factory() as session:
            stmt = select(ProvaModel).where(
                func.upper(ProvaModel.exame) == exame_norm,
                ProvaModel.curso == curso_norm,
                ProvaModel.ano == ano,
            )
            row = session.scalar(stmt)
            return _para_dominio_prova(row) if row is not None else None

    def listar(self) -> list[Prova]:
        with self._session_factory() as session:
            stmt = select(ProvaModel).order_by(
                ProvaModel.ano.desc(),
                ProvaModel.exame.asc(),
                ProvaModel.curso.asc(),
                ProvaModel.id.asc(),
            )
            return [_para_dominio_prova(row) for row in session.scalars(stmt).all()]


class RepositorioIngestoesSqlAlchemy:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def salvar(self, ingestao: Ingestao) -> Ingestao:
        agora = _agora_utc()
        metadados_dict = _para_dict_metadados_ingestao(ingestao.metadados)
        with self._session_factory.begin() as session:
            row = session.get(IngestaoModel, ingestao.id)
            if row is None:
                row = IngestaoModel(
                    id=ingestao.id,
                    prova_id=ingestao.prova_id,
                    status=ingestao.status.value,
                    mensagem_erro=ingestao.mensagem_erro,
                    metadados=metadados_dict,
                    iniciada_em=ingestao.iniciada_em,
                    concluida_em=ingestao.concluida_em,
                    criada_em=ingestao.criada_em or agora,
                )
                session.add(row)
            else:
                row.prova_id = ingestao.prova_id
                row.status = ingestao.status.value
                row.mensagem_erro = ingestao.mensagem_erro
                row.metadados = metadados_dict
                row.iniciada_em = ingestao.iniciada_em
                row.concluida_em = ingestao.concluida_em
                if ingestao.criada_em is not None:
                    row.criada_em = ingestao.criada_em
            session.flush()
            return _para_dominio_ingestao(row)

    def buscar_por_id(self, ingestao_id: UUID) -> Ingestao | None:
        with self._session_factory() as session:
            row = session.get(IngestaoModel, ingestao_id)
            return _para_dominio_ingestao(row) if row is not None else None

    def buscar_ultima_por_prova(self, prova_id: UUID) -> Ingestao | None:
        with self._session_factory() as session:
            stmt = (
                select(IngestaoModel)
                .where(IngestaoModel.prova_id == prova_id)
                .order_by(IngestaoModel.criada_em.desc(), IngestaoModel.id.desc())
                .limit(1)
            )
            row = session.scalar(stmt)
            return _para_dominio_ingestao(row) if row is not None else None

    def listar_por_prova(self, prova_id: UUID) -> list[Ingestao]:
        with self._session_factory() as session:
            stmt = (
                select(IngestaoModel)
                .where(IngestaoModel.prova_id == prova_id)
                .order_by(IngestaoModel.criada_em.desc(), IngestaoModel.id.desc())
            )
            return [_para_dominio_ingestao(row) for row in session.scalars(stmt).all()]

    def marcar_em_processamento_como_interrompidas(self, agora: datetime, motivo: str) -> int:
        motivo_limpo = motivo.strip() or "Processo interrompido durante execução."
        with self._session_factory.begin() as session:
            stmt = (
                update(IngestaoModel)
                .where(IngestaoModel.status == StatusIngestao.PROCESSANDO.value)
                .values(
                    status=StatusIngestao.INTERROMPIDA.value,
                    mensagem_erro=motivo_limpo,
                    concluida_em=agora,
                )
            )
            result = session.execute(stmt)
            return int(result.rowcount or 0)


class RepositorioQuestoesSqlAlchemy:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def _upsert_em_sessao(self, session: Session, questao: Questao) -> QuestaoModel:
        stmt = (
            select(QuestaoModel)
            .where(QuestaoModel.id == questao.id)
            .options(
                selectinload(QuestaoModel.alternativas),
                selectinload(QuestaoModel.ativos_visuais),
                selectinload(QuestaoModel.alertas_extracao),
            )
        )
        row = session.scalar(stmt)

        alternativa_correta = (
            questao.gabarito.alternativa_correta.value if questao.gabarito.alternativa_correta else None
        )

        if row is None:
            row = QuestaoModel(
                id=questao.id,
                prova_id=questao.prova_id,
                numero=questao.numero,
                componente=questao.componente.value,
                tipo=questao.tipo.value,
                enunciado=questao.enunciado,
                paginas=list(questao.paginas),
                situacao_gabarito=questao.gabarito.situacao_gabarito.value,
                alternativa_correta=alternativa_correta,
                editada_manualmente=questao.editada_manualmente,
            )
            for alt in questao.alternativas:
                row.alternativas.append(
                    AlternativaModel(id=alt.id, questao_id=questao.id, letra=alt.letra.value, texto=alt.texto)
                )
            for ativo in questao.ativos_visuais:
                row.ativos_visuais.append(
                    AtivoVisualModel(
                        id=ativo.id,
                        questao_id=questao.id,
                        origem=ativo.origem.value,
                        alternativa_letra=ativo.alternativa_letra.value if ativo.alternativa_letra else None,
                        ordem=ativo.ordem,
                        pagina=ativo.pagina,
                        bbox=_para_dict_bbox(ativo.bbox),
                        chave_arquivo=ativo.chave_arquivo,
                    )
                )
            for alerta in questao.alertas_extracao:
                severidade = alerta.severidade.value if alerta.severidade else SeveridadeAlerta.CRITICO.value
                row.alertas_extracao.append(
                    AlertaExtracaoModel(
                        id=alerta.id,
                        questao_id=questao.id,
                        codigo=alerta.codigo.value,
                        severidade=severidade,
                        status=alerta.status.value,
                        mensagem=alerta.mensagem,
                        resolvido_em=alerta.resolvido_em,
                    )
                )
            session.add(row)
            return row

        row.prova_id = questao.prova_id
        row.numero = questao.numero
        row.componente = questao.componente.value
        row.tipo = questao.tipo.value
        row.enunciado = questao.enunciado
        row.paginas = list(questao.paginas)
        row.situacao_gabarito = questao.gabarito.situacao_gabarito.value
        row.alternativa_correta = alternativa_correta
        row.editada_manualmente = questao.editada_manualmente

        self._reconciliar_alternativas(session, row, questao.alternativas)
        self._reconciliar_ativos(session, row, questao.ativos_visuais)
        self._reconciliar_alertas(session, row, questao.alertas_extracao)
        return row

    @staticmethod
    def _reconciliar_alternativas(
        session: Session,
        row: QuestaoModel,
        alternativas: Sequence[Alternativa],
    ) -> None:
        incoming_por_letra = {alt.letra.value: alt for alt in alternativas}
        existentes_por_id = {item.id: item for item in row.alternativas}
        removeu = False

        for existente in list(row.alternativas):
            alvo = incoming_por_letra.get(existente.letra)
            if alvo is None or alvo.id != existente.id:
                row.alternativas.remove(existente)
                removeu = True

        if removeu:
            session.flush()
            existentes_por_id = {item.id: item for item in row.alternativas}

        for alt in alternativas:
            existente = existentes_por_id.get(alt.id)
            if existente is not None:
                existente.letra = alt.letra.value
                existente.texto = alt.texto
            else:
                row.alternativas.append(
                    AlternativaModel(
                        id=alt.id,
                        questao_id=row.id,
                        letra=alt.letra.value,
                        texto=alt.texto,
                    )
                )

    @staticmethod
    def _reconciliar_ativos(
        session: Session,
        row: QuestaoModel,
        ativos: Sequence[AtivoVisual],
    ) -> None:
        incoming_ids = {ativo.id for ativo in ativos}
        removeu = False

        for existente in list(row.ativos_visuais):
            if existente.id not in incoming_ids:
                row.ativos_visuais.remove(existente)
                removeu = True

        if removeu:
            session.flush()

        existentes_por_id = {item.id: item for item in row.ativos_visuais}
        for ativo in ativos:
            existente = existentes_por_id.get(ativo.id)
            alternativa_letra = ativo.alternativa_letra.value if ativo.alternativa_letra else None
            bbox_dict = _para_dict_bbox(ativo.bbox)
            if existente is not None:
                existente.origem = ativo.origem.value
                existente.alternativa_letra = alternativa_letra
                existente.ordem = ativo.ordem
                existente.pagina = ativo.pagina
                existente.bbox = bbox_dict
                existente.chave_arquivo = ativo.chave_arquivo
            else:
                row.ativos_visuais.append(
                    AtivoVisualModel(
                        id=ativo.id,
                        questao_id=row.id,
                        origem=ativo.origem.value,
                        alternativa_letra=alternativa_letra,
                        ordem=ativo.ordem,
                        pagina=ativo.pagina,
                        bbox=bbox_dict,
                        chave_arquivo=ativo.chave_arquivo,
                    )
                )

    @staticmethod
    def _reconciliar_alertas(
        session: Session,
        row: QuestaoModel,
        alertas: Sequence[AlertaExtracao],
    ) -> None:
        incoming_por_codigo = {alerta.codigo.value: alerta for alerta in alertas}
        removeu = False

        for existente in list(row.alertas_extracao):
            alvo = incoming_por_codigo.get(existente.codigo)
            if alvo is None or alvo.id != existente.id:
                row.alertas_extracao.remove(existente)
                removeu = True

        if removeu:
            session.flush()

        existentes_por_id = {item.id: item for item in row.alertas_extracao}
        for alerta in alertas:
            severidade = alerta.severidade.value if alerta.severidade else SeveridadeAlerta.CRITICO.value
            existente = existentes_por_id.get(alerta.id)
            if existente is not None:
                existente.codigo = alerta.codigo.value
                existente.severidade = severidade
                existente.status = alerta.status.value
                existente.mensagem = alerta.mensagem
                existente.resolvido_em = alerta.resolvido_em
            else:
                row.alertas_extracao.append(
                    AlertaExtracaoModel(
                        id=alerta.id,
                        questao_id=row.id,
                        codigo=alerta.codigo.value,
                        severidade=severidade,
                        status=alerta.status.value,
                        mensagem=alerta.mensagem,
                        resolvido_em=alerta.resolvido_em,
                    )
                )

    def salvar(self, questao: Questao) -> Questao:
        with self._session_factory.begin() as session:
            row = self._upsert_em_sessao(session, questao)
            session.flush()
            session.refresh(row)
            return _para_dominio_questao(row)

    def salvar_lote(self, questoes: Sequence[Questao]) -> list[Questao]:
        if not questoes:
            return []
        with self._session_factory.begin() as session:
            rows = [self._upsert_em_sessao(session, questao) for questao in questoes]
            session.flush()
            for row in rows:
                session.refresh(row)
            return [_para_dominio_questao(row) for row in rows]

    def buscar_por_id(self, questao_id: UUID) -> Questao | None:
        with self._session_factory() as session:
            stmt = (
                select(QuestaoModel)
                .where(QuestaoModel.id == questao_id)
                .options(
                    selectinload(QuestaoModel.alternativas),
                    selectinload(QuestaoModel.ativos_visuais),
                    selectinload(QuestaoModel.alertas_extracao),
                )
            )
            row = session.scalar(stmt)
            return _para_dominio_questao(row) if row is not None else None

    def buscar_por_prova_e_numero(self, prova_id: UUID, numero: int) -> Questao | None:
        with self._session_factory() as session:
            stmt = (
                select(QuestaoModel)
                .where(QuestaoModel.prova_id == prova_id, QuestaoModel.numero == numero)
                .options(
                    selectinload(QuestaoModel.alternativas),
                    selectinload(QuestaoModel.ativos_visuais),
                    selectinload(QuestaoModel.alertas_extracao),
                )
            )
            row = session.scalar(stmt)
            return _para_dominio_questao(row) if row is not None else None

    def listar_por_prova(self, prova_id: UUID) -> list[Questao]:
        with self._session_factory() as session:
            stmt = (
                select(QuestaoModel)
                .where(QuestaoModel.prova_id == prova_id)
                .options(
                    selectinload(QuestaoModel.alternativas),
                    selectinload(QuestaoModel.ativos_visuais),
                    selectinload(QuestaoModel.alertas_extracao),
                )
                .order_by(QuestaoModel.numero.asc(), QuestaoModel.id.asc())
            )
            return [_para_dominio_questao(row) for row in session.scalars(stmt).all()]

    def buscar_por_texto(
        self,
        termo: str,
        *,
        prova_id: UUID | None = None,
        taxonomia_id: UUID | None = None,
        limite: int = 50,
    ) -> list[Questao]:
        if isinstance(limite, bool) or not isinstance(limite, int) or limite < 1:
            raise ErroValidacaoDominio(f"'limite' deve ser inteiro >= 1; recebido: {limite!r}.")

        termo_limpo = termo.strip()
        if not termo_limpo:
            return []

        padrao_ilike = f"%{_escapar_like(termo_limpo)}%"
        enunciado_ilike = QuestaoModel.enunciado.ilike(padrao_ilike, escape="\\")
        alt_ilike = exists(
            select(AlternativaModel.id).where(
                AlternativaModel.questao_id == QuestaoModel.id,
                AlternativaModel.texto.ilike(padrao_ilike, escape="\\"),
            )
        )

        filtros_classificacao = [
            ClassificacaoModel.questao_id == QuestaoModel.id,
            ClassificacaoModel.vigente.is_(True),
        ]
        if taxonomia_id is not None:
            filtros_classificacao.append(ClassificacaoModel.taxonomia_id == taxonomia_id)

        topico_elem = func.jsonb_array_elements_text(ClassificacaoModel.topicos).table_valued("value").alias("topico")
        topicos_ilike = exists(
            select(ClassificacaoModel.id)
            .select_from(ClassificacaoModel)
            .join(topico_elem, true())
            .where(
                *filtros_classificacao,
                topico_elem.c.value.ilike(padrao_ilike, escape="\\"),
            )
        )

        if _CARACTERES_TECNICOS_RE.search(termo_limpo):
            condicao_busca = or_(enunciado_ilike, alt_ilike, topicos_ilike)
            relevancia = case(
                (enunciado_ilike, 2.0),
                (alt_ilike, 1.5),
                (topicos_ilike, 1.0),
                else_=0.0,
            )
        else:
            ts_query = func.websearch_to_tsquery("pt_unaccent", termo_limpo)
            topicos_tsv_expr = func.jsonb_to_tsvector(
                text("'pt_unaccent'::regconfig"),
                ClassificacaoModel.topicos,
                text("'[\"string\"]'::jsonb"),
            )
            topicos_tsv = exists(
                select(ClassificacaoModel.id).where(
                    *filtros_classificacao,
                    topicos_tsv_expr.op("@@")(ts_query),
                )
            )
            questao_tsv = QuestaoModel.busca_tsv.op("@@")(ts_query)
            condicao_busca = or_(questao_tsv, topicos_tsv, enunciado_ilike, alt_ilike, topicos_ilike)
            relevancia = func.coalesce(func.ts_rank_cd(QuestaoModel.busca_tsv, ts_query), 0.0) + case(
                (enunciado_ilike, 1.0),
                (alt_ilike, 0.5),
                (topicos_ilike, 0.5),
                else_=0.0,
            )

        with self._session_factory() as session:
            stmt = (
                select(QuestaoModel)
                .where(condicao_busca)
                .options(
                    selectinload(QuestaoModel.alternativas),
                    selectinload(QuestaoModel.ativos_visuais),
                    selectinload(QuestaoModel.alertas_extracao),
                )
            )
            if prova_id is not None:
                stmt = stmt.where(QuestaoModel.prova_id == prova_id)

            stmt = stmt.order_by(relevancia.desc(), QuestaoModel.numero.asc(), QuestaoModel.id.asc()).limit(limite)
            return [_para_dominio_questao(row) for row in session.scalars(stmt).all()]


class RepositorioAtivosVisuaisSqlAlchemy:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def salvar(self, ativo: AtivoVisual) -> AtivoVisual:
        if ativo.questao_id is None:
            raise ErroValidacaoDominio("AtivoVisual exige 'questao_id' definido para persistência.")

        alternativa_letra = ativo.alternativa_letra.value if ativo.alternativa_letra else None
        bbox_dict = _para_dict_bbox(ativo.bbox)

        with self._session_factory.begin() as session:
            row = session.get(AtivoVisualModel, ativo.id)
            if row is None:
                row = AtivoVisualModel(
                    id=ativo.id,
                    questao_id=ativo.questao_id,
                    origem=ativo.origem.value,
                    alternativa_letra=alternativa_letra,
                    ordem=ativo.ordem,
                    pagina=ativo.pagina,
                    bbox=bbox_dict,
                    chave_arquivo=ativo.chave_arquivo,
                )
                session.add(row)
            else:
                row.questao_id = ativo.questao_id
                row.origem = ativo.origem.value
                row.alternativa_letra = alternativa_letra
                row.ordem = ativo.ordem
                row.pagina = ativo.pagina
                row.bbox = bbox_dict
                row.chave_arquivo = ativo.chave_arquivo
            session.flush()
            return _para_dominio_ativo(row)

    def buscar_por_id(self, ativo_id: UUID) -> AtivoVisual | None:
        with self._session_factory() as session:
            row = session.get(AtivoVisualModel, ativo_id)
            return _para_dominio_ativo(row) if row is not None else None

    def listar_por_questao(self, questao_id: UUID) -> list[AtivoVisual]:
        with self._session_factory() as session:
            stmt = (
                select(AtivoVisualModel)
                .where(AtivoVisualModel.questao_id == questao_id)
                .order_by(AtivoVisualModel.ordem.asc(), AtivoVisualModel.id.asc())
            )
            return [_para_dominio_ativo(row) for row in session.scalars(stmt).all()]

    def remover(self, ativo_id: UUID) -> None:
        with self._session_factory.begin() as session:
            session.execute(delete(AtivoVisualModel).where(AtivoVisualModel.id == ativo_id))


class RepositorioTaxonomiasSqlAlchemy:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def salvar(self, taxonomia: Taxonomia) -> Taxonomia:
        with self._session_factory.begin() as session:
            stmt = (
                select(TaxonomiaModel)
                .where(TaxonomiaModel.id == taxonomia.id)
                .options(selectinload(TaxonomiaModel.disciplinas))
            )
            row = session.scalar(stmt)
            if row is None:
                row = TaxonomiaModel(
                    id=taxonomia.id,
                    codigo=taxonomia.codigo,
                    nome=taxonomia.nome,
                    curso_referencia=taxonomia.curso_referencia,
                )
                for ordem, disc in enumerate(taxonomia.disciplinas, start=1):
                    row.disciplinas.append(
                        DisciplinaModel(
                            id=disc.id,
                            taxonomia_id=taxonomia.id,
                            codigo=disc.codigo,
                            nome=disc.nome,
                            ementa=disc.ementa,
                            ativa=disc.ativa,
                            ordem=ordem,
                        )
                    )
                session.add(row)
                session.flush()
                return _para_dominio_taxonomia(row)

            row.codigo = taxonomia.codigo
            row.nome = taxonomia.nome
            row.curso_referencia = taxonomia.curso_referencia

            incoming_por_codigo = {disc.codigo: disc for disc in taxonomia.disciplinas}
            removeu = False
            for existente in list(row.disciplinas):
                alvo = incoming_por_codigo.get(existente.codigo)
                if alvo is None or alvo.id != existente.id:
                    row.disciplinas.remove(existente)
                    removeu = True

            if removeu:
                session.flush()

            existentes_por_id = {item.id: item for item in row.disciplinas}
            for ordem, disc in enumerate(taxonomia.disciplinas, start=1):
                existente = existentes_por_id.get(disc.id)
                if existente is not None:
                    existente.codigo = disc.codigo
                    existente.nome = disc.nome
                    existente.ementa = disc.ementa
                    existente.ativa = disc.ativa
                    existente.ordem = ordem
                else:
                    row.disciplinas.append(
                        DisciplinaModel(
                            id=disc.id,
                            taxonomia_id=row.id,
                            codigo=disc.codigo,
                            nome=disc.nome,
                            ementa=disc.ementa,
                            ativa=disc.ativa,
                            ordem=ordem,
                        )
                    )
            session.flush()
            return _para_dominio_taxonomia(row)

    def buscar_por_id(self, taxonomia_id: UUID) -> Taxonomia | None:
        with self._session_factory() as session:
            stmt = (
                select(TaxonomiaModel)
                .where(TaxonomiaModel.id == taxonomia_id)
                .options(selectinload(TaxonomiaModel.disciplinas))
            )
            row = session.scalar(stmt)
            return _para_dominio_taxonomia(row) if row is not None else None

    def buscar_por_codigo(self, codigo: str) -> Taxonomia | None:
        codigo_norm = codigo.strip()
        with self._session_factory() as session:
            stmt = (
                select(TaxonomiaModel)
                .where(TaxonomiaModel.codigo == codigo_norm)
                .options(selectinload(TaxonomiaModel.disciplinas))
            )
            row = session.scalar(stmt)
            return _para_dominio_taxonomia(row) if row is not None else None

    def listar(self) -> list[Taxonomia]:
        with self._session_factory() as session:
            stmt = (
                select(TaxonomiaModel)
                .options(selectinload(TaxonomiaModel.disciplinas))
                .order_by(TaxonomiaModel.codigo.asc(), TaxonomiaModel.id.asc())
            )
            return [_para_dominio_taxonomia(row) for row in session.scalars(stmt).all()]

    def contar_classificacoes_vigentes_por_disciplina(
        self,
        taxonomia_id: UUID,
        disciplina_codigo: str,
    ) -> int:
        codigo_norm = disciplina_codigo.strip()
        if not codigo_norm:
            return 0
        with self._session_factory() as session:
            stmt = select(func.count(ClassificacaoModel.id)).where(
                ClassificacaoModel.taxonomia_id == taxonomia_id,
                ClassificacaoModel.vigente.is_(True),
                or_(
                    ClassificacaoModel.disciplina_principal == codigo_norm,
                    ClassificacaoModel.disciplinas_secundarias.contains([codigo_norm]),
                ),
            )
            total = session.scalar(stmt)
            return int(total or 0)


class RepositorioPerfisClassificacaoSqlAlchemy:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def salvar(self, perfil: PerfilClassificacao) -> PerfilClassificacao:
        agora = _agora_utc()
        with self._session_factory.begin() as session:
            existente = session.get(PerfilClassificacaoModel, perfil.id)
            if existente is not None:
                if (
                    existente.codigo != perfil.codigo
                    or existente.versao != perfil.versao
                    or existente.diretrizes_gerais != perfil.diretrizes_gerais
                    or existente.guia_fronteiras != perfil.guia_fronteiras
                    or existente.template_prompt != perfil.template_prompt
                    or existente.descricao != perfil.descricao
                ):
                    raise ErroInvarianteDominio(
                        f"PerfilClassificacao '{perfil.codigo}:{perfil.versao}' é imutável após criação."
                    )
                return _para_dominio_perfil(existente)

            row = PerfilClassificacaoModel(
                id=perfil.id,
                codigo=perfil.codigo,
                versao=perfil.versao,
                diretrizes_gerais=perfil.diretrizes_gerais,
                guia_fronteiras=perfil.guia_fronteiras,
                template_prompt=perfil.template_prompt,
                descricao=perfil.descricao,
                criado_em=perfil.criado_em or agora,
            )
            session.add(row)
            session.flush()
            return _para_dominio_perfil(row)

    def buscar_por_id(self, perfil_id: UUID) -> PerfilClassificacao | None:
        with self._session_factory() as session:
            row = session.get(PerfilClassificacaoModel, perfil_id)
            return _para_dominio_perfil(row) if row is not None else None

    def buscar_por_codigo_e_versao(self, codigo: str, versao: str) -> PerfilClassificacao | None:
        codigo_norm = codigo.strip()
        versao_norm = versao.strip()
        with self._session_factory() as session:
            stmt = select(PerfilClassificacaoModel).where(
                PerfilClassificacaoModel.codigo == codigo_norm,
                PerfilClassificacaoModel.versao == versao_norm,
            )
            row = session.scalar(stmt)
            return _para_dominio_perfil(row) if row is not None else None

    def listar(self) -> list[PerfilClassificacao]:
        with self._session_factory() as session:
            stmt = select(PerfilClassificacaoModel).order_by(
                PerfilClassificacaoModel.codigo.asc(),
                PerfilClassificacaoModel.versao.asc(),
                PerfilClassificacaoModel.id.asc(),
            )
            return [_para_dominio_perfil(row) for row in session.scalars(stmt).all()]


class RepositorioExecucoesClassificacaoSqlAlchemy:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def salvar(self, execucao: ExecucaoClassificacao) -> ExecucaoClassificacao:
        agora = _agora_utc()
        snap_tax = _descongelar_json(execucao.snapshot_taxonomia)
        snap_perf = _descongelar_json(execucao.snapshot_perfil)
        erros = {str(k): str(v) for k, v in execucao.erros_por_questao.items()}

        with self._session_factory.begin() as session:
            row = session.get(ExecucaoClassificacaoModel, execucao.id)
            if row is None:
                row = ExecucaoClassificacaoModel(
                    id=execucao.id,
                    taxonomia_id=execucao.taxonomia_id,
                    perfil_id=execucao.perfil_id,
                    snapshot_taxonomia=snap_tax,
                    snapshot_perfil=snap_perf,
                    escopo=execucao.escopo.value,
                    incluir_revisadas=execucao.incluir_revisadas,
                    status=execucao.status.value,
                    total_itens=execucao.total_itens,
                    processadas=execucao.processadas,
                    divergencias_abertas=execucao.divergencias_abertas,
                    erros_por_questao=erros,
                    cache_hits=execucao.cache_hits,
                    prompt_tokens=execucao.prompt_tokens,
                    completion_tokens=execucao.completion_tokens,
                    criada_em=execucao.criada_em or agora,
                    iniciada_em=execucao.iniciada_em,
                    concluida_em=execucao.concluida_em,
                )
                session.add(row)
            else:
                row.taxonomia_id = execucao.taxonomia_id
                row.perfil_id = execucao.perfil_id
                row.snapshot_taxonomia = snap_tax
                row.snapshot_perfil = snap_perf
                row.escopo = execucao.escopo.value
                row.incluir_revisadas = execucao.incluir_revisadas
                row.status = execucao.status.value
                row.total_itens = execucao.total_itens
                row.processadas = execucao.processadas
                row.divergencias_abertas = execucao.divergencias_abertas
                row.erros_por_questao = erros
                row.cache_hits = execucao.cache_hits
                row.prompt_tokens = execucao.prompt_tokens
                row.completion_tokens = execucao.completion_tokens
                if execucao.criada_em is not None:
                    row.criada_em = execucao.criada_em
                row.iniciada_em = execucao.iniciada_em
                row.concluida_em = execucao.concluida_em
            session.flush()
            return _para_dominio_execucao(row)

    def buscar_por_id(self, execucao_id: UUID) -> ExecucaoClassificacao | None:
        with self._session_factory() as session:
            row = session.get(ExecucaoClassificacaoModel, execucao_id)
            return _para_dominio_execucao(row) if row is not None else None

    def listar(self) -> list[ExecucaoClassificacao]:
        with self._session_factory() as session:
            stmt = select(ExecucaoClassificacaoModel).order_by(
                ExecucaoClassificacaoModel.criada_em.desc(),
                ExecucaoClassificacaoModel.id.desc(),
            )
            return [_para_dominio_execucao(row) for row in session.scalars(stmt).all()]

    def marcar_em_processamento_como_interrompidas(self, agora: datetime) -> int:
        with self._session_factory.begin() as session:
            stmt = (
                update(ExecucaoClassificacaoModel)
                .where(ExecucaoClassificacaoModel.status == StatusExecucaoClassificacao.PROCESSANDO.value)
                .values(
                    status=StatusExecucaoClassificacao.INTERROMPIDA.value,
                    concluida_em=agora,
                )
            )
            result = session.execute(stmt)
            return int(result.rowcount or 0)


class RepositorioClassificacoesSqlAlchemy:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def salvar(self, classificacao: Classificacao) -> Classificacao:
        agora = _agora_utc()
        with self._session_factory.begin() as session:
            row = session.get(ClassificacaoModel, classificacao.id)
            if row is None:
                row = _para_modelo_classificacao(classificacao, criada_em_padrao=agora)
                session.add(row)
            else:
                row.questao_id = classificacao.questao_id
                row.taxonomia_id = classificacao.taxonomia_id
                row.execucao_id = classificacao.execucao_id
                row.substitui_classificacao_id = classificacao.substitui_classificacao_id
                row.disciplina_principal = classificacao.disciplina_principal
                row.disciplinas_secundarias = list(classificacao.disciplinas_secundarias)
                row.topicos = list(classificacao.topicos)
                row.justificativa = classificacao.justificativa
                row.confianca = classificacao.confianca
                row.origem = classificacao.origem.value
                row.status = classificacao.status.value
                row.vigente = classificacao.vigente
                row.revisao_prioritaria = classificacao.revisao_prioritaria
                row.alertas_validacao = list(classificacao.alertas_validacao)
                if classificacao.criada_em is not None:
                    row.criada_em = classificacao.criada_em
                row.revisada_em = classificacao.revisada_em
            session.flush()
            return _para_dominio_classificacao(row)

    def registrar_substituicao(
        self,
        anterior: Classificacao,
        nova: Classificacao,
    ) -> Classificacao:
        if nova.questao_id != anterior.questao_id or nova.taxonomia_id != anterior.taxonomia_id:
            raise ErroValidacaoDominio(
                "Classificação substituta deve pertencer ao mesmo par (questao_id, taxonomia_id) da anterior."
            )
        if not nova.vigente:
            raise ErroValidacaoDominio("Classificação substituta deve ser persistida com vigente=True.")

        agora = _agora_utc()
        with self._session_factory.begin() as session:
            anterior_row = session.scalar(
                select(ClassificacaoModel).where(ClassificacaoModel.id == anterior.id).with_for_update()
            )
            if anterior_row is None:
                raise ErroInvarianteDominio(f"Classificação anterior não encontrada: {anterior.id}.")
            if not anterior_row.vigente:
                raise ErroInvarianteDominio("Só é possível substituir classificação atualmente vigente.")

            # Obrigatório executar UPDATE + flush() antes do INSERT de vigente=true
            # devido ao índice único parcial não-deferrable em (questao_id, taxonomia_id) WHERE vigente = true.
            anterior_row.vigente = False
            session.flush()

            nova_row = ClassificacaoModel(
                id=nova.id,
                questao_id=nova.questao_id,
                taxonomia_id=nova.taxonomia_id,
                execucao_id=nova.execucao_id,
                substitui_classificacao_id=nova.substitui_classificacao_id or anterior.id,
                disciplina_principal=nova.disciplina_principal,
                disciplinas_secundarias=list(nova.disciplinas_secundarias),
                topicos=list(nova.topicos),
                justificativa=nova.justificativa,
                confianca=nova.confianca,
                origem=nova.origem.value,
                status=nova.status.value,
                vigente=True,
                revisao_prioritaria=nova.revisao_prioritaria,
                alertas_validacao=list(nova.alertas_validacao),
                criada_em=nova.criada_em or agora,
                revisada_em=nova.revisada_em,
            )
            session.add(nova_row)
            session.flush()
            anterior.vigente = False
            return _para_dominio_classificacao(nova_row)

    def buscar_por_id(self, classificacao_id: UUID) -> Classificacao | None:
        with self._session_factory() as session:
            row = session.get(ClassificacaoModel, classificacao_id)
            return _para_dominio_classificacao(row) if row is not None else None

    def buscar_vigente(self, questao_id: UUID, taxonomia_id: UUID) -> Classificacao | None:
        with self._session_factory() as session:
            stmt = select(ClassificacaoModel).where(
                ClassificacaoModel.questao_id == questao_id,
                ClassificacaoModel.taxonomia_id == taxonomia_id,
                ClassificacaoModel.vigente.is_(True),
            )
            row = session.scalar(stmt)
            return _para_dominio_classificacao(row) if row is not None else None

    def listar_historico(self, questao_id: UUID, taxonomia_id: UUID) -> list[Classificacao]:
        with self._session_factory() as session:
            stmt = (
                select(ClassificacaoModel)
                .where(
                    ClassificacaoModel.questao_id == questao_id,
                    ClassificacaoModel.taxonomia_id == taxonomia_id,
                )
                .order_by(ClassificacaoModel.criada_em.desc(), ClassificacaoModel.id.desc())
            )
            return [_para_dominio_classificacao(row) for row in session.scalars(stmt).all()]

    def listar_vigentes_por_questao(self, questao_id: UUID) -> list[Classificacao]:
        with self._session_factory() as session:
            stmt = (
                select(ClassificacaoModel)
                .where(
                    ClassificacaoModel.questao_id == questao_id,
                    ClassificacaoModel.vigente.is_(True),
                )
                .order_by(ClassificacaoModel.criada_em.desc(), ClassificacaoModel.id.desc())
            )
            return [_para_dominio_classificacao(row) for row in session.scalars(stmt).all()]

    def listar_fila_revisao(
        self,
        taxonomia_id: UUID,
        *,
        status: StatusClassificacao | None = None,
        apenas_revisao_prioritaria: bool = False,
    ) -> list[Classificacao]:
        with self._session_factory() as session:
            stmt = (
                select(ClassificacaoModel)
                .join(QuestaoModel, ClassificacaoModel.questao_id == QuestaoModel.id)
                .join(ProvaModel, QuestaoModel.prova_id == ProvaModel.id)
                .where(
                    ClassificacaoModel.taxonomia_id == taxonomia_id,
                    ClassificacaoModel.vigente.is_(True),
                )
            )
            if status is not None:
                stmt = stmt.where(ClassificacaoModel.status == StatusClassificacao(status).value)
            if apenas_revisao_prioritaria:
                stmt = stmt.where(ClassificacaoModel.revisao_prioritaria.is_(True))

            stmt = stmt.order_by(
                ClassificacaoModel.revisao_prioritaria.desc(),
                ClassificacaoModel.confianca.asc(),
                ProvaModel.ano.desc(),
                QuestaoModel.numero.asc(),
                ClassificacaoModel.id.asc(),
            )
            return [_para_dominio_classificacao(row) for row in session.scalars(stmt).all()]


class RepositorioDivergenciasReclassificacaoSqlAlchemy:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def salvar(self, divergencia: DivergenciaReclassificacao) -> DivergenciaReclassificacao:
        agora = _agora_utc()
        with self._session_factory.begin() as session:
            row = session.get(DivergenciaReclassificacaoModel, divergencia.id)
            resolucao_str = divergencia.resolucao.value if divergencia.resolucao else None
            if row is None:
                row = DivergenciaReclassificacaoModel(
                    id=divergencia.id,
                    questao_id=divergencia.questao_id,
                    taxonomia_id=divergencia.taxonomia_id,
                    execucao_id=divergencia.execucao_id,
                    classificacao_vigente_id=divergencia.classificacao_vigente_id,
                    classificacao_candidata_id=divergencia.classificacao_candidata_id,
                    disciplina_principal_candidata=divergencia.disciplina_principal_candidata,
                    disciplinas_secundarias_candidatas=list(divergencia.disciplinas_secundarias_candidatas),
                    topicos_candidatos=list(divergencia.topicos_candidatos),
                    justificativa_candidata=divergencia.justificativa_candidata,
                    confianca_candidata=divergencia.confianca_candidata,
                    status=divergencia.status.value,
                    resolucao=resolucao_str,
                    criada_em=divergencia.criada_em or agora,
                    resolvida_em=divergencia.resolvida_em,
                )
                session.add(row)
            else:
                row.questao_id = divergencia.questao_id
                row.taxonomia_id = divergencia.taxonomia_id
                row.execucao_id = divergencia.execucao_id
                row.classificacao_vigente_id = divergencia.classificacao_vigente_id
                row.classificacao_candidata_id = divergencia.classificacao_candidata_id
                row.disciplina_principal_candidata = divergencia.disciplina_principal_candidata
                row.disciplinas_secundarias_candidatas = list(divergencia.disciplinas_secundarias_candidatas)
                row.topicos_candidatos = list(divergencia.topicos_candidatos)
                row.justificativa_candidata = divergencia.justificativa_candidata
                row.confianca_candidata = divergencia.confianca_candidata
                row.status = divergencia.status.value
                row.resolucao = resolucao_str
                if divergencia.criada_em is not None:
                    row.criada_em = divergencia.criada_em
                row.resolvida_em = divergencia.resolvida_em
            session.flush()
            return _para_dominio_divergencia(row)

    def buscar_por_id(self, divergencia_id: UUID) -> DivergenciaReclassificacao | None:
        with self._session_factory() as session:
            row = session.get(DivergenciaReclassificacaoModel, divergencia_id)
            return _para_dominio_divergencia(row) if row is not None else None

    def listar(
        self,
        *,
        taxonomia_id: UUID | None = None,
        status: StatusDivergencia | None = None,
    ) -> list[DivergenciaReclassificacao]:
        with self._session_factory() as session:
            stmt = (
                select(DivergenciaReclassificacaoModel)
                .join(
                    ExecucaoClassificacaoModel,
                    DivergenciaReclassificacaoModel.execucao_id == ExecucaoClassificacaoModel.id,
                )
                .join(QuestaoModel, DivergenciaReclassificacaoModel.questao_id == QuestaoModel.id)
                .join(ProvaModel, QuestaoModel.prova_id == ProvaModel.id)
            )
            if taxonomia_id is not None:
                stmt = stmt.where(DivergenciaReclassificacaoModel.taxonomia_id == taxonomia_id)
            if status is not None:
                stmt = stmt.where(DivergenciaReclassificacaoModel.status == StatusDivergencia(status).value)

            stmt = stmt.order_by(
                ExecucaoClassificacaoModel.criada_em.desc(),
                ProvaModel.ano.desc(),
                QuestaoModel.numero.asc(),
                DivergenciaReclassificacaoModel.id.asc(),
            )
            return [_para_dominio_divergencia(row) for row in session.scalars(stmt).all()]

    def resolver_atomicamente(
        self,
        divergencia_id: UUID,
        resolucao: ResolucaoDivergencia,
        agora: datetime,
        nova_classificacao: Classificacao | None = None,
    ) -> DivergenciaReclassificacao:
        try:
            resolucao_norm = ResolucaoDivergencia(resolucao)
        except ValueError as err:
            raise ErroValidacaoDominio(f"Resolução de divergência inválida: {resolucao!r}.") from err

        if resolucao_norm == ResolucaoDivergencia.EDITAR_MANUALMENTE:
            if nova_classificacao is None:
                raise ErroValidacaoDominio("Resolução 'editar_manualmente' exige nova_classificacao.")
            if not nova_classificacao.vigente:
                raise ErroValidacaoDominio(
                    "Nova classificação em 'editar_manualmente' deve estar marcada como vigente=True."
                )
            if nova_classificacao.status != StatusClassificacao.APROVADA:
                raise ErroValidacaoDominio("Nova classificação em 'editar_manualmente' deve ter status 'aprovada'.")
        if resolucao_norm == ResolucaoDivergencia.MANTER_HUMANA and nova_classificacao is not None:
            raise ErroValidacaoDominio("Resolução 'manter_humana' exige nova_classificacao=None.")

        with self._session_factory.begin() as session:
            div_row = session.scalar(
                select(DivergenciaReclassificacaoModel)
                .where(DivergenciaReclassificacaoModel.id == divergencia_id)
                .with_for_update()
            )
            if div_row is None:
                raise ErroInvarianteDominio(f"Divergência não encontrada: {divergencia_id}.")

            divergencia = _para_dominio_divergencia(div_row)
            divergencia.resolver(resolucao_norm, agora)

            if resolucao_norm in {ResolucaoDivergencia.EDITAR_MANUALMENTE, ResolucaoDivergencia.ACEITAR_CANDIDATA}:
                vigente_row = session.scalar(
                    select(ClassificacaoModel)
                    .where(ClassificacaoModel.id == div_row.classificacao_vigente_id)
                    .with_for_update()
                )
                if vigente_row is None or not vigente_row.vigente:
                    raise ErroInvarianteDominio("Classificação vigente associada à divergência não está mais vigente.")

                if resolucao_norm == ResolucaoDivergencia.EDITAR_MANUALMENTE:
                    if nova_classificacao is None:
                        raise ErroValidacaoDominio("Resolução 'editar_manualmente' exige nova_classificacao.")
                    if (
                        nova_classificacao.questao_id != div_row.questao_id
                        or nova_classificacao.taxonomia_id != div_row.taxonomia_id
                    ):
                        raise ErroValidacaoDominio(
                            "Nova classificação deve pertencer ao mesmo par (questao_id, taxonomia_id) da divergência."
                        )
                    vigente_row.vigente = False
                    session.flush()

                    nova_row = ClassificacaoModel(
                        id=nova_classificacao.id,
                        questao_id=nova_classificacao.questao_id,
                        taxonomia_id=nova_classificacao.taxonomia_id,
                        execucao_id=nova_classificacao.execucao_id,
                        substitui_classificacao_id=nova_classificacao.substitui_classificacao_id or vigente_row.id,
                        disciplina_principal=nova_classificacao.disciplina_principal,
                        disciplinas_secundarias=list(nova_classificacao.disciplinas_secundarias),
                        topicos=list(nova_classificacao.topicos),
                        justificativa=nova_classificacao.justificativa,
                        confianca=nova_classificacao.confianca,
                        origem=nova_classificacao.origem.value,
                        status=nova_classificacao.status.value,
                        vigente=True,
                        revisao_prioritaria=nova_classificacao.revisao_prioritaria,
                        alertas_validacao=list(nova_classificacao.alertas_validacao),
                        criada_em=nova_classificacao.criada_em or agora,
                        revisada_em=nova_classificacao.revisada_em or agora,
                    )
                    session.add(nova_row)
                else:
                    self._aplicar_candidata_na_transacao(
                        session=session,
                        div_row=div_row,
                        vigente_row=vigente_row,
                        agora=agora,
                        nova_classificacao=nova_classificacao,
                    )

            div_row.status = divergencia.status.value
            div_row.resolucao = divergencia.resolucao.value if divergencia.resolucao else None
            div_row.resolvida_em = divergencia.resolvida_em
            session.flush()
            return _para_dominio_divergencia(div_row)

    @staticmethod
    def _aplicar_candidata_na_transacao(
        *,
        session: Session,
        div_row: DivergenciaReclassificacaoModel,
        vigente_row: ClassificacaoModel,
        agora: datetime,
        nova_classificacao: Classificacao | None,
    ) -> None:
        if nova_classificacao is not None:
            if (
                nova_classificacao.questao_id != div_row.questao_id
                or nova_classificacao.taxonomia_id != div_row.taxonomia_id
            ):
                raise ErroValidacaoDominio(
                    "Classificação candidata deve pertencer ao mesmo par (questao_id, taxonomia_id) da divergência."
                )
            existente_cand = session.scalar(
                select(ClassificacaoModel).where(ClassificacaoModel.id == nova_classificacao.id).with_for_update()
            )
            vigente_row.vigente = False
            session.flush()
            if existente_cand is not None:
                existente_cand.vigente = True
                existente_cand.status = StatusClassificacao.APROVADA.value
                existente_cand.revisada_em = nova_classificacao.revisada_em or agora
                existente_cand.substitui_classificacao_id = existente_cand.substitui_classificacao_id or vigente_row.id
            else:
                session.add(
                    ClassificacaoModel(
                        id=nova_classificacao.id,
                        questao_id=nova_classificacao.questao_id,
                        taxonomia_id=nova_classificacao.taxonomia_id,
                        execucao_id=nova_classificacao.execucao_id,
                        substitui_classificacao_id=nova_classificacao.substitui_classificacao_id or vigente_row.id,
                        disciplina_principal=nova_classificacao.disciplina_principal,
                        disciplinas_secundarias=list(nova_classificacao.disciplinas_secundarias),
                        topicos=list(nova_classificacao.topicos),
                        justificativa=nova_classificacao.justificativa,
                        confianca=nova_classificacao.confianca,
                        origem=nova_classificacao.origem.value,
                        status=nova_classificacao.status.value,
                        vigente=True,
                        revisao_prioritaria=nova_classificacao.revisao_prioritaria,
                        alertas_validacao=list(nova_classificacao.alertas_validacao),
                        criada_em=nova_classificacao.criada_em or agora,
                        revisada_em=nova_classificacao.revisada_em or agora,
                    )
                )
            return

        if div_row.classificacao_candidata_id is not None:
            cand_row = session.scalar(
                select(ClassificacaoModel)
                .where(ClassificacaoModel.id == div_row.classificacao_candidata_id)
                .with_for_update()
            )
            if cand_row is not None:
                vigente_row.vigente = False
                session.flush()
                cand_row.vigente = True
                cand_row.status = StatusClassificacao.APROVADA.value
                cand_row.revisada_em = agora
                cand_row.substitui_classificacao_id = cand_row.substitui_classificacao_id or vigente_row.id
                return

        candidata = Classificacao(
            questao_id=div_row.questao_id,
            taxonomia_id=div_row.taxonomia_id,
            disciplina_principal=div_row.disciplina_principal_candidata,
            disciplinas_secundarias=tuple(div_row.disciplinas_secundarias_candidatas or ()),
            topicos=tuple(div_row.topicos_candidatos or ()),
            justificativa=div_row.justificativa_candidata,
            confianca=div_row.confianca_candidata,
            origem=OrigemClassificacao.AUTOMATICA,
            status=StatusClassificacao.APROVADA,
            vigente=True,
            execucao_id=div_row.execucao_id,
            substitui_classificacao_id=vigente_row.id,
            criada_em=agora,
            revisada_em=agora,
        )
        vigente_row.vigente = False
        session.flush()
        session.add(_para_modelo_classificacao(candidata, criada_em_padrao=agora))
