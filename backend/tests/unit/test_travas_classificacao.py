from __future__ import annotations

from datetime import UTC, datetime

import pytest

from domain.enums import CodigoAlertaExtracao, StatusAlerta
from domain.prova import AlertaExtracao
from domain.taxonomia import Disciplina, Taxonomia
from domain.travas_classificacao import (
    ALERTA_BAIXA_CONFIANCA,
    calcular_revisao_prioritaria,
    validar_e_normalizar_classificacao,
)


def _taxonomia() -> Taxonomia:
    return Taxonomia(
        codigo="enade-ec",
        nome="ENADE Eng. Computação",
        disciplinas=[
            Disciplina("algoritmos", "Algoritmos", "Complexidade."),
            Disciplina("redes", "Redes", "TCP/IP."),
            Disciplina("sistemas-operacionais", "Sistemas Operacionais", "Processos."),
            Disciplina("banco-de-dados", "Banco de Dados", "SQL."),
            Disciplina("arquivada", "Disciplina Arquivada", "Antiga.", ativa=False),
        ],
    )


def test_trava_rejeita_disciplina_principal_invalida_ou_arquivada_com_elegivel_retry() -> None:
    tax = _taxonomia()

    res_fantasma = validar_e_normalizar_classificacao(
        {
            "disciplina_principal": "disciplina-fantasma",
            "disciplinas_secundarias": [],
            "topicos": ["grafos"],
            "justificativa": "Justificativa técnica.",
            "confianca": 0.99,
        },
        tax,
    )
    assert res_fantasma.valida is False
    assert res_fantasma.elegivel_retry is True

    res_arquivada = validar_e_normalizar_classificacao(
        {
            "disciplina_principal": "arquivada",
            "disciplinas_secundarias": [],
            "topicos": ["legado"],
            "justificativa": "Justificativa técnica.",
            "confianca": 0.99,
        },
        tax,
    )
    assert res_arquivada.valida is False
    assert res_arquivada.elegivel_retry is True


def test_trava_saneia_secundarias_duplicadas_iguais_fantasmas_e_limite_2() -> None:
    tax = _taxonomia()
    res = validar_e_normalizar_classificacao(
        {
            "disciplina_principal": "algoritmos",
            "disciplinas_secundarias": [
                "algoritmos",
                "redes",
                "fantasma",
                "arquivada",
                "redes",
                "sistemas-operacionais",
                "banco-de-dados",
            ],
            "topicos": ["grafos"],
            "justificativa": "Questão interdisciplinar.",
            "confianca": 0.95,
        },
        tax,
    )

    assert res.valida is True
    assert res.disciplina_principal == "algoritmos"
    assert res.disciplinas_secundarias == ("redes", "sistemas-operacionais")
    assert res.houve_saneamento is True
    assert res.revisao_prioritaria is True
    assert "removida_secundaria_igual_principal:algoritmos" in res.alertas_validacao
    assert "removida_secundaria_invalida:fantasma" in res.alertas_validacao
    assert "removida_secundaria_invalida:arquivada" in res.alertas_validacao
    assert "removida_secundaria_duplicada:redes" in res.alertas_validacao
    assert "secundarias_truncadas_para_2:3" in res.alertas_validacao


def test_trava_normaliza_topicos_sem_cortar_palavras_e_limita_a_4() -> None:
    tax = _taxonomia()
    res = validar_e_normalizar_classificacao(
        {
            "disciplina_principal": "algoritmos",
            "disciplinas_secundarias": [],
            "topicos": [
                "Computação Gráfica",
                "computacao grafica",
                "processamento-digital-de-sinais-avancados",
                "TCP / UDP!!",
                "tokenunicocommaisdetrintaedoiscaracteres",
                "Árvores Binárias",
                "Quinto Tópico Excedente",
            ],
            "justificativa": "Vários tópicos.",
            "confianca": 0.90,
        },
        tax,
    )

    assert res.valida is True
    assert res.topicos == (
        "computacao-grafica",
        "processamento-digital-de-sinais",
        "tcp-udp",
        "arvores-binarias",
    )
    assert all(len(t) <= 32 for t in res.topicos)
    assert res.houve_saneamento is True
    assert res.revisao_prioritaria is True


