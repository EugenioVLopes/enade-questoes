#!/usr/bin/env python3
"""PROTOTYPE (descartável) — Ticket 05: Docling vs PyMuPDF 2.1 + pdfplumber em provas reais do ENADE.

Executa cada extrator em subprocesso isolado para medir tempo e pico de RAM (RSS) sem contaminação
entre PyTorch (Docling) e ONNX Runtime (PyMuPDF 2.1), e gera um relatório HTML autossuficiente em
data/prototype-05/comparacao-extracao.html para inspeção humana.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import resource
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_ENADE = ROOT / "data" / "enade"
OUT_DIR = ROOT / "data" / "prototype-05"

PROVA_2023 = DATA_ENADE / "2023" / "prova_enade_2023_engenharia_computacao.pdf"
GAB_2023 = DATA_ENADE / "2023" / "gabarito_enade_2023_engenharia_computacao.pdf"
PROVA_2019 = DATA_ENADE / "2019" / "prova_enade_2019_engenharia_computacao.pdf"
GAB_2019 = DATA_ENADE / "2019" / "gabarito_enade_2019_engenharia_computacao.pdf"
PROVA_2017 = DATA_ENADE / "2017" / "prova_enade_2017_engenharia_computacao.pdf"
GAB_2017 = DATA_ENADE / "2017" / "gabarito_enade_2017_engenharia_computacao.pdf"

# Páginas representativas (1-based) para A/B de enriquecimentos CodeFormulaV2 na prova 2023:
# p.14 = Q10 (fórmula/Symbol ρ + circuito), p.19 = Q15 (código), p.20 = Q16 (código),
# p.25 = Q22 (código + figura), p.26 = Q23 (diagrama/tabela)
ENRICHED_2023_PAGES = [14, 19, 20, 25, 26]

# Páginas de stress-test de 2019 (alternativas 2 colunas + figuras vetoriais + ÁREA LIVRE)
SPOT_2019_PAGES = [16, 22, 23, 24]

# Páginas de stress-test de 2017 (corpo em 2 colunas Q09-Q13 + ToUnicode corrompido)
SPOT_2017_PAGES = [17, 18]


def peak_rss_mb() -> float:
    """Retorna pico de memória RSS do processo atual em MB (Linux: ru_maxrss em KiB)."""
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 1)


def make_subset_pdf(src: Path, pages_1based: list[int], dst: Path) -> Path:
    import pymupdf

    dst.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(src) as doc:
        sub = pymupdf.open()
        for pno in pages_1based:
            sub.insert_pdf(doc, from_page=pno - 1, to_page=pno - 1)
        sub.save(dst)
        sub.close()
    return dst


def render_reference_pages(pdf_path: Path, pages_1based: list[int], out_dir: Path, prefix: str) -> dict[int, str]:
    import pypdfium2 as pdfium

    out_dir.mkdir(parents=True, exist_ok=True)
    rendered: dict[int, str] = {}
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        for pno in pages_1based:
            page = pdf[pno - 1]
            pil_img = page.render(scale=120 / 72).to_pil().convert("RGB")
            img_path = out_dir / f"{prefix}_p{pno:02d}.png"
            pil_img.save(img_path, format="PNG", optimize=True)
            rendered[pno] = str(img_path.relative_to(OUT_DIR))
    finally:
        pdf.close()
    return rendered


# ---------------------------------------------------------------------------
# STEP 1: Gabaritos (pdfplumber vs pymupdf) nas 3 edições reais
# ---------------------------------------------------------------------------

def parse_gabarito_rows(rows: list[list[Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in rows:
        cells = [re.sub(r"\s+", " ", str(c)).strip() for c in row if c is not None and str(c).strip()]
        if len(cells) < 2:
            continue
        label, val = cells[0], cells[-1].upper()
        if label.upper() in {"ITEM", "QUESTÃO", "QUESTAO"} or val in {"GABARITO"}:
            continue
        m_disc = re.match(r"^QUEST[ÃA]O\s+DISCURSIVA\s+(\d+)$", label, re.I)
        if m_disc:
            items.append({"numero": int(m_disc.group(1)), "tipo": "discursiva", "rotulo": label, "gabarito": val})
            continue
        m_obj = re.match(r"^(?:QUEST[ÃA]O\s+)?(\d+)$", label, re.I)
        if m_obj and (val in {"A", "B", "C", "D", "E", "ANULADA", "***"} or "ANUL" in val):
            items.append({
                "numero": int(m_obj.group(1)),
                "tipo": "objetiva",
                "rotulo": label,
                "gabarito": "ANULADA" if "ANUL" in val else val,
            })
    return items


def step_gabarito() -> None:
    import pdfplumber
    import pymupdf

    editions = [
        ("2023", GAB_2023, 38, 2),
        ("2019", GAB_2019, 35, 0),
        ("2017", GAB_2017, 35, 0),
    ]
    results: dict[str, Any] = {}
    for year, path, exp_obj, exp_disc in editions:
        # pdfplumber
        t0 = time.perf_counter()
        with pdfplumber.open(path) as pdf:
            raw_rows: list[list[Any]] = []
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    raw_rows.extend(table)
        t_plumber = (time.perf_counter() - t0) * 1000
        plumber_items = parse_gabarito_rows(raw_rows)

        # pymupdf find_tables
        t0 = time.perf_counter()
        with pymupdf.open(path) as doc:
            pm_rows: list[list[Any]] = []
            for page in doc:
                tabs = page.find_tables()
                for tab in tabs.tables:
                    pm_rows.extend(tab.extract())
        t_pymupdf = (time.perf_counter() - t0) * 1000
        pm_items = parse_gabarito_rows(pm_rows)

        def summarize(items: list[dict[str, Any]], ms: float) -> dict[str, Any]:
            objs = [x for x in items if x["tipo"] == "objetiva"]
            discs = [x for x in items if x["tipo"] == "discursiva"]
            anuladas = [x["numero"] for x in objs if x["gabarito"] == "ANULADA"]
            return {
                "time_ms": round(ms, 1),
                "objetivas_encontradas": len(objs),
                "objetivas_esperadas": exp_obj,
                "discursivas_encontradas": len(discs),
                "discursivas_esperadas": exp_disc,
                "anuladas": anuladas,
                "completo": len(objs) == exp_obj and len(discs) == exp_disc,
                "items": items,
            }

        results[year] = {
            "pdfplumber": summarize(plumber_items, t_plumber),
            "pymupdf_find_tables": summarize(pm_items, t_pymupdf),
            "match_exato": plumber_items == pm_items,
        }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "gabaritos.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[gabarito] concluído:", {y: (r["pdfplumber"]["completo"], r["pymupdf_find_tables"]["completo"], r["match_exato"]) for y, r in results.items()})


# ---------------------------------------------------------------------------
# STEP 2: PyMuPDF 2.1 (com pymupdf-layout) na prova 2023 completa
# ---------------------------------------------------------------------------

def run_pymupdf_extract(pdf_path: Path, out_subdir: Path, dpi: int = 150) -> dict[str, Any]:
    import pymupdf
    import pymupdf.layout  # ativa detecção de layout ONNX
    import pymupdf4llm

    out_subdir.mkdir(parents=True, exist_ok=True)
    img_dir = out_subdir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    doc = pymupdf.open(pdf_path)
    num_pages = len(doc)

    # Usa pymupdf4llm.to_markdown com layout ativo, header=False, footer=False e recorte de figuras
    md_kwargs = dict(
        header=False,
        footer=False,
        write_images=True,
        image_path=str(img_dir),
        image_format="png",
        dpi=dpi,
        page_chunks=True,
    )
    try:
        chunks = pymupdf4llm.to_markdown(doc, **md_kwargs)
    except TypeError:
        md_kwargs.pop("dpi", None)
        md_kwargs["image_dpi"] = dpi
        chunks = pymupdf4llm.to_markdown(doc, **md_kwargs)

    t_md = time.perf_counter() - t0

    # Também mede to_json() para obter bounding boxes float das regiões detectadas
    t1 = time.perf_counter()
    json_str = pymupdf4llm.to_json(doc, header=False, footer=False)
    t_json = time.perf_counter() - t1
    doc.close()

    full_md = "\n\n<!-- PAGE_BREAK -->\n\n".join(c["text"] for c in chunks)
    (out_subdir / "output.md").write_text(full_md, encoding="utf-8")
    (out_subdir / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (out_subdir / "layout.json").write_text(json_str, encoding="utf-8")

    layout_data = json.loads(json_str)
    box_counts: dict[str, int] = {}
    for p in layout_data.get("pages", []):
        for b in p.get("boxes", []):
            cls = b.get("boxclass", "unknown")
            box_counts[cls] = box_counts.get(cls, 0) + 1

    images = sorted(p.name for p in img_dir.glob("*.png"))
    metrics = {
        "engine": "pymupdf-2.1 (pymupdf-layout + pymupdf4llm)",
        "pdf": str(pdf_path.name),
        "pages": num_pages,
        "time_markdown_s": round(t_md, 2),
        "time_json_s": round(t_json, 2),
        "sec_per_page": round(t_md / max(num_pages, 1), 3),
        "peak_rss_mb": peak_rss_mb(),
        "images_extracted": len(images),
        "box_class_counts": box_counts,
        "output_md": str((out_subdir / "output.md").relative_to(OUT_DIR)),
        "images_dir": str(img_dir.relative_to(OUT_DIR)),
    }
    (out_subdir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


def step_pymupdf() -> None:
    m = run_pymupdf_extract(PROVA_2023, OUT_DIR / "pymupdf_2023")
    print("[pymupdf 2023]", json.dumps(m, ensure_ascii=False))


# ---------------------------------------------------------------------------
# STEP 3: Docling 2.151.1 na prova 2023 completa (e A/B enriquecido)
# ---------------------------------------------------------------------------

def run_docling_extract(
    pdf_path: Path,
    out_subdir: Path,
    *,
    do_ocr: bool = False,
    do_code: bool = False,
    do_formula: bool = False,
    images_scale: float = 2.0,
) -> dict[str, Any]:
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.doc import ImageRefMode

    out_subdir.mkdir(parents=True, exist_ok=True)
    artifacts_dir = out_subdir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    t_init0 = time.perf_counter()
    opts = PdfPipelineOptions(
        do_ocr=do_ocr,
        do_table_structure=True,
        generate_picture_images=True,
        images_scale=images_scale,
        do_code_enrichment=do_code,
        do_formula_enrichment=do_formula,
    )
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=opts,
                backend=PyPdfiumDocumentBackend,
            )
        }
    )
    t_init = time.perf_counter() - t_init0

    t_conv0 = time.perf_counter()
    result = converter.convert(pdf_path)
    t_conv = time.perf_counter() - t_conv0

    doc = result.document
    md_path = out_subdir / "output.md"
    doc.save_as_markdown(
        md_path,
        artifacts_dir=artifacts_dir,
        image_mode=ImageRefMode.REFERENCED,
        page_break_placeholder="\n\n<!-- PAGE_BREAK -->\n\n",
    )

    label_counts: dict[str, int] = {}
    layer_counts: dict[str, int] = {}
    for item, _level in doc.iterate_items():
        lbl = str(getattr(item, "label", type(item).__name__))
        layer = str(getattr(item, "content_layer", "unknown"))
        label_counts[lbl] = label_counts.get(lbl, 0) + 1
        layer_counts[layer] = layer_counts.get(layer, 0) + 1

    num_pages = len(doc.pages)
    images = sorted(p.name for p in artifacts_dir.glob("*.png"))
    metrics = {
        "engine": f"docling-2.151.1 (ocr={do_ocr}, code={do_code}, formula={do_formula})",
        "pdf": str(pdf_path.name),
        "pages": num_pages,
        "time_init_s": round(t_init, 2),
        "time_convert_s": round(t_conv, 2),
        "time_total_s": round(t_init + t_conv, 2),
        "sec_per_page": round(t_conv / max(num_pages, 1), 2),
        "peak_rss_mb": peak_rss_mb(),
        "images_extracted": len(images),
        "pictures_count": len(doc.pictures),
        "tables_count": len(doc.tables),
        "label_counts": label_counts,
        "layer_counts": layer_counts,
        "output_md": str(md_path.relative_to(OUT_DIR)),
        "images_dir": str(artifacts_dir.relative_to(OUT_DIR)),
    }
    (out_subdir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


def step_docling() -> None:
    m = run_docling_extract(PROVA_2023, OUT_DIR / "docling_2023", do_ocr=False, do_code=False, do_formula=False)
    print("[docling 2023]", json.dumps(m, ensure_ascii=False))


def step_docling_enriched() -> None:
    sub_pdf = make_subset_pdf(PROVA_2023, ENRICHED_2023_PAGES, OUT_DIR / "subset_2023_enriched.pdf")
    m = run_docling_extract(sub_pdf, OUT_DIR / "docling_2023_enriched", do_ocr=False, do_code=True, do_formula=True)
    print("[docling 2023 enriched]", json.dumps(m, ensure_ascii=False))


# ---------------------------------------------------------------------------
# STEP 4: Stress-tests 2019 (2-col alternatives) e 2017 (2-col body + mojibake + OCR)
# ---------------------------------------------------------------------------

def step_spot_pymupdf() -> None:
    sub_2019 = make_subset_pdf(PROVA_2019, SPOT_2019_PAGES, OUT_DIR / "subset_2019.pdf")
    sub_2017 = make_subset_pdf(PROVA_2017, SPOT_2017_PAGES, OUT_DIR / "subset_2017.pdf")
    m19 = run_pymupdf_extract(sub_2019, OUT_DIR / "spot_pymupdf_2019")
    m17 = run_pymupdf_extract(sub_2017, OUT_DIR / "spot_pymupdf_2017")
    print("[spot pymupdf 2019]", m19["time_markdown_s"], "s,", m19["images_extracted"], "imgs")
    print("[spot pymupdf 2017]", m17["time_markdown_s"], "s,", m17["images_extracted"], "imgs")


def step_spot_docling() -> None:
    sub_2019 = make_subset_pdf(PROVA_2019, SPOT_2019_PAGES, OUT_DIR / "subset_2019.pdf")
    sub_2017 = make_subset_pdf(PROVA_2017, SPOT_2017_PAGES, OUT_DIR / "subset_2017.pdf")
    m19 = run_docling_extract(sub_2019, OUT_DIR / "spot_docling_2019", do_ocr=False)
    m17_no_ocr = run_docling_extract(sub_2017, OUT_DIR / "spot_docling_2017_no_ocr", do_ocr=False)
    m17_ocr = run_docling_extract(sub_2017, OUT_DIR / "spot_docling_2017_ocr", do_ocr=True)
    print("[spot docling 2019]", m19["time_convert_s"], "s,", m19["images_extracted"], "imgs")
    print("[spot docling 2017 no_ocr]", m17_no_ocr["time_convert_s"], "s")
    print("[spot docling 2017 ocr]", m17_ocr["time_convert_s"], "s,", m17_ocr["images_extracted"], "imgs")


# ---------------------------------------------------------------------------
# STEP 5: Segmentação determinística + análise de qualidade + HTML autossuficiente
# ---------------------------------------------------------------------------

PERCEPTION_RE = re.compile(r"QUESTION[ÁA]RIO\s+DE\s+PERCEP[ÇC][ÃA]O", re.I)
QUESTION_HDR_RE = re.compile(
    r"(?m)^(?:[#*>\s_`]*)(?:QUEST[ÃA]O)\s+0?(\d{1,2})\b[^\n]*$"
)
ALT_RE = re.compile(r"(?m)^(?:\s*[*_>`-]*\s*)([A-E])(?:\s*[*_]*\s*)(?:[\)\.]|\s+)")
IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
NOISE_PATTERNS = [
    re.compile(r"VALIDINEP\w*", re.I),
    re.compile(r"\*R\d{6,}\*"),
    re.compile(r"ÁREA\s+LIVRE", re.I),
    re.compile(r"ENGENHARIA\s+DE\s+COMPUTA[ÇC][ÃA]O\s*$", re.I | re.M),
]


def segment_questions_2023(md_text: str, base_dir: Path, gabarito_map: dict[int, str]) -> dict[str, Any]:
    # 1. Verifica e trunca antes do Questionário de Percepção da Prova
    m_perc = PERCEPTION_RE.search(md_text)
    perception_found = m_perc is not None
    body = md_text[: m_perc.start()] if m_perc else md_text

    # Também checa se existe duplicação de QUESTÃO 01..09 caso truncamento falhasse
    matches = list(QUESTION_HDR_RE.finditer(body))
    questions: dict[int, dict[str, Any]] = {}
    duplicates: list[int] = []

    for idx, m in enumerate(matches):
        qnum = int(m.group(1))
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        chunk = body[start:end].strip()

        if qnum in questions:
            duplicates.append(qnum)
        # Mantemos apenas CE (10..38) na avaliação principal, mas registramos tudo
        if 10 <= qnum <= 38:
            # Alternativas A-E: tenta detectar linhas iniciando com A..E (ou blocos de alternativas)
            alt_matches = list(re.finditer(r"(?m)^\s*(?:[*_>`-]*\s*)?([A-E])(?:\s*[*_]*)(?:\s+|\)\s*|\.\s+)", chunk))
            # Filtra sequência crescente A -> B -> C -> D -> E mais próxima do final (evita falsos positivos no enunciado)
            found_letters = []
            seen = set()
            for am in alt_matches:
                letter = am.group(1)
                if letter not in seen:
                    seen.add(letter)
                    found_letters.append(letter)
            # Checa ordem estrita A, B, C, D, E em algum bloco
            all_5_ordered = _has_ordered_abcde(chunk)

            # Imagens referenciadas neste bloco
            raw_imgs = IMG_RE.findall(chunk)
            resolved_imgs = []
            for rel in raw_imgs:
                p = Path(rel)
                if not p.is_absolute():
                    p = (base_dir / rel).resolve()
                if p.exists():
                    resolved_imgs.append(str(p))

            # Ruído vazado neste bloco
            noise_hits = []
            for npat in NOISE_PATTERNS:
                noise_hits.extend(npat.findall(chunk))

            has_table = bool(re.search(r"(?m)^\|.*\|$", chunk))
            has_code_fence = "```" in chunk
            has_page_break = "<!-- PAGE_BREAK -->" in chunk

            questions[qnum] = {
                "numero": qnum,
                "gabarito": gabarito_map.get(qnum, "?"),
                "char_len": len(chunk),
                "alternatives_found": sorted(seen),
                "all_5_alternatives": all_5_ordered,
                "images": resolved_imgs,
                "image_count": len(resolved_imgs),
                "has_table": has_table,
                "has_code_fence": has_code_fence,
                "spans_pages": has_page_break,
                "noise_hits": noise_hits,
                "markdown": chunk,
            }

    ce_nums = list(range(10, 39))
    found_ce = [n for n in ce_nums if n in questions]
    missing_ce = [n for n in ce_nums if n not in questions]
    all5_count = sum(1 for n in found_ce if questions[n]["all_5_alternatives"])
    total_imgs = sum(questions[n]["image_count"] for n in found_ce)
    qs_with_imgs = [n for n in found_ce if questions[n]["image_count"] > 0]
    total_noise = sum(len(questions[n]["noise_hits"]) for n in found_ce)
    q10_text = questions.get(10, {}).get("markdown", "")
    q10_has_rho = ("ρ" in q10_text) or ("\\rho" in q10_text)
    q25_spans = questions.get(25, {}).get("spans_pages", False)
    q25_len = questions.get(25, {}).get("char_len", 0)

    return {
        "perception_marker_found": perception_found,
        "duplicates_before_trunc": duplicates,
        "ce_found": len(found_ce),
        "ce_expected": 29,
        "ce_missing": missing_ce,
        "all_5_alternatives_count": all5_count,
        "missing_5_alternatives": [n for n in found_ce if not questions[n]["all_5_alternatives"]],
        "total_images_linked": total_imgs,
        "questions_with_images": qs_with_imgs,
        "tables_questions": [n for n in found_ce if questions[n]["has_table"]],
        "code_fence_questions": [n for n in found_ce if questions[n]["has_code_fence"]],
        "noise_hits_total": total_noise,
        "q10_rho_preserved": q10_has_rho,
        "q25_cross_page_intact": q25_spans and questions.get(25, {}).get("all_5_alternatives", False),
        "q25_char_len": q25_len,
        "questions": questions,
    }


def _has_ordered_abcde(chunk: str) -> bool:
    """Verifica se A, B, C, D, E aparecem em ordem como marcadores de alternativa."""
    # Em Markdown de provas do ENADE, alternativas podem aparecer como:
    # 'A texto...', '**A** texto...', '- A texto...', 'A) texto...', ou até inline em tabela/bloco
    pos = -1
    for letter in ["A", "B", "C", "D", "E"]:
        pat = re.compile(rf"(?m)(?:^|\n)\s*(?:[-*>\s]*[*_`]*){letter}(?:[*_`]*)(?:[\)\.]|\s+)")
        m = pat.search(chunk, pos + 1)
        if not m:
            return False
        pos = m.start()
    return True


def img_to_data_uri(path: Path) -> str:
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{b64}"


def step_report() -> None:
    # Renderiza páginas de referência para inspeção visual no HTML
    ref_dir = OUT_DIR / "ref_pages"
    ref_2023 = render_reference_pages(PROVA_2023, ENRICHED_2023_PAGES + [28, 29], ref_dir, "2023")
    ref_2019 = render_reference_pages(PROVA_2019, SPOT_2019_PAGES, ref_dir, "2019")
    ref_2017 = render_reference_pages(PROVA_2017, SPOT_2017_PAGES, ref_dir, "2017")

    gabaritos = json.loads((OUT_DIR / "gabaritos.json").read_text(encoding="utf-8"))
    gab_2023_map = {
        x["numero"]: x["gabarito"]
        for x in gabaritos["2023"]["pdfplumber"]["items"]
        if x["tipo"] == "objetiva"
    }

    docling_metrics = json.loads((OUT_DIR / "docling_2023" / "metrics.json").read_text(encoding="utf-8"))
    pymupdf_metrics = json.loads((OUT_DIR / "pymupdf_2023" / "metrics.json").read_text(encoding="utf-8"))
    enriched_metrics = json.loads((OUT_DIR / "docling_2023_enriched" / "metrics.json").read_text(encoding="utf-8"))

    docling_md = (OUT_DIR / "docling_2023" / "output.md").read_text(encoding="utf-8")
    pymupdf_md = (OUT_DIR / "pymupdf_2023" / "output.md").read_text(encoding="utf-8")
    enriched_md = (OUT_DIR / "docling_2023_enriched" / "output.md").read_text(encoding="utf-8")

    seg_docling = segment_questions_2023(docling_md, OUT_DIR / "docling_2023", gab_2023_map)
    seg_pymupdf = segment_questions_2023(pymupdf_md, OUT_DIR / "pymupdf_2023", gab_2023_map)

    # Stress tests 2019 e 2017
    spot = {
        "2019_docling_md": (OUT_DIR / "spot_docling_2019" / "output.md").read_text(encoding="utf-8"),
        "2019_pymupdf_md": (OUT_DIR / "spot_pymupdf_2019" / "output.md").read_text(encoding="utf-8"),
        "2019_docling_metrics": json.loads((OUT_DIR / "spot_docling_2019" / "metrics.json").read_text(encoding="utf-8")),
        "2019_pymupdf_metrics": json.loads((OUT_DIR / "spot_pymupdf_2019" / "metrics.json").read_text(encoding="utf-8")),
        "2017_pymupdf_md": (OUT_DIR / "spot_pymupdf_2017" / "output.md").read_text(encoding="utf-8"),
        "2017_docling_no_ocr_md": (OUT_DIR / "spot_docling_2017_no_ocr" / "output.md").read_text(encoding="utf-8"),
        "2017_docling_ocr_md": (OUT_DIR / "spot_docling_2017_ocr" / "output.md").read_text(encoding="utf-8"),
        "2017_docling_ocr_metrics": json.loads((OUT_DIR / "spot_docling_2017_ocr" / "metrics.json").read_text(encoding="utf-8")),
    }

    summary = {
        "gabaritos": {
            y: {
                "pdfplumber_completo": g["pdfplumber"]["completo"],
                "pdfplumber_ms": g["pdfplumber"]["time_ms"],
                "pymupdf_completo": g["pymupdf_find_tables"]["completo"],
                "pymupdf_ms": g["pymupdf_find_tables"]["time_ms"],
                "anuladas": g["pdfplumber"]["anuladas"],
                "match_exato": g["match_exato"],
            }
            for y, g in gabaritos.items()
        },
        "docling_2023": {**docling_metrics, **{k: v for k, v in seg_docling.items() if k != "questions"}},
        "pymupdf_2023": {**pymupdf_metrics, **{k: v for k, v in seg_pymupdf.items() if k != "questions"}},
        "docling_2023_enriched_5pages": enriched_metrics,
        "spot_2019_docling": spot["2019_docling_metrics"],
        "spot_2019_pymupdf": spot["2019_pymupdf_metrics"],
        "spot_2017_docling_ocr": spot["2017_docling_ocr_metrics"],
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    html_doc = build_html_report(
        summary=summary,
        gabaritos=gabaritos,
        seg_docling=seg_docling,
        seg_pymupdf=seg_pymupdf,
        enriched_md=enriched_md,
        spot=spot,
        ref_2023=ref_2023,
        ref_2019=ref_2019,
        ref_2017=ref_2017,
    )
    html_path = OUT_DIR / "comparacao-extracao.html"
    html_path.write_text(html_doc, encoding="utf-8")
    print(f"[report] gerado: {html_path} ({html_path.stat().st_size // 1024} KB)")
    print("[summary]", json.dumps(summary, ensure_ascii=False, indent=2))


def _render_imgs_html(img_paths: list[str]) -> str:
    if not img_paths:
        return '<div class="muted">Nenhuma figura vinculada</div>'
    parts = []
    for p_str in img_paths:
        p = Path(p_str)
        if p.exists():
            uri = img_to_data_uri(p)
            parts.append(f'<figure><img src="{uri}" loading="lazy"><figcaption>{html.escape(p.name)}</figcaption></figure>')
    return '<div class="img-grid">' + "".join(parts) + "</div>"


def _render_dir_imgs_html(img_dir: Path) -> str:
    imgs = sorted(img_dir.glob("*.png"))
    return _render_imgs_html([str(p) for p in imgs])


def build_html_report(
    *,
    summary: dict[str, Any],
    gabaritos: dict[str, Any],
    seg_docling: dict[str, Any],
    seg_pymupdf: dict[str, Any],
    enriched_md: str,
    spot: dict[str, Any],
    ref_2023: dict[int, str],
    ref_2019: dict[int, str],
    ref_2017: dict[int, str],
) -> str:
    d23 = summary["docling_2023"]
    p23 = summary["pymupdf_2023"]
    e23 = summary["docling_2023_enriched_5pages"]

    q_cards = []
    for qnum in range(10, 39):
        dq = seg_docling["questions"].get(qnum)
        pq = seg_pymupdf["questions"].get(qnum)
        gab = (dq or pq or {}).get("gabarito", "?")
        d_badge = "ok" if (dq and dq["all_5_alternatives"]) else "warn"
        p_badge = "ok" if (pq and pq["all_5_alternatives"]) else "warn"
        tags = []
        if (dq and dq["image_count"]) or (pq and pq["image_count"]):
            tags.append("figura")
        if (dq and dq["has_table"]) or (pq and pq["has_table"]):
            tags.append("tabela")
        if (dq and dq["has_code_fence"]) or (pq and pq["has_code_fence"]):
            tags.append("codigo")
        if (dq and dq["spans_pages"]) or (pq and pq["spans_pages"]):
            tags.append("multipagina")
        if d_badge == "warn" or p_badge == "warn":
            tags.append("alerta")

        d_meta = f'Alts A-E: {"OK" if (dq and dq["all_5_alternatives"]) else "FALHA"} | Imgs: {dq["image_count"] if dq else 0} | Ruído: {len(dq["noise_hits"]) if dq else 0}'
        p_meta = f'Alts A-E: {"OK" if (pq and pq["all_5_alternatives"]) else "FALHA"} | Imgs: {pq["image_count"] if pq else 0} | Ruído: {len(pq["noise_hits"]) if pq else 0}'

        q_cards.append(f"""
        <div class="q-card" data-tags="{' '.join(tags)}">
          <div class="q-header">
            <h3>Questão {qnum:02d} <span class="badge gab">Gabarito: {html.escape(str(gab))}</span></h3>
            <div class="badges">
              <span class="badge {d_badge}">Docling: {d_meta}</span>
              <span class="badge {p_badge}">PyMuPDF: {p_meta}</span>
            </div>
          </div>
          <div class="cols-2">
            <div class="col">
              <h4>Docling 2.151.1 (MIT)</h4>
              {_render_imgs_html(dq["images"] if dq else [])}
              <pre>{html.escape(dq["markdown"] if dq else "[NÃO SEGMENTADA]")}</pre>
            </div>
            <div class="col">
              <h4>PyMuPDF 2.1 (AGPL-3.0)</h4>
              {_render_imgs_html(pq["images"] if pq else [])}
              <pre>{html.escape(pq["markdown"] if pq else "[NÃO SEGMENTADA]")}</pre>
            </div>
          </div>
        </div>
        """)

    # Páginas de referência 2023 para aba Enriched
    enriched_pages_html = []
    for pno in ENRICHED_2023_PAGES:
        uri = img_to_data_uri(OUT_DIR / ref_2023[pno])
        enriched_pages_html.append(f'<figure><img src="{uri}" loading="lazy"><figcaption>Original 2023 p.{pno}</figcaption></figure>')

    spot_2019_refs = "".join(
        f'<figure><img src="{img_to_data_uri(OUT_DIR / ref_2019[pno])}" loading="lazy"><figcaption>Original 2019 p.{pno}</figcaption></figure>'
        for pno in SPOT_2019_PAGES
    )
    spot_2017_refs = "".join(
        f'<figure><img src="{img_to_data_uri(OUT_DIR / ref_2017[pno])}" loading="lazy"><figcaption>Original 2017 p.{pno}</figcaption></figure>'
        for pno in SPOT_2017_PAGES
    )

    gab_rows = []
    for yr in ["2023", "2019", "2017"]:
        g = gabaritos[yr]
        pl = g["pdfplumber"]
        pm = g["pymupdf_find_tables"]
        gab_rows.append(f"""
        <tr>
          <td><strong>{yr}</strong></td>
          <td>{"OK" if pl["completo"] else "FALHA"} ({pl["objetivas_encontradas"]}/{pl["objetivas_esperadas"]} obj, {pl["discursivas_encontradas"]} disc) — {pl["time_ms"]} ms</td>
          <td>{"OK" if pm["completo"] else "FALHA"} ({pm["objetivas_encontradas"]}/{pm["objetivas_esperadas"]} obj, {pm["discursivas_encontradas"]} disc) — {pm["time_ms"]} ms</td>
          <td>{"SIM" if g["match_exato"] else "DIVERGE"}</td>
          <td>{html.escape(str(pl["anuladas"]))}</td>
        </tr>
        """)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Protótipo 05 — Docling vs PyMuPDF 2.1 (ENADE Engenharia de Computação)</title>
<style>
  :root {{ --bg:#f7f7f5; --card:#fff; --ink:#1c1c1c; --muted:#666; --accent:#1f5eff; --border:#e2e2dd; --ok:#0f7b3e; --warn:#b54708; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: system-ui, -apple-system, sans-serif; background:var(--bg); color:var(--ink); line-height:1.45; }}
  header {{ background:#111; color:#fff; padding:20px 28px; }}
  header h1 {{ margin:0 0 6px; font-size:20px; }}
  header p {{ margin:0; color:#ccc; font-size:13px; max-width:960px; }}
  main {{ max-width:1480px; margin:0 auto; padding:20px 24px 60px; }}
  .tabs {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:18px; border-bottom:1px solid var(--border); padding-bottom:10px; }}
  .tab-btn {{ border:1px solid var(--border); background:#fff; padding:8px 14px; border-radius:6px; cursor:pointer; font-size:13px; font-weight:600; }}
  .tab-btn.active {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
  .panel {{ display:none; }}
  .panel.active {{ display:block; }}
  table {{ width:100%; border-collapse:collapse; background:#fff; border:1px solid var(--border); margin-bottom:20px; font-size:13px; }}
  th, td {{ padding:10px 12px; border:1px solid var(--border); text-align:left; vertical-align:top; }}
  th {{ background:#f0f0ec; font-weight:600; }}
  .filters {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px; }}
  .filter-btn {{ border:1px solid var(--border); background:#fff; padding:5px 10px; border-radius:999px; cursor:pointer; font-size:12px; }}
  .filter-btn.active {{ background:#111; color:#fff; border-color:#111; }}
  .q-card {{ background:var(--card); border:1px solid var(--border); border-radius:8px; margin-bottom:16px; overflow:hidden; }}
  .q-header {{ padding:12px 16px; background:#fafaf8; border-bottom:1px solid var(--border); display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; }}
  .q-header h3 {{ margin:0; font-size:15px; }}
  .badges {{ display:flex; gap:6px; flex-wrap:wrap; }}
  .badge {{ font-size:11px; padding:3px 8px; border-radius:999px; font-weight:600; }}
  .badge.ok {{ background:#e6f6ec; color:var(--ok); }}
  .badge.warn {{ background:#fef3e7; color:var(--warn); }}
  .badge.gab {{ background:#e8efff; color:var(--accent); margin-left:8px; }}
  .cols-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:0; }}
  .cols-3 {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; }}
  .col {{ padding:14px 16px; border-right:1px solid var(--border); min-width:0; }}
  .col:last-child {{ border-right:none; }}
  .col h4 {{ margin:0 0 10px; font-size:13px; color:var(--muted); text-transform:uppercase; letter-spacing:0.03em; }}
  pre {{ white-space:pre-wrap; word-break:break-word; background:#f7f7f4; border:1px solid var(--border); padding:10px; border-radius:6px; font-size:12px; max-height:460px; overflow:auto; margin:8px 0 0; }}
  .img-grid {{ display:flex; flex-wrap:wrap; gap:10px; margin-bottom:10px; }}
  figure {{ margin:0; border:1px solid var(--border); border-radius:6px; padding:6px; background:#fff; max-width:340px; }}
  figure img {{ max-width:100%; max-height:260px; display:block; object-fit:contain; }}
  figcaption {{ font-size:11px; color:var(--muted); margin-top:4px; word-break:break-all; }}
  .muted {{ font-size:12px; color:var(--muted); margin-bottom:8px; }}
  .card {{ background:#fff; border:1px solid var(--border); border-radius:8px; padding:16px; margin-bottom:16px; }}
</style>
</head>
<body>
<header>
  <h1>Protótipo Descartável (Decisão 05) — Docling 2.151.1 vs PyMuPDF 2.1 + pdfplumber</h1>
  <p>Questão prototipada: qual extrator entrega o melhor resultado ponta a ponta em provas reais do ENADE de Engenharia de Computação (segmentação Q10–Q38, alternativas A–E, figuras vetoriais recortadas, código, tabelas, fórmulas, layouts multi-coluna 2019/2017, encoding corrompido 2017, gabarito oficial e custo de CPU/RAM local)?</p>
</header>
<main>
  <div class="tabs">
    <button class="tab-btn active" onclick="showTab('resumo', this)">Resumo & Métricas</button>
    <button class="tab-btn" onclick="showTab('q2023', this)">ENADE 2023 — 29 Questões CE (Lado a Lado)</button>
    <button class="tab-btn" onclick="showTab('enriched', this)">A/B Fórmulas & Código (CodeFormulaV2)</button>
    <button class="tab-btn" onclick="showTab('spot2019', this)">Stress 2019 (Alts 2 Colunas & Circuitos)</button>
    <button class="tab-btn" onclick="showTab('spot2017', this)">Stress 2017 (2 Colunas + Mojibake + OCR)</button>
    <button class="tab-btn" onclick="showTab('gabaritos', this)">Gabaritos (2023 / 2019 / 2017)</button>
  </div>

  <section id="resumo" class="panel active">
    <h2>1. Comparação Ponta a Ponta — ENADE 2023 Completo (40 páginas, Q10–Q38)</h2>
    <table>
      <thead>
        <tr><th>Critério</th><th>Docling 2.151.1 (MIT, PyPdfium2, CPU)</th><th>PyMuPDF 2.1 (AGPL-3.0, pymupdf-layout ONNX)</th><th>Docling + CodeFormulaV2 (5 págs)</th></tr>
      </thead>
      <tbody>
        <tr><td>Tempo de conversão (wall)</td><td><strong>{d23['time_convert_s']} s</strong> (init: {d23['time_init_s']} s)</td><td><strong>{p23['time_markdown_s']} s</strong> (json: {p23['time_json_s']} s)</td><td><strong>{e23['time_convert_s']} s</strong> (5 págs)</td></tr>
        <tr><td>Velocidade média</td><td>{d23['sec_per_page']} s/pág</td><td>{p23['sec_per_page']} s/pág</td><td>{e23['sec_per_page']} s/pág</td></tr>
        <tr><td>Pico de RAM (RSS isolado)</td><td>{d23['peak_rss_mb']} MB</td><td>{p23['peak_rss_mb']} MB</td><td>{e23['peak_rss_mb']} MB</td></tr>
        <tr><td>Questões CE segmentadas (Q10–Q38)</td><td><strong>{d23['ce_found']} / 29</strong> (faltando: {d23['ce_missing']})</td><td><strong>{p23['ce_found']} / 29</strong> (faltando: {p23['ce_missing']})</td><td>—</td></tr>
        <tr><td>Alternativas A–E em ordem</td><td><strong>{d23['all_5_alternatives_count']} / 29</strong> (alertas: {d23['missing_5_alternatives']})</td><td><strong>{p23['all_5_alternatives_count']} / 29</strong> (alertas: {p23['missing_5_alternatives']})</td><td>—</td></tr>
        <tr><td>Q25 multipágina (p.28→p.29) intacta</td><td>{"SIM" if d23['q25_cross_page_intact'] else "NÃO"} ({d23['q25_char_len']} chars)</td><td>{"SIM" if p23['q25_cross_page_intact'] else "NÃO"} ({p23['q25_char_len']} chars)</td><td>—</td></tr>
        <tr><td>Armadilha Percepção (p.39) detectada</td><td>{"SIM" if d23['perception_marker_found'] else "NÃO"}</td><td>{"SIM" if p23['perception_marker_found'] else "NÃO"}</td><td>—</td></tr>
        <tr><td>Figuras recortadas (total PDF / ligadas ao CE)</td><td>{d23['images_extracted']} total / <strong>{d23['total_images_linked']}</strong> no CE ({len(d23['questions_with_images'])} questões)</td><td>{p23['images_extracted']} total / <strong>{p23['total_images_linked']}</strong> no CE ({len(p23['questions_with_images'])} questões)</td><td>{e23['images_extracted']} (5 págs)</td></tr>
        <tr><td>Questões com tabelas / blocos de código</td><td>Tabelas: {len(d23['tables_questions'])} {d23['tables_questions']}<br>Código: {len(d23['code_fence_questions'])} {d23['code_fence_questions']}</td><td>Tabelas: {len(p23['tables_questions'])} {p23['tables_questions']}<br>Código: {len(p23['code_fence_questions'])} {p23['code_fence_questions']}</td><td>Labels: {html.escape(str(e23['label_counts']))}</td></tr>
        <tr><td>Ruído de cabeçalho/marca d'água vazado no CE</td><td>{d23['noise_hits_total']} ocorrências</td><td>{p23['noise_hits_total']} ocorrências</td><td>—</td></tr>
        <tr><td>Símbolo grego ρ preservado na Q10</td><td>{"SIM" if d23['q10_rho_preserved'] else "NÃO (fonte Symbol → r)"}</td><td>{"SIM" if p23['q10_rho_preserved'] else "NÃO (fonte Symbol → r)"}</td><td>Ver aba A/B</td></tr>
      </tbody>
    </table>

    <h2>2. Gabaritos Oficiais (3 formatos reais)</h2>
    <table>
      <thead><tr><th>Edição</th><th>pdfplumber (MIT)</th><th>PyMuPDF find_tables</th><th>Match 100%</th><th>Anuladas</th></tr></thead>
      <tbody>{"".join(gab_rows)}</tbody>
    </table>
  </section>

  <section id="q2023" class="panel">
    <div class="filters">
      <button class="filter-btn active" onclick="filterQ('all', this)">Todas (29)</button>
      <button class="filter-btn" onclick="filterQ('alerta', this)">Com alerta A–E</button>
      <button class="filter-btn" onclick="filterQ('figura', this)">Com figura</button>
      <button class="filter-btn" onclick="filterQ('tabela', this)">Com tabela</button>
      <button class="filter-btn" onclick="filterQ('codigo', this)">Com código</button>
      <button class="filter-btn" onclick="filterQ('multipagina', this)">Multipágina</button>
    </div>
    {"".join(q_cards)}
  </section>

  <section id="enriched" class="panel">
    <div class="card">
      <h3>Páginas originais de referência (2023: p.14 Q10, p.19 Q15, p.20 Q16, p.25 Q22, p.26 Q23)</h3>
      <div class="img-grid">{"".join(enriched_pages_html)}</div>
      <h3>Saída Docling + CodeFormulaV2 ({e23['time_convert_s']} s = {e23['sec_per_page']} s/pág, RSS {e23['peak_rss_mb']} MB)</h3>
      {_render_dir_imgs_html(OUT_DIR / "docling_2023_enriched" / "artifacts")}
      <pre>{html.escape(enriched_md)}</pre>
    </div>
  </section>

  <section id="spot2019" class="panel">
    <div class="card">
      <h3>ENADE 2019 — Páginas de referência (p.16 Q09 alts 2 colunas Java, p.22–24 circuitos + ÁREA LIVRE)</h3>
      <div class="img-grid">{spot_2019_refs}</div>
      <div class="cols-2">
        <div class="col">
          <h4>Docling 2.151.1 ({spot['2019_docling_metrics']['time_convert_s']} s)</h4>
          {_render_dir_imgs_html(OUT_DIR / "spot_docling_2019" / "artifacts")}
          <pre>{html.escape(spot['2019_docling_md'])}</pre>
        </div>
        <div class="col">
          <h4>PyMuPDF 2.1 ({spot['2019_pymupdf_metrics']['time_markdown_s']} s)</h4>
          {_render_dir_imgs_html(OUT_DIR / "spot_pymupdf_2019" / "images")}
          <pre>{html.escape(spot['2019_pymupdf_md'])}</pre>
        </div>
      </div>
    </div>
  </section>

  <section id="spot2017" class="panel">
    <div class="card">
      <h3>ENADE 2017 — Páginas de referência (p.17–18: corpo em 2 colunas + ToUnicode CMap corrompido)</h3>
      <div class="img-grid">{spot_2017_refs}</div>
      <div class="cols-3">
        <div class="col">
          <h4>PyMuPDF 2.1 (sem OCR)</h4>
          <pre>{html.escape(spot['2017_pymupdf_md'])}</pre>
        </div>
        <div class="col">
          <h4>Docling (do_ocr=False)</h4>
          <pre>{html.escape(spot['2017_docling_no_ocr_md'])}</pre>
        </div>
        <div class="col">
          <h4>Docling (do_ocr=True RapidOCR — {spot['2017_docling_ocr_metrics']['time_convert_s']} s)</h4>
          {_render_dir_imgs_html(OUT_DIR / "spot_docling_2017_ocr" / "artifacts")}
          <pre>{html.escape(spot['2017_docling_ocr_md'])}</pre>
        </div>
      </div>
    </div>
  </section>

  <section id="gabaritos" class="panel">
    <div class="card">
      <h3>Gabaritos extraídos (JSON completo — pdfplumber)</h3>
      <pre>{html.escape(json.dumps(gabaritos, ensure_ascii=False, indent=2))}</pre>
    </div>
  </section>
</main>
<script>
function showTab(id, btn) {{
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
}}
function filterQ(tag, btn) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.q-card').forEach(c => {{
    if (tag === 'all') {{ c.style.display = ''; return; }}
    const tags = (c.getAttribute('data-tags') || '').split(' ');
    c.style.display = tags.includes(tag) ? '' : 'none';
  }});
}}
</script>
</body>
</html>
"""


def run_all() -> None:
    steps = ["gabarito", "pymupdf", "docling", "docling-enriched", "spot-pymupdf", "spot-docling", "report"]
    for step in steps:
        print(f"\n>>> Executando etapa isolada: {step}", flush=True)
        subprocess.run([sys.executable, str(Path(__file__)), "--step", step], check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--step",
        default="all",
        choices=["all", "gabarito", "pymupdf", "docling", "docling-enriched", "spot-pymupdf", "spot-docling", "report"],
    )
    args = parser.parse_args()
    dispatch = {
        "all": run_all,
        "gabarito": step_gabarito,
        "pymupdf": step_pymupdf,
        "docling": step_docling,
        "docling-enriched": step_docling_enriched,
        "spot-pymupdf": step_spot_pymupdf,
        "spot-docling": step_spot_docling,
        "report": step_report,
    }
    dispatch[args.step]()


if __name__ == "__main__":
    main()
