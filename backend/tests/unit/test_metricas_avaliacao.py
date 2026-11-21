from __future__ import annotations

from datetime import UTC, datetime

import pytest

from domain.avaliacao import (
    ChaveQuestaoOuro,
    ConjuntoOuro,
    ItemConjuntoOuro,
    PredicaoClassificacao,
)
from domain.exceptions import ErroInvarianteDominio, ErroValidacaoDominio
from domain.metricas_avaliacao import avaliar_gate_regressao, calcular_avaliacao_classificacao


def _chave(numero: int) -> ChaveQuestaoOuro:
    return ChaveQuestaoOuro("ENADE", "Engenharia de Computação", 2023, numero)


def test_metricas_secundarias_vazio_igual_vazio_e_macro_f1_disciplina_rara() -> None:
    agora = datetime(2026, 11, 20, 21, 20, tzinfo=UTC)
    itens = [ItemConjuntoOuro(chave=_chave(i), disciplina_principal="comum") for i in range(1, 20)]
    itens.append(
        ItemConjuntoOuro(
            chave=_chave(20),
            disciplina_principal="rara",
            disciplinas_secundarias=("sec-a", "sec-b"),
        )
    )
    ouro = ConjuntoOuro("1.0", "enade-ec", agora, tuple(itens))

    preds = [
        PredicaoClassificacao(
            chave=_chave(i),
            conclusao_valida=True,
            disciplina_principal="comum",
            disciplinas_secundarias=(),
            confianca=0.92,
            latencia_ms=100.0 + i,
            prompt_tokens=1000,
            completion_tokens=150,
            from_cache=(i % 2 == 0),
            passes=(("comum", ()), ("comum", ())),
        )
        for i in range(1, 20)
    ]
    preds.append(
        PredicaoClassificacao(
            chave=_chave(20),
            conclusao_valida=True,
            disciplina_principal="comum",  # Erro na disciplina rara com alta confiança!
            disciplinas_secundarias=("sec-b", "sec-c"),  # Jaccard = 1/3, F1 = 1/2
            confianca=0.85,
            revisao_prioritaria=True,
            justificativa="Confundiu disciplina rara com comum.",
            latencia_ms=500.0,
            prompt_tokens=1200,
            completion_tokens=180,
            passes=(("comum", ("sec-b", "sec-c")), ("rara", ("sec-a",))),
        )
    )

    avaliacao = calcular_avaliacao_classificacao(
        ouro,
        preds,
        perfil_codigo="v2",
        perfil_versao="1.0",
        modelo_identidade="modelo-x",
        executado_em=agora,
    )

    # Acurácia = 19/20 = 0.95; Macro-F1 = (F1(comum) + F1(rara)=0) / 2
    assert avaliacao.camada1.acuracia_principal == pytest.approx(0.95)
    f1_comum = (2 * 19) / (2 * 19 + 1 + 0)
    assert avaliacao.camada1.macro_f1_principal == pytest.approx(f1_comum / 2.0)

    # 19 itens com ∅ == ∅ -> 1.0 + 1 item com {a,b} vs {b,c} -> Jaccard=1/3, F1=0.5
    assert avaliacao.camada1.jaccard_secundarias == pytest.approx((19 * 1.0 + (1 / 3)) / 20)
    assert avaliacao.camada1.f1_secundarias == pytest.approx((19 * 1.0 + 0.5) / 20)
    assert avaliacao.camada1.exact_match == pytest.approx(0.95)

    # Camada 2: matriz de confusão + ranking + divergências
    assert avaliacao.camada2.matriz_confusao["rara"]["comum"] == 1
    assert len(avaliacao.camada2.pares_confusao_ranqueados) == 1
    assert avaliacao.camada2.pares_confusao_ranqueados[0].esperada == "rara"
    assert avaliacao.camada2.pares_confusao_ranqueados[0].predita == "comum"
    assert len(avaliacao.camada2.divergencias) == 1
    assert avaliacao.camada2.divergencias[0].chave == _chave(20)

    # Camada 3: erro em alta confiança (>= 0.85) e estabilidade multipass
    assert avaliacao.camada3.conclusao_valida == pytest.approx(1.0)
    assert avaliacao.camada3.validade_primeira_tentativa == pytest.approx(1.0)
    assert avaliacao.camada3.total_alta_confianca == 20
    assert avaliacao.camada3.erros_alta_confianca == 1
    assert avaliacao.camada3.taxa_erro_alta_confianca == pytest.approx(0.05)
    assert avaliacao.camada3.estabilidade_multipass == pytest.approx(19 / 20)


