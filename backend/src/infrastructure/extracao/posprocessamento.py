"""Pós-processamento determinístico de saída do Docling para questões e ativos do ENADE."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from application.ports.extracao import (
    AlternativaExtraida,
    AtivoVisualExtraido,
    QuestaoExtraida,
)
from domain.alertas_extracao import MARCADOR_FORMULA_NAO_DECODIFICADA
from domain.enums import LetraAlternativa, OrigemAtivoVisual
from domain.prova import BoundingBox, FaixaQuestoes, MetadadosIngestao

TipoElementoDocling = Literal[
    "section_header",
    "text",
    "list_item",
    "table",
    "code",
    "picture",
    "formula",
]

_PERCEPTION_RE = re.compile(
    r"^\s*(?:[#*>\s_`]*)(?:QUESTION[ÁA]RIO\s+DE\s+PERCEP[ÇC][ÃA]O)\b",
    re.IGNORECASE,
)
_QUESTAO_HDR_RE = re.compile(
    r"^(?:[#*>\s_`]*)(?:QUEST[ÃA]O)\s+0?(\d{1,2})\b(?!\s+DISCURSIVA)",
    re.IGNORECASE,
)
_QUESTAO_DISCURSIVA_HDR_RE = re.compile(
    r"^(?:[#*>\s_`]*)(?:QUEST[ÃA]O)\s+DISCURSIVA\b",
    re.IGNORECASE,
)
_ALT_LIST_RE = re.compile(r"^([A-E])(?:\s*[).]\s*|\s+)(.+)$", re.DOTALL)
_ALT_EXPLICIT_PUNCT_RE = re.compile(r"^([A-E])\s*[).]\s*(.+)$", re.DOTALL)
_ALT_MARKER_RE = re.compile(r"^([A-E])[).]?$")
_STEM_CUE_AFTER_LIST_RE = re.compile(
    r"^(?:É\s+correto|Assinale|A\s+respeito|Com\s+base|Considerando)\b",
    re.IGNORECASE,
)

# Ruídos textuais observados em cadernos reais do INEP/ENADE:
# - Marca d'água VALIDINEP2023 / VALIDIN3P2023 / VALIDINEEP2023 / VALIDDIN (preservando 'validado' etc.)
# - Código de caderno *R082023XX*
# - Rótulo 'ÁREA LIVRE' isolado em linha
# - Cabeçalho/rodapé isolado 'ENGENHARIA DE COMPUTAÇÃO' (com eventual número de página adjacente)
_WATERMARK_RE = re.compile(r"(?:VALIDIN[E3]+P\w*|VALIDDIN\w*)+", re.IGNORECASE)
_BARCODE_TEXT_RE = re.compile(r"\*R\d[0-9A-Z]{4,}\*")
_AREA_LIVRE_LINE_RE = re.compile(r"^\s*(?:#+\s*)?[ÁA]REA\s+LIVRE\s*$", re.IGNORECASE)
_CURSO_HEADER_LINE_RE = re.compile(
    r"^\s*(?:#+\s*)?(?:\d+\s+)?ENGENHARIA\s+DE\s+COMPUTA[ÇC][ÃA]O(?:\s+\d+)?\s*$",
    re.IGNORECASE,
)
_MULTI_BLANK_RE = re.compile(r"\n{3,}")

_MARGEM_SUPERIOR_MAX_RATIO = 0.12
_MARGEM_INFERIOR_MIN_RATIO = 0.88
_MARGEM_LARGURA_MAX_PT = 200.0
_MARGEM_ALTURA_MAX_PT = 75.0
_MIN_LARGURA_FIGURA_PT = 90.0
_MIN_ALTURA_FIGURA_PT = 55.0
_MIN_AREA_FIGURA_PT2 = 10_000.0
_MIN_LARGURA_FIGURA_PX = 180
_MIN_ALTURA_FIGURA_PX = 110


@dataclass(frozen=True, slots=True)
class ElementoDocling:
    """Representação normalizada e pura de um item extraído pelo Docling."""

    tipo: TipoElementoDocling
    texto: str = ""
    pagina: int = 1
    bbox: BoundingBox | None = None
    page_width: float = 0.0
    page_height: float = 0.0
    imagem_png: bytes | None = None
    img_width_px: int = 0
    img_height_px: int = 0
    marker: str = ""
    enumerated: bool = False


def limpar_ruido_textual(texto: str) -> str:
    """Remove marcas d'água, códigos de barra textuais e cabeçalhos/rótulos isolados."""
    if not texto:
        return ""

    sem_watermark = _WATERMARK_RE.sub("", texto)
    sem_codigo = _BARCODE_TEXT_RE.sub("", sem_watermark)

    linhas_limpas: list[str] = []
    for linha in sem_codigo.splitlines():
        if _AREA_LIVRE_LINE_RE.match(linha):
            continue
        if _CURSO_HEADER_LINE_RE.match(linha):
            continue
        limpa = linha.strip()
        if limpa:
            linhas_limpas.append(limpa)
        elif linhas_limpas and linhas_limpas[-1] != "":
            linhas_limpas.append("")

    resultado = "\n".join(linhas_limpas).strip()
    return _MULTI_BLANK_RE.sub("\n\n", resultado)


