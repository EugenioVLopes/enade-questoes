# Comparar ferramentas de extração de PDF para provas do ENADE (Docling vs alternativas)

Type: research
Status: resolved
Blocked by: none

## Question

Como o **Docling** se compara às principais alternativas para converter provas acadêmicas brasileiras em PDF (layout de duas colunas, cabeçalhos/rodapés repetidos, figuras/diagramas/circuitos, tabelas, equações e blocos de código) — em especial **PyMuPDF (`pymupdf` / `pymupdf4llm`)**, **pdfplumber**, **Marker** e o canal **renderização (`pypdfium2`) + modelo de visão (VLM)**?

Investigar em fontes primárias (documentação oficial e repositórios):
1. Capacidade de preservar ordem de leitura em layout de duas colunas.
2. Extração e recorte de figuras/imagens vinculadas ao fluxo da questão (bounding boxes / exportação de imagens).
3. Qualidade em tabelas, trechos de código e fórmulas matemáticas.
4. Requisitos de execução local em máquina sem GPU dedicada (CPU, memória, tamanho de modelos baixados, velocidade por página) e compatibilidade com Python 3.13 + `uv`.
5. Recomendação objetiva de quais 2 abordagens levar para o protótipo em prova real ([Prototipar extração em uma prova real do ENADE (Docling vs alternativa)](./05-prototipar-extracao-prova-real.md)).


## Answer

A comparação em fontes primárias (PyPI, documentação oficial e Hugging Face) recomenda levar **2 abordagens complementares** para o protótipo em prova real ([05-prototipar-extracao-prova-real.md](./05-prototipar-extracao-prova-real.md)):

1. **Docling (`2.151.1`, MIT)** — com `PyPdfiumDocumentBackend`, `do_ocr=False`, `generate_picture_images=True`, `do_table_structure=True` (`TableFormer`) e teste A/B de `do_code_enrichment`/`do_formula_enrichment` (`CodeFormulaV2`), configurado com índice `pytorch-cpu` no `uv` (~320–385 MB de pesos base; ~1 GB com `CodeFormulaV2`). Entrega o conjunto mais completo em licença permissiva para duas colunas, separação de cabeçalho/rodapé (`furniture`), recorte de figuras vetoriais/bitmap com `bbox` vinculada ao fluxo (`PictureItem`) e tabelas complexas.
2. **PyMuPDF `2.1` (`pymupdf` + `pymupdf4llm` + `pymupdf-layout`, Dual AGPL-3.0 / comercial)** — linha de base ultrarrápida em CPU **sem PyTorch** (usa `onnxruntime`), com detecção multi-coluna, `header=False`/`footer=False`, preservação de blocos de código monoespaçados e recorte de figuras (`write_images=True` / `to_json()`). Ponto fraco: sem conversor neural de fórmulas para LaTeX e alerta de licença AGPL-3.0 caso o sistema seja distribuído fechado.

**Papel das demais opções:** `pdfplumber` (MIT) é fraco para duas colunas automáticas e figuras vetoriais, mas excelente auxiliar determinístico para o **gabarito oficial em tabela**; `Marker 2.2.0` (Apache-2.0 / pesos OpenRAIL-M) fica como 3ª opção reserva em CPU (`--mode fast --ocr_inline_math`) caso fórmulas sejam decisivas; e `pypdfium2 + VLM` não convém como extrator primário da prova inteira sem GPU (custo, ~35 s/pág, não determinismo e ausência de recorte nativo de figuras), servindo apenas como fallback pontual sobre recortes difíceis.

[Relatório completo](../pesquisas/extracao-pdf-docling-vs-alternativas.md)
