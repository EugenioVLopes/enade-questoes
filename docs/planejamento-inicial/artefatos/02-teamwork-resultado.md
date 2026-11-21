# Artefato — Resultado Teamwork da Tarefa 02

Tarefa: [02 — Núcleo de domínio, regras determinísticas e portas](../tarefas/02-nucleo-dominio-regras-deterministicas.md)
Prompt aprovado: [02-teamwork-prompt.md](./02-teamwork-prompt.md)
Veredito da auditoria independente pós-vitória: **`VICTORY CONFIRMED`** (5 iterações)

## Resumo das entregas

- **Núcleo de domínio puro (`R1`, `backend/src/domain/`)**:
  - Entidades, objetos de valor, enums e exceções puras aderentes aos 16 termos canônicos de [GLOSSARY.md](../../../GLOSSARY.md), usando exclusivamente Python 3.13 stdlib (zero dependências de frameworks ou I/O, zero `assert` em produção): `enums.py`, `exceptions.py`, `prova.py`, `taxonomia.py`, `classificacao.py`, `avaliacao.py` e `__init__.py`.
- **Regras determinísticas puras (`R2`, `backend/src/domain/`)**:
  - `faixas_enade.py`: faixas padrão do Componente Específico por edição (`2014–2019: 09–35`, `2023: 10–38`, `2026+: 16–45`) com suporte a override explícito.
  - `alertas_extracao.py`: avaliação determinística dos 6 `AlertaExtracao` (4 críticos e 2 informativos) e reavaliação automática dos 4 estruturais após edição de conteúdo, mantendo alertas de inspeção (`pdf_via_ocr`, `fonte_symbol_detectada`) até verificação explícita.
  - `travas_classificacao.py`: rejeição de `disciplina_principal` fora do catálogo ativo (elegibilidade a 1 retry corretivo), saneamento de `disciplinas_secundarias`, normalização de `Tópico`s em `kebab-case` ASCII curto (1–4 itens, até 32 chars sem cortar palavras) e cálculo de `revisao_prioritaria`.
  - `classificacao.py`: critério de `DivergenciaReclassificacao` comparando exclusivamente `(disciplina_principal, set(disciplinas_secundarias))`.
  - `reprocessamento.py`: política de reprocessamento de `Prova` preservando `Questão`s com `editada_manualmente = true` quando `sobrescrever_editadas = false`.
  - `metricas_avaliacao.py`: calculador determinístico das 3 camadas de métricas de `AvaliacaoClassificacao` (incluindo `∅ == ∅ → 1.0`, Macro-F1 com disciplinas raras, matriz de confusão, validade 1ª tentativa, erro em alta confiança `>= 0.85`) e avaliador de gate (`baseline` vs `candidato`, padrão e `--modo-migracao`).
- **Portas na camada de aplicação (`R3`, `backend/src/application/ports/`)**:
  - Contratos `@runtime_checkable` (`Protocol`) e DTOs imutáveis em `extracao.py` (`ExtratorProva`, `ExtratorGabarito`, `RenderizadorPaginaPdf`), `classificacao.py` (`ClassificadorMultimodal`), `armazenamento.py` (`ArmazenamentoArquivos`), `repositorios.py` (repositórios de domínio) e `__init__.py`.
- **Testes unitários puros (`backend/tests/unit/`)**:
  - 9 novos módulos de teste sem I/O externo (`test_domain_prova.py`, `test_faixas_enade.py`, `test_alertas_extracao.py`, `test_reprocessamento.py`, `test_domain_taxonomia_classificacao.py`, `test_travas_classificacao.py`, `test_divergencia_reclassificacao.py`, `test_metricas_avaliacao.py`, `test_application_ports.py`), totalizando 110 testes unitários aprovados.
- **Documentação e limites de escopo (`R4`)**:
  - [02-nucleo-dominio-regras-deterministicas.md](../tarefas/02-nucleo-dominio-regras-deterministicas.md) atualizado com `Status: concluida`, critérios de aceite marcados e evidências reais de execução.
  - Fora de escopo respeitado (sem SQLAlchemy, Alembic, FastAPI, Docling, `pdfplumber`, `pypdfium2` ou chamadas HTTP/LLM reais) e 0 caminhos absolutos locais nos arquivos `.md` do repositório.

## Verificações confirmadas na auditoria independente

- `cd backend && uv run python --version`: `Python 3.13.15` (exit `0`).
- `cd backend && uv run lint-imports` (e `--no-cache`): `Analyzed 50 files, 154 dependencies.`, `Contracts: 3 kept, 0 broken.` (exit `0`).
- `cd backend && uv run ruff check .`: `All checks passed!` (exit `0`).
- `cd backend && uv run ruff format --check .`: `48 files already formatted` (exit `0`).
- `cd backend && uv run pytest tests/unit/ -v`: `110 passed, 1 warning in 0.12s` (exit `0`).
- Higiene e integridade: `0` instruções `assert` em `backend/src/`, `0` caminhos absolutos locais em `docs/`, `GLOSSARY.md` e `AGENTS.md`, e alterações mantidas na *working tree* sem `git commit` ou `git push`.
