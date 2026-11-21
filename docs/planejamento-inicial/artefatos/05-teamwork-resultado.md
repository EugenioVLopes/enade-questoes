# Artefato — Resultado Teamwork da Tarefa 05

Tarefa: [05 — Worker local sequencial e API de Provas, Ingestão, Gabarito e Mídia](../tarefas/05-worker-local-api-provas-ingestao.md)
Prompt aprovado: [05-teamwork-prompt.md](./05-teamwork-prompt.md)
Veredito da auditoria independente pós-vitória: **`VICTORY CONFIRMED`** (2 iterações)

## Resumo das entregas

- **Worker local sequencial e Health (`R1`, `backend/src/application/worker.py`, `backend/src/application/health.py`, `backend/src/presentation/api/app.py`, `backend/src/presentation/api/v1/health.py` e `frontend/src/api/client.ts`)**:
  - Implementado `WorkerLocal` executando 1 tarefa pesada por vez (`Ingestão` ou `Execução de Classificação`) integrado ao `lifespan` do FastAPI.
  - Recuperação no boot marcando qualquer `Ingestão` ou `Execução de Classificação` residual em `processando` como `interrompida`, drenagem cooperativa da fila em parada/reinício e `ClassificacaoEncadeadaHook` persistido em `MetadadosIngestao` (`backend/src/domain/prova.py`) / `ingestoes.metadados` (`backend/src/infrastructure/persistence/repositorios.py`).
  - Estado ao vivo do worker (`estado`, `tarefa_ativa`, `tipo`, `alvo`, `processadas`, `total`) exposto em `GET /api/v1/health` e validado pelo schema Zod do frontend.
- **Casos de uso e endpoints de `Provas`, `Gabarito` e `Reprocessar Prova` (`R2`, `backend/src/application/provas.py`, `backend/src/application/exceptions.py`, `backend/src/presentation/api/v1/provas.py`, `backend/src/presentation/api/schemas.py`, `backend/src/presentation/main.py` e `backend/pyproject.toml`)**:
  - `POST /api/v1/provas` (`multipart/form-data` com `python-multipart`): retorna `202 Accepted` e enfileira a ingestão; duplicidade de `(exame, curso, ano)` retorna `409 Conflict` estruturado com `prova_id` existente; aplica default do intervalo do Componente Específico conforme regra do ano (`2023 -> 7..35`, demais `-> 9..35`).
  - `GET /api/v1/provas` e `GET /api/v1/provas/{id}`: retornam estado da `Ingestão`, contagens de `Questão`s, `Alerta de Extração`s abertos, estatísticas de filtro de margem e status de classificação encadeada.
  - `PUT /api/v1/provas/{id}/gabarito`: valida o PDF antes da substituição, reconcilia por `numero` oficial preservando 100% das `Classificação`s e edições manuais de texto, reavalia `gabarito_ausente_na_prova` e retorna resumo de diff (`mantidas`, `alteradas`, `anuladas`, `sem_correspondencia`, `questoes_sem_gabarito`).
  - `POST /api/v1/provas/{id}/reprocessar` (`sobrescrever_editadas: bool = false`): reconcilia por `numero` oficial preservando `Questão`s com `editada_manualmente = true` quando `false` (e sobrescrevendo quando `true`), preservando `Classificação`s e `Gabarito` vinculados, permitindo retentar `Ingestão` em `erro`/`interrompida` e removendo PNGs órfãos.
- **Entrega controlada de mídia e renderização de páginas PDF (`R3`, `backend/src/application/midia.py`, `backend/src/presentation/api/v1/_http_cache.py` e `backend/src/presentation/api/v1/ativos_visuais.py`)**:
  - `GET /api/v1/provas/{id}/paginas/{pagina}/imagem` (via `pypdfium2`) e `GET /api/v1/ativos-visuais/{id}/arquivo` (via `ArmazenamentoArquivos`, sem `StaticFiles`), retornando `image/png` com `ETag` SHA-256, `Cache-Control` e suporte a `304 Not Modified` quando `If-None-Match` coincide.
- **Sincronização OpenAPI e suíte de testes (`R4`, `frontend/src/api/schema.d.ts`, `backend/tests/integration/test_worker_local.py` e `backend/tests/integration/test_api_provas.py`)**:
  - `backend/src/presentation/openapi_export.py` mantido compatível com exportação offline e `frontend/src/api/schema.d.ts` regenerado via `make types`.
  - Testes de integração cobrindo o worker local sequencial, recuperação de tarefas `interrompida`s, endpoints de `Provas`/`Gabarito`/reprocessamento/mídia com extratores fake rápidos e 1 smoke test com extrator real (`@pytest.mark.enade_real`).

## Verificações confirmadas na auditoria independente

- `make lint`: exit `0` (`ruff check`, `ruff format --check` em 78 arquivos, `lint-imports` 3/3 contratos mantidos, `tsc -b`, `eslint .`).
- `make types`: exit `0` (`frontend/src/api/schema.d.ts` sincronizado e `frontend/.openapi.json` removido).
- `cd backend && uv run pytest tests/integration/test_api_provas.py tests/integration/test_worker_local.py -m "not enade_real" -v`: exit `0` (`9 passed, 1 deselected`).
- `cd backend && uv run pytest tests/integration/test_api_provas.py -m enade_real -v`: exit `0` (`1 passed, 2 deselected`, smoke test real com PDF oficial do ENADE 2023).
- `make test`: exit `0` (`177 passed` no backend + `1 passed` no frontend).

## Notas consultivas (não bloqueantes para futuras tarefas)

- Itens fora de escopo permanecem para as tarefas seguintes conforme planejado: execução real de classificação LLM (Tarefas 06/07), CRUD de `Taxonomia` (Tarefa 07), endpoints de revisão `/api/v1/questoes` (Tarefa 08) e telas React (Tarefas 09+).
- A unicidade de `(exame, curso, ano)` segue a constraint `uq_provas_upper_exame_curso_ano` da Tarefa 03 (case-insensitive em `exame`, case-sensitive em `curso`).
