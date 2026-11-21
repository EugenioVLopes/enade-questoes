"""Inspeção determinística leve de PDF (CMap ToUnicode corrompido e fontes Symbol/MT-Extra)."""

from __future__ import annotations

import ctypes
import re
from pathlib import Path

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from domain.exceptions import ErroValidacaoDominio

_CID_TOKEN_RE = re.compile(r"\(cid:\d+\)")
_FONT_SYMBOL_RE = re.compile(r"(?:symbol|mt-?extra|mtextra)", re.IGNORECASE)

_MIN_CHARS_PAGINA = 30
_LIMIAR_RAZAO_MOJIBAKE = 0.05


def _caractere_mojibake(ch: str) -> bool:
    code = ord(ch)
    if code < 0x20 and ch not in "\r\n\t":
        return True
    if 0x0100 <= code <= 0x024F:
        return True
    if 0x0370 <= code <= 0x08FF:
        return True
    return ch == "\ufffd"


def texto_indica_cmap_corrompido(texto: str) -> bool:
    """Detecta mojibake típico de ToUnicode CMap corrompido em uma página."""
    if not texto:
        return False
    cid_tokens = _CID_TOKEN_RE.findall(texto)
    if len(cid_tokens) >= 3:
        return True

    chars = [ch for ch in texto if not ch.isspace()]
    if len(chars) < _MIN_CHARS_PAGINA:
        return False

    suspeitos = sum(1 for ch in chars if _caractere_mojibake(ch))
    return (suspeitos / len(chars)) > _LIMIAR_RAZAO_MOJIBAKE


def nome_fonte_indica_symbol(nome_fonte: str) -> bool:
    """Retorna True se o nome da fonte PDF corresponde a Symbol, EuclidSymbol ou MT-Extra."""
    return bool(nome_fonte and _FONT_SYMBOL_RE.search(nome_fonte))


def detectar_cmap_corrompido(caminho_pdf: Path) -> bool:
    """Verifica se o PDF apresenta camada textual com ToUnicode CMap corrompido."""
    caminho = Path(caminho_pdf)
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {caminho}")

    try:
        doc = pdfium.PdfDocument(str(caminho))
    except Exception as err:
        raise ErroValidacaoDominio(f"Não foi possível abrir o PDF '{caminho}': {err}") from err

    try:
        paginas_com_texto = 0
        paginas_corrompidas = 0
        for idx in range(len(doc)):
            page = doc[idx]
            textpage = page.get_textpage()
            try:
                texto = textpage.get_text_range()
            finally:
                textpage.close()
                page.close()

            chars_visiveis = sum(1 for ch in texto if not ch.isspace())
            if chars_visiveis >= _MIN_CHARS_PAGINA or "(cid:" in texto:
                paginas_com_texto += 1
                if texto_indica_cmap_corrompido(texto):
                    paginas_corrompidas += 1

        if paginas_com_texto == 0:
            return False
        return paginas_corrompidas >= 2 or (paginas_corrompidas / paginas_com_texto) >= 0.5
    finally:
        doc.close()


def detectar_paginas_fonte_symbol(caminho_pdf: Path) -> tuple[int, ...]:
    """Retorna páginas 1-based que utilizam fonte Symbol, EuclidSymbol ou MT-Extra."""
    caminho = Path(caminho_pdf)
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {caminho}")

    try:
        doc = pdfium.PdfDocument(str(caminho))
    except Exception as err:
        raise ErroValidacaoDominio(f"Não foi possível abrir o PDF '{caminho}': {err}") from err

    paginas_symbol: list[int] = []
    buf_len = 512
    buf = ctypes.create_string_buffer(buf_len)
    flags = ctypes.c_int()

    try:
        for idx in range(len(doc)):
            page = doc[idx]
            textpage = page.get_textpage()
            try:
                total_chars = textpage.count_chars()
                encontrou = False
                for char_idx in range(total_chars):
                    tam = pdfium_c.FPDFText_GetFontInfo(textpage, char_idx, buf, buf_len, ctypes.byref(flags))
                    if tam > 0:
                        if tam > buf_len:
                            maior = ctypes.create_string_buffer(tam)
                            pdfium_c.FPDFText_GetFontInfo(textpage, char_idx, maior, tam, ctypes.byref(flags))
                            nome_fonte = maior.value.decode("utf-8", errors="ignore")
                        else:
                            nome_fonte = buf.value.decode("utf-8", errors="ignore")
                        if nome_fonte_indica_symbol(nome_fonte):
                            encontrou = True
                            break
                if encontrou:
                    paginas_symbol.append(idx + 1)
            finally:
                textpage.close()
                page.close()
        return tuple(paginas_symbol)
    finally:
        doc.close()
