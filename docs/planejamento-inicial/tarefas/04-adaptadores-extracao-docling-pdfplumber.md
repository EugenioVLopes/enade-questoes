# 04 — Adaptadores de extração documental (Docling em subprocesso, pdfplumber e pypdfium2)

Status: `concluida`

Plano: [plano.md](../plano.md) · Pedido: [task.md](../task.md) · Protótipo base: [run_prototype.py](../../../prototypes/05-extracao-pdf/run_prototype.py) · Decisões: [extração em prova real](../decisoes/05-prototipar-extracao-prova-real.md), [tratamento de mídia e casos de borda](../decisoes/10-tratamento-edicao-midia-e-casos-borda.md)

## Contexto

O protótipo descartável da decisão 05 validou **Docling 2.151.1** + **`pdfplumber`** nas 3 edições reais do ENADE (`2017`, `2019`, `2023`), mas evidenciou requisitos operacionais obrigatórios para produção: isolamento de memória em subprocesso (~2,3 GB de RAM do PyTorch), detecção automática de CMap corrompido (2017), truncamento do `QUESTIONÁRIO DE PERCEPÇÃO`, filtro de barcodes/logos de margem, recorte automático do `bbox` de `formula_nao_decodificada` via `pypdfium2` e detecção de fonte `Symbol`.

## Entrega observável

Adaptadores de produção em `backend/src/infrastructure/extracao/` implementando `ExtratorProva`, `ExtratorGabarito` e `RenderizadorPaginaPdf`, validados em testes unitários (pós-processamento e casos de borda) e testes de integração contra os PDFs oficiais locais em `data/enade/{2017,2019,2023}/`.

## Escopo e limites

- **Adicionar dependências de extração** no `backend/pyproject.toml`: `docling==2.151.1` (com `torch` CPU via índice `pytorch-cpu` no `uv`), `pdfplumber`, `pypdfium2` e `Pillow`.
- **`ExtratorProvaDocling` (em subprocesso isolado)**:
  - Executa Docling em subprocesso dedicado (`multiprocessing` com `spawn` ou `subprocess` executando worker módulo dedicado), devolvendo a saída estruturada (`extracao_bruta.json` + PNGs recortados) e garantindo liberação imediata de RAM ao término.
  - Configuração padrão validada: `PyPdfiumDocumentBackend`, `do_ocr=False`, `do_table_structure=True`, `generate_picture_images=True`, `images_scale=2.0`, `do_code_enrichment=False`, `do_formula_enrichment=False`.
  - Detector determinístico de ToUnicode CMap corrompido (mojibake): aciona fallback `do_ocr=True` + `RapidOcrOptions(force_full_page_ocr=True)` e emite `Alerta de Extração` `pdf_via_ocr`.
  - Pós-processamento determinístico: truncamento antes de `QUESTIONÁRIO DE PERCEPÇÃO` (case-insensitive), remoção de ruído (`VALIDINEP...`, `*R082023XX*`, `Área livre`), filtro de margem/dimensão para descartar barcodes/logos (registrando estatística agregada nos metadados da `Ingestão`), recorte automático via `pypdfium2` do `bbox` de `FormulaItem` (`<!-- formula-not-decoded -->`) como `Ativo Visual` (`origem = formula_recorte`), detecção de fonte `Symbol`/`MT-Extra` por página (`fonte_symbol_detectada`) e emissão dos alertas estruturais (`formula_nao_decodificada`, `alternativas_incompletas`, `enunciado_suspeito`).
- **`ExtratorGabaritoPdfPlumber`**:
  - Extração determinística de tabelas normalizando os 3 formatos oficiais do INEP (`QUESTÃO DISCURSIVA N` → `***`, `ANULADA` e numeração pura `1..35`).
- **`RenderizadorPaginaPdfPypdfium2`**:
  - Renderização sob demanda de uma página específica de `prova.pdf` para PNG em escala legível para conferência na revisão.