def test_camada3_trata_baixa_confianca_limpa_como_valida_primeira_tentativa_e_zero_alta_confianca() -> None:
    agora = datetime(2026, 11, 20, 21, 20, tzinfo=UTC)
    ouro = ConjuntoOuro(
        "1.0",
        "enade-ec",
        agora,
        (ItemConjuntoOuro(chave=_chave(1), disciplina_principal="alg"),),
    )
    avaliacao = calcular_avaliacao_classificacao(
        ouro,
        (
            PredicaoClassificacao(
                chave=_chave(1),
                conclusao_valida=True,
                disciplina_principal="alg",
                confianca=0.65,
                revisao_prioritaria=True,
                tentativas=1,
                houve_saneamento=False,
            ),
        ),
        perfil_codigo="v2",
        perfil_versao="1.0",
        modelo_identidade="modelo-x",
        executado_em=agora,
    )
    assert avaliacao.camada3.validade_primeira_tentativa == pytest.approx(1.0)
    assert avaliacao.camada3.total_alta_confianca == 0
    assert avaliacao.camada3.taxa_erro_alta_confianca == pytest.approx(0.0)


def _avaliacao_para_gate(
    *,
    num_itens: int,
    acertos_principal: int,
    acertos_secundarias: int,
    validas: int,
    validas_1a_tentativa: int,
    taxonomia_codigo: str = "enade-ec",
) -> object:
    agora = datetime(2026, 11, 20, 21, 20, tzinfo=UTC)
    itens = tuple(
        ItemConjuntoOuro(
            chave=_chave(i),
            disciplina_principal="alg" if i <= num_itens // 2 else "redes",
            disciplinas_secundarias=("so",),
        )
        for i in range(1, num_itens + 1)
    )
    ouro = ConjuntoOuro("1.0", taxonomia_codigo, agora, itens)
    preds = []
    for idx, item in enumerate(itens, start=1):
        valida = idx <= validas
        prim_tentativa = idx <= validas_1a_tentativa
        principal = (
            item.disciplina_principal
            if idx <= acertos_principal
            else ("redes" if item.disciplina_principal == "alg" else "alg")
        )
        secs = ("so",) if idx <= acertos_secundarias else ()
        preds.append(
            PredicaoClassificacao(
                chave=item.chave,
                conclusao_valida=valida,
                disciplina_principal=principal if valida else None,
                disciplinas_secundarias=secs if valida else (),
                tentativas=1 if prim_tentativa else 2,
                houve_saneamento=False,
                confianca=0.90,
            )
        )
    return calcular_avaliacao_classificacao(
        ouro,
        preds,
        perfil_codigo="v2",
        perfil_versao="1.0",
        modelo_identidade="m",
        executado_em=agora,
    )


def test_gate_regressao_rejeita_snapshots_distintos_e_piso_estrutural_100_95() -> None:
    base = _avaliacao_para_gate(
        num_itens=100,
        acertos_principal=80,
        acertos_secundarias=80,
        validas=100,
        validas_1a_tentativa=100,
    )
    outro_ouro = _avaliacao_para_gate(
        num_itens=10,
        acertos_principal=10,
        acertos_secundarias=10,
        validas=10,
        validas_1a_tentativa=10,
    )
    with pytest.raises(ErroInvarianteDominio):
        avaliar_gate_regressao(base, outro_ouro)  # type: ignore[arg-type]

    cand_conclusao_99 = _avaliacao_para_gate(
        num_itens=100,
        acertos_principal=99,
        acertos_secundarias=99,
        validas=99,
        validas_1a_tentativa=99,
    )
    res_conclusao = avaliar_gate_regressao(base, cand_conclusao_99, modo_migracao=True)  # type: ignore[arg-type]
    assert res_conclusao.aprovado is False
    assert any("conclusao_valida" in m for m in res_conclusao.motivos_reprovacao)

    cand_primeira_94 = _avaliacao_para_gate(
        num_itens=100,
        acertos_principal=95,
        acertos_secundarias=95,
        validas=100,
        validas_1a_tentativa=94,
    )
    res_primeira = avaliar_gate_regressao(base, cand_primeira_94, modo_migracao=True)  # type: ignore[arg-type]
    assert res_primeira.aprovado is False
    assert any("validade_primeira_tentativa" in m for m in res_primeira.motivos_reprovacao)


