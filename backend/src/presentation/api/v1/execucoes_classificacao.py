from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from application.execucoes_classificacao import (
    CriarExecucaoClassificacaoUseCase,
    DetalharExecucaoClassificacaoUseCase,
    ListarExecucoesClassificacaoUseCase,
    RetomarExecucaoClassificacaoUseCase,
)
from domain.classificacao import ExecucaoClassificacao
from domain.enums import EscopoExecucao
from presentation.api.schemas import (
    ErroDetalheResponse,
    EscopoExecucaoLiteral,
    ExecucaoClassificacaoAceitaResponse,
    ExecucaoClassificacaoCriarRequest,
    ExecucaoClassificacaoDetalheResponse,
    ExecucaoClassificacaoResumoResponse,
    ListaExecucoesClassificacaoResponse,
    SnapshotExecucaoResumoResponse,
    SnapshotPerfilResumoResponse,
    SnapshotTaxonomiaResumoResponse,
    StatusExecucaoLiteral,
)

router = APIRouter(prefix="/api/v1/execucoes-classificacao", tags=["execucoes-classificacao"])


def _resolver_state(request: Request, attr: str) -> object:
    valor = getattr(request.app.state, attr, None)
    if valor is None:
        raise RuntimeError(f"Dependência '{attr}' não configurada em app.state.")
    return valor


def get_criar_execucao_use_case(request: Request) -> CriarExecucaoClassificacaoUseCase:
    return cast(CriarExecucaoClassificacaoUseCase, _resolver_state(request, "criar_execucao_use_case"))


def get_listar_execucoes_use_case(request: Request) -> ListarExecucoesClassificacaoUseCase:
    return cast(ListarExecucoesClassificacaoUseCase, _resolver_state(request, "listar_execucoes_use_case"))


def get_detalhar_execucao_use_case(request: Request) -> DetalharExecucaoClassificacaoUseCase:
    return cast(DetalharExecucaoClassificacaoUseCase, _resolver_state(request, "detalhar_execucao_use_case"))


def get_retomar_execucao_use_case(request: Request) -> RetomarExecucaoClassificacaoUseCase:
    return cast(RetomarExecucaoClassificacaoUseCase, _resolver_state(request, "retomar_execucao_use_case"))


def _descongelar_json(valor: Any) -> Any:
    if isinstance(valor, Mapping):
        return {str(k): _descongelar_json(v) for k, v in valor.items()}
    if isinstance(valor, list | tuple):
        return [_descongelar_json(v) for v in valor]
    return valor


def _extrair_uuid_opcional(valor: Any) -> UUID | None:
    if valor is None:
        return None
    if isinstance(valor, UUID):
        return valor
    try:
        return UUID(str(valor))
    except (ValueError, TypeError, AttributeError):
        return None


def _texto_snapshot(snap: Mapping[str, Any], chave: str) -> str:
    valor = snap.get(chave)
    if valor is None:
        return ""
    return str(valor)


def _serializar_snapshot_resumo(execucao: ExecucaoClassificacao) -> SnapshotExecucaoResumoResponse:
    snap_tax = execucao.snapshot_taxonomia
    snap_perf = execucao.snapshot_perfil
    disciplinas_raw = snap_tax.get("disciplinas")
    disciplinas = (
        disciplinas_raw
        if isinstance(disciplinas_raw, Sequence) and not isinstance(disciplinas_raw, str | bytes | bytearray)
        else ()
    )
    disciplinas_codigos = [
        str(item.get("codigo", "")) for item in disciplinas if isinstance(item, Mapping) and item.get("codigo")
    ]
    return SnapshotExecucaoResumoResponse(
        taxonomia=SnapshotTaxonomiaResumoResponse(
            id=_extrair_uuid_opcional(snap_tax.get("id")) or execucao.taxonomia_id,
            codigo=_texto_snapshot(snap_tax, "codigo"),
            nome=_texto_snapshot(snap_tax, "nome"),
            curso_referencia=_texto_snapshot(snap_tax, "curso_referencia"),
            total_disciplinas=len(disciplinas),
            disciplinas_codigos=disciplinas_codigos,
        ),
        perfil=SnapshotPerfilResumoResponse(
            id=_extrair_uuid_opcional(snap_perf.get("id")) or execucao.perfil_id,
            codigo=_texto_snapshot(snap_perf, "codigo"),
            versao=_texto_snapshot(snap_perf, "versao"),
            descricao=_texto_snapshot(snap_perf, "descricao"),
        ),
    )


def _serializar_aceita(execucao: ExecucaoClassificacao) -> ExecucaoClassificacaoAceitaResponse:
    return ExecucaoClassificacaoAceitaResponse(
        execucao_id=execucao.id,
        taxonomia_id=execucao.taxonomia_id,
        perfil_id=execucao.perfil_id,
        escopo=cast(EscopoExecucaoLiteral, execucao.escopo.value),
        escopo_prova_id=execucao.escopo_prova_id,
        escopo_questao_ids=list(execucao.escopo_questao_ids),
        incluir_revisadas=execucao.incluir_revisadas,
        status=cast(StatusExecucaoLiteral, execucao.status.value),
        total_itens=execucao.total_itens,
        processadas=execucao.processadas,
    )


