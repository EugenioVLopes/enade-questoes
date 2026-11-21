# 05 — Worker local sequencial e API de Provas, Ingestão, Gabarito e Mídia

Status: `concluida`

Plano: [plano.md](../plano.md) · Pedido: [task.md](../task.md) · Explicação: [explicacao.md](../explicacao.md) · Decisões: [arquitetura e contratos](../decisoes/08-arquitetura-e-simplificacao-stack.md), [fluxos de ingestão](../decisoes/09-fluxos-interface-web-revisao-consulta.md), [reprocessamento seguro e páginas PDF](../decisoes/10-tratamento-edicao-midia-e-casos-borda.md)

## Contexto

Com a persistência e os adaptadores de extração prontos, precisamos entregar a primeira fatia funcional completa do backend: o **worker local sequencial** (que executa 1 tarefa pesada por vez e recupera tarefas `interrompida`s no boot) e todos os endpoints de `Provas`, `Ingestão`, atualização independente de `Gabarito`, `Reprocessar Prova` e entrega controlada de `Ativo Visual`s e páginas renderizadas do PDF.

## Entrega observável

Endpoints `/api/v1/provas/...` e `/api/v1/ativos-visuais/{id}/arquivo` operacionais e acompanhados pelo worker local sequencial, com contrato OpenAPI exportado para TypeScript via `make types`.

## Escopo e limites

- **Worker local sequencial (`backend/src/application/worker.py`)**:
  - Fila em memória/banco coordenada pelo lifespan do FastAPI executando **1 tarefa pesada por vez** (`Ingestão` ou `Execução de Classificação`).
  - No boot, marca qualquer `Ingestão` ou `Execução de Classificação` deixada em `processando` como `interrompida`.
  - Expõe estado resumido da tarefa ativa (tipo, alvo, progresso `processadas/total`) para o indicador global da UI e `GET /api/v1/health`.
- **Casos de uso e endpoints `/api/v1/provas`**:
  - `POST /api/v1/provas` (`multipart/form-data`: PDF obrigatório da prova, PDF opcional de gabarito, `exame`, `curso`, `ano`, `questao_inicio`/`questao_fim` opcionais com default pela regra do ano, `taxonomia_id`/`perfil_id` opcionais para encadeamento futuro) → `202 Accepted` (`409 Conflict` estruturado se `(exame, curso, ano)` já existir, retornando `prova_id` existente).
  - `GET /api/v1/provas` e `GET /api/v1/provas/{id}` (estado da `Ingestão`, contagens de `Questão`s, `Alerta de Extração`s abertos, estatísticas de filtro de margem e status de classificação encadeada).
  - `PUT /api/v1/provas/{id}/gabarito`: extrai o novo PDF de `Gabarito`, atualiza as `Questão`s por `numero` oficial sem perder `Classificação`s nem edições de texto, reavalia `gabarito_ausente_na_prova` e retorna resumo de diff (`mantidas`, `alteradas`, `anuladas`, `sem_correspondencia`).
  - `POST /api/v1/provas/{id}/reprocessar` (`sobrescrever_editadas: bool = false`): reconcilia por `numero` oficial preservando `Questão`s com `editada_manualmente = true` (quando `false`), `Classificação`s e `Gabarito` vinculados; permite também retentar `Ingestão` em `erro` ou `interrompida`.
  - `GET /api/v1/provas/{id}/paginas/{pagina}/imagem`: renderiza página original do PDF sob demanda via `pypdfium2` com `ETag` e `Cache-Control`.
  - `GET /api/v1/ativos-visuais/{id}/arquivo`: entrega PNG via `ArmazenamentoArquivos` com `ETag` e `Cache-Control` (sem `StaticFiles`).
- **Regenerar tipos TS**: rodar `make types` atualizando o contrato gerado em `frontend/src/api/`.
- **Fora de escopo**: execução real de classificação LLM (apenas gancho/hook para a Tarefa 07), CRUD de `Taxonomia` e tela React.