def test_gate_regressao_modos_padrao_e_migracao_com_tolerancia_e_diff_de_itens() -> None:
    base = _avaliacao_para_gate(
        num_itens=100,
        acertos_principal=80,
        acertos_secundarias=80,
        validas=100,
        validas_1a_tentativa=100,
    )
    # Queda de exatos -2.0 p.p. em acurácia e -5.0 p.p. em jaccard (78/100 e 75/100)
    cand_borda_migracao = _avaliacao_para_gate(
        num_itens=100,
        acertos_principal=78,
        acertos_secundarias=75,
        validas=100,
        validas_1a_tentativa=95,
    )

    gate_padrao = avaliar_gate_regressao(base, cand_borda_migracao, modo_migracao=False)  # type: ignore[arg-type]
    assert gate_padrao.aprovado is False

    gate_migracao = avaliar_gate_regressao(base, cand_borda_migracao, modo_migracao=True)  # type: ignore[arg-type]
    assert gate_migracao.aprovado is True
    assert gate_migracao.delta_acuracia == pytest.approx(-0.02)
    assert gate_migracao.delta_jaccard == pytest.approx(-0.05)
    assert len(gate_migracao.regressoes) == 5

    # Queda de -3.0 p.p. em acurácia reprova mesmo em modo migração
    cand_reprovado_migracao = _avaliacao_para_gate(
        num_itens=100,
        acertos_principal=77,
        acertos_secundarias=75,
        validas=100,
        validas_1a_tentativa=100,
    )
    gate_migracao_reprovado = avaliar_gate_regressao(
        base,
        cand_reprovado_migracao,
        modo_migracao=True,  # type: ignore[arg-type]
    )
    assert gate_migracao_reprovado.aprovado is False


def test_gate_regressao_registra_ganhos_e_regressoes_de_principal_mesmo_com_exact_match_false() -> None:
    agora = datetime(2026, 11, 20, 21, 25, tzinfo=UTC)
    ouro = ConjuntoOuro(
        "1.0",
        "enade-ec",
        agora,
        (
            ItemConjuntoOuro(chave=_chave(1), disciplina_principal="alg", disciplinas_secundarias=("so",)),
            ItemConjuntoOuro(chave=_chave(2), disciplina_principal="redes", disciplinas_secundarias=("so",)),
        ),
    )
    baseline = calcular_avaliacao_classificacao(
        ouro,
        (
            # Item 1: principal correta, secundária errada -> exact_match=False
            PredicaoClassificacao(
                chave=_chave(1),
                conclusao_valida=True,
                disciplina_principal="alg",
                disciplinas_secundarias=(),
                confianca=0.90,
            ),
            # Item 2: principal errada, secundária errada -> exact_match=False
            PredicaoClassificacao(
                chave=_chave(2),
                conclusao_valida=True,
                disciplina_principal="alg",
                disciplinas_secundarias=(),
                confianca=0.90,
            ),
        ),
        perfil_codigo="v1",
        perfil_versao="1.0",
        modelo_identidade="m",
        executado_em=agora,
    )
    candidato = calcular_avaliacao_classificacao(
        ouro,
        (
            # Item 1 regride na principal (True -> False) mantendo exact_match=False
            PredicaoClassificacao(
                chave=_chave(1),
                conclusao_valida=True,
                disciplina_principal="redes",
                disciplinas_secundarias=(),
                confianca=0.90,
            ),
            # Item 2 ganha na principal (False -> True) mantendo exact_match=False
            PredicaoClassificacao(
                chave=_chave(2),
                conclusao_valida=True,
                disciplina_principal="redes",
                disciplinas_secundarias=(),
                confianca=0.90,
            ),
        ),
        perfil_codigo="v2",
        perfil_versao="1.0",
        modelo_identidade="m",
        executado_em=agora,
    )

    gate = avaliar_gate_regressao(baseline, candidato)
    assert len(gate.regressoes) == 1
    assert gate.regressoes[0].chave == _chave(1)
    assert gate.regressoes[0].baseline_exact_match is False
    assert gate.regressoes[0].candidato_exact_match is False
    assert gate.regressoes[0].baseline_principal_correta is True
    assert gate.regressoes[0].candidato_principal_correta is False

    assert len(gate.ganhos) == 1
    assert gate.ganhos[0].chave == _chave(2)
    assert gate.ganhos[0].baseline_exact_match is False
    assert gate.ganhos[0].candidato_exact_match is False
    assert gate.ganhos[0].baseline_principal_correta is False
    assert gate.ganhos[0].candidato_principal_correta is True


