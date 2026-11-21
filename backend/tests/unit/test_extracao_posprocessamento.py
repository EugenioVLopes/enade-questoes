"""Testes unitários rápidos (sem ML/Docling) do pós-processamento e inspeção de PDF."""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pypdfium2 as pdfium
import pytest
from docling_core.types.doc import DoclingDocument
from PIL import Image

from application.ports.extracao import ExtratorProva
from domain.alertas_extracao import (
    MARCADOR_FORMULA_NAO_DECODIFICADA,
    avaliar_alertas_extracao,
)
from domain.enums import CodigoAlertaExtracao, LetraAlternativa, OrigemAtivoVisual
from domain.exceptions import ErroValidacaoDominio
from domain.prova import Alternativa, BoundingBox, FaixaQuestoes, Questao
from infrastructure.extracao.extrator_prova import (
    ExtratorProvaDocling,
    docling_document_para_elementos,
)
from infrastructure.extracao.inspecao_pdf import (
    detectar_cmap_corrompido,
    detectar_paginas_fonte_symbol,
    nome_fonte_indica_symbol,
    texto_indica_cmap_corrompido,
)
from infrastructure.extracao.posprocessamento import (
    ElementoDocling,
    filtrar_imagem_margem_ou_pequena,
    limpar_ruido_textual,
    posprocessar_elementos,
    truncar_questionario_percepcao,
)


