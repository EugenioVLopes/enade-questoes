"""Adaptador de extração de gabaritos oficiais do INEP via pdfplumber."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pdfplumber

from application.ports.extracao import ItemGabaritoExtraido, ResultadoExtracaoGabarito
from domain.enums import LetraAlternativa, SituacaoGabarito, TipoQuestao
from domain.exceptions import ErroValidacaoDominio
from domain.prova import Gabarito

_WHITESPACE_RE = re.compile(r"\s+")
_DISCURSIVA_RE = re.compile(r"^QUEST[ÃA]O\s+DISCURSIVA\s+0*(\d+)$", re.IGNORECASE)
_OBJETIVA_RE = re.compile(r"^(?:QUEST[ÃA]O\s+)?0*(\d+)$", re.IGNORECASE)
_HEADER_LABELS = frozenset({"ITEM", "QUESTÃO", "QUESTAO", "GABARITO"})
_LETRAS_VALIDAS = frozenset({"A", "B", "C", "D", "E"})


def _normalizar_celula(valor: Any) -> str:
    return _WHITESPACE_RE.sub(" ", str(valor)).strip()


def _interpretar_valor_objetiva(val: str) -> Gabarito | None:
    if "ANUL" in val:
        return Gabarito(SituacaoGabarito.ANULADA)
    if val in _LETRAS_VALIDAS:
        return Gabarito(SituacaoGabarito.VALIDA, LetraAlternativa(val))
    if val in {"***", "-", "PENDENTE"}:
        return Gabarito(SituacaoGabarito.PENDENTE)
    return None


def _interpretar_valor_discursiva(val: str) -> Gabarito | None:
    if "ANUL" in val:
        return Gabarito(SituacaoGabarito.ANULADA)
    if val in {"***", "-", "PENDENTE", "DISCURSIVA"} or "*" in val:
        return Gabarito(SituacaoGabarito.PENDENTE)
    return None


def parsear_linhas_gabarito(rows: Sequence[Sequence[Any]]) -> ResultadoExtracaoGabarito:
    """Normaliza linhas extraídas de tabelas do INEP nos 3 formatos oficiais."""
    itens: list[ItemGabaritoExtraido] = []
    vistos: dict[tuple[TipoQuestao, int], ItemGabaritoExtraido] = {}

    for row in rows:
        cells = [_normalizar_celula(c) for c in row if c is not None and _normalizar_celula(c)]
        if len(cells) < 2:
            continue

        label, val = cells[0], cells[-1].upper()
        if label.upper() in _HEADER_LABELS or val == "GABARITO":
            continue

        m_disc = _DISCURSIVA_RE.match(label)
        if m_disc:
            numero = int(m_disc.group(1))
            if numero < 1:
                continue
            gabarito = _interpretar_valor_discursiva(val)
            if gabarito is None:
                continue
            item = ItemGabaritoExtraido(
                numero=numero,
                tipo=TipoQuestao.DISCURSIVA,
                gabarito=gabarito,
                rotulo=label,
            )
            chave = (TipoQuestao.DISCURSIVA, numero)
            if chave in vistos:
                if vistos[chave].gabarito != item.gabarito:
                    raise ErroValidacaoDominio(
                        f"Gabarito conflitante para questão discursiva {numero}: "
                        f"{vistos[chave].gabarito!r} vs {item.gabarito!r}."
                    )
                continue
            vistos[chave] = item
            itens.append(item)
            continue

        m_obj = _OBJETIVA_RE.match(label)
        if m_obj:
            numero = int(m_obj.group(1))
            if numero < 1:
                continue
            gabarito = _interpretar_valor_objetiva(val)
            if gabarito is None:
                continue
            item = ItemGabaritoExtraido(
                numero=numero,
                tipo=TipoQuestao.OBJETIVA,
                gabarito=gabarito,
                rotulo=label,
            )
            chave = (TipoQuestao.OBJETIVA, numero)
            if chave in vistos:
                if vistos[chave].gabarito != item.gabarito:
                    raise ErroValidacaoDominio(
                        f"Gabarito conflitante para questão objetiva {numero}: "
                        f"{vistos[chave].gabarito!r} vs {item.gabarito!r}."
                    )
                continue
            vistos[chave] = item
            itens.append(item)

    if not itens:
        raise ErroValidacaoDominio("Nenhum item válido de gabarito encontrado nas tabelas do PDF.")

    return ResultadoExtracaoGabarito(itens=tuple(itens))


class ExtratorGabaritoPdfPlumber:
    """Implementação de ``ExtratorGabarito`` usando ``pdfplumber``."""

    def extrair(self, caminho_pdf: Path) -> ResultadoExtracaoGabarito:
        caminho = Path(caminho_pdf)
        if not caminho.is_file():
            raise FileNotFoundError(f"Arquivo de gabarito não encontrado: {caminho}")

        logging.getLogger("pdfminer").setLevel(logging.ERROR)
        raw_rows: list[list[Any]] = []
        try:
            with pdfplumber.open(caminho) as pdf:
                for page in pdf.pages:
                    for table in page.extract_tables() or []:
                        raw_rows.extend(table)
        except ErroValidacaoDominio:
            raise
        except Exception as err:
            raise ErroValidacaoDominio(f"Falha ao ler PDF de gabarito '{caminho}': {err}") from err

        return parsear_linhas_gabarito(raw_rows)