def test_calcular_avaliacao_normaliza_espacos_predicao_e_trunca_justificativa_curta() -> None:
    agora = datetime(2026, 11, 20, 21, 25, tzinfo=UTC)
    ouro = ConjuntoOuro(
        "1.0",
        "enade-ec",
        agora,
        (
            ItemConjuntoOuro(chave=_chave(1), disciplina_principal="alg", disciplinas_secundarias=("so",)),
            ItemConjuntoOuro(chave=_chave(2), disciplina_principal="redes"),
        ),
    )
    preds = (
        PredicaoClassificacao(
            chave=_chave(1),
            conclusao_valida=True,
            disciplina_principal="  alg  ",
            disciplinas_secundarias=("  so ", "  "),
            justificativa="Texto ok.",
            confianca=0.95,
        ),
        PredicaoClassificacao(
            chave=_chave(2),
            conclusao_valida=True,
            disciplina_principal="alg",
            justificativa="ABCDEF",
            confianca=0.90,
        ),
    )

    av_len_2 = calcular_avaliacao_classificacao(
        ouro,
        preds,
        perfil_codigo="v2",
        perfil_versao="1.0",
        modelo_identidade="m",
        executado_em=agora,
        max_chars_justificativa=2,
    )
    assert av_len_2.camada1.acuracia_principal == pytest.approx(0.5)
    assert av_len_2.camada1.exact_match == pytest.approx(0.5)
    assert av_len_2.camada2.divergencias[0].trecho_justificativa == "AB"

    av_len_0 = calcular_avaliacao_classificacao(
        ouro,
        preds,
        perfil_codigo="v2",
        perfil_versao="1.0",
        modelo_identidade="m",
        executado_em=agora,
        max_chars_justificativa=0,
    )
    assert av_len_0.camada2.divergencias[0].trecho_justificativa == ""


@pytest.mark.parametrize(
    ("kwargs_invalidos",),
    [
        ({"disciplinas_secundarias": "so"},),
        ({"disciplinas_secundarias": b"so"},),
        ({"disciplinas_secundarias": bytearray(b"so")},),
        ({"disciplinas_secundarias": {"so": 1}},),
        ({"disciplinas_secundarias": 123},),
        ({"disciplinas_secundarias": [123]},),
        ({"latencia_ms": float("nan")},),
        ({"latencia_ms": float("inf")},),
        ({"latencia_ms": float("-inf")},),
        ({"latencia_ms": True},),
        ({"latencia_ms": -0.1},),
        ({"prompt_tokens": True},),
        ({"prompt_tokens": False},),
        ({"prompt_tokens": -1},),
        ({"completion_tokens": True},),
        ({"completion_tokens": False},),
        ({"completion_tokens": -1},),
    ],
)
def test_predicao_classificacao_rejeita_secundarias_latencia_e_tokens_invalidos(
    kwargs_invalidos: dict[str, object],
) -> None:
    base_kwargs: dict[str, object] = {
        "chave": _chave(1),
        "conclusao_valida": True,
        "disciplina_principal": "alg",
        "confianca": 0.9,
    }
    base_kwargs.update(kwargs_invalidos)
    with pytest.raises(ErroValidacaoDominio):
        PredicaoClassificacao(**base_kwargs)  # type: ignore[arg-type]