- **Fora de escopo**: endpoints HTTP, worker assíncrono do FastAPI e classificação por LLM.

## Dependências

- [02 — Núcleo de domínio, regras determinísticas e portas](02-nucleo-dominio-regras-deterministicas.md)
- [03 — Persistência PostgreSQL 16, Alembic, armazenamento local e seed inicial](03-persistencia-postgres-alembic-seed.md)

## Critérios de aceite

- [x] `ExtratorGabaritoPdfPlumber` extrai 100% corretamente os 3 gabaritos reais (`2017`, `2019` com `ANULADA`, `2023` com `***`) em `< 500 ms` cada.
- [x] `ExtratorProvaDocling` roda em subprocesso isolado, segmenta 29/29 questões do Componente Específico no ENADE 2023, filtra barcodes/logos de margem e recorta automaticamente o `bbox` de `formula_nao_decodificada` (ex.: Q13/2023) como `Ativo Visual` (`origem = formula_recorte`).
- [x] Em página/prova com CMap corrompido (ex.: ENADE 2017), o detector aciona automaticamente `force_full_page_ocr=True` e registra `Alerta de Extração` `pdf_via_ocr`.
- [x] Páginas com fonte `Symbol` (ex.: Q10/2023) recebem o alerta informativo `fonte_symbol_detectada` sem forçar `revisao_prioritaria`.
- [x] `RenderizadorPaginaPdfPypdfium2` renderiza página solicitada em PNG válido e rejeita número de página fora do intervalo.
- [x] Testes de integração sobre `data/enade/` usam marker dedicado (`@pytest.mark.enade_real`) e pulam graciosamente caso os PDFs locais não estejam presentes.

## Verificação

- Testes rápidos: `uv run pytest tests/unit/test_extracao_posprocessamento.py`.
- Testes em PDFs reais: `uv run pytest -m enade_real tests/integration/test_extracao_real.py`.

## Evidências e pendências

- **Artefatos locais do Teamwork (fora do Git)**: `docs/planejamento-inicial/artefatos/04-teamwork/` (`prompt.md`, `resultado.md` e relatórios de auditoria; veredito: `VICTORY CONFIRMED`).
- **Dependências e configuração**: `backend/pyproject.toml` e `backend/uv.lock` atualizados com `docling==2.151.1`, `onnxruntime>=1.20` (RapidOCR), `pdfplumber>=0.11.10`, `pypdfium2>=5.15.2`, `pillow>=13.0.0` e `torch`/`torchvision` CPU via índice `pytorch-cpu`, marker `enade_real` e isolamento `pypdfium2`/`PIL` no `import-linter`.
- **Adaptadores de extração**: `backend/src/infrastructure/extracao/` (`__init__.py`, `_worker.py`, `extrator_prova.py`, `inspecao_pdf.py`, `posprocessamento.py`, `gabarito.py`, `renderizador.py`) implementando `ExtratorProvaDocling` em subprocesso isolado com fallback RapidOCR para CMap corrompido, `ExtratorGabaritoPdfPlumber` e `RenderizadorPaginaPdfPypdfium2`.
- **Testes unitários e de integração**: `backend/tests/unit/test_extracao_posprocessamento.py`, `backend/tests/unit/test_extracao_gabarito.py`, `backend/tests/unit/test_extracao_renderizador.py` e `backend/tests/integration/test_extracao_real.py`.
- **Verificações executadas**:
  - `make lint` → exit code `0` (`ruff check .`, `ruff format --check .` em 69 arquivos, `lint-imports` 3/3 contratos em 75 arquivos, `pnpm type-check`, `pnpm lint`)
  - `cd backend && uv run pytest tests/unit/test_extracao_posprocessamento.py -v` → `7 passed` (`0.47s`)
  - `cd backend && uv run pytest -m enade_real tests/integration/test_extracao_real.py -v` → `6 passed` (`63.90s`)
  - `make test` → `166 passed` (backend) + `1 passed` (frontend)
- **Pendências**: nenhuma na Tarefa 04.
