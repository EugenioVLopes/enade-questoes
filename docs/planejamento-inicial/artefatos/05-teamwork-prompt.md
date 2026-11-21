Implementar o worker local sequencial (`backend/src/application/worker.py`) e os endpoints da API para `Provas`, `Ingestão`, atualização independente de `Gabarito`, `Reprocessar Prova`, entrega controlada de `Ativo Visual`s e renderização de páginas PDF, com sincronização dos tipos OpenAPI para TypeScript via `make types`.

Integrity mode: development

Reference material: `docs/planejamento-inicial/tarefas/05-worker-local-api-provas-ingestao.md`, `docs/planejamento-inicial/plano.md`, `docs/planejamento-inicial/decisoes/08-arquitetura-e-simplificacao-stack.md`, `docs/planejamento-inicial/decisoes/09-fluxos-interface-web-revisao-consulta.md`, `docs/planejamento-inicial/decisoes/10-tratamento-edicao-midia-e-casos-borda.md`.

## Requirements

### R1. Worker local sequencial (`backend/src/application/worker.py`)
Manter fila em memória/banco coordenada pelo lifespan do FastAPI executando 1 tarefa pesada por vez (`Ingestão` ou `Execução de Classificação`). No boot, marcar qualquer `Ingestão` ou `Execução de Classificação` deixada em `processando` como `interrompida` e expor estado resumido da tarefa ativa (tipo, alvo, progresso `processadas/total`) para o indicador global da UI e `GET /api/v1/health`.

### R2. Casos de uso e endpoints `/api/v1/provas`
Implementar os seguintes casos de uso e endpoints:
- `POST /api/v1/provas` (`multipart/form-data`: PDF obrigatório da prova, PDF opcional de gabarito, `exame`, `curso`, `ano`, `questao_inicio`/`questao_fim` opcionais com default pela regra do ano, `taxonomia_id`/`perfil_id` opcionais para encadeamento futuro) → `202 Accepted`, ou `409 Conflict` estruturado com `prova_id` existente se `(exame, curso, ano)` já existir.
- `GET /api/v1/provas` e `GET /api/v1/provas/{id}` retornando estado da `Ingestão`, contagens de `Questão`s, `Alerta de Extração`s abertos, estatísticas de filtro de margem e status de classificação encadeada.
- `PUT /api/v1/provas/{id}/gabarito`: extrai o novo PDF de `Gabarito`, atualiza as `Questão`s por `numero` oficial sem perder `Classificação`s nem edições de texto, reavalia `gabarito_ausente_na_prova` e retorna resumo de diff (`mantidas`, `alteradas`, `anuladas`, `sem_correspondencia`).
- `POST /api/v1/provas/{id}/reprocessar` (`sobrescrever_editadas: bool = false`): reconcilia por `numero` oficial preservando `Questão`s com `editada_manualmente = true` (quando `false`), `Classificação`s e `Gabarito` vinculados; permite também retentar `Ingestão` em `erro` ou `interrompida`.

### R3. Entrega controlada de mídia e renderização de páginas PDF
Implementar:
- `GET /api/v1/provas/{id}/paginas/{pagina}/imagem`: renderiza página original do PDF sob demanda via `pypdfium2` com `ETag` e `Cache-Control`.
- `GET /api/v1/ativos-visuais/{id}/arquivo`: entrega PNG via `ArmazenamentoArquivos` com `ETag` e `Cache-Control` (sem `StaticFiles`).

### R4. Sincronização OpenAPI e limites de escopo
Rodar `make types` atualizando o contrato gerado em `frontend/src/api/`. Ficam fora de escopo: execução real de classificação LLM (apenas gancho/hook para a Tarefa 07), CRUD de `Taxonomia` e tela React.

## Verification Resources

- PDFs oficiais em `data/enade/` e marcador `enade_real` configurado em `backend/pyproject.toml`.
- Suíte e fixtures existentes em `backend/tests/` e comandos em `Makefile` (`make lint`, `make types`, `uv run pytest`).
- Especificação e decisões em `docs/planejamento-inicial/`.

## Acceptance Criteria

### API, Worker e Mídia
- [ ] `POST /api/v1/provas` retorna `202 Accepted`, processa em background sequencialmente via worker e persiste `Questão`s, `Alternativa`s, `Ativo Visual`s e `Alerta de Extração`s; reenvio do mesmo `(exame, curso, ano)` retorna `409 Conflict` com `prova_id`.
- [ ] `PUT /api/v1/provas/{id}/gabarito` atualiza gabarito preliminar → definitivo preservando 100% das `Classificação`s e retornando contagens exatas de `mantidas / alteradas / anuladas`.
- [ ] `POST /api/v1/provas/{id}/reprocessar` preserva `Questão`s com `editada_manualmente = true` quando `sobrescrever_editadas = false` e sobrescreve quando `sobrescrever_editadas = true`.
- [ ] Reinício simulado do worker converte `Ingestão` em `processando` para `interrompida`.
- [ ] Endpoints de imagem (`/ativos-visuais/{id}/arquivo` e `/provas/{id}/paginas/{pagina}/imagem`) retornam `image/png` com `ETag` e `304 Not Modified` quando `If-None-Match` coincide.

### Verificação Automatizada e Contratos
- [ ] `uv run pytest tests/integration/test_api_provas.py tests/integration/test_worker_local.py` passa (com extratores fake rápidos para a suíte padrão + 1 smoke test com extrator real).
- [ ] `make lint && make types` completa sem erros e mantém `frontend/src/api/` sincronizado.
