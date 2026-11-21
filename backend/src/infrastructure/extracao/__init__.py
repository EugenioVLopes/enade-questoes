"""Adaptadores concretos de extração documental (Docling, pdfplumber, pypdfium2)."""

from infrastructure.extracao.extrator_prova import ExtratorProvaDocling
from infrastructure.extracao.gabarito import ExtratorGabaritoPdfPlumber
from infrastructure.extracao.renderizador import RenderizadorPaginaPdfPypdfium2

__all__ = [
    "ExtratorGabaritoPdfPlumber",
    "ExtratorProvaDocling",
    "RenderizadorPaginaPdfPypdfium2",
]