def _serializar_resumo(execucao: ExecucaoClassificacao) -> ExecucaoClassificacaoResumoResponse:
    return ExecucaoClassificacaoResumoResponse(
        id=execucao.id,
        taxonomia_id=execucao.taxonomia_id,
        perfil_id=execucao.perfil_id,
        escopo=cast(EscopoExecucaoLiteral, execucao.escopo.value),
        escopo_prova_id=execucao.escopo_prova_id,
        escopo_questao_ids=list(execucao.escopo_questao_ids),
        incluir_revisadas=execucao.incluir_revisadas,
        status=cast(StatusExecucaoLiteral, execucao.status.value),
        total_itens=execucao.total_itens,
        processadas=execucao.processadas,
        total_erros=len(execucao.erros_por_questao),
        divergencias_abertas=execucao.divergencias_abertas,
        cache_hits=execucao.cache_hits,
        prompt_tokens=execucao.prompt_tokens,
        completion_tokens=execucao.completion_tokens,
        criada_em=execucao.criada_em,
        iniciada_em=execucao.iniciada_em,
        concluida_em=execucao.concluida_em,
        snapshot_resumo=_serializar_snapshot_resumo(execucao),
    )


def _serializar_detalhe(execucao: ExecucaoClassificacao) -> ExecucaoClassificacaoDetalheResponse:
    return ExecucaoClassificacaoDetalheResponse(
        id=execucao.id,
        taxonomia_id=execucao.taxonomia_id,
        perfil_id=execucao.perfil_id,
        escopo=cast(EscopoExecucaoLiteral, execucao.escopo.value),
        escopo_prova_id=execucao.escopo_prova_id,
        escopo_questao_ids=list(execucao.escopo_questao_ids),
        incluir_revisadas=execucao.incluir_revisadas,
        status=cast(StatusExecucaoLiteral, execucao.status.value),
        total_itens=execucao.total_itens,
        processadas=execucao.processadas,
        total_erros=len(execucao.erros_por_questao),
        divergencias_abertas=execucao.divergencias_abertas,
        cache_hits=execucao.cache_hits,
        prompt_tokens=execucao.prompt_tokens,
        completion_tokens=execucao.completion_tokens,
        criada_em=execucao.criada_em,
        iniciada_em=execucao.iniciada_em,
        concluida_em=execucao.concluida_em,
        snapshot_resumo=_serializar_snapshot_resumo(execucao),
        erros_por_questao=dict(execucao.erros_por_questao),
        snapshot_taxonomia=cast(dict[str, Any], _descongelar_json(execucao.snapshot_taxonomia)),
        snapshot_perfil=cast(dict[str, Any], _descongelar_json(execucao.snapshot_perfil)),
        questao_ids_alvo=list(execucao.questao_ids_alvo),
        questao_ids_concluidas=list(execucao.questao_ids_concluidas),
    )


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ExecucaoClassificacaoAceitaResponse,
    responses={
        404: {"model": ErroDetalheResponse},
        422: {"model": ErroDetalheResponse},
    },
    summary="Congela snapshots de Taxonomia/Perfil, resolve escopo e enfileira uma Execução de Classificação",
)
def criar_execucao_classificacao(
    payload: ExecucaoClassificacaoCriarRequest,
    use_case: Annotated[CriarExecucaoClassificacaoUseCase, Depends(get_criar_execucao_use_case)],
) -> ExecucaoClassificacaoAceitaResponse:
    execucao = use_case.execute(
        taxonomia_id=payload.taxonomia_id,
        perfil_id=payload.perfil_id,
        escopo=EscopoExecucao(payload.escopo),
        incluir_revisadas=payload.incluir_revisadas,
        prova_id=payload.prova_id,
        questao_ids=payload.questao_ids,
    )
    return _serializar_aceita(execucao)


@router.get(
    "",
    response_model=ListaExecucoesClassificacaoResponse,
    summary="Lista as Execuções de Classificação com filtro opcional por Taxonomia",
)
def listar_execucoes_classificacao(
    use_case: Annotated[ListarExecucoesClassificacaoUseCase, Depends(get_listar_execucoes_use_case)],
    taxonomia_id: Annotated[UUID | None, Query()] = None,
) -> ListaExecucoesClassificacaoResponse:
    itens = [_serializar_resumo(item) for item in use_case.execute(taxonomia_id=taxonomia_id)]
    return ListaExecucoesClassificacaoResponse(itens=itens, total=len(itens))


@router.get(
    "/{execucao_id}",
    response_model=ExecucaoClassificacaoDetalheResponse,
    responses={404: {"model": ErroDetalheResponse}},
    summary="Obtém os detalhes, progresso, erros por questão e snapshots congelados de uma Execução",
)
def detalhar_execucao_classificacao(
    execucao_id: UUID,
    use_case: Annotated[DetalharExecucaoClassificacaoUseCase, Depends(get_detalhar_execucao_use_case)],
) -> ExecucaoClassificacaoDetalheResponse:
    return _serializar_detalhe(use_case.execute(execucao_id))


@router.post(
    "/{execucao_id}/retomar",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ExecucaoClassificacaoAceitaResponse,
    responses={
        404: {"model": ErroDetalheResponse},
        409: {"model": ErroDetalheResponse},
    },
    summary="Reenfileira a retomada de uma Execução interrompida ou concluída com erros",
)
def retomar_execucao_classificacao(
    execucao_id: UUID,
    use_case: Annotated[RetomarExecucaoClassificacaoUseCase, Depends(get_retomar_execucao_use_case)],
) -> ExecucaoClassificacaoAceitaResponse:
    execucao = use_case.execute(execucao_id)
    return _serializar_aceita(execucao)
