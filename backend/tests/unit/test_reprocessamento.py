from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from domain.alertas_extracao import avaliar_alertas_extracao
from domain.enums import CodigoAlertaExtracao, LetraAlternativa, SituacaoGabarito, StatusAlerta
from domain.prova import Alternativa, Gabarito, Questao
from domain.reprocessamento import aplicar_gabarito_na_prova, reconciliar_reprocessamento_prova


def _alts(prefixo: str) -> list[Alternativa]:
    return [Alternativa(letra=letra, texto=f"{prefixo} {letra.value}") for letra in LetraAlternativa]


def test_reprocessamento_preserva_editadas_manualmente_por_padrao() -> None:
    prova_id = uuid4()
    q_editada = Questao(
        prova_id=prova_id,
        numero=10,
        enunciado="Enunciado curado manualmente com precisão.",
        paginas=(4,),
        alternativas=_alts("Curada"),
        gabarito=Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.A),
        editada_manualmente=True,
    )
    q_automatica = Questao(
        prova_id=prova_id,
        numero=11,
        enunciado="Enunciado antigo extraído automaticamente.",
        paginas=(5,),
        alternativas=_alts("Antiga"),
        gabarito=Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.B),
        editada_manualmente=False,
    )
    q_ausente = Questao(
        prova_id=prova_id,
        numero=12,
        enunciado="Questão existente que não veio na reextração parcial.",
        paginas=(6,),
        alternativas=_alts("Existente"),
        editada_manualmente=False,
    )

    nova_10 = Questao(
        prova_id=prova_id,
        numero=10,
        enunciado="Novo texto bruto do parser que não deve sobrescrever.",
        paginas=(4,),
        alternativas=_alts("Bruta"),
    )
    nova_11 = Questao(
        prova_id=prova_id,
        numero=11,
        enunciado="Novo texto corrigido pelo parser atualizado.",
        paginas=(5,),
        alternativas=_alts("Nova"),
    )
    nova_13 = Questao(
        prova_id=prova_id,
        numero=13,
        enunciado="Questão recém descoberta no reprocessamento.",
        paginas=(7,),
        alternativas=_alts("Adicionada"),
    )

    res = reconciliar_reprocessamento_prova(
        [q_editada, q_automatica, q_ausente],
        [nova_10, nova_11, nova_13],
        sobrescrever_editadas=False,
    )

    assert res.preservadas_editadas == (10,)
    assert res.atualizadas == (11,)
    assert res.adicionadas == (13,)
    assert res.ausentes_na_extracao == (12,)

    por_numero = {q.numero: q for q in res.questoes_finais}
    assert por_numero[10].enunciado == "Enunciado curado manualmente com precisão."
    assert por_numero[10].editada_manualmente is True
    assert por_numero[11].id == q_automatica.id
    assert por_numero[11].enunciado == "Novo texto corrigido pelo parser atualizado."
    assert por_numero[11].gabarito == Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.B)
    assert por_numero[12].id == q_ausente.id


def test_reprocessamento_sobrescreve_editadas_quando_solicitado() -> None:
    prova_id = uuid4()
    q_editada = Questao(
        prova_id=prova_id,
        numero=10,
        enunciado="Texto manual",
        alternativas=_alts("Manual"),
        editada_manualmente=True,
    )
    nova_10 = Questao(
        prova_id=prova_id,
        numero=10,
        enunciado="Texto reextraído",
        alternativas=_alts("Reextraido"),
    )

    res = reconciliar_reprocessamento_prova([q_editada], [nova_10], sobrescrever_editadas=True)
    assert res.atualizadas == (10,)
    assert res.preservadas_editadas == ()
    assert res.questoes_finais[0].id == q_editada.id
    assert res.questoes_finais[0].enunciado == "Texto reextraído"
    assert res.questoes_finais[0].editada_manualmente is False


