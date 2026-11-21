"""Adaptador de renderização sob demanda e recorte de páginas PDF via pypdfium2."""

from __future__ import annotations

import math
from collections.abc import Iterable
from io import BytesIO
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from domain.exceptions import ErroValidacaoDominio
from domain.prova import BoundingBox

_DPI_MINIMO = 1
_DPI_MAXIMO = 600


def _validar_pagina(pagina: int, total_paginas: int | None = None) -> int:
    if isinstance(pagina, bool) or not isinstance(pagina, int) or pagina < 1:
        raise ErroValidacaoDominio(f"'pagina' deve ser inteiro >= 1; recebido: {pagina!r}.")
    if total_paginas is not None and pagina > total_paginas:
        raise ErroValidacaoDominio(f"Página {pagina} fora do intervalo válido (1..{total_paginas}).")
    return pagina


def _validar_dpi(dpi: int) -> int:
    if isinstance(dpi, bool) or not isinstance(dpi, int) or dpi < _DPI_MINIMO or dpi > _DPI_MAXIMO:
        raise ErroValidacaoDominio(f"'dpi' deve ser inteiro entre {_DPI_MINIMO} e {_DPI_MAXIMO}; recebido: {dpi!r}.")
    return dpi


def _abrir_pdf(caminho_pdf: Path) -> pdfium.PdfDocument:
    caminho = Path(caminho_pdf)
    if not caminho.is_file():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {caminho}")
    try:
        return pdfium.PdfDocument(str(caminho))
    except Exception as err:
        raise ErroValidacaoDominio(f"Não foi possível abrir o PDF '{caminho}': {err}") from err


def _renderizar_pagina_pil(doc: pdfium.PdfDocument, pagina: int, dpi: int) -> tuple[Image.Image, float, float]:
    page = doc[pagina - 1]
    try:
        page_w, page_h = page.get_size()
        bitmap = page.render(scale=dpi / 72.0)
        try:
            pil_img = bitmap.to_pil().convert("RGB")
        finally:
            bitmap.close()
        return pil_img, float(page_w), float(page_h)
    finally:
        page.close()


def _pil_para_png_bytes(imagem: Image.Image) -> bytes:
    buf = BytesIO()
    imagem.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def recortar_bbox_pdf_para_png(
    caminho_pdf: Path,
    pagina: int,
    bbox: BoundingBox,
    *,
    dpi: int = 144,
    margem_pt: float = 4.0,
) -> bytes:
    """Recorta uma região ``BoundingBox`` (origem top-left em pontos PDF) como PNG RGB."""
    _validar_pagina(pagina)
    _validar_dpi(dpi)
    resultados = recortar_lote_bboxes_pdf_para_png(
        caminho_pdf,
        [(pagina, bbox)],
        dpi=dpi,
        margem_pt=margem_pt,
    )
    return resultados[0]


def recortar_lote_bboxes_pdf_para_png(
    caminho_pdf: Path,
    regioes: Iterable[tuple[int, BoundingBox]],
    *,
    dpi: int = 144,
    margem_pt: float = 4.0,
) -> list[bytes]:
    """Recorta várias regiões (pagina, bbox) reutilizando páginas renderizadas no mesmo PDF."""
    _validar_dpi(dpi)
    lista_regioes = list(regioes)
    if not lista_regioes:
        return []

    doc = _abrir_pdf(caminho_pdf)
    try:
        total = len(doc)
        cache_paginas: dict[int, tuple[Image.Image, float, float]] = {}
        recortes: list[bytes] = []
        for pagina, bbox in lista_regioes:
            _validar_pagina(pagina, total)
            if pagina not in cache_paginas:
                cache_paginas[pagina] = _renderizar_pagina_pil(doc, pagina, dpi)
            pil_img, page_w, page_h = cache_paginas[pagina]
            img_w, img_h = pil_img.size

            x0_pt = max(0.0, min(page_w, bbox.x0 - margem_pt))
            y0_pt = max(0.0, min(page_h, bbox.y0 - margem_pt))
            x1_pt = max(0.0, min(page_w, bbox.x1 + margem_pt))
            y1_pt = max(0.0, min(page_h, bbox.y1 + margem_pt))

            px0 = max(0, min(img_w - 1, int(math.floor((x0_pt / page_w) * img_w))))
            py0 = max(0, min(img_h - 1, int(math.floor((y0_pt / page_h) * img_h))))
            px1 = max(px0 + 1, min(img_w, int(math.ceil((x1_pt / page_w) * img_w))))
            py1 = max(py0 + 1, min(img_h, int(math.ceil((y1_pt / page_h) * img_h))))

            crop = pil_img.crop((px0, py0, px1, py1))
            recortes.append(_pil_para_png_bytes(crop))
        return recortes
    finally:
        doc.close()


class RenderizadorPaginaPdfPypdfium2:
    """Implementação de ``RenderizadorPaginaPdf`` usando ``pypdfium2`` e ``Pillow``."""

    def contar_paginas(self, caminho_pdf: Path) -> int:
        doc = _abrir_pdf(caminho_pdf)
        try:
            return len(doc)
        finally:
            doc.close()

    def renderizar_pagina(self, caminho_pdf: Path, pagina: int, dpi: int = 150) -> bytes:
        _validar_pagina(pagina)
        _validar_dpi(dpi)
        doc = _abrir_pdf(caminho_pdf)
        try:
            total = len(doc)
            _validar_pagina(pagina, total)
            pil_img, _, _ = _renderizar_pagina_pil(doc, pagina, dpi)
            return _pil_para_png_bytes(pil_img)
        finally:
            doc.close()
