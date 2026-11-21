from __future__ import annotations

import pytest

from domain.exceptions import ErroValidacaoDominio, FaixaQuestoesIndisponivelError
from domain.faixas_enade import resolver_faixa_componente_especifico
from domain.prova import FaixaQuestoes


@pytest.mark.parametrize(
    ("ano", "esperado"),
    [
        (2014, FaixaQuestoes(9, 35)),
        (2017, FaixaQuestoes(9, 35)),
        (2019, FaixaQuestoes(9, 35)),
        (2023, FaixaQuestoes(10, 38)),
        (2026, FaixaQuestoes(16, 45)),
        (2027, FaixaQuestoes(16, 45)),
    ],
)
def test_resolver_faixa_componente_especifico_por_edicao(ano: int, esperado: FaixaQuestoes) -> None:
    assert resolver_faixa_componente_especifico(ano) == esperado


def test_resolver_faixa_aceita_override_explicito() -> None:
    assert resolver_faixa_componente_especifico(2021, questao_inicio=11, questao_fim=39) == FaixaQuestoes(11, 39)
    assert resolver_faixa_componente_especifico(2023, questao_inicio=1, questao_fim=30) == FaixaQuestoes(1, 30)


def test_resolver_faixa_rejeita_override_parcial() -> None:
    with pytest.raises(ErroValidacaoDominio):
        resolver_faixa_componente_especifico(2023, questao_inicio=10, questao_fim=None)
    with pytest.raises(ErroValidacaoDominio):
        resolver_faixa_componente_especifico(2023, questao_inicio=None, questao_fim=38)


@pytest.mark.parametrize("ano", [2011, 2020, 2021, 2022, 2024, 2025])
def test_resolver_faixa_ano_desconhecido_sem_override_lanca_erro_especifico(ano: int) -> None:
    with pytest.raises(FaixaQuestoesIndisponivelError):
        resolver_faixa_componente_especifico(ano)


@pytest.mark.parametrize("ano_invalido", [1899, -500, True])
def test_resolver_faixa_rejeita_ano_invalido_consistente_com_prova(ano_invalido: int) -> None:
    with pytest.raises(ErroValidacaoDominio):
        resolver_faixa_componente_especifico(ano_invalido, questao_inicio=1, questao_fim=10)
