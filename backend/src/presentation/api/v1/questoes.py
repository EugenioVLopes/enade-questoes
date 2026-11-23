from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status

from application.ports.consulta_questoes import ContadoresRevisao, ItemConsultaQuestao, OrdenacaoConsulta, StatusRevisao
from application.questoes import (
    ANO_MAXIMO,
    ANO_MINIMO,
    PAGINA_MAXIMA,
    TAMANHO_MAXIMO_IMAGEM_BYTES,
    AdicionarAtivoVisualUseCase,
    AlternativaEdicao,
    ConsultarQuestoesUseCase,
    DetalharQuestaoUseCase,
    DetalheQuestao,
    EditarConteudoQuestaoUseCase,
    GabaritoEdicao,
    ParametrosConsultaQuestoes,
    ResolverAlertaExtracaoUseCase,
)
from application.revisao import (
    AprovarClassificacaoUseCase,
    CorrecaoClassificacao,
    CorrigirClassificacaoUseCase,
    ResolverDivergenciaUseCase,
)
from domain.classificacao import Classificacao, DivergenciaReclassificacao
from domain.enums import LetraAlternativa, SeveridadeAlerta, SituacaoGabarito
from domain.prova import AlertaExtracao, AtivoVisual, Questao
from presentation.api.schemas import ErroDetalheResponse
from presentation.api.schemas_questoes import (
    AlertaExtracaoResponse,
    AlternativaResponse,
    AtivoVisualResponse,
    AtualizarAlertaRequest,
    ClassificacaoOutraTaxonomiaResponse,
    ClassificacaoResponse,
    ClassificacaoResumoResponse,
    ContadoresRevisaoResponse,
    CorrigirClassificacaoRequest,
    DetalheQuestaoResponse,
    DivergenciaResponse,
    EditarQuestaoRequest,
    GabaritoResponse,
    ItemQuestaoResponse,
    ListaQuestoesResponse,
    ProvaResumoResponse,
    ResolverDivergenciaRequest,
    ResolverDivergenciaResponse,
)
from presentation.api.tipos import TextoSeguro

router = APIRouter(prefix="/api/v1/questoes", tags=["questoes"])

TAMANHO_TRECHO = 240


def _resolver_state(request: Request, attr: str) -> object:
    valor = getattr(request.app.state, attr, None)
    if valor is None:
        raise RuntimeError(f"Dependência '{attr}' não configurada em app.state.")
    return valor


def get_consultar_questoes_use_case(request: Request) -> ConsultarQuestoesUseCase:
    return cast(ConsultarQuestoesUseCase, _resolver_state(request, "consultar_questoes_use_case"))


def get_detalhar_questao_use_case(request: Request) -> DetalharQuestaoUseCase:
    return cast(DetalharQuestaoUseCase, _resolver_state(request, "detalhar_questao_use_case"))


def get_aprovar_classificacao_use_case(request: Request) -> AprovarClassificacaoUseCase:
    return cast(AprovarClassificacaoUseCase, _resolver_state(request, "aprovar_classificacao_use_case"))


def get_corrigir_classificacao_use_case(request: Request) -> CorrigirClassificacaoUseCase:
    return cast(CorrigirClassificacaoUseCase, _resolver_state(request, "corrigir_classificacao_use_case"))


def get_resolver_divergencia_use_case(request: Request) -> ResolverDivergenciaUseCase:
    return cast(ResolverDivergenciaUseCase, _resolver_state(request, "resolver_divergencia_use_case"))


def get_editar_questao_use_case(request: Request) -> EditarConteudoQuestaoUseCase:
    return cast(EditarConteudoQuestaoUseCase, _resolver_state(request, "editar_questao_use_case"))


def get_resolver_alerta_use_case(request: Request) -> ResolverAlertaExtracaoUseCase:
    return cast(ResolverAlertaExtracaoUseCase, _resolver_state(request, "resolver_alerta_use_case"))


def get_adicionar_ativo_visual_use_case(request: Request) -> AdicionarAtivoVisualUseCase:
    return cast(AdicionarAtivoVisualUseCase, _resolver_state(request, "adicionar_ativo_visual_use_case"))