## Dependências

- [03 — Persistência PostgreSQL 16, Alembic, armazenamento local e seed inicial](03-persistencia-postgres-alembic-seed.md)
- [04 — Adaptadores de extração documental (Docling em subprocesso, pdfplumber e pypdfium2)](04-adaptadores-extracao-docling-pdfplumber.md)

## Critérios de aceite

- [x] `POST /api/v1/provas` retorna `202 Accepted`, processa em background sequencialmente via worker e persiste `Questão`s, `Alternativa`s, `Ativo Visual`s e `Alerta de Extração`s; reenvio do mesmo `(exame, curso, ano)` retorna `409 Conflict` com `prova_id`.
- [x] `PUT /api/v1/provas/{id}/gabarito` atualiza gabarito preliminar → definitivo preservando 100% das `Classificação`s e retornando contagens exatas de `mantidas / alteradas / anuladas`.
- [x] `POST /api/v1/provas/{id}/reprocessar` preserva `Questão`s com `editada_manualmente = true` quando `sobrescrever_editadas = false` e sobrescreve quando `sobrescrever_editadas = true`.
- [x] Reinício simulado do worker converte `Ingestão` em `processando` para `interrompida`.
- [x] Endpoints de imagem (`/ativos-visuais/{id}/arquivo` e `/provas/{id}/paginas/{pagina}/imagem`) retornam `image/png` com `ETag` e `304 Not Modified` quando `If-None-Match` coincide.
- [x] `make types` completa sem erros.

## Verificação

- `uv run pytest tests/integration/test_api_provas.py tests/integration/test_worker_local.py` (com extratores fake rápidos para a suíte padrão + 1 smoke test com extrator real).
- `make lint && make types`.

## Evidências e pendências

- **Artefatos do Teamwork**: [prompt aprovado](../artefatos/05-teamwork-prompt.md) · [relatório de resultado](../artefatos/05-teamwork-resultado.md) (auditoria independente pós-vitória: `VICTORY CONFIRMED`).
- **Worker local sequencial e Health**: `backend/src/application/worker.py`, `backend/src/application/health.py`, `backend/src/presentation/api/app.py`, `backend/src/presentation/api/v1/health.py` e `frontend/src/api/client.ts` implementando `WorkerLocal` (1 tarefa pesada por vez, recuperação de `processando -> interrompida` no boot, hook de encadeamento em `MetadadosIngestao` e progresso ao vivo em `GET /api/v1/health`).
- **Casos de uso e endpoints de Provas e Mídia**: `backend/src/application/provas.py`, `backend/src/application/midia.py`, `backend/src/application/exceptions.py`, `backend/src/presentation/api/v1/provas.py`, `backend/src/presentation/api/v1/ativos_visuais.py`, `backend/src/presentation/api/v1/_http_cache.py` e `backend/src/presentation/api/schemas.py`.
- **Sincronização OpenAPI e testes**: `frontend/src/api/schema.d.ts` atualizado via `make types`; `backend/tests/integration/test_worker_local.py` e `backend/tests/integration/test_api_provas.py` cobrindo suíte rápida + smoke test `@pytest.mark.enade_real`.
- **Verificações executadas**:
  - `make lint` → exit code `0` (`ruff check`, `ruff format --check` em 78 arquivos, `lint-imports` 3/3 contratos, `tsc -b`, `eslint .`)
  - `make types` → exit code `0` (`frontend/src/api/schema.d.ts` sincronizado)
  - `cd backend && uv run pytest tests/integration/test_api_provas.py tests/integration/test_worker_local.py -m "not enade_real" -v` → `9 passed, 1 deselected`
  - `cd backend && uv run pytest tests/integration/test_api_provas.py -m enade_real -v` → `1 passed, 2 deselected`
  - `make test` → `177 passed` (backend) + `1 passed` (frontend)
- **Pendências**: nenhuma na Tarefa 05.
