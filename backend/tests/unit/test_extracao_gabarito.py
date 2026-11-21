"""Testes unitários do adaptador ``ExtratorGabaritoPdfPlumber`` e parser de tabelas."""

from __future__ import annotations

from pathlib import Path

import pytest

from application.ports.extracao import ExtratorGabarito
from domain.enums import LetraAlternativa, SituacaoGabarito, TipoQuestao
from domain.exceptions import ErroValidacaoDominio
from domain.prova import Gabarito
from infrastructure.extracao.gabarito import (
    ExtratorGabaritoPdfPlumber,
    parsear_linhas_gabarito,
)


def test_parsear_linhas_gabarito_suporta_tres_formatos_inep() -> None:
    linhas_2023 = [
        ["", "Item", "", "Gabarito", ""],
        ["", "QUESTÃO DISCURSIVA 1", "***", None, None],
        ["", "QUESTÃO DISCURSIVA 2", "***", None, None],
        ["", "QUESTÃO 1", "D", None, None],
        ["", "QUESTÃO 2", "ANULADA", None, None],
        ["", "QUESTÃO 38", "a", None, None],
    ]
    res_2023 = parsear_linhas_gabarito(linhas_2023)
    assert len(res_2023.itens) == 5
    assert res_2023.itens[0].tipo == TipoQuestao.DISCURSIVA
    assert res_2023.itens[0].gabarito == Gabarito(SituacaoGabarito.PENDENTE)
    assert res_2023.itens[1].numero == 2 and res_2023.itens[1].tipo == TipoQuestao.DISCURSIVA
    assert res_2023.mapa_objetivas() == {
        1: Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.D),
        2: Gabarito(SituacaoGabarito.ANULADA),
        38: Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.A),
    }

    linhas_2017 = [
        ["ITEM", None, "GABARITO", None],
        ["1", None, "C", None],
        ["35", None, "E", None],
    ]
    res_2017 = parsear_linhas_gabarito(linhas_2017)
    assert res_2017.mapa_objetivas() == {
        1: Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.C),
        35: Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.E),
    }


def test_parsear_linhas_gabarito_deduplica_identicos_e_rejeita_conflitos_ou_vazio() -> None:
    linhas_dup = [
        ["ITEM", "GABARITO"],
        ["1", "B"],
        ["1", "B"],
    ]
    assert parsear_linhas_gabarito(linhas_dup).mapa_objetivas() == {
        1: Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa.B),
    }

    with pytest.raises(ErroValidacaoDominio, match="conflitante"):
        parsear_linhas_gabarito([["1", "A"], ["1", "B"]])

    with pytest.raises(ErroValidacaoDominio, match="Nenhum item válido"):
        parsear_linhas_gabarito([["ITEM", "GABARITO"], ["CURSO", "ENGENHARIA"]])


def test_extrator_gabarito_protocolo_e_erros(tmp_path: Path) -> None:
    extrator = ExtratorGabaritoPdfPlumber()
    assert isinstance(extrator, ExtratorGabarito)

    with pytest.raises(FileNotFoundError):
        extrator.extrair(tmp_path / "nao_existe.pdf")

    arquivo_invalido = tmp_path / "invalido.pdf"
    arquivo_invalido.write_bytes(b"nao e um pdf")
    with pytest.raises(ErroValidacaoDominio):
        extrator.extrair(arquivo_invalido)