# ---------------------------------------------------------------------------
# Serialização (compartilhada com presentation/api/v1/ativos_visuais.py)
# ---------------------------------------------------------------------------


def serializar_ativo(ativo: AtivoVisual) -> AtivoVisualResponse:
    return AtivoVisualResponse(
        id=ativo.id,
        origem=ativo.origem,
        alternativa_letra=ativo.alternativa_letra,
        ordem=ativo.ordem,
        pagina=ativo.pagina,
        url_arquivo=f"/api/v1/ativos-visuais/{ativo.id}/arquivo",
    )


def _serializar_alerta(alerta: AlertaExtracao) -> AlertaExtracaoResponse:
    return AlertaExtracaoResponse(
        id=alerta.id,
        codigo=alerta.codigo,
        severidade=cast(SeveridadeAlerta, alerta.severidade),
        status=alerta.status,
        mensagem=alerta.mensagem,
        resolvido_em=alerta.resolvido_em,
    )


def _serializar_classificacao(c: Classificacao) -> ClassificacaoResponse:
    return ClassificacaoResponse(
        id=c.id,
        questao_id=c.questao_id,
        taxonomia_id=c.taxonomia_id,
        disciplina_principal=c.disciplina_principal,
        disciplinas_secundarias=list(c.disciplinas_secundarias),
        topicos=list(c.topicos),
        justificativa=c.justificativa,
        confianca=c.confianca,
        origem=c.origem,
        status=c.status,
        vigente=c.vigente,
        revisao_prioritaria=c.revisao_prioritaria,
        execucao_id=c.execucao_id,
        substitui_classificacao_id=c.substitui_classificacao_id,
        alertas_validacao=list(c.alertas_validacao),
        criada_em=c.criada_em,
        revisada_em=c.revisada_em,
    )


def _serializar_divergencia(d: DivergenciaReclassificacao) -> DivergenciaResponse:
    return DivergenciaResponse(
        id=d.id,
        questao_id=d.questao_id,
        taxonomia_id=d.taxonomia_id,
        execucao_id=d.execucao_id,
        classificacao_vigente_id=d.classificacao_vigente_id,
        classificacao_candidata_id=d.classificacao_candidata_id,
        disciplina_principal_candidata=d.disciplina_principal_candidata,
        disciplinas_secundarias_candidatas=list(d.disciplinas_secundarias_candidatas),
        topicos_candidatos=list(d.topicos_candidatos),
        justificativa_candidata=d.justificativa_candidata,
        confianca_candidata=d.confianca_candidata,
        status=d.status,
        resolucao=d.resolucao,
        criada_em=d.criada_em,
        resolvida_em=d.resolvida_em,
    )


def _serializar_detalhe(detalhe: DetalheQuestao) -> DetalheQuestaoResponse:
    questao: Questao = detalhe.questao
    prova = detalhe.prova
    ativos = sorted(questao.ativos_visuais, key=lambda a: (a.ordem, str(a.id)))
    alternativas = sorted(questao.alternativas, key=lambda a: a.letra.value)
    return DetalheQuestaoResponse(
        id=questao.id,
        prova=ProvaResumoResponse(id=prova.id, exame=prova.exame, curso=prova.curso, ano=prova.ano),
        numero=questao.numero,
        componente=questao.componente.value,
        tipo=questao.tipo.value,
        paginas=list(questao.paginas),
        enunciado=questao.enunciado,
        editada_manualmente=questao.editada_manualmente,
        versao=questao.versao,
        alternativas=[AlternativaResponse(letra=a.letra, texto=a.texto) for a in alternativas],
        ativos_visuais=[serializar_ativo(a) for a in ativos],
        gabarito=GabaritoResponse(
            situacao_gabarito=questao.gabarito.situacao_gabarito,
            alternativa_correta=questao.gabarito.alternativa_correta,
        ),
        alertas_extracao=[_serializar_alerta(a) for a in questao.alertas_extracao],
        taxonomia_id=detalhe.taxonomia_id,
        classificacao_vigente=(
            _serializar_classificacao(detalhe.classificacao_vigente) if detalhe.classificacao_vigente else None
        ),
        disciplinas_arquivadas_em_uso=list(detalhe.disciplinas_arquivadas_em_uso),
        divergencia_aberta=(
            _serializar_divergencia(detalhe.divergencia_aberta) if detalhe.divergencia_aberta else None
        ),
        historico=[_serializar_classificacao(c) for c in detalhe.historico],
        outras_taxonomias=[
            ClassificacaoOutraTaxonomiaResponse(
                taxonomia_id=o.classificacao.taxonomia_id,
                taxonomia_codigo=o.taxonomia_codigo,
                taxonomia_nome=o.taxonomia_nome,
                classificacao=_serializar_classificacao(o.classificacao),
            )
            for o in detalhe.outras_taxonomias
        ],
    )