def _png_bytes(width: int = 100, height: int = 80, color: tuple[int, int, int] = (20, 90, 200)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def _criar_pdf_imagem(caminho: Path, num_paginas: int = 1) -> Path:
    pdf = pdfium.PdfDocument.new()
    try:
        for idx in range(num_paginas):
            img = Image.new("RGB", (400, 600), (240 - idx * 20, 240, 240))
            pdf_img = pdfium.PdfImage.new(pdf)
            pdf_img.set_bitmap(pdfium.PdfBitmap.from_pil(img))
            pdf_img.set_matrix(pdfium.PdfMatrix().scale(400, 600))
            page = pdf.new_page(400, 600)
            page.insert_obj(pdf_img)
            page.gen_content()
            page.close()
        pdf.save(str(caminho))
    finally:
        pdf.close()
    return caminho


def test_truncar_questionario_percepcao_ignora_capa_e_protege_2019_p38() -> None:
    elementos = [
        ElementoDocling(tipo="table", texto="| Questionário de Percepção da Prova | 01 a 09 | - | - |", pagina=1),
        ElementoDocling(
            tipo="text",
            texto="As respostas do questionário de percepção da prova devem ser marcadas no cartão.",
            pagina=1,
        ),
        ElementoDocling(
            tipo="section_header",
            texto="QUESTÃO 09",
            pagina=16,
            bbox=BoundingBox(30, 80, 120, 95),
            page_width=567,
            page_height=780,
        ),
        ElementoDocling(tipo="text", texto="Enunciado real da questão 9 do componente específico.", pagina=16),
        # Simula ordem invertida em p.38 (ENADE 2019): Q09 da percepção emitida antes do título, mas abaixo em Y
        ElementoDocling(
            tipo="section_header",
            texto="QuEStão 09",
            pagina=38,
            bbox=BoundingBox(30, 500, 120, 515),
            page_width=567,
            page_height=780,
        ),
        ElementoDocling(
            tipo="text",
            texto="Você achou a prova extensa?",
            pagina=38,
            bbox=BoundingBox(30, 520, 300, 540),
            page_width=567,
            page_height=780,
        ),
        ElementoDocling(
            tipo="section_header",
            texto="QuEStionÁrio dE pErCEpção da prova",
            pagina=38,
            bbox=BoundingBox(30, 72, 400, 90),
            page_width=567,
            page_height=780,
        ),
        ElementoDocling(tipo="section_header", texto="QUESTÃO 01", pagina=39),
    ]

    truncados = truncar_questionario_percepcao(elementos)
    textos = [e.texto for e in truncados]
    assert any("Questionário de Percepção da Prova" in t for t in textos)
    assert "Enunciado real da questão 9 do componente específico." in textos
    assert "Você achou a prova extensa?" not in textos
    assert "QUESTÃO 01" not in textos


def test_limpar_ruido_textual_remove_variantes_sem_corromper_validado() -> None:
    bruto = (
        "VALIDINEP2023VALIDIN3P2023VALIDINEEP2023VALIDDIN\n"
        "O modelo foi validado em laboratório com validação cruzada e *Resultados* positivos.\n"
        "*R082023XX*\n"
        "ÁREA LIVRE\n"
        "14 ENGENHARIA DE COMPUTAÇÃO\n"
        "ENGENHARIA DE COMPUTAÇÃO 15\n"
        "Texto final preservado."
    )
    limpo = limpar_ruido_textual(bruto)
    assert "VALID" not in limpo
    assert "*R082023XX*" not in limpo
    assert "ÁREA LIVRE" not in limpo
    assert "ENGENHARIA DE COMPUTAÇÃO" not in limpo
    assert "validado" in limpo
    assert "validação" in limpo
    assert "*Resultados*" in limpo
    assert "Texto final preservado." in limpo


def test_filtrar_imagem_margem_ou_pequena_descarta_barcodes_e_preserva_figuras() -> None:
    barcode_topo = ElementoDocling(
        tipo="picture",
        pagina=14,
        bbox=BoundingBox(55.3, 27.2, 161.9, 54.1),
        page_width=566.9,
        page_height=779.5,
        img_width_px=213,
        img_height_px=54,
    )
    logo_topo = ElementoDocling(
        tipo="picture",
        pagina=14,
        bbox=BoundingBox(223.5, 27.2, 342.7, 49.8),
        page_width=566.9,
        page_height=779.5,
        img_width_px=238,
        img_height_px=46,
    )
    figura_real_q10 = ElementoDocling(
        tipo="picture",
        pagina=14,
        bbox=BoundingBox(89.8, 222.6, 476.4, 426.2),
        page_width=566.9,
        page_height=779.5,
        img_width_px=773,
        img_height_px=407,
    )
    figura_real_2017 = ElementoDocling(
        tipo="picture",
        pagina=17,
        bbox=BoundingBox(100.0, 168.0, 310.6, 376.8),
        page_width=628.1,
        page_height=826.5,
        img_width_px=421,
        img_height_px=418,
    )

    assert filtrar_imagem_margem_ou_pequena(barcode_topo) is True
    assert filtrar_imagem_margem_ou_pequena(logo_topo) is True
    assert filtrar_imagem_margem_ou_pequena(figura_real_q10) is False
    assert filtrar_imagem_margem_ou_pequena(figura_real_2017) is False


def test_posprocessamento_segmenta_casos_borda_2023_e_dispara_alertas_corretos() -> None:
    img_q10 = _png_bytes(773, 407, (10, 20, 30))
    img_q13_circ = _png_bytes(679, 280, (30, 40, 50))
    img_q25_circ = _png_bytes(984, 447, (50, 60, 70))
    img_barcode = _png_bytes(213, 54, (0, 0, 0))
    crop_q13_formula = _png_bytes(520, 180, (255, 255, 255))

    elementos = [
        # Formação Geral (fora de faixa_ce 10..38)
        ElementoDocling(tipo="section_header", texto="QUESTÃO 01", pagina=3),
        ElementoDocling(tipo="text", texto="Texto da formação geral deve ser ignorado.", pagina=3),
        # Q10 com imagem real + barcode na margem + tabela + 5 alternativas
        ElementoDocling(
            tipo="picture",
            pagina=14,
            bbox=BoundingBox(55.0, 27.0, 161.0, 54.0),
            page_width=567.0,
            page_height=780.0,
            imagem_png=img_barcode,
            img_width_px=213,
            img_height_px=54,
        ),
        ElementoDocling(tipo="section_header", texto="QUESTÃO 10", pagina=14),
        ElementoDocling(tipo="text", texto="Os resistores limitam a corrente elétrica em um circuito.", pagina=14),
        ElementoDocling(
            tipo="picture",
            pagina=14,
            bbox=BoundingBox(90.0, 222.0, 476.0, 426.0),
            page_width=567.0,
            page_height=780.0,
            imagem_png=img_q10,
            img_width_px=773,
            img_height_px=407,
        ),
        ElementoDocling(tipo="table", texto="| Material | r |\n|---|---|\n| Carbono | 40 |", pagina=14),
        ElementoDocling(tipo="list_item", texto="A 2 resistores de grafite em série.", pagina=14),
        ElementoDocling(tipo="list_item", texto="B 3 resistores de carbono em série.", pagina=14),
        ElementoDocling(tipo="list_item", texto="C 2 resistores de grafite em paralelo.", pagina=14),
        ElementoDocling(tipo="list_item", texto="D 2 resistores de carbono em paralelo.", pagina=14),
        ElementoDocling(tipo="list_item", texto="E 3 resistores de níquel-cromo em série.", pagina=14),
        # Q12 com prosa iniciando com "A figura..." e lista numerada 1..3 (não confundir com alternativa A)
        ElementoDocling(tipo="section_header", texto="QUESTÃO 12", pagina=16),
        ElementoDocling(tipo="text", texto="A figura a seguir apresenta propriedades de uma relação R.", pagina=16),
        ElementoDocling(tipo="list_item", texto="1. Reflexividade.", pagina=16, marker="1.", enumerated=True),
        ElementoDocling(tipo="list_item", texto="2. Simetria.", pagina=16, marker="2.", enumerated=True),
        ElementoDocling(tipo="list_item", texto="A A relação é de equivalência.", pagina=16),
        ElementoDocling(tipo="list_item", texto="B A relação é simétrica.", pagina=16),
        ElementoDocling(tipo="list_item", texto="C A relação é transitiva.", pagina=16),
        ElementoDocling(tipo="list_item", texto="D Subconjunto 1.", pagina=16),
        ElementoDocling(tipo="list_item", texto="E Subconjunto 2.", pagina=16),
        # Q13 com FormulaItem (preservar marcador + recortar via pypdfium2)
        ElementoDocling(tipo="section_header", texto="QUESTÃO 13", pagina=17),
        ElementoDocling(tipo="text", texto="A figura representa um circuito elétrico e seu grafo.", pagina=17),
        ElementoDocling(
            tipo="picture",
            pagina=17,
            bbox=BoundingBox(90.0, 200.0, 450.0, 350.0),
            page_width=567.0,
            page_height=780.0,
            imagem_png=img_q13_circ,
            img_width_px=679,
            img_height_px=280,
        ),
        ElementoDocling(
            tipo="formula",
            texto="",
            pagina=17,
            bbox=BoundingBox(30.5, 510.6, 288.6, 594.9),
            page_width=567.0,
            page_height=780.0,
        ),
        # Q15 com todas alternativas em CodeItem (preservar em enunciado -> alternativas_incompletas)
        ElementoDocling(tipo="section_header", texto="QUESTÃO 15", pagina=19),
        ElementoDocling(tipo="text", texto="Assinale a opção que apresenta um trecho com memory leak.", pagina=19),
        ElementoDocling(tipo="code", texto="A void f(){}\nB int f(){ return 0; }\nC ...\nD ...\nE ...", pagina=19),
        # Q25 multipágina (p.28 -> p.29) com subheaders Verilog/VHDL e barcode no meio
        ElementoDocling(tipo="section_header", texto="QUESTÃO 25", pagina=28),
        ElementoDocling(tipo="text", texto="Um exemplo de circuito sequencial é o contador de 4 bits.", pagina=28),
        ElementoDocling(
            tipo="picture",
            pagina=28,
            bbox=BoundingBox(90.0, 200.0, 490.0, 420.0),
            page_width=567.0,
            page_height=780.0,
            imagem_png=img_q25_circ,
            img_width_px=984,
            img_height_px=447,
        ),
        ElementoDocling(tipo="section_header", texto="Verilog:", pagina=28),
        ElementoDocling(tipo="code", texto="module contador_4bits(); endmodule", pagina=28),
        ElementoDocling(
            tipo="picture",
            pagina=28,
            bbox=BoundingBox(200.0, 740.0, 320.0, 770.0),
            page_width=567.0,
            page_height=780.0,
            imagem_png=img_barcode,
            img_width_px=240,
            img_height_px=60,
        ),
        ElementoDocling(tipo="section_header", texto="VHDL:", pagina=29),
        ElementoDocling(tipo="code", texto="entity contador_4bits is end entity;", pagina=29),
        ElementoDocling(tipo="list_item", texto="A Verdadeiras e justifica.", pagina=29),
        ElementoDocling(tipo="list_item", texto="B Verdadeiras sem justificativa.", pagina=29),
        ElementoDocling(tipo="list_item", texto="C I verdadeira, II falsa.", pagina=29),
        ElementoDocling(tipo="list_item", texto="D I falsa, II verdadeira.", pagina=29),
        ElementoDocling(tipo="list_item", texto="E Ambas falsas.", pagina=29),
        # Q30 alternativas multiparágrafo
        ElementoDocling(tipo="section_header", texto="QUESTÃO 30", pagina=33),
        ElementoDocling(tipo="text", texto="Assinale a opção com conflito de dados em C.", pagina=33),
        ElementoDocling(tipo="list_item", texto="A Processador 1:", pagina=33),
        ElementoDocling(tipo="text", texto="int a = &A[0][0];", pagina=33),
        ElementoDocling(tipo="text", texto="Processador 2:", pagina=33),
        ElementoDocling(tipo="text", texto="int b = &A[0][0];", pagina=33),
        ElementoDocling(tipo="list_item", texto="B Processador 1:", pagina=33),
        ElementoDocling(tipo="text", texto="*A[0][0] = 10;", pagina=33),
        ElementoDocling(tipo="list_item", texto="C Processador 1:", pagina=33),
        ElementoDocling(tipo="text", texto="*A[0][0] = 10;", pagina=33),
        ElementoDocling(tipo="list_item", texto="D Processador 1:", pagina=33),
        ElementoDocling(tipo="text", texto="int a = &A[0][0];", pagina=33),
        ElementoDocling(tipo="list_item", texto="E Processador 1:", pagina=33),
        ElementoDocling(tipo="text", texto="*A[0][0] = 20;", pagina=33),
        ElementoDocling(tipo="text", texto="VALIDINEP2023VALIDIN3P2023", pagina=33),
        # Questionário de Percepção no final
        ElementoDocling(tipo="section_header", texto="QUESTIONÁRIO DE PERCEPÇÃO DA PROVA", pagina=39),
        ElementoDocling(tipo="section_header", texto="QUESTÃO 10", pagina=39),
    ]

    regioes_chamadas: list[tuple[int, BoundingBox]] = []

    def fake_recorte(regioes: list[tuple[int, BoundingBox]]) -> list[bytes]:
        regioes_chamadas.extend(regioes)
        return [crop_q13_formula for _ in regioes]

    questoes, metadados = posprocessar_elementos(
        elementos,
        FaixaQuestoes(10, 38),
        recortar_formulas_fn=fake_recorte,  # type: ignore[arg-type]
        usou_ocr=False,
        paginas_fonte_symbol=(14, 16, 17, 21, 22, 26, 32),
    )

    por_num = {q.numero: q for q in questoes}
    assert sorted(por_num) == [10, 12, 13, 15, 25, 30]
    assert metadados.total_questoes_extraidas == 6
    assert metadados.imagens_detectadas == 5
    assert metadados.imagens_filtradas_margem == 2
    assert metadados.formulas_recortadas == 1
    assert metadados.usou_ocr is False
    assert metadados.paginas_fonte_symbol == (14, 16, 17, 21, 22, 26, 32)
    assert len(regioes_chamadas) == 1 and regioes_chamadas[0][0] == 17

    # Q10: tabela + imagem real + 5 alternativas + fonte symbol sem alerta crítico
    q10 = por_num[10]
    assert q10.paginas == (14,)
    assert len(q10.alternativas) == 5
    assert len(q10.ativos_visuais) == 1
    assert q10.ativos_visuais[0].origem == OrigemAtivoVisual.PICTURE_DOCLING
    q10_dom = Questao(
        prova_id=uuid4(),
        numero=10,
        enunciado=q10.enunciado,
        paginas=q10.paginas,
        alternativas=[Alternativa(a.letra, a.texto) for a in q10.alternativas],
    )
    alertas_q10 = avaliar_alertas_extracao(
        q10_dom,
        usou_ocr=metadados.usou_ocr,
        paginas_com_fonte_symbol=metadados.paginas_fonte_symbol,
    )
    assert any(a.codigo == CodigoAlertaExtracao.FONTE_SYMBOL_DETECTADA for a in alertas_q10)
    assert not q10_dom.tem_alerta_critico_aberto

    # Q12: prosa "A figura..." preservada no enunciado, 5 alternativas extraídas
    q12 = por_num[12]
    assert "A figura a seguir" in q12.enunciado
    assert "1. Reflexividade." in q12.enunciado
    assert [a.letra for a in q12.alternativas] == list(LetraAlternativa)

    # Q13: marcador formula-not-decoded preservado + FORMULA_RECORTE + PICTURE_DOCLING
    q13 = por_num[13]
    assert MARCADOR_FORMULA_NAO_DECODIFICADA in q13.enunciado
    assert [a.origem for a in q13.ativos_visuais] == [
        OrigemAtivoVisual.PICTURE_DOCLING,
        OrigemAtivoVisual.FORMULA_RECORTE,
    ]
    assert [a.ordem for a in q13.ativos_visuais] == [0, 1]

    # Q15: CodeItem preservado, alternativas vazias -> alerta alternativas_incompletas
    q15 = por_num[15]
    assert "void f()" in q15.enunciado
    assert q15.alternativas == ()

    # Q25: multipágina (28, 29), 5 alternativas e somente 1 figura real
    q25 = por_num[25]
    assert q25.paginas == (28, 29)
    assert len(q25.alternativas) == 5
    assert len(q25.ativos_visuais) == 1
    assert "Verilog:" in q25.enunciado and "VHDL:" in q25.enunciado

    # Q30: alternativas multiparágrafo preservadas sem watermark
    q30 = por_num[30]
    assert len(q30.alternativas) == 5
    assert "Processador 1:\n\nint a = &A[0][0];\n\nProcessador 2:\n\nint b = &A[0][0];" == q30.alternativas[0].texto
    assert "VALID" not in q30.alternativas[-1].texto


def test_cmap_mojibake_e_deteccao_symbol_regras_puras() -> None:
    mojibake_2017 = "\x04ĮŐƵƌĂĂƐĞŐƵŝƌƌĞƉƌĞƐĞŶƚĂŽĚŝĂŐƌĂŵĂĚĞƚĞŶƐĆŽ\x12\x1c" * 3
    texto_limpo_2019 = "Considerando o texto apresentado, avalie as afirmações a seguir sobre sistemas."
    texto_euclid_2023 = "Para todo a Î S, a R a e a R b Û b R a conforme definição matemática formal."

    assert texto_indica_cmap_corrompido(mojibake_2017) is True
    assert texto_indica_cmap_corrompido("(cid:4)(cid:3)(cid:302) texto corrompido") is True
    assert texto_indica_cmap_corrompido(texto_limpo_2019) is False
    assert texto_indica_cmap_corrompido(texto_limpo_2019 + " \ufffd") is False
    assert texto_indica_cmap_corrompido(texto_euclid_2023) is False

    assert nome_fonte_indica_symbol("UVHADP+EuclidSymbol-BoldItalic") is True
    assert nome_fonte_indica_symbol("GIHPPR+SymbolMT") is True
    assert nome_fonte_indica_symbol("SymbolM2") is True
    assert nome_fonte_indica_symbol("MT-Extra") is True
    assert nome_fonte_indica_symbol("CourierNewPSMT") is False
    assert nome_fonte_indica_symbol("ArialMT") is False


def test_inspecao_pdf_erros_e_pdf_sem_texto(tmp_path: Path) -> None:
    pdf_path = _criar_pdf_imagem(tmp_path / "imagem.pdf", num_paginas=2)
    assert detectar_cmap_corrompido(pdf_path) is False
    assert detectar_paginas_fonte_symbol(pdf_path) == ()

    with pytest.raises(FileNotFoundError):
        detectar_cmap_corrompido(tmp_path / "inexistente.pdf")
    with pytest.raises(FileNotFoundError):
        detectar_paginas_fonte_symbol(tmp_path / "inexistente.pdf")


def test_extrator_prova_docling_invoca_subprocesso_isolado_sem_torch_no_pai(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = _criar_pdf_imagem(tmp_path / "prova.pdf", num_paginas=1)

    doc = DoclingDocument(name="prova")
    doc.add_page(page_no=1, size={"width": 400.0, "height": 600.0})  # type: ignore[arg-type]
    doc.add_text(label="section_header", text="QUESTÃO 10")  # type: ignore[arg-type]
    doc.add_text(label="text", text="Enunciado de teste válido com texto suficiente.")  # type: ignore[arg-type]
    doc_json = doc.model_dump_json()

    chamadas: list[tuple[Path, Path, bool]] = []

    def fake_worker(self: ExtratorProvaDocling, pdf_p: Path, json_out: Path, *, usar_ocr: bool) -> None:
        chamadas.append((pdf_p, json_out, usar_ocr))
        json_out.write_text(doc_json, encoding="utf-8")

    monkeypatch.setattr("infrastructure.extracao.extrator_prova.detectar_cmap_corrompido", lambda _p: True)
    monkeypatch.setattr("infrastructure.extracao.extrator_prova.detectar_paginas_fonte_symbol", lambda _p: (1,))
    monkeypatch.setattr(ExtratorProvaDocling, "_executar_worker", fake_worker)

    extrator = ExtratorProvaDocling()
    assert isinstance(extrator, ExtratorProva)

    res = extrator.extrair(pdf_path, FaixaQuestoes(10, 38))
    assert len(chamadas) == 1
    assert chamadas[0][0] == pdf_path
    assert chamadas[0][2] is True
    assert res.metadados.usou_ocr is True
    assert res.metadados.paginas_fonte_symbol == (1,)
    assert len(res.questoes) == 1
    assert res.questoes[0].numero == 10
    assert "torch" not in sys.modules

    elementos = docling_document_para_elementos(doc)
    assert len(elementos) == 2

    with pytest.raises(FileNotFoundError):
        extrator.extrair(tmp_path / "ausente.pdf", FaixaQuestoes(10, 38))
    with pytest.raises(ErroValidacaoDominio):
        ExtratorProvaDocling(timeout_s=0)
