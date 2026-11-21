from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from domain.alertas_extracao import (
    MARCADOR_FORMULA_NAO_DECODIFICADA,
    avaliar_alertas_extracao,
    marcar_alerta_verificado,
    reavaliar_alertas_estruturais,
)
from domain.enums import CodigoAlertaExtracao, LetraAlternativa, SituacaoGabarito, StatusAlerta, TipoQuestao
from domain.exceptions import ErroInvarianteDominio
from domain.prova import Alternativa, Gabarito, Questao


def _alternativas_validas() -> list[Alternativa]:
    return [Alternativa(letra=letra, texto=f"Alternativa {letra.value} válida") for letra in LetraAlternativa]


def _questao_limpa() -> Questao:
    return Questao(
        prova_id=uuid4(),
        numero=13,
        enunciado="Considere um algoritmo de ordenação por comparação com complexidade O(n log n).",
        paginas=(10, 11),
        alternativas=_alternativas_validas(),
        gabarito=Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.C),
    )


def test_avaliar_alertas_detecta_todos_os_6_codigos_deterministicamente() -> None:
    alternativas = _alternativas_validas()
    alternativas[2] = Alternativa(LetraAlternativa.C, f"Valor {MARCADOR_FORMULA_NAO_DECODIFICADA}")
    alternativas_incompletas = alternativas[:4]

    questao = Questao(
        prova_id=uuid4(),
        numero=13,
        enunciado="![img](fig.png)",
        paginas=(7,),
        alternativas=alternativas_incompletas,
        gabarito=Gabarito(SituacaoGabarito.PENDENTE),
    )

    alertas = avaliar_alertas_extracao(
        questao,
        usou_ocr=True,
        paginas_com_fonte_symbol=(7, 8),
        gabarito_enviado_na_prova=True,
    )
    codigos = {alerta.codigo for alerta in alertas}
    assert codigos == {
        CodigoAlertaExtracao.FORMULA_NAO_DECODIFICADA,
        CodigoAlertaExtracao.ALTERNATIVAS_INCOMPLETAS,
        CodigoAlertaExtracao.PDF_VIA_OCR,
        CodigoAlertaExtracao.ENUNCIADO_SUSPEITO,
        CodigoAlertaExtracao.FONTE_SYMBOL_DETECTADA,
        CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA,
    }
    assert questao.tem_alerta_critico_aberto is True


def test_avaliar_alertas_nao_gera_gabarito_ausente_quando_gabarito_nao_foi_enviado() -> None:
    questao = _questao_limpa()
    questao.gabarito = Gabarito(SituacaoGabarito.PENDENTE)

    alertas = avaliar_alertas_extracao(questao, gabarito_enviado_na_prova=False)
    assert alertas == []


def test_avaliar_alertas_nao_marca_enunciado_suspeito_para_codigo_curto_legivel() -> None:
    questao = _questao_limpa()
    questao.enunciado = "Analise o código:\n```c\nint x = 10;\n```"

    alertas = avaliar_alertas_extracao(questao)
    assert CodigoAlertaExtracao.ENUNCIADO_SUSPEITO not in {a.codigo for a in alertas}


def test_avaliar_alertas_marca_enunciado_suspeito_com_caractere_corrompido() -> None:
    questao = _questao_limpa()
    questao.enunciado = "Considere a função f(x) = \ufffd no intervalo real."

    alertas = avaliar_alertas_extracao(questao)
    assert {a.codigo for a in alertas} == {CodigoAlertaExtracao.ENUNCIADO_SUSPEITO}


def test_reavaliar_alertas_fecha_estruturais_e_preserva_inspecao_ate_verificacao() -> None:
    t1 = datetime(2026, 11, 20, 21, 5, tzinfo=UTC)
    t2 = datetime(2026, 11, 20, 21, 10, tzinfo=UTC)
    t3 = datetime(2026, 11, 20, 21, 15, tzinfo=UTC)

    questao = Questao(
        prova_id=uuid4(),
        numero=15,
        enunciado=f"Texto curto {MARCADOR_FORMULA_NAO_DECODIFICADA}",
        paginas=(12,),
        alternativas=_alternativas_validas()[:3],
        gabarito=Gabarito(SituacaoGabarito.PENDENTE),
    )
    avaliar_alertas_extracao(
        questao,
        usou_ocr=True,
        paginas_com_fonte_symbol=(12,),
        gabarito_enviado_na_prova=True,
    )

    questao.editar_conteudo(
        enunciado="Considere a integral definida de x^2 no intervalo de zero até um.",
        alternativas=_alternativas_validas(),
        gabarito=Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.B),
    )
    reavaliar_alertas_estruturais(questao, t1)

    por_codigo = {a.codigo: a for a in questao.alertas_extracao}
    for codigo_estrutural in (
        CodigoAlertaExtracao.FORMULA_NAO_DECODIFICADA,
        CodigoAlertaExtracao.ALTERNATIVAS_INCOMPLETAS,
        CodigoAlertaExtracao.ENUNCIADO_SUSPEITO,
        CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA,
    ):
        assert por_codigo[codigo_estrutural].status == StatusAlerta.RESOLVIDO
        assert por_codigo[codigo_estrutural].resolvido_em == t1

    assert por_codigo[CodigoAlertaExtracao.PDF_VIA_OCR].status == StatusAlerta.ABERTO
    assert por_codigo[CodigoAlertaExtracao.FONTE_SYMBOL_DETECTADA].status == StatusAlerta.ABERTO
    assert questao.tem_alerta_critico_aberto is True

    questao.editar_conteudo(enunciado="Curto")
    reavaliar_alertas_estruturais(questao, t2)
    assert por_codigo[CodigoAlertaExtracao.ENUNCIADO_SUSPEITO].status == StatusAlerta.ABERTO
    assert por_codigo[CodigoAlertaExtracao.ENUNCIADO_SUSPEITO].resolvido_em is None

    with pytest.raises(ErroInvarianteDominio):
        marcar_alerta_verificado(questao, CodigoAlertaExtracao.ENUNCIADO_SUSPEITO, t3)

    questao.editar_conteudo(enunciado="Enunciado completo e legível após nova edição manual.")
    reavaliar_alertas_estruturais(questao, t3)
    marcar_alerta_verificado(questao, CodigoAlertaExtracao.PDF_VIA_OCR, t3)
    marcar_alerta_verificado(questao, CodigoAlertaExtracao.FONTE_SYMBOL_DETECTADA, t3)

    assert questao.codigos_alertas_abertos == set()
    assert questao.tem_alerta_critico_aberto is False
    assert questao.editada_manualmente is True


def test_avaliar_alertas_nao_marca_alternativas_incompletas_para_questao_discursiva() -> None:
    questao_discursiva = Questao(
        prova_id=uuid4(),
        numero=1,
        tipo=TipoQuestao.DISCURSIVA,
        enunciado="Discorra sobre a arquitetura de pipelines superescalares e previsão de desvios.",
        paginas=(2,),
        alternativas=[],
    )

    alertas = avaliar_alertas_extracao(questao_discursiva)
    assert alertas == []

    questao_discursiva.editar_conteudo(enunciado="Curto")
    alertas_corrompida = avaliar_alertas_extracao(questao_discursiva)
    assert [a.codigo for a in alertas_corrompida] == [CodigoAlertaExtracao.ENUNCIADO_SUSPEITO]