def test_aplicar_gabarito_atualiza_contadores_e_reavalia_alerta_sem_marcar_edicao_manual() -> None:
    agora = datetime(2026, 11, 20, 21, 12, tzinfo=UTC)
    prova_id = uuid4()
    q10 = Questao(
        prova_id=prova_id,
        numero=10,
        enunciado="Questão dez com texto suficientemente longo.",
        alternativas=_alts("Q10"),
        gabarito=Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.A),
    )
    q11 = Questao(
        prova_id=prova_id,
        numero=11,
        enunciado="Questão onze com texto suficientemente longo.",
        alternativas=_alts("Q11"),
        gabarito=Gabarito(SituacaoGabarito.PENDENTE),
    )
    avaliar_alertas_extracao(q11, gabarito_enviado_na_prova=True)

    q12 = Questao(
        prova_id=prova_id,
        numero=12,
        enunciado="Questão doze com texto suficientemente longo.",
        alternativas=_alts("Q12"),
        gabarito=Gabarito(SituacaoGabarito.PENDENTE),
    )

    resumo = aplicar_gabarito_na_prova(
        [q10, q11, q12],
        {
            10: Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.A),
            11: Gabarito(SituacaoGabarito.ANULADA),
            99: Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.E),
        },
        agora,
    )

    assert resumo.mantidas == 1
    assert resumo.alteradas == 1
    assert resumo.anuladas == 1
    assert resumo.sem_correspondencia == (99,)
    assert resumo.questoes_sem_gabarito == (12,)
    assert q10.editada_manualmente is False
    assert q11.editada_manualmente is False
    assert q11.alertas_extracao[0].status == StatusAlerta.RESOLVIDO
    assert CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA in q12.codigos_alertas_abertos


def test_reprocessamento_reconcilia_alerta_gabarito_ausente_com_gabarito_preservado() -> None:
    agora = datetime(2026, 11, 20, 21, 30, tzinfo=UTC)
    prova_id = uuid4()
    q_atual = Questao(
        prova_id=prova_id,
        numero=10,
        enunciado="Enunciado anterior suficientemente longo e legível.",
        alternativas=_alts("Antiga"),
        gabarito=Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.C),
    )
    q_nova = Questao(
        prova_id=prova_id,
        numero=10,
        enunciado="Enunciado reextraído suficientemente longo e legível.",
        alternativas=_alts("Nova"),
        gabarito=Gabarito(SituacaoGabarito.PENDENTE),
    )
    avaliar_alertas_extracao(q_nova, gabarito_enviado_na_prova=True)
    assert CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA in q_nova.codigos_alertas_abertos

    res_sem_agora = reconciliar_reprocessamento_prova([q_atual], [q_nova])
    q_final_sem_agora = res_sem_agora.questoes_finais[0]
    assert q_final_sem_agora.gabarito == Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.C)
    assert CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA not in q_final_sem_agora.codigos_alertas_abertos

    res_com_agora = reconciliar_reprocessamento_prova([q_atual], [q_nova], agora=agora)
    q_final_com_agora = res_com_agora.questoes_finais[0]
    assert q_final_com_agora.gabarito == Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.C)
    assert CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA not in q_final_com_agora.codigos_alertas_abertos
    alerta_resolvido = next(
        a for a in q_final_com_agora.alertas_extracao if a.codigo == CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA
    )
    assert alerta_resolvido.status == StatusAlerta.RESOLVIDO
    assert alerta_resolvido.resolvido_em == agora


def test_reprocessamento_preserva_alerta_gabarito_ausente_quando_gabarito_permanece_pendente() -> None:
    prova_id = uuid4()
    q_atual = Questao(
        prova_id=prova_id,
        numero=10,
        enunciado="Enunciado anterior suficientemente longo e legível.",
        alternativas=_alts("Antiga"),
        gabarito=Gabarito(SituacaoGabarito.PENDENTE),
    )
    avaliar_alertas_extracao(q_atual, gabarito_enviado_na_prova=True)

    q_nova = Questao(
        prova_id=prova_id,
        numero=10,
        enunciado="Enunciado reextraído suficientemente longo e legível.",
        alternativas=_alts("Nova"),
        gabarito=Gabarito(SituacaoGabarito.PENDENTE),
    )
    avaliar_alertas_extracao(q_nova, gabarito_enviado_na_prova=False)

    res = reconciliar_reprocessamento_prova([q_atual], [q_nova])
    assert CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA in res.questoes_finais[0].codigos_alertas_abertos
