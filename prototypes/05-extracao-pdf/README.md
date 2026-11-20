# Protótipo descartável — Ticket 05 (Extração de PDF: Docling vs PyMuPDF 2.1)

> **PROTOTYPE (descartável)**: código criado apenas para responder à decisão [05 — Prototipar extração em uma prova real do ENADE](../../docs/planejamento-inicial/decisoes/05-prototipar-extracao-prova-real.md). Não faz parte do código de produção.

## Como executar

```bash
cd prototypes/05-extracao-pdf
uv sync --python 3.13
uv run python run_prototype.py
```

Saídas geradas em `../../data/prototype-05/` (fora do Git via `.gitignore`):
- `comparacao-extracao.html` — painel HTML autossuficiente (abrir direto no navegador) com comparação lado a lado de todas as 29 questões objetivas do CE (ENADE 2023), A/B de `CodeFormulaV2`, stress-test 2019 (alternativas em 2 colunas) e 2017 (corpo em 2 colunas + ToUnicode corrompido + OCR), e parser de gabaritos (2023/2019/2017).
- `summary.json` — métricas objetivas (tempo total, s/página, pico de RAM RSS, cobertura de segmentação, alternativas A–E, vazamento de ruído e figuras recortadas).
