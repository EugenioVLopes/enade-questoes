"""Worker isolado em subprocesso para execução do Docling sem reter PyTorch em RAM."""

from __future__ import annotations

import argparse
from pathlib import Path


def executar_conversao_docling(
    caminho_pdf: Path,
    caminho_saida_json: Path,
    *,
    usar_ocr: bool = False,
    images_scale: float = 2.0,
) -> None:
    """Executa ``DocumentConverter`` (PyPdfiumDocumentBackend) e grava ``DoclingDocument`` JSON."""
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pipeline_options = PdfPipelineOptions(
        do_ocr=usar_ocr,
        do_table_structure=True,
        generate_picture_images=True,
        images_scale=images_scale,
        do_code_enrichment=False,
        do_formula_enrichment=False,
    )
    if usar_ocr:
        pipeline_options.ocr_options = RapidOcrOptions(force_full_page_ocr=True)

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
                backend=PyPdfiumDocumentBackend,
            )
        }
    )
    resultado = converter.convert(caminho_pdf)
    caminho_saida_json.parent.mkdir(parents=True, exist_ok=True)
    caminho_saida_json.write_text(resultado.document.model_dump_json(), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Subprocesso isolado Docling para Enade Questões.")
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--out-doc-json", required=True, type=Path)
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--images-scale", type=float, default=2.0)
    args = parser.parse_args(argv)

    executar_conversao_docling(
        args.pdf,
        args.out_doc_json,
        usar_ocr=args.ocr,
        images_scale=args.images_scale,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
