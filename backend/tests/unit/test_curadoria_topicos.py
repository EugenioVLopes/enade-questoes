"""Curadoria de Tópicos: normalização e substituição por correção."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from domain.classificacao import Classificacao, normalizar_topicos_curadoria
from domain.enums import OrigemClassificacao, StatusClassificacao
from domain.exceptions import ErroValidacaoDominio


def test_normalizar_topicos_curadoria_levanta_quando_topico_normaliza_para_vazio() -> None:
    assert normalizar_topicos_curadoria(["Escalonamento de Processos", "escalonamento-de-processos"]) == (
        "escalonamento-de-processos",
    )
    for invalido in ("!!!", "   ", "---"):
        with pytest.raises(ErroValidacaoDominio):
            normalizar_topicos_curadoria(["valido", invalido])


def test_substituir_por_correcao_com_topico_vazio_nao_torna_a_anterior_nao_vigente() -> None:
    anterior = Classificacao(
        questao_id=uuid4(),
        taxonomia_id=uuid4(),
        disciplina_principal="redes",
        topicos=("roteamento",),
        justificativa="IA.",
        confianca=0.5,
        origem=OrigemClassificacao.AUTOMATICA,
        status=StatusClassificacao.PENDENTE_REVISAO,
        vigente=True,
    )
    with pytest.raises(ErroValidacaoDominio):
        anterior.substituir_por_correcao(
            disciplina_principal="redes",
            topicos=["!!!"],
            justificativa="Ajuste.",
            agora=datetime(2026, 11, 22, tzinfo=UTC),
        )
    assert anterior.vigente is True