def _parece_cabecalho_questao(elemento: ElementoDocling) -> int | None:
    if elemento.tipo not in {"section_header", "text"}:
        return None
    texto = elemento.texto.strip()
    if not texto:
        return None
    m = _QUESTAO_HDR_RE.match(texto)
    if not m:
        return None
    if elemento.tipo == "section_header" or len(texto) <= 45 or texto.startswith(("QUESTÃO", "QUESTAO")):
        return int(m.group(1))
    return None


def _eh_marcador_percepcao_fim(elemento: ElementoDocling, *, ja_viu_questao: bool) -> bool:
    if elemento.tipo not in {"section_header", "text"}:
        return False
    texto = elemento.texto.strip()
    if not texto or len(texto) > 80:
        return False
    if not _PERCEPTION_RE.match(texto):
        return False
    return ja_viu_questao or (elemento.tipo == "section_header" and elemento.pagina >= 5)


def truncar_questionario_percepcao(elementos: Sequence[ElementoDocling]) -> list[ElementoDocling]:
    """Trunca antes do ``QUESTIONÁRIO DE PERCEPÇÃO`` final sem falso positivo na capa."""
    ja_viu_questao = False
    idx_marcador: int | None = None
    marcador: ElementoDocling | None = None

    for idx, elem in enumerate(elementos):
        if _eh_marcador_percepcao_fim(elem, ja_viu_questao=ja_viu_questao):
            idx_marcador = idx
            marcador = elem
            break
        if _parece_cabecalho_questao(elem) is not None or _QUESTAO_DISCURSIVA_HDR_RE.match(elem.texto.strip()):
            ja_viu_questao = True

    if idx_marcador is None or marcador is None:
        return list(elementos)

    pagina_marcador = marcador.pagina
    bbox_marcador = marcador.bbox
    mantidos: list[ElementoDocling] = []
    for elem in elementos[:idx_marcador]:
        if elem.pagina > pagina_marcador:
            continue
        if (
            elem.pagina == pagina_marcador
            and bbox_marcador is not None
            and elem.bbox is not None
            and elem.bbox.y0 >= bbox_marcador.y0 - 2.0
        ):
            # Proteção contra ordem de leitura invertida (ex.: ENADE 2019 p. 38)
            continue
        mantidos.append(elem)
    return mantidos