def _serializar_item(item: ItemConsultaQuestao) -> ItemQuestaoResponse:
    questao = item.questao
    trecho = questao.enunciado.strip()
    if len(trecho) > TAMANHO_TRECHO:
        trecho = trecho[:TAMANHO_TRECHO].rstrip() + "…"
    c = item.classificacao
    return ItemQuestaoResponse(
        id=questao.id,
        prova=ProvaResumoResponse(
            id=questao.prova_id, exame=item.prova_exame, curso=item.prova_curso, ano=item.prova_ano
        ),
        numero=questao.numero,
        trecho=trecho,
        situacao_gabarito=questao.gabarito.situacao_gabarito,
        editada_manualmente=questao.editada_manualmente,
        alertas_abertos=[a.codigo for a in questao.alertas_extracao if a.is_aberto],
        revisao_prioritaria=item.revisao_prioritaria,
        tem_divergencia_aberta=item.tem_divergencia_aberta,
        usa_disciplina_arquivada=item.usa_disciplina_arquivada,
        possui_ativos_visuais=bool(questao.ativos_visuais),
        classificacao=(
            ClassificacaoResumoResponse(
                id=c.id,
                origem=c.origem,
                status=c.status,
                confianca=c.confianca,
                revisao_prioritaria=c.revisao_prioritaria,
                disciplina_principal=c.disciplina_principal,
                disciplinas_secundarias=list(c.disciplinas_secundarias),
                topicos=list(c.topicos),
            )
            if c is not None
            else None
        ),
    )


def _serializar_contadores(c: ContadoresRevisao | None) -> ContadoresRevisaoResponse | None:
    if c is None:
        return None
    return ContadoresRevisaoResponse(
        pendentes=c.pendentes, divergencias=c.divergencias, disciplina_arquivada=c.disciplina_arquivada
    )


def _correcao(payload: CorrigirClassificacaoRequest) -> CorrecaoClassificacao:
    return CorrecaoClassificacao(
        disciplina_principal=payload.disciplina_principal,
        disciplinas_secundarias=tuple(payload.disciplinas_secundarias),
        topicos=tuple(payload.topicos),
        justificativa=payload.justificativa,
    )


# ---------------------------------------------------------------------------
# Consulta
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=ListaQuestoesResponse,
    responses={404: {"model": ErroDetalheResponse}, 422: {"model": ErroDetalheResponse}},
    summary="Consulta Questões com busca textual/trigrama, filtros combináveis, paginação e contadores de abas",
)
def listar_questoes(
    use_case: Annotated[ConsultarQuestoesUseCase, Depends(get_consultar_questoes_use_case)],
    q: Annotated[TextoSeguro | None, Query()] = None,
    prova_id: Annotated[UUID | None, Query()] = None,
    ano: Annotated[int | None, Query(ge=ANO_MINIMO, le=ANO_MAXIMO)] = None,
    taxonomia_id: Annotated[UUID | None, Query()] = None,
    disciplina_id: Annotated[UUID | None, Query()] = None,
    incluir_secundarias: Annotated[bool, Query()] = True,
    topico: Annotated[TextoSeguro | None, Query()] = None,
    status_revisao: Annotated[StatusRevisao | None, Query()] = None,
    revisao_prioritaria: Annotated[bool | None, Query()] = None,
    com_divergencia: Annotated[bool | None, Query()] = None,
    usa_disciplina_arquivada: Annotated[bool | None, Query()] = None,
    situacao_gabarito: Annotated[SituacaoGabarito | None, Query()] = None,
    com_alerta_extracao: Annotated[bool | None, Query()] = None,
    ordenacao: Annotated[OrdenacaoConsulta, Query()] = OrdenacaoConsulta.CONSULTA,
    pagina: Annotated[int, Query(ge=1, le=PAGINA_MAXIMA)] = 1,
    tamanho_pagina: Annotated[int, Query()] = 50,
) -> ListaQuestoesResponse:
    resultado = use_case.execute(
        ParametrosConsultaQuestoes(
            q=q,
            prova_id=prova_id,
            ano=ano,
            taxonomia_id=taxonomia_id,
            disciplina_id=disciplina_id,
            incluir_secundarias=incluir_secundarias,
            topico=topico,
            status_revisao=status_revisao,
            revisao_prioritaria=revisao_prioritaria,
            com_divergencia=com_divergencia,
            usa_disciplina_arquivada=usa_disciplina_arquivada,
            situacao_gabarito=situacao_gabarito,
            com_alerta_extracao=com_alerta_extracao,
            ordenacao=ordenacao,
            pagina=pagina,
            tamanho_pagina=tamanho_pagina,
        )
    )
    return ListaQuestoesResponse(
        itens=[_serializar_item(i) for i in resultado.pagina.itens],
        total=resultado.pagina.total,
        pagina=resultado.numero_pagina,
        tamanho_pagina=resultado.tamanho_pagina,
        taxonomia_id=resultado.taxonomia_id,
        contadores=_serializar_contadores(resultado.contadores),
    )


