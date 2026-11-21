from __future__ import annotations

from uuid import uuid4

import pytest

from domain.classificacao import Classificacao
from domain.enums import OrigemClassificacao, StatusClassificacao
from domain.exceptions import ErroValidacaoDominio
from domain.travas_classificacao import detectar_divergencia


def _classificacao(
    principal: str,
    secundarias: tuple[str, ...] = (),
    topicos: tuple[str, ...] = ("grafos",),
    justificativa: str = "Justificativa A",
    confianca: float = 0.95,
) -> Classificacao:
    return Classificacao(
        questao_id=uuid4(),
        taxonomia_id=uuid4(),
        disciplina_principal=principal,
        disciplinas_secundarias=secundarias,
        topicos=topicos,
        justificativa=justificativa,
        confianca=confianca,
        origem=OrigemClassificacao.HUMANA,
        status=StatusClassificacao.APROVADA,
    )


def test_detectar_divergencia_ignora_ordem_secundarias_topicos_justificativa_e_confianca() -> None:
    vigente = _classificacao(
        "algoritmos",
        ("redes", "banco-de-dados"),
        topicos=("grafos", "dijkstra"),
        justificativa="Texto original.",
        confianca=0.98,
    )
    candidata = _classificacao(
        "algoritmos",
        ("banco-de-dados", "redes"),
        topicos=("roteamento",),
        justificativa="Justificativa totalmente diferente gerada pelo novo perfil.",
        confianca=0.71,
    )

    assert detectar_divergencia(vigente, candidata) is False


def test_detectar_divergencia_dispara_apenas_quando_muda_principal_ou_conjunto_secundarias() -> None:
    vigente = _classificacao("algoritmos", ("redes",))

    assert detectar_divergencia(vigente, _classificacao("estruturas-de-dados", ("redes",))) is True
    assert detectar_divergencia(vigente, _classificacao("algoritmos", ())) is True
    assert detectar_divergencia(vigente, _classificacao("algoritmos", ("redes", "banco-de-dados"))) is True
    assert detectar_divergencia(vigente, _classificacao("algoritmos", ("sistemas-operacionais",))) is True


def test_detectar_divergencia_trata_mapping_com_none_espacos_e_rejeita_tipos_invalidos() -> None:
    vigente = _classificacao("algoritmos", ())
    assert (
        detectar_divergencia(vigente, {"disciplina_principal": "algoritmos", "disciplinas_secundarias": None}) is False
    )
    assert (
        detectar_divergencia(
            _classificacao("algoritmos", ("redes",)),
            {"disciplina_principal": "  algoritmos ", "disciplinas_secundarias": ["  ", " redes "]},
        )
        is False
    )

    for entrada_invalida in (
        {"disciplina_principal": "algoritmos", "disciplinas_secundarias": "redes"},
        {"disciplina_principal": "algoritmos", "disciplinas_secundarias": b"redes"},
        {"disciplina_principal": "algoritmos", "disciplinas_secundarias": bytearray(b"redes")},
        {"disciplina_principal": "algoritmos", "disciplinas_secundarias": {"redes": 1}},
        {"disciplina_principal": "algoritmos", "disciplinas_secundarias": 123},
        {"disciplina_principal": "algoritmos", "disciplinas_secundarias": [123]},
    ):
        with pytest.raises(ErroValidacaoDominio):
            detectar_divergencia(vigente, entrada_invalida)