def filtrar_imagem_margem_ou_pequena(elemento: ElementoDocling) -> bool:
    """Retorna True se ``PictureItem`` for barcode/logo de margem ou figura muito pequena."""
    bbox = elemento.bbox
    if bbox is not None:
        w_pt = bbox.x1 - bbox.x0
        h_pt = bbox.y1 - bbox.y0
        if elemento.page_height > 0:
            y0_ratio = bbox.y0 / elemento.page_height
            y1_ratio = bbox.y1 / elemento.page_height
            em_margem = y1_ratio <= _MARGEM_SUPERIOR_MAX_RATIO or y0_ratio >= _MARGEM_INFERIOR_MIN_RATIO
            if em_margem and (w_pt <= _MARGEM_LARGURA_MAX_PT or h_pt <= _MARGEM_ALTURA_MAX_PT):
                return True
        if w_pt < _MIN_LARGURA_FIGURA_PT or h_pt < _MIN_ALTURA_FIGURA_PT or (w_pt * h_pt) < _MIN_AREA_FIGURA_PT2:
            return True
        return False

    if elemento.img_width_px > 0 and elemento.img_height_px > 0:
        return elemento.img_width_px < _MIN_LARGURA_FIGURA_PX or elemento.img_height_px < _MIN_ALTURA_FIGURA_PX
    return False


def _extrair_inicio_alternativa(elemento: ElementoDocling) -> tuple[LetraAlternativa, str, bool] | None:
    if elemento.tipo != "list_item":
        return None
    texto = elemento.texto.strip()
    marker = elemento.marker.strip()
    if marker:
        m_marker = _ALT_MARKER_RE.match(marker)
        if m_marker and texto:
            return LetraAlternativa(m_marker.group(1)), texto, True

    m_punct = _ALT_EXPLICIT_PUNCT_RE.match(texto)
    if m_punct:
        corpo = m_punct.group(2).strip()
        if corpo:
            return LetraAlternativa(m_punct.group(1)), corpo, True

    m_plain = _ALT_LIST_RE.match(texto)
    if m_plain:
        corpo = m_plain.group(2).strip()
        if corpo:
            return LetraAlternativa(m_plain.group(1)), corpo, False
    return None


def _renderizar_elemento_enunciado(elemento: ElementoDocling) -> str:
    if elemento.tipo == "section_header":
        return f"## {elemento.texto.strip()}" if elemento.texto.strip() else ""
    if elemento.tipo == "code":
        return f"```\n{elemento.texto.strip()}\n```" if elemento.texto.strip() else ""
    if elemento.tipo == "table":
        return elemento.texto.strip()
    if elemento.tipo == "formula":
        return elemento.texto.strip() or MARCADOR_FORMULA_NAO_DECODIFICADA
    if elemento.tipo == "list_item":
        texto = elemento.texto.strip()
        if not texto:
            return ""
        marker = elemento.marker.strip()
        if marker and not texto.startswith(marker):
            return f"{marker} {texto}" if elemento.enumerated else f"- {marker} {texto}"
        return f"- {texto}"
    if elemento.tipo == "text":
        return elemento.texto.strip()
    return ""


