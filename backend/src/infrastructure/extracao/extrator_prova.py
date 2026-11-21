"""Adaptador ``ExtratorProvaDocling`` executando Docling em subprocesso isolado."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from io import BytesIO
from pathlib import Path

from docling_core.types.doc import (
    CodeItem,
    DoclingDocument,
    FormulaItem,
    ListItem,
    PictureItem,
    SectionHeaderItem,
    TableItem,
    TextItem,
)

from application.ports.extracao import ResultadoExtracaoProva
from domain.exceptions import ErroValidacaoDominio
from domain.prova import BoundingBox, FaixaQuestoes
from infrastructure.extracao.inspecao_pdf import (
    detectar_cmap_corrompido,
    detectar_paginas_fonte_symbol,
)
from infrastructure.extracao.posprocessamento import (
    ElementoDocling,
    posprocessar_elementos,
)
from infrastructure.extracao.renderizador import recortar_lote_bboxes_pdf_para_png

_SRC_ROOT = Path(__file__).resolve().parents[2]


def _converter_bbox_para_top_left(
    bbox_docling: object,
    page_width: float,
    page_height: float,
) -> BoundingBox | None:
    if bbox_docling is None or page_height <= 0:
        return None
    tl = bbox_docling.to_top_left_origin(page_height)  # type: ignore[attr-defined]
    x0 = max(0.0, float(tl.l))
    y0 = max(0.0, float(tl.t))
    x1 = min(page_width, float(tl.r)) if page_width > 0 else float(tl.r)
    y1 = min(page_height, float(tl.b))
    if x1 <= x0 or y1 <= y0:
        return None
    return BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)


def docling_document_para_elementos(doc: DoclingDocument) -> list[ElementoDocling]:
    """Converte um ``DoclingDocument`` na sequência linear de ``ElementoDocling``."""
    elementos: list[ElementoDocling] = []
    for item, _level in doc.iterate_items():
        prov = item.prov[0] if getattr(item, "prov", None) else None
        pagina = int(prov.page_no) if prov is not None and prov.page_no >= 1 else 1
        page_info = doc.pages.get(pagina)
        page_w = float(page_info.size.width) if page_info is not None else 0.0
        page_h = float(page_info.size.height) if page_info is not None else 0.0
        bbox = _converter_bbox_para_top_left(prov.bbox if prov is not None else None, page_w, page_h)

        if isinstance(item, SectionHeaderItem):
            elementos.append(
                ElementoDocling(
                    tipo="section_header",
                    texto=item.text,
                    pagina=pagina,
                    bbox=bbox,
                    page_width=page_w,
                    page_height=page_h,
                )
            )
        elif isinstance(item, ListItem):
            elementos.append(
                ElementoDocling(
                    tipo="list_item",
                    texto=item.text,
                    pagina=pagina,
                    bbox=bbox,
                    page_width=page_w,
                    page_height=page_h,
                    marker=getattr(item, "marker", "") or "",
                    enumerated=bool(getattr(item, "enumerated", False)),
                )
            )
        elif isinstance(item, CodeItem):
            elementos.append(
                ElementoDocling(
                    tipo="code",
                    texto=item.text,
                    pagina=pagina,
                    bbox=bbox,
                    page_width=page_w,
                    page_height=page_h,
                )
            )
        elif isinstance(item, TableItem):
            elementos.append(
                ElementoDocling(
                    tipo="table",
                    texto=item.export_to_markdown(doc),
                    pagina=pagina,
                    bbox=bbox,
                    page_width=page_w,
                    page_height=page_h,
                )
            )
        elif isinstance(item, FormulaItem):
            elementos.append(
                ElementoDocling(
                    tipo="formula",
                    texto=item.text or "",
                    pagina=pagina,
                    bbox=bbox,
                    page_width=page_w,
                    page_height=page_h,
                )
            )
        elif isinstance(item, PictureItem):
            pil_img = item.get_image(doc)
            png_bytes: bytes | None = None
            img_w = 0
            img_h = 0
            if pil_img is not None:
                img_w, img_h = pil_img.size
                buf = BytesIO()
                pil_img.convert("RGB").save(buf, format="PNG", optimize=True)
                png_bytes = buf.getvalue()
            elementos.append(
                ElementoDocling(
                    tipo="picture",
                    pagina=pagina,
                    bbox=bbox,
                    page_width=page_w,
                    page_height=page_h,
                    imagem_png=png_bytes,
                    img_width_px=img_w,
                    img_height_px=img_h,
                )
            )
        elif isinstance(item, TextItem):
            elementos.append(
                ElementoDocling(
                    tipo="text",
                    texto=item.text,
                    pagina=pagina,
                    bbox=bbox,
                    page_width=page_w,
                    page_height=page_h,
                )
            )
    return elementos


class ExtratorProvaDocling:
    """Implementação de ``ExtratorProva`` com Docling em subprocesso isolado."""

    def __init__(self, *, timeout_s: float = 600.0, images_scale: float = 2.0) -> None:
        if timeout_s <= 0:
            raise ErroValidacaoDominio(f"'timeout_s' deve ser > 0; recebido: {timeout_s!r}.")
        if images_scale <= 0:
            raise ErroValidacaoDominio(f"'images_scale' deve ser > 0; recebido: {images_scale!r}.")
        self._timeout_s = timeout_s
        self._images_scale = images_scale

    def extrair(self, caminho_pdf: Path, faixa_ce: FaixaQuestoes) -> ResultadoExtracaoProva:
        caminho = Path(caminho_pdf)
        if not caminho.is_file():
            raise FileNotFoundError(f"Arquivo de prova não encontrado: {caminho}")
        if not isinstance(faixa_ce, FaixaQuestoes):
            raise ErroValidacaoDominio(f"'faixa_ce' deve ser FaixaQuestoes; recebido: {faixa_ce!r}.")

        usou_ocr = detectar_cmap_corrompido(caminho)
        paginas_fonte_symbol = detectar_paginas_fonte_symbol(caminho)

        with tempfile.TemporaryDirectory(prefix="enade-docling-") as tmp_dir:
            doc_json_path = Path(tmp_dir) / "docling.json"
            self._executar_worker(caminho, doc_json_path, usar_ocr=usou_ocr)
            extracao_bruta_json = doc_json_path.read_text(encoding="utf-8")

        doc = DoclingDocument.model_validate_json(extracao_bruta_json)
        elementos = docling_document_para_elementos(doc)

        questoes, metadados = posprocessar_elementos(
            elementos,
            faixa_ce,
            recortar_formulas_fn=lambda regioes: recortar_lote_bboxes_pdf_para_png(caminho, regioes),
            usou_ocr=usou_ocr,
            paginas_fonte_symbol=paginas_fonte_symbol,
        )
        return ResultadoExtracaoProva(
            questoes=questoes,
            extracao_bruta_json=extracao_bruta_json,
            metadados=metadados,
        )

    def _executar_worker(self, caminho_pdf: Path, caminho_saida_json: Path, *, usar_ocr: bool) -> None:
        cmd = [
            sys.executable,
            "-m",
            "infrastructure.extracao._worker",
            "--pdf",
            str(caminho_pdf),
            "--out-doc-json",
            str(caminho_saida_json),
            "--images-scale",
            str(self._images_scale),
        ]
        if usar_ocr:
            cmd.append("--ocr")

        env = os.environ.copy()
        src_str = str(_SRC_ROOT)
        pythonpath_atual = env.get("PYTHONPATH", "")
        caminhos = [p for p in pythonpath_atual.split(os.pathsep) if p]
        if src_str not in caminhos:
            env["PYTHONPATH"] = os.pathsep.join([src_str, *caminhos]) if caminhos else src_str

        try:
            subprocess.run(  # noqa: S603
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=self._timeout_s,
                env=env,
            )
        except subprocess.TimeoutExpired as err:
            raise RuntimeError(
                f"Subprocesso Docling excedeu timeout de {self._timeout_s:.1f}s ao processar '{caminho_pdf}'."
            ) from err
        except subprocess.CalledProcessError as err:
            stderr = (err.stderr or "").strip()
            raise RuntimeError(
                f"Subprocesso Docling falhou (código {err.returncode}) ao processar '{caminho_pdf}': {stderr}"
            ) from err