@router.get(
    "/{questao_id}",
    response_model=DetalheQuestaoResponse,
    responses={404: {"model": ErroDetalheResponse}},
    summary="Detalha uma Questão com classificação vigente, divergência aberta e histórico na Taxonomia solicitada",
)
def obter_questao(
    questao_id: UUID,
    use_case: Annotated[DetalharQuestaoUseCase, Depends(get_detalhar_questao_use_case)],
    taxonomia_id: Annotated[UUID | None, Query()] = None,
) -> DetalheQuestaoResponse:
    return _serializar_detalhe(use_case.execute(questao_id, taxonomia_id=taxonomia_id))


# ---------------------------------------------------------------------------
# Revisão humana
# ---------------------------------------------------------------------------


@router.post(
    "/{questao_id}/classificacoes/{taxonomia_id}/aprovar",
    response_model=ClassificacaoResponse,
    responses={404: {"model": ErroDetalheResponse}, 409: {"model": ErroDetalheResponse}},
    summary="Aprova in-place a Classificação vigente pendente de revisão",
)
def aprovar_classificacao(
    questao_id: UUID,
    taxonomia_id: UUID,
    use_case: Annotated[AprovarClassificacaoUseCase, Depends(get_aprovar_classificacao_use_case)],
) -> ClassificacaoResponse:
    return _serializar_classificacao(use_case.execute(questao_id, taxonomia_id))


@router.post(
    "/{questao_id}/classificacoes/{taxonomia_id}/corrigir",
    status_code=status.HTTP_201_CREATED,
    response_model=ClassificacaoResponse,
    responses={
        404: {"model": ErroDetalheResponse},
        409: {"model": ErroDetalheResponse},
        422: {"model": ErroDetalheResponse},
    },
    summary="Cria Classificação humana vigente que substitui a atual, preservando a predição da IA",
)
def corrigir_classificacao(
    questao_id: UUID,
    taxonomia_id: UUID,
    payload: CorrigirClassificacaoRequest,
    use_case: Annotated[CorrigirClassificacaoUseCase, Depends(get_corrigir_classificacao_use_case)],
) -> ClassificacaoResponse:
    return _serializar_classificacao(use_case.execute(questao_id, taxonomia_id, _correcao(payload)))


@router.post(
    "/{questao_id}/divergencias/{divergencia_id}/resolver",
    response_model=ResolverDivergenciaResponse,
    responses={
        404: {"model": ErroDetalheResponse},
        409: {"model": ErroDetalheResponse},
        422: {"model": ErroDetalheResponse},
    },
    summary="Resolve atomicamente uma Divergência de Reclassificação aberta",
)
def resolver_divergencia(
    questao_id: UUID,
    divergencia_id: UUID,
    payload: ResolverDivergenciaRequest,
    use_case: Annotated[ResolverDivergenciaUseCase, Depends(get_resolver_divergencia_use_case)],
) -> ResolverDivergenciaResponse:
    resultado = use_case.execute(
        questao_id,
        divergencia_id,
        payload.resolucao,
        _correcao(payload.classificacao) if payload.classificacao is not None else None,
    )
    return ResolverDivergenciaResponse(
        divergencia=_serializar_divergencia(resultado.divergencia),
        classificacao_vigente=(
            _serializar_classificacao(resultado.classificacao_vigente) if resultado.classificacao_vigente else None
        ),
    )


