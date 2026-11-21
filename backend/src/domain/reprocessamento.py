"""Políticas determinísticas de Reprocessamento de Prova e atualização de Gabarito."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from domain.alertas_extracao import reavaliar_alertas_estruturais
from domain.enums import CodigoAlertaExtracao, SituacaoGabarito
from domain.exceptions import ErroValidacaoDominio
from domain.prova import AlertaExtracao, Alternativa, AtivoVisual, Gabarito, Questao


@dataclass(frozen=True, slots=True)
class ResultadoReprocessamento:
    """Resumo da reconciliação de questões ao reprocessar o PDF de uma Prova."""

    questoes_finais: tuple[Questao, ...]
    adicionadas: tuple[int, ...]
    atualizadas: tuple[int, ...]
    preservadas_editadas: tuple[int, ...]
    ausentes_na_extracao: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ResumoAtualizacaoGabarito:
    """Contadores resultantes da aplicação independente de Gabarito na Prova."""

    mantidas: int
    alteradas: int
    anuladas: int
    sem_correspondencia: tuple[int, ...]
    questoes_sem_gabarito: tuple[int, ...]


def _indexar_por_numero(questoes: Sequence[Questao], origem: str) -> dict[int, Questao]:
    indice: dict[int, Questao] = {}
    for questao in questoes:
        if questao.numero in indice:
            raise ErroValidacaoDominio(f"Número de questão duplicado ({questao.numero}) em {origem}.")
        indice[questao.numero] = questao
    return indice


def _clonar_ativos_para_questao(ativos: Sequence[AtivoVisual], questao_id: object) -> list[AtivoVisual]:
    from uuid import UUID

    qid = questao_id if isinstance(questao_id, UUID) else None
    return [
        AtivoVisual(
            id=ativo.id,
            questao_id=qid,
            origem=ativo.origem,
            ordem=ativo.ordem,
            alternativa_letra=ativo.alternativa_letra,
            pagina=ativo.pagina,
            bbox=ativo.bbox,
            chave_arquivo=ativo.chave_arquivo,
        )
        for ativo in ativos
    ]


def _clonar_alerta(alerta: AlertaExtracao) -> AlertaExtracao:
    return AlertaExtracao(
        id=alerta.id,
        codigo=alerta.codigo,
        severidade=alerta.severidade,
        status=alerta.status,
        mensagem=alerta.mensagem,
        resolvido_em=alerta.resolvido_em,
    )


def _reconciliar_alertas_gabarito(
    q_atual: Questao,
    q_nova: Questao,
    gabarito_final: Gabarito,
    agora: datetime | None,
) -> list[AlertaExtracao]:
    alertas = [_clonar_alerta(al) for al in q_nova.alertas_extracao]
    if gabarito_final.situacao_gabarito != SituacaoGabarito.PENDENTE:
        reconciliados: list[AlertaExtracao] = []
        for al in alertas:
            if al.codigo == CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA and al.is_aberto:
                if agora is not None:
                    al.resolver(agora)
                    reconciliados.append(al)
                continue
            reconciliados.append(al)
        return reconciliados

    ja_possui_alerta_gabarito = any(al.codigo == CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA for al in alertas)
    if not ja_possui_alerta_gabarito:
        alerta_atual_aberto = next(
            (
                al
                for al in q_atual.alertas_extracao
                if al.codigo == CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA and al.is_aberto
            ),
            None,
        )
        if alerta_atual_aberto is not None:
            alertas.append(_clonar_alerta(alerta_atual_aberto))
    return alertas


def reconciliar_reprocessamento_prova(
    questoes_atuais: Sequence[Questao],
    questoes_extraidas: Sequence[Questao],
    *,
    sobrescrever_editadas: bool = False,
    agora: datetime | None = None,
) -> ResultadoReprocessamento:
    """Reconcilia reprocessamento por número oficial preservando edições manuais por padrão."""
    atuais_por_numero = _indexar_por_numero(questoes_atuais, "questoes_atuais")
    extraidas_por_numero = _indexar_por_numero(questoes_extraidas, "questoes_extraidas")

    finais_por_numero: dict[int, Questao] = {}
    adicionadas: list[int] = []
    atualizadas: list[int] = []
    preservadas_editadas: list[int] = []
    ausentes_na_extracao: list[int] = []

    for numero, q_nova in sorted(extraidas_por_numero.items()):
        q_atual = atuais_por_numero.get(numero)
        if q_atual is None:
            nova_copia = Questao(
                id=q_nova.id,
                prova_id=q_nova.prova_id,
                numero=q_nova.numero,
                enunciado=q_nova.enunciado,
                componente=q_nova.componente,
                tipo=q_nova.tipo,
                paginas=q_nova.paginas,
                alternativas=[Alternativa(id=a.id, letra=a.letra, texto=a.texto) for a in q_nova.alternativas],
                ativos_visuais=_clonar_ativos_para_questao(q_nova.ativos_visuais, q_nova.id),
                gabarito=q_nova.gabarito,
                alertas_extracao=[_clonar_alerta(al) for al in q_nova.alertas_extracao],
                editada_manualmente=False,
            )
            finais_por_numero[numero] = nova_copia
            adicionadas.append(numero)
            continue

        if q_atual.editada_manualmente and not sobrescrever_editadas:
            finais_por_numero[numero] = q_atual
            preservadas_editadas.append(numero)
            continue

        gabarito_final = (
            q_atual.gabarito if q_nova.gabarito.situacao_gabarito == SituacaoGabarito.PENDENTE else q_nova.gabarito
        )
        alertas_reconciliados = _reconciliar_alertas_gabarito(q_atual, q_nova, gabarito_final, agora)
        q_reconciliada = Questao(
            id=q_atual.id,
            prova_id=q_atual.prova_id,
            numero=q_atual.numero,
            enunciado=q_nova.enunciado,
            componente=q_nova.componente,
            tipo=q_nova.tipo,
            paginas=q_nova.paginas,
            alternativas=[Alternativa(id=a.id, letra=a.letra, texto=a.texto) for a in q_nova.alternativas],
            ativos_visuais=_clonar_ativos_para_questao(q_nova.ativos_visuais, q_atual.id),
            gabarito=gabarito_final,
            alertas_extracao=alertas_reconciliados,
            editada_manualmente=False,
        )
        finais_por_numero[numero] = q_reconciliada
        atualizadas.append(numero)

    for numero, q_atual in sorted(atuais_por_numero.items()):
        if numero not in extraidas_por_numero:
            finais_por_numero[numero] = q_atual
            ausentes_na_extracao.append(numero)

    ordenadas = tuple(finais_por_numero[num] for num in sorted(finais_por_numero))
    return ResultadoReprocessamento(
        questoes_finais=ordenadas,
        adicionadas=tuple(adicionadas),
        atualizadas=tuple(atualizadas),
        preservadas_editadas=tuple(preservadas_editadas),
        ausentes_na_extracao=tuple(ausentes_na_extracao),
    )


def aplicar_gabarito_na_prova(
    questoes: Sequence[Questao],
    gabaritos_por_numero: Mapping[int, Gabarito],
    agora: datetime,
) -> ResumoAtualizacaoGabarito:
    """Aplica novo gabarito por número oficial sem alterar editada_manualmente."""
    questoes_por_numero = _indexar_por_numero(questoes, "questoes")
    mantidas = 0
    alteradas = 0
    anuladas = 0
    questoes_sem_gabarito: list[int] = []

    for numero in sorted(questoes_por_numero):
        questao = questoes_por_numero[numero]
        novo_gabarito = gabaritos_por_numero.get(numero)
        if novo_gabarito is not None:
            if questao.gabarito == novo_gabarito:
                mantidas += 1
            else:
                alteradas += 1
            if novo_gabarito.situacao_gabarito == SituacaoGabarito.ANULADA:
                anuladas += 1
            questao.aplicar_gabarito_oficial(novo_gabarito)
        else:
            questoes_sem_gabarito.append(numero)

        reavaliar_alertas_estruturais(questao, agora, gabarito_enviado_na_prova=True)

    sem_correspondencia = tuple(sorted(num for num in gabaritos_por_numero if num not in questoes_por_numero))
    return ResumoAtualizacaoGabarito(
        mantidas=mantidas,
        alteradas=alteradas,
        anuladas=anuladas,
        sem_correspondencia=sem_correspondencia,
        questoes_sem_gabarito=tuple(questoes_sem_gabarito),
    )
