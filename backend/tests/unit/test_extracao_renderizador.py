"""Testes unitários do adaptador ``RenderizadorPaginaPdfPypdfium2`` e recorte de bbox."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pypdfium2 as pdfium
import pytest
from PIL import Image

from application.ports.extracao import RenderizadorPaginaPdf
from domain.exceptions import ErroValidacaoDominio
from domain.prova import BoundingBox
from infrastructure.extracao.renderizador import (
    RenderizadorPaginaPdfPypdfium2,
    recortar_bbox_pdf_para_png,
)


def _criar_pdf_sintetico(caminho: Path, paginas: int = 2) -> Path:
    pdf = pdfium.PdfDocument.new()
    try:
        for idx in range(paginas):
            img = Image.new("RGB", (300, 400), (200 - idx * 50, 220, 240))
            pdf_img = pdfium.PdfImage.new(pdf)
            pdf_img.set_bitmap(pdfium.PdfBitmap.from_pil(img))
            pdf_img.set_matrix(pdfium.PdfMatrix().scale(300, 400))
            page = pdf.new_page(300, 400)
            page.insert_obj(pdf_img)
            page.gen_content()
            page.close()
        pdf.save(str(caminho))
    finally:
        pdf.close()
    return caminho


def test_renderizador_conta_paginas_renderiza_png_e_recorta_bbox(tmp_path: Path) -> None:
    pdf_path = _criar_pdf_sintetico(tmp_path / "sintetico.pdf", paginas=2)
    renderizador = RenderizadorPaginaPdfPypdfium2()
    assert isinstance(renderizador, RenderizadorPaginaPdf)

    assert renderizador.contar_paginas(pdf_path) == 2

    png_bytes = renderizador.renderizar_pagina(pdf_path, pagina=1, dpi=144)
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    with Image.open(BytesIO(png_bytes)) as img:
        assert img.mode == "RGB"
        assert img.size == (600, 800)

    recorte_bytes = recortar_bbox_pdf_para_png(
        pdf_path,
        pagina=2,
        bbox=BoundingBox(50.0, 100.0, 150.0, 200.0),
        dpi=144,
        margem_pt=0.0,
    )
    with Image.open(BytesIO(recorte_bytes)) as crop:
        assert crop.mode == "RGB"
        assert crop.size == (200, 200)


@pytest.mark.parametrize("pagina_invalida", [0, -1, 3, True, False])
def test_renderizador_rejeita_pagina_invalida(tmp_path: Path, pagina_invalida: int) -> None:
    pdf_path = _criar_pdf_sintetico(tmp_path / "sintetico.pdf", paginas=2)
    renderizador = RenderizadorPaginaPdfPypdfium2()

    with pytest.raises(ErroValidacaoDominio):
        renderizador.renderizar_pagina(pdf_path, pagina=pagina_invalida)


@pytest.mark.parametrize("dpi_invalido", [0, -72, 601, True, False])
def test_renderizador_rejeita_dpi_invalido(tmp_path: Path, dpi_invalido: int) -> None:
    pdf_path = _criar_pdf_sintetico(tmp_path / "sintetico.pdf", paginas=1)
    renderizador = RenderizadorPaginaPdfPypdfium2()

    with pytest.raises(ErroValidacaoDominio):
        renderizador.renderizar_pagina(pdf_path, pagina=1, dpi=dpi_invalido)


def test_renderizador_arquivo_inexistente_ou_corrompido(tmp_path: Path) -> None:
    renderizador = RenderizadorPaginaPdfPypdfium2()

    with pytest.raises(FileNotFoundError):
        renderizador.contar_paginas(tmp_path / "inexistente.pdf")
    with pytest.raises(FileNotFoundError):
        renderizador.renderizar_pagina(tmp_path / "inexistente.pdf", pagina=1)

    invalido = tmp_path / "corrompido.pdf"
    invalido.write_bytes(b"corrompido")
    with pytest.raises(ErroValidacaoDominio):
        renderizador.contar_paginas(invalido)