# ---------------------------------------------------------------------------
# Edição curada de conteúdo, alertas e Ativos Visuais
# ---------------------------------------------------------------------------


@router.patch(
    "/{questao_id}",
    response_model=DetalheQuestaoResponse,
    responses={
        404: {"model": ErroDetalheResponse},
        409: {"model": ErroDetalheResponse},
        422: {"model": ErroDetalheResponse},
    },
    summary="Edita enunciado, Alternativas e Gabarito e reavalia os alertas estruturais (sem acionar LLM)",
)
def editar_questao(
    questao_id: UUID,
    payload: EditarQuestaoRequest,
    editar: Annotated[EditarConteudoQuestaoUseCase, Depends(get_editar_questao_use_case)],
    detalhar: Annotated[DetalharQuestaoUseCase, Depends(get_detalhar_questao_use_case)],
    taxonomia_id: Annotated[UUID | None, Query()] = None,
) -> DetalheQuestaoResponse:
    editar.execute(
        questao_id,
        enunciado=payload.enunciado,
        alternativas=(
            [AlternativaEdicao(letra=a.letra, texto=a.texto) for a in payload.alternativas]
            if payload.alternativas is not None
            else None
        ),
        gabarito=(
            GabaritoEdicao(
                situacao_gabarito=payload.gabarito.situacao_gabarito,
                alternativa_correta=payload.gabarito.alternativa_correta,
            )
            if payload.gabarito is not None
            else None
        ),
        versao=payload.versao,
    )
    return _serializar_detalhe(detalhar.execute(questao_id, taxonomia_id=taxonomia_id))


@router.patch(
    "/{questao_id}/alertas/{alerta_id}",
    response_model=DetalheQuestaoResponse,
    responses={404: {"model": ErroDetalheResponse}, 422: {"model": ErroDetalheResponse}},
    summary="Marca como resolvido um alerta de inspeção (pdf_via_ocr, fonte_symbol_detectada)",
)
def atualizar_alerta(
    questao_id: UUID,
    alerta_id: UUID,
    _payload: AtualizarAlertaRequest,
    resolver: Annotated[ResolverAlertaExtracaoUseCase, Depends(get_resolver_alerta_use_case)],
    detalhar: Annotated[DetalharQuestaoUseCase, Depends(get_detalhar_questao_use_case)],
    taxonomia_id: Annotated[UUID | None, Query()] = None,
) -> DetalheQuestaoResponse:
    resolver.execute(questao_id, alerta_id)
    return _serializar_detalhe(detalhar.execute(questao_id, taxonomia_id=taxonomia_id))


@router.post(
    "/{questao_id}/ativos-visuais",
    status_code=status.HTTP_201_CREATED,
    response_model=AtivoVisualResponse,
    responses={404: {"model": ErroDetalheResponse}, 422: {"model": ErroDetalheResponse}},
    summary="Envia manualmente um Ativo Visual (PNG/JPEG) para a Questão",
)
async def adicionar_ativo_visual(
    questao_id: UUID,
    use_case: Annotated[AdicionarAtivoVisualUseCase, Depends(get_adicionar_ativo_visual_use_case)],
    arquivo: Annotated[UploadFile, File(...)],
    alternativa_letra: Annotated[LetraAlternativa | None, Form()] = None,
    ordem: Annotated[int | None, Form(ge=0, le=2_147_483_647)] = None,
) -> AtivoVisualResponse:
    conteudo = await arquivo.read(TAMANHO_MAXIMO_IMAGEM_BYTES + 1)
    ativo = use_case.execute(questao_id, conteudo, alternativa_letra=alternativa_letra, ordem=ordem)
    return serializar_ativo(ativo)


__all__ = ["router", "serializar_ativo"]
