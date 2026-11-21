# Artefato — Resultado Teamwork da Tarefa 04

Tarefa: [04 — Adaptadores de extração documental (Docling em subprocesso, pdfplumber e pypdfium2)](../tarefas/04-adaptadores-extracao-docling-pdfplumber.md)
Prompt aprovado: [04-teamwork-prompt.md](./04-teamwork-prompt.md)
Veredito da auditoria independente pós-vitória: **`VICTORY CONFIRMED`** (1 iteração)

## Resumo das entregas

- **Dependências e configuração (`R1`, `backend/pyproject.toml` e `backend/uv.lock`)**:
  - Adicionados `docling==2.151.1`, `onnxruntime>=1.20` (RapidOCR), `pdfplumber>=0.11.10`, `pypdfium2>=5.15.2`, `pillow>=13.0.0` e `torch`/`torchvision` CPU via índice `pytorch-cpu` (`https://download.pytorch.org/whl/cpu`).
  - Registrado o marker `enade_real` no `pytest` e atualizadas as fronteiras do `import-linter` (`pypdfium2` e `PIL` proibidos em `domain` e `application`).
- **`ExtratorProvaDocling` em subprocesso isolado (`R2`, `backend/src/infrastructure/extracao/`)**:
  - `extrator_prova.py` e `_worker.py` executando o Docling (`PyPdfiumDocumentBackend`, `do_ocr=False`, `do_table_structure=True`, `generate_picture_images=True`, `images_scale=2.0`, `do_code_enrichment=False`, `do_formula_enrichment=False`) em subprocesso dedicado (`python -m infrastructure.extracao._worker`) para liberação imediata de RAM (`torch` não é importado no processo pai).
  - `inspecao_pdf.py` com detecção determinística de ToUnicode CMap corrompido (mojibake) via `pypdfium2`, acionando automaticamente o fallback `do_ocr=True` + `RapidOcrOptions(force_full_page_ocr=True)` e sinalizando `usou_ocr=True` em `MetadadosIngestao` para emissão do alerta `pdf_via_ocr`.
- **Pós-processamento determinístico de prova e mídia (`R3`, `backend/src/infrastructure/extracao/posprocessamento.py` e `inspecao_pdf.py`)**:
  - Truncamento antes de `QUESTIONÁRIO DE PERCEPÇÃO` (case-insensitive, preservando a tabela de sumário da página 1 e tratando a ordenação vertical por coordenada Y na página do cabeçalho).
  - Remoção de ruído textual (`VALIDINEP...`, `*R082023XX*`, `Área livre` e cabeçalho isolado de curso).
  - Filtro de margem e dimensão para descartar barcodes e logos (contagens agregadas registradas em `MetadadosIngestao`).
  - Recorte automático via `pypdfium2` do `bbox` de `FormulaItem` (`<!-- formula-not-decoded -->`) como `AtivoVisualExtraido` (`origem = formula_recorte`).
  - Detecção de fonte `Symbol` / `EuclidSymbol` / `MT-Extra` por página (`FPDFText_GetFontInfo`), registrando `MetadadosIngestao.paginas_fonte_symbol` para emissão de `fonte_symbol_detectada`.
  - Segmentação das questões e alternativas do Componente Específico para alimentar as validações determinísticas de alertas estruturais (`formula_nao_decodificada`, `alternativas_incompletas`, `enunciado_suspeito`).
- **`ExtratorGabaritoPdfPlumber` e `RenderizadorPaginaPdfPypdfium2` (`R4`, `backend/src/infrastructure/extracao/gabarito.py` e `renderizador.py`)**:
  - `ExtratorGabaritoPdfPlumber` com extração determinística de tabelas normalizando os 3 formatos oficiais do INEP (`QUESTÃO DISCURSIVA N` → `***`/`PENDENTE`, `ANULADA` e numeração pura `1..35`).
  - `RenderizadorPaginaPdfPypdfium2` para contagem de páginas e renderização sob demanda de uma página específica de `prova.pdf` para PNG em escala legível, rejeitando números de página fora do intervalo válido.
- **Testes unitários e de integração (`backend/tests/`)**:
  - Unitários: `tests/unit/test_extracao_posprocessamento.py` (7 testes), `tests/unit/test_extracao_gabarito.py` e `tests/unit/test_extracao_renderizador.py`.
  - Integração: `tests/integration/test_extracao_real.py` (6 testes com `@pytest.mark.enade_real`, pulando graciosamente quando os PDFs locais não estão presentes).
- **Fora de escopo respeitado (`R5`)**:
  - Sem endpoints HTTP novos, sem worker assíncrono do FastAPI e sem classificação por LLM.

## Verificações confirmadas na auditoria independente

- `make lint`: exit `0` (`ruff check .`, `ruff format --check .` em 69 arquivos, `lint-imports` 3/3 contratos em 75 arquivos, `pnpm type-check`, `pnpm lint`).
- `cd backend && uv run pytest tests/unit/test_extracao_posprocessamento.py -v`: exit `0` (`7 passed` em `0.47s`).
- `cd backend && uv run pytest -m enade_real tests/integration/test_extracao_real.py -v`: exit `0` (`6 passed` em `63.90s`), confirmando extração dos gabaritos reais 2017/2019/2023 em `< 500 ms`, validação do renderizador de página, segmentação de 29/29 questões do CE e recorte de `FormulaItem` no ENADE 2023, detecção de página com fonte `Symbol` e fallback automático `force_full_page_ocr=True` + `pdf_via_ocr` no ENADE 2017.
- `make test`: exit `0` (`166 passed` no backend + `1 passed` no frontend).
- Higiene e integridade: `0` referências a `pymupdf`/`fitz`; `torch` e `torchvision` bloqueados na variante `+cpu`; `0` caminhos absolutos locais ou artefatos de IA/MCP no repositório.

## Notas consultivas (não bloqueantes para futuras tarefas)

- Textos contendo `>= 5%` de caracteres gregos Unicode padrão (`0x0370..0x08FF`) podem acionar a heurística de CMap corrompido em `inspecao_pdf.py`.
- Sub-itens `list_item` aninhados dentro de alternativas e pequenos guardas adicionais de entrada em `gabarito.py`, `extrator_prova.py` e `renderizador.py` foram registrados como oportunidades de endurecimento futuro (nenhum afeta as edições 2017, 2019 ou 2023 do ENADE).