def test_trava_limpa_nao_dispara_saneamento_nem_revisao_prioritaria() -> None:
    tax = _taxonomia()
    res = validar_e_normalizar_classificacao(
        {
            "disciplina_principal": "redes",
            "disciplinas_secundarias": ["sistemas-operacionais"],
            "topicos": ["roteamento-ospf", "camada-de-rede"],
            "justificativa": "Questão sobre protocolo OSPF.",
            "confianca": 0.75,
        },
        tax,
    )
    assert res.valida is True
    assert res.houve_saneamento is False
    assert res.revisao_prioritaria is False
    assert res.alertas_validacao == ()


@pytest.mark.parametrize(
    "codigo_critico",
    [
        CodigoAlertaExtracao.FORMULA_NAO_DECODIFICADA,
        CodigoAlertaExtracao.ALTERNATIVAS_INCOMPLETAS,
        CodigoAlertaExtracao.PDF_VIA_OCR,
        CodigoAlertaExtracao.ENUNCIADO_SUSPEITO,
    ],
)
def test_revisao_prioritaria_aciona_com_confianca_099_para_qualquer_alerta_critico_aberto(
    codigo_critico: CodigoAlertaExtracao,
) -> None:
    tax = _taxonomia()
    alerta = AlertaExtracao(codigo=codigo_critico)
    res = validar_e_normalizar_classificacao(
        {
            "disciplina_principal": "algoritmos",
            "disciplinas_secundarias": [],
            "topicos": ["grafos"],
            "justificativa": "Classificação com confiança alta.",
            "confianca": 0.99,
        },
        tax,
        alertas_extracao=(alerta,),
    )
    assert res.revisao_prioritaria is True


def test_revisao_prioritaria_ignora_critico_resolvido_e_informativos_abertos() -> None:
    agora = datetime(2026, 11, 20, 21, 15, tzinfo=UTC)
    critico_resolvido = AlertaExtracao(
        codigo=CodigoAlertaExtracao.FORMULA_NAO_DECODIFICADA,
        status=StatusAlerta.RESOLVIDO,
        resolvido_em=agora,
    )
    info_symbol = AlertaExtracao(codigo=CodigoAlertaExtracao.FONTE_SYMBOL_DETECTADA)
    info_gab = AlertaExtracao(codigo=CodigoAlertaExtracao.GABARITO_AUSENTE_NA_PROVA)

    assert calcular_revisao_prioritaria(0.99, (critico_resolvido, info_symbol, info_gab), ()) is False
    assert calcular_revisao_prioritaria(0.749, (), ()) is True
    assert calcular_revisao_prioritaria(0.75, (), (ALERTA_BAIXA_CONFIANCA,)) is False
    assert calcular_revisao_prioritaria(0.95, (), ("removida_secundaria_invalida:x",)) is True


@pytest.mark.parametrize("sequencia_bytes", [bytearray(b"redes"), memoryview(b"redes")])
def test_trava_rejeita_bytearray_e_memoryview_em_secundarias_e_topicos(sequencia_bytes: object) -> None:
    tax = _taxonomia()

    res_sec = validar_e_normalizar_classificacao(
        {
            "disciplina_principal": "algoritmos",
            "disciplinas_secundarias": sequencia_bytes,
            "topicos": ["grafos"],
            "justificativa": "Justificativa técnica.",
            "confianca": 0.9,
        },
        tax,
    )
    assert res_sec.valida is False
    assert res_sec.elegivel_retry is True
    assert res_sec.motivo_rejeicao == "disciplinas_secundarias_formato_invalido"

    res_top = validar_e_normalizar_classificacao(
        {
            "disciplina_principal": "algoritmos",
            "disciplinas_secundarias": [],
            "topicos": sequencia_bytes,
            "justificativa": "Justificativa técnica.",
            "confianca": 0.9,
        },
        tax,
    )
    assert res_top.valida is False
    assert res_top.elegivel_retry is True
    assert res_top.motivo_rejeicao == "topicos_formato_invalido"
