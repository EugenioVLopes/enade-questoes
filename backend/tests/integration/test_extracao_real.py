"""Testes de integração contra os cadernos e gabaritos reais do ENADE em data/enade/."""

from __future__ import annotations

import json
import sys
import time
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pypdfium2 as pdfium
import pytest
from PIL import Image

from domain.alertas_extracao import (
    MARCADOR_FORMULA_NAO_DECODIFICADA,
    avaliar_alertas_extracao,
)
from domain.enums import (
    CodigoAlertaExtracao,
    LetraAlternativa,
    OrigemAtivoVisual,
    SituacaoGabarito,
    TipoQuestao,
)
from domain.exceptions import ErroValidacaoDominio
from domain.prova import Alternativa, FaixaQuestoes, Gabarito, Questao
from infrastructure.extracao import (
    ExtratorGabaritoPdfPlumber,
    ExtratorProvaDocling,
    RenderizadorPaginaPdfPypdfium2,
)
from infrastructure.extracao.inspecao_pdf import (
    detectar_cmap_corrompido,
    detectar_paginas_fonte_symbol,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_ENADE = REPO_ROOT / "data" / "enade"

PROVA_2017 = DATA_ENADE / "2017" / "prova_enade_2017_engenharia_computacao.pdf"
GAB_2017 = DATA_ENADE / "2017" / "gabarito_enade_2017_engenharia_computacao.pdf"
PROVA_2019 = DATA_ENADE / "2019" / "prova_enade_2019_engenharia_computacao.pdf"
GAB_2019 = DATA_ENADE / "2019" / "gabarito_enade_2019_engenharia_computacao.pdf"
PROVA_2023 = DATA_ENADE / "2023" / "prova_enade_2023_engenharia_computacao.pdf"
GAB_2023 = DATA_ENADE / "2023" / "gabarito_enade_2023_engenharia_computacao.pdf"

_TODOS_PDFS = (PROVA_2017, GAB_2017, PROVA_2019, GAB_2019, PROVA_2023, GAB_2023)

pytestmark = pytest.mark.enade_real


def _exigir_pdfs_enade() -> None:
    ausentes = [str(p) for p in _TODOS_PDFS if not p.is_file()]
    if ausentes:
        pytest.skip(f"PDFs oficiais do ENADE ausentes localmente: {ausentes}")


def _fatiar_paginas_pdf(origem: Path, paginas_1based: list[int], destino: Path) -> Path:
    src = pdfium.PdfDocument(str(origem))
    dst = pdfium.PdfDocument.new()
    try:
        dst.import_pages(src, pages=[p - 1 for p in paginas_1based])
        dst.save(str(destino))
    finally:
        dst.close()
        src.close()
    return destino


def test_extracao_gabaritos_reais_em_menos_de_500ms() -> None:
    _exigir_pdfs_enade()
    extrator = ExtratorGabaritoPdfPlumber()

    t0 = time.perf_counter()
    res_2017 = extrator.extrair(GAB_2017)
    dur_2017 = time.perf_counter() - t0
    assert dur_2017 < 0.5
    assert len(res_2017.mapa_objetivas()) == 35
    assert all(item.tipo == TipoQuestao.OBJETIVA for item in res_2017.itens)

    t0 = time.perf_counter()
    res_2019 = extrator.extrair(GAB_2019)
    dur_2019 = time.perf_counter() - t0
    assert dur_2019 < 0.5
    mapa_2019 = res_2019.mapa_objetivas()
    assert len(mapa_2019) == 35
    assert mapa_2019[1] == Gabarito(SituacaoGabarito.ANULADA)

    t0 = time.perf_counter()
    res_2023 = extrator.extrair(GAB_2023)
    dur_2023 = time.perf_counter() - t0
    assert dur_2023 < 0.5
    discursivas_2023 = [i for i in res_2023.itens if i.tipo == TipoQuestao.DISCURSIVA]
    assert len(discursivas_2023) == 2
    assert all(d.gabarito == Gabarito(SituacaoGabarito.PENDENTE) for d in discursivas_2023)
    assert len(res_2023.mapa_objetivas()) == 38


def test_renderizador_real_2023() -> None:
    _exigir_pdfs_enade()
    renderizador = RenderizadorPaginaPdfPypdfium2()

    assert renderizador.contar_paginas(PROVA_2023) == 40
    png_bytes = renderizador.renderizar_pagina(PROVA_2023, pagina=14, dpi=150)
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    with Image.open(BytesIO(png_bytes)) as img:
        assert img.mode == "RGB"
        assert img.width > 1000 and img.height > 1400

    with pytest.raises(ErroValidacaoDominio):
        renderizador.renderizar_pagina(PROVA_2023, pagina=0)
    with pytest.raises(ErroValidacaoDominio):
        renderizador.renderizar_pagina(PROVA_2023, pagina=41)


def test_inspecao_cmap_e_symbol_nas_tres_edicoes() -> None:
    _exigir_pdfs_enade()
    assert detectar_cmap_corrompido(PROVA_2017) is True
    assert detectar_cmap_corrompido(PROVA_2019) is False
    assert detectar_cmap_corrompido(PROVA_2023) is False

    paginas_2023 = detectar_paginas_fonte_symbol(PROVA_2023)
    assert 14 in paginas_2023
    assert 17 in paginas_2023
    assert 32 in paginas_2023

    assert 13 in detectar_paginas_fonte_symbol(PROVA_2019)
    assert 17 in detectar_paginas_fonte_symbol(PROVA_2017)


def test_extracao_completa_enade_2023_em_subprocesso_isolado() -> None:
    _exigir_pdfs_enade()
    extrator = ExtratorProvaDocling()
    res = extrator.extrair(PROVA_2023, FaixaQuestoes(10, 38))

    assert "torch" not in sys.modules
    assert res.metadados.usou_ocr is False
    assert res.metadados.total_questoes_extraidas == 29
    assert [q.numero for q in res.questoes] == list(range(10, 39))
    assert res.metadados.imagens_filtradas_margem > 0
    assert res.metadados.imagens_detectadas > res.metadados.imagens_filtradas_margem
    assert res.metadados.formulas_recortadas >= 1
    assert 14 in res.metadados.paginas_fonte_symbol

    bruto = json.loads(res.extracao_bruta_json)
    assert isinstance(bruto, dict) and "pages" in bruto

    por_num = {q.numero: q for q in res.questoes}
    for q in res.questoes:
        assert "VALIDINEP" not in q.enunciado
        assert "VALIDIN3P" not in q.enunciado
        assert "VALIDDIN" not in q.enunciado

    # Q10: circuito + tabela + 5 alternativas + fonte symbol informativa (sem alerta crítico)
    q10 = por_num[10]
    assert q10.paginas == (14,)
    assert [a.letra for a in q10.alternativas] == list(LetraAlternativa)
    assert any(a.origem == OrigemAtivoVisual.PICTURE_DOCLING for a in q10.ativos_visuais)
    q10_dom = Questao(
        prova_id=uuid4(),
        numero=10,
        enunciado=q10.enunciado,
        paginas=q10.paginas,
        alternativas=[Alternativa(a.letra, a.texto) for a in q10.alternativas],
    )
    alertas_q10 = avaliar_alertas_extracao(
        q10_dom,
        usou_ocr=res.metadados.usou_ocr,
        paginas_com_fonte_symbol=res.metadados.paginas_fonte_symbol,
    )
    assert any(a.codigo == CodigoAlertaExtracao.FONTE_SYMBOL_DETECTADA for a in alertas_q10)
    assert not q10_dom.tem_alerta_critico_aberto

    # Q13: FormulaItem recortado como FORMULA_RECORTE + marcador preservado
    q13 = por_num[13]
    assert MARCADOR_FORMULA_NAO_DECODIFICADA in q13.enunciado
    formulas_q13 = [a for a in q13.ativos_visuais if a.origem == OrigemAtivoVisual.FORMULA_RECORTE]
    assert len(formulas_q13) == 1
    assert formulas_q13[0].pagina == 17
    assert formulas_q13[0].bbox is not None
    assert formulas_q13[0].conteudo_png.startswith(b"\x89PNG\r\n\x1a\n")
    q13_dom = Questao(prova_id=uuid4(), numero=13, enunciado=q13.enunciado, paginas=q13.paginas)
    alertas_q13 = avaliar_alertas_extracao(q13_dom)
    assert any(a.codigo == CodigoAlertaExtracao.FORMULA_NAO_DECODIFICADA for a in alertas_q13)

    # Q15: bloco C preservado no enunciado -> alerta alternativas_incompletas
    q15 = por_num[15]
    assert q15.alternativas == ()
    assert "malloc" in q15.enunciado

    # Q25: questão multipágina (p.28 -> p.29) intacta
    q25 = por_num[25]
    assert q25.paginas == (28, 29)
    assert [a.letra for a in q25.alternativas] == list(LetraAlternativa)

    # Q30: alternativas multiparágrafo
    q30 = por_num[30]
    assert [a.letra for a in q30.alternativas] == list(LetraAlternativa)
    assert "Processador 1:" in q30.alternativas[0].texto
    assert "Processador 2:" in q30.alternativas[0].texto


def test_extracao_enade_2017_aciona_ocr_por_cmap_corrompido(tmp_path: Path) -> None:
    _exigir_pdfs_enade()
    sub_2017 = _fatiar_paginas_pdf(PROVA_2017, [17, 18], tmp_path / "subset_2017.pdf")

    extrator = ExtratorProvaDocling()
    res = extrator.extrair(sub_2017, FaixaQuestoes(9, 13))

    assert "torch" not in sys.modules
    assert res.metadados.usou_ocr is True
    assert res.metadados.total_questoes_extraidas >= 3

    por_num = {q.numero: q for q in res.questoes}
    assert 10 in por_num
    q10_texto = por_num[10].enunciado.lower()
    assert "diagrama" in q10_texto
    assert "\x04" not in q10_texto
    assert "ĮŐƵƌĂ" not in por_num[10].enunciado

    q10_dom = Questao(
        prova_id=uuid4(),
        numero=10,
        enunciado=por_num[10].enunciado,
        paginas=por_num[10].paginas,
        alternativas=[Alternativa(a.letra, a.texto) for a in por_num[10].alternativas],
    )
    alertas_q10 = avaliar_alertas_extracao(q10_dom, usou_ocr=res.metadados.usou_ocr)
    assert any(a.codigo == CodigoAlertaExtracao.PDF_VIA_OCR for a in alertas_q10)


def test_extracao_enade_2019_trunca_percepcao_sem_sobrescrever_q09(tmp_path: Path) -> None:
    _exigir_pdfs_enade()
    sub_2019 = _fatiar_paginas_pdf(PROVA_2019, [16, 22, 23, 24, 38], tmp_path / "subset_2019.pdf")

    extrator = ExtratorProvaDocling()
    res = extrator.extrair(sub_2019, FaixaQuestoes(9, 35))

    assert "torch" not in sys.modules
    assert res.metadados.usou_ocr is False
    assert res.metadados.total_questoes_extraidas == 5
    assert res.metadados.imagens_filtradas_margem >= 8
    assert res.metadados.paginas_fonte_symbol == (3, 4)

    por_num = {q.numero: q for q in res.questoes}
    assert sorted(por_num) == [9, 16, 17, 18, 19]
    assert "MergeSort" in por_num[9].enunciado
    assert "percepção" not in por_num[9].enunciado.lower()
    assert len(por_num[16].ativos_visuais) == 1
    assert len(por_num[17].ativos_visuais) == 1
    assert [a.letra for a in por_num[16].alternativas] == list(LetraAlternativa)