def _separar_enunciado_e_alternativas(
    itens: Sequence[ElementoDocling],
) -> tuple[str, tuple[AlternativaExtraida, ...]]:
    # Localiza o último bloco válido de alternativas iniciando em 'A'
    candidatos_inicio: list[int] = []
    for idx, item in enumerate(itens):
        parsed = _extrair_inicio_alternativa(item)
        if parsed is not None and parsed[0] == LetraAlternativa.A:
            candidatos_inicio.append(idx)

    inicio_alts: int | None = None
    for idx_a in reversed(candidatos_inicio):
        # Rejeita se houver um prompt de enunciado ("É correto...", "Assinale...") após este item
        tem_prompt_posterior = any(
            item.tipo in {"section_header", "text"} and _STEM_CUE_AFTER_LIST_RE.match(item.texto.strip())
            for item in itens[idx_a + 1 :]
        )
        if tem_prompt_posterior:
            continue

        letras_vistas: list[LetraAlternativa] = []
        primeiro = _extrair_inicio_alternativa(itens[idx_a])
        if primeiro is None:
            continue
        letras_vistas.append(primeiro[0])
        tem_pontuacao_explicita = primeiro[2]

        for item in itens[idx_a + 1 :]:
            parsed = _extrair_inicio_alternativa(item)
            if parsed is not None and parsed[0].value > letras_vistas[-1].value:
                letras_vistas.append(parsed[0])

        if len(letras_vistas) >= 2 or tem_pontuacao_explicita:
            inicio_alts = idx_a
            break

    if inicio_alts is None:
        partes = [_renderizar_elemento_enunciado(it) for it in itens]
        enunciado = "\n\n".join(p for p in partes if p)
        return enunciado, ()

    partes_enunciado = [_renderizar_elemento_enunciado(it) for it in itens[:inicio_alts]]
    enunciado = "\n\n".join(p for p in partes_enunciado if p)

    alternativas_buf: list[tuple[LetraAlternativa, list[str]]] = []
    for item in itens[inicio_alts:]:
        parsed = _extrair_inicio_alternativa(item)
        if parsed is not None:
            letra, corpo, _ = parsed
            if not alternativas_buf or letra.value > alternativas_buf[-1][0].value:
                alternativas_buf.append((letra, [corpo]))
                continue

        if alternativas_buf:
            if item.tipo == "formula":
                alternativas_buf[-1][1].append(item.texto.strip() or MARCADOR_FORMULA_NAO_DECODIFICADA)
            elif item.tipo == "code" and item.texto.strip():
                alternativas_buf[-1][1].append(f"```\n{item.texto.strip()}\n```")
            elif item.tipo in {"text", "table"} and item.texto.strip():
                alternativas_buf[-1][1].append(item.texto.strip())

    alternativas = tuple(
        AlternativaExtraida(letra=letra, texto="\n\n".join(blocos).strip()) for letra, blocos in alternativas_buf
    )
    return enunciado, alternativas


