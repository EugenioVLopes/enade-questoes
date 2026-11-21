Implementar os adaptadores de produção de extração documental (`ExtratorProvaDocling` em subprocesso isolado, `ExtratorGabaritoPdfPlumber` e `RenderizadorPaginaPdfPypdfium2`) em `backend/src/infrastructure/extracao/` e configurar as dependências de extração em `backend/pyproject.toml`, atendendo às portas de `backend/src/application/ports/extracao.py` para a v1 do Enade Questões.

Integrity mode: development

Reference material:
- `docs/planejamento-inicial/tarefas/04-adaptadores-extracao-docling-pdfplumber.md`
- `docs/planejamento-inicial/decisoes/05-prototipar-extracao-prova-real.md`
- `docs/planejamento-inicial/decisoes/10-tratamento-edicao-midia-e-casos-borda.md`
- `prototypes/05-extracao-pdf/run_prototype.py`

## Requirements

### R1. Dependências e configuração do backend
Adicionar as dependências de extração em `backend/pyproject.toml`: `docling==2.151.1` (com `torch` CPU via índice `pytorch-cpu` no `uv`), `pdfplumber`, `pypdfium2` e `Pillow`. Manter a conformidade com os contratos de arquitetura hexagonal (`import-linter`) e regras de estilo/lint (`ruff`).

### R2. `ExtratorProvaDocling` em subprocesso isolado
Implementar `ExtratorProva` (`ExtratorProvaDocling`) em `backend/src/infrastructure/extracao/` executando o Docling (`PyPdfiumDocumentBackend`, `do_ocr=False`, `do_table_structure=True`, `generate_picture_images=True`, `images_scale=2.0`, `do_code_enrichment=False`, `do_formula_enrichment=False`) em subprocesso dedicado (`multiprocessing` com `spawn` ou `subprocess` executando módulo worker dedicado), devolvendo a saída estruturada (`extracao_bruta_json` e PNGs recortados) e garantindo liberação imediata de RAM ao término. Incluir detector determinístico de ToUnicode CMap corrompido (mojibake) que aciona automaticamente o fallback `do_ocr=True` + `RapidOcrOptions(force_full_page_ocr=True)` e sinaliza `usou_ocr` nos metadados para emissão do `Alerta de Extração` `pdf_via_ocr`.

### R3. Pós-processamento determinístico de prova e mídia
Aplicar pós-processamento determinístico sobre a saída do Docling:
- Truncamento antes de `QUESTIONÁRIO DE PERCEPÇÃO` (case-insensitive);
- Remoção de ruído textual (`VALIDINEP...`, `*R082023XX*`, `Área livre`);
- Filtro de margem e dimensão para descartar barcodes e logos (registrando as contagens agregadas em `MetadadosIngestao`);
- Recorte automático via `pypdfium2` do `bbox` de `FormulaItem` (`<!-- formula-not-decoded -->`) como `AtivoVisualExtraido` (`origem = formula_recorte`);
- Detecção de fonte `Symbol`/`MT-Extra` por página, registrando as páginas em `MetadadosIngestao.paginas_fonte_symbol` para emissão de `fonte_symbol_detectada`;
- Segmentação das questões e alternativas para alimentar as validações determinísticas de alertas estruturais (`formula_nao_decodificada`, `alternativas_incompletas`, `enunciado_suspeito`).

### R4. `ExtratorGabaritoPdfPlumber` e `RenderizadorPaginaPdfPypdfium2`
Implementar `ExtratorGabarito` (`ExtratorGabaritoPdfPlumber`) com extração determinística de tabelas normalizando os 3 formatos oficiais do INEP (`QUESTÃO DISCURSIVA N` → `***`, `ANULADA` e numeração pura `1..35`). Implementar `RenderizadorPaginaPdf` (`RenderizadorPaginaPdfPypdfium2`) para contagem de páginas e renderização sob demanda de uma página específica de `prova.pdf` para PNG em escala legível, rejeitando números de página fora do intervalo válido.

### R5. Escopo excluído e entrega
Ficam fora de escopo: endpoints HTTP, worker assíncrono do FastAPI e classificação por LLM. Entregar apenas código, dependências e testes, sem alterar os arquivos em `docs/`.

## Verification Resources
- Protótipo de referência: `prototypes/05-extracao-pdf/run_prototype.py`
- PDFs oficiais locais para testes de integração: `data/enade/{2017,2019,2023}/`
- Suíte e verificadores do repositório: `make lint` e `make test`

## Acceptance Criteria

### Extração de gabaritos e renderização
- [ ] `ExtratorGabaritoPdfPlumber` extrai 100% corretamente os 3 gabaritos reais (`2017`, `2019` com `ANULADA`, `2023` com `***`) em `< 500 ms` cada.
- [ ] `RenderizadorPaginaPdfPypdfium2` renderiza a página solicitada em PNG válido e rejeita número de página fora do intervalo.

### Extração de provas, subprocesso e casos de borda
- [ ] `ExtratorProvaDocling` roda em subprocesso isolado, segmenta 29/29 questões do Componente Específico no ENADE 2023, filtra barcodes/logos de margem e recorta automaticamente o `bbox` de `formula_nao_decodificada` (ex.: Q13/2023) como `AtivoVisualExtraido` (`origem = formula_recorte`).
- [ ] Em página/prova com CMap corrompido (ex.: ENADE 2017), o detector aciona automaticamente `force_full_page_ocr=True` e registra `usou_ocr=True` para emissão de `Alerta de Extração` `pdf_via_ocr`.
- [ ] Páginas com fonte `Symbol`/`MT-Extra` (ex.: Q10/2023) são registradas em `paginas_fonte_symbol` para emissão do alerta informativo `fonte_symbol_detectada` sem forçar `revisao_prioritaria`.

### Suítes de testes e conformidade
- [ ] Testes unitários (incluindo `backend/tests/unit/test_extracao_posprocessamento.py`) cobrem pós-processamento e casos de borda e passam com `uv run pytest tests/unit/test_extracao_posprocessamento.py`.
- [ ] Testes de integração em `backend/tests/integration/test_extracao_real.py` usam `@pytest.mark.enade_real`, pulam graciosamente apenas quando os PDFs locais em `data/enade/` não estão presentes, rodam tanto no `pytest` padrão quanto com `uv run pytest -m enade_real tests/integration/test_extracao_real.py`, e validam a detecção de CMap/OCR na edição 2017 (no PDF completo ou em páginas representativas).
- [ ] `make test` e `make lint` (`ruff check`, `ruff format --check`, `lint-imports`) passam sem erros, e nenhum arquivo em `docs/` foi modificado.