def posprocessar_elementos(
    elementos: Sequence[ElementoDocling],
    faixa_ce: FaixaQuestoes,
    *,
    recortar_formulas_fn: Callable[[Sequence[tuple[int, BoundingBox]]], Sequence[bytes]],
    usou_ocr: bool = False,
    paginas_fonte_symbol: Sequence[int] = (),
) -> tuple[tuple[QuestaoExtraida, ...], MetadadosIngestao]:
    """Executa truncamento, limpeza, filtro de margem/dimensão, recorte de fórmulas e segmentação CE."""
    truncados = truncar_questionario_percepcao(elementos)

    blocos_por_questao: dict[int, list[ElementoDocling]] = {}
    questoes_fechadas: set[int] = set()
    questao_atual: int | None = None

    imagens_detectadas = 0
    imagens_filtradas_margem = 0

    for elem in truncados:
        if elem.tipo == "picture":
            imagens_detectadas += 1
            if filtrar_imagem_margem_ou_pequena(elem):
                imagens_filtradas_margem += 1
                continue
            if questao_atual is not None:
                blocos_por_questao[questao_atual].append(elem)
            continue

        if elem.tipo == "code":
            if questao_atual is not None:
                blocos_por_questao[questao_atual].append(elem)
            continue

        if elem.tipo == "formula":
            if questao_atual is not None:
                blocos_por_questao[questao_atual].append(elem)
            continue

        texto_limpo = limpar_ruido_textual(elem.texto) if elem.tipo != "table" else elem.texto.strip()
        if not texto_limpo:
            continue

        elem_limpo = ElementoDocling(
            tipo=elem.tipo,
            texto=texto_limpo,
            pagina=elem.pagina,
            bbox=elem.bbox,
            page_width=elem.page_width,
            page_height=elem.page_height,
            imagem_png=elem.imagem_png,
            img_width_px=elem.img_width_px,
            img_height_px=elem.img_height_px,
            marker=elem.marker,
            enumerated=elem.enumerated,
        )

        if _QUESTAO_DISCURSIVA_HDR_RE.match(texto_limpo):
            if questao_atual is not None:
                questoes_fechadas.add(questao_atual)
            questao_atual = None
            continue

        qnum = _parece_cabecalho_questao(elem_limpo)
        if qnum is not None:
            if questao_atual is not None and questao_atual != qnum:
                questoes_fechadas.add(questao_atual)

            if faixa_ce.contem(qnum) and qnum not in questoes_fechadas:
                questao_atual = qnum
                blocos_por_questao.setdefault(qnum, [])
                # Preserva eventual texto na mesma linha após "QUESTÃO NN"
                m_hdr = _QUESTAO_HDR_RE.match(texto_limpo)
                if m_hdr:
                    resto = texto_limpo[m_hdr.end() :].strip(" :.-")
                    if resto:
                        blocos_por_questao[qnum].append(
                            ElementoDocling(
                                tipo="text",
                                texto=resto,
                                pagina=elem_limpo.pagina,
                                bbox=elem_limpo.bbox,
                                page_width=elem_limpo.page_width,
                                page_height=elem_limpo.page_height,
                            )
                        )
            else:
                questao_atual = None
            continue

        if questao_atual is not None:
            blocos_por_questao[questao_atual].append(elem_limpo)

    # Prepara lote de recortes de FormulaItem dentro das questões do CE mantidas
    requisicoes_formula: list[tuple[int, BoundingBox]] = []
    indice_formula_por_elem: dict[tuple[int, int], int] = {}
    for qnum in sorted(blocos_por_questao):
        for idx_item, item in enumerate(blocos_por_questao[qnum]):
            if item.tipo == "formula" and item.bbox is not None and item.pagina >= 1:
                indice_formula_por_elem[(qnum, idx_item)] = len(requisicoes_formula)
                requisicoes_formula.append((item.pagina, item.bbox))

    recortes_formula = list(recortar_formulas_fn(requisicoes_formula)) if requisicoes_formula else []

    questoes_extraidas: list[QuestaoExtraida] = []
    formulas_recortadas = 0

    for qnum in sorted(blocos_por_questao):
        itens_q = blocos_por_questao[qnum]
        enunciado, alternativas = _separar_enunciado_e_alternativas(itens_q)
        paginas = tuple(sorted({item.pagina for item in itens_q if item.pagina >= 1}))

        ativos: list[AtivoVisualExtraido] = []
        ordem = 0
        for idx_item, item in enumerate(itens_q):
            if item.tipo == "picture" and item.imagem_png and item.pagina >= 1:
                ativos.append(
                    AtivoVisualExtraido(
                        origem=OrigemAtivoVisual.PICTURE_DOCLING,
                        conteudo_png=item.imagem_png,
                        ordem=ordem,
                        pagina=item.pagina,
                        bbox=item.bbox,
                    )
                )
                ordem += 1
            elif item.tipo == "formula":
                idx_recorte = indice_formula_por_elem.get((qnum, idx_item))
                if idx_recorte is not None and idx_recorte < len(recortes_formula):
                    png_bytes = recortes_formula[idx_recorte]
                    if png_bytes:
                        ativos.append(
                            AtivoVisualExtraido(
                                origem=OrigemAtivoVisual.FORMULA_RECORTE,
                                conteudo_png=png_bytes,
                                ordem=ordem,
                                pagina=item.pagina,
                                bbox=item.bbox,
                            )
                        )
                        ordem += 1
                        formulas_recortadas += 1

        questoes_extraidas.append(
            QuestaoExtraida(
                numero=qnum,
                enunciado=enunciado,
                paginas=paginas,
                alternativas=alternativas,
                ativos_visuais=tuple(ativos),
            )
        )

    paginas_symbol_norm = tuple(sorted({p for p in paginas_fonte_symbol if p >= 1}))
    metadados = MetadadosIngestao(
        total_questoes_extraidas=len(questoes_extraidas),
        imagens_detectadas=imagens_detectadas,
        imagens_filtradas_margem=imagens_filtradas_margem,
        formulas_recortadas=formulas_recortadas,
        usou_ocr=usou_ocr,
        paginas_fonte_symbol=paginas_symbol_norm,
        gabarito_enviado=False,
    )
    return tuple(questoes_extraidas), metadados
