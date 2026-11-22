# 07 — API de Taxonomias, Perfis de Classificação e Execuções de Classificação

Status: `concluida`

Plano: [plano.md](../plano.md) · Pedido: [task.md](../task.md) · Explicação: [explicacao.md](../explicacao.md) · Decisões: [modelo de domínio](../decisoes/06-modelo-de-dominio-e-glossario.md), [arquitetura e contratos](../decisoes/08-arquitetura-e-simplificacao-stack.md), [fluxos de taxonomias e execuções](../decisoes/09-fluxos-interface-web-revisao-consulta.md)

## Contexto

Para permitir múltiplas grades curriculares, versionamento seguro de diretrizes editoriais e reclassificações controladas sem sobrescrever decisões humanas, precisamos expor os endpoints de `Taxonomia`, `Disciplina`, `Perfil de Classificação` e `Execução de Classificação`, integrando esta última ao worker local sequencial e ao encadeamento opcional pós-`Ingestão`.

## Entrega observável

Endpoints `/api/v1/taxonomias`, `/api/v1/disciplinas`, `/api/v1/perfis-classificacao` e `/api/v1/execucoes-classificacao` operacionais no backend, executando classificação incremental via `ClassificadorMultimodal` com snapshot congelado, abertura de `Divergência de Reclassificação`, retomada parcial e tipos TypeScript sincronizados via `make types`.

## Escopo e limites

- **`Taxonomia`s e `Disciplina`s**:
  - `GET /api/v1/taxonomias`, `POST /api/v1/taxonomias`, `PATCH /api/v1/taxonomias/{id}`.
  - `POST /api/v1/taxonomias/{id}/disciplinas`, `PATCH /api/v1/disciplinas/{id}` (incluindo arquivar/reativar `ativa = false | true`, nunca exclusão física; incluir contagem de `Classificação`s vigentes impactadas no detalhe/resposta).
- **`Perfil de Classificação`**:
  - `GET /api/v1/perfis-classificacao` e `POST /api/v1/perfis-classificacao` (criação de novas versões imutáveis, opcionalmente clonando campos de um `perfil_base_id`).
- **`Execução de Classificação` (inicial, individual e reclassificação)**:
  - `POST /api/v1/execucoes-classificacao` (`taxonomia_id`, `perfil_id`, escopo: `todas | prova_id | pendentes | disciplina_arquivada | questao_ids`, `incluir_revisadas: bool = false`) → `202 Accepted`.
  - `GET /api/v1/execucoes-classificacao` e `GET /api/v1/execucoes-classificacao/{id}` (snapshot resumido, `processadas/total`, erros por questão, divergências abertas, hits de cache e tokens).
  - `POST /api/v1/execucoes-classificacao/{id}/retomar`: enfileira retomada para execuções em `interrompida` ou `concluida_com_erros`, processando apenas questões pendentes ou que falharam.
- **Execução no worker local e encadeamento pós-`Ingestão`**:
  - Congela `snapshot_taxonomia` (disciplinas ativas + ementas) e `snapshot_perfil` ao criar a execução.
  - Grava resultados questão a questão no PostgreSQL:
    - Questão sem classificação ou `pendente_revisao`: grava nova `Classificação` automática vigente;
    - Questão já `aprovada` por humano e `incluir_revisadas = false`: pula (sem chamar LLM);
    - Questão já `aprovada` por humano e `incluir_revisadas = true`: mantém humana vigente; se mudar `(disciplina_principal, set(disciplinas_secundarias))`, abre `Divergência de Reclassificação`, caso contrário apenas registra histórico concordante.
  - Conecta o encadeamento opcional de `POST /api/v1/provas` quando `taxonomia_id`/`perfil_id` são enviados, garantindo que falha no LLM nunca invalida a `Ingestão` concluída.
- **Regenerar tipos TS**: rodar `make types`.

## Dependências

- [03 — Persistência PostgreSQL 16, Alembic, armazenamento local e seed inicial](03-persistencia-postgres-alembic-seed.md)
- [05 — Worker local sequencial e API de Provas, Ingestão, Gabarito e Mídia](05-worker-local-api-provas-ingestao.md)
- [06 — Classificador multimodal OpenAI-compatível, cache determinístico e travas](06-classificador-multimodal-cache-travas.md)

## Critérios de aceite

- [x] CRUD de `Taxonomia` e `Disciplina` funciona, impedindo exclusão física e expondo contagem de classificações vigentes ao arquivar uma `Disciplina`.
- [x] `POST /api/v1/perfis-classificacao` gera versões imutáveis sem alterar snapshots de execuções passadas.
- [x] `Execução de Classificação` com `incluir_revisadas = false` pula questões já aprovadas por humano sem consumir o classificador.
- [x] `Execução de Classificação` com `incluir_revisadas = true` nunca sobrescreve a `Classificação` humana vigente e abre `Divergência de Reclassificação` apenas quando mudam `Disciplina` principal ou secundárias.
- [x] `POST /api/v1/execucoes-classificacao/{id}/retomar` reprocessa apenas itens faltantes/falhos de uma execução `interrompida` ou `concluida_com_erros`.
- [x] Encadeamento pós-`Ingestão` funciona e uma falha simulada do LLM preserva 100% da `Prova` e `Questão`s ingeridas.
- [x] `make types` atualiza os tipos TypeScript sem erros.

## Verificação

- `uv run pytest tests/integration/test_api_taxonomias.py tests/integration/test_execucoes_classificacao.py` (usando `ClassificadorMultimodal` fake determinístico).
- `make lint && make types`.

## Evidências e pendências

- **Artefatos locais do Teamwork (fora do Git)**: `docs/planejamento-inicial/artefatos/07-teamwork/` (`prompt.md`, `resultado.md` e relatórios de auditoria; veredito: `VICTORY CONFIRMED`).
- **Domínio, Migration 0002 e Persistência**: `backend/alembic/versions/0002_execucao_escopo_e_progresso.py`, `backend/src/domain/taxonomia.py`, `backend/src/domain/classificacao.py`, `backend/src/application/ports/repositorios.py`, `backend/src/infrastructure/persistence/models.py` e `backend/src/infrastructure/persistence/repositorios.py` (rastreamento de escopo e progresso por questão em `execucoes_classificacao`, reconstrução `de_snapshot`, atualização não destrutiva de disciplinas com `with_for_update()`, imutabilidade de `codigo`, contagem batch de `classificacoes_vigentes_impactadas` e queries dos 5 escopos de execução).
- **Casos de uso, Worker Local e Encadeamento pós-Ingestão**: `backend/src/application/taxonomias.py`, `backend/src/application/execucoes_classificacao.py`, `backend/src/application/provas.py`, `backend/src/application/worker.py` e `backend/src/application/exceptions.py` implementando CRUD de taxonomias/disciplinas, versionamento imutável de perfis (com clonagem opcional via `perfil_base_id`), `ExecutarLoteClassificacaoService`, retomada parcial (`interrompida | concluida_com_erros`) e `HookClassificacaoEncadeada` isolando falhas de LLM da `Ingestão` concluída.
- **Rotas HTTP `/api/v1/...`, Wiring e Tipos TypeScript**: `backend/src/presentation/api/v1/taxonomias.py`, `backend/src/presentation/api/v1/perfis_classificacao.py`, `backend/src/presentation/api/v1/execucoes_classificacao.py`, `backend/src/presentation/api/schemas.py`, `backend/src/presentation/api/app.py`, `backend/src/presentation/main.py` e `frontend/src/api/schema.d.ts` sincronizado via `make types`.
- **Testes automatizados**: `backend/tests/unit/test_domain_taxonomia_classificacao.py`, `backend/tests/unit/test_application_ports.py`, `backend/tests/unit/test_application_taxonomias_execucoes.py`, `backend/tests/integration/test_persistence.py`, `backend/tests/integration/test_api_taxonomias.py` e `backend/tests/integration/test_execucoes_classificacao.py`.
- **Verificações executadas**:
  - `cd backend && uv run pytest tests/integration/test_api_taxonomias.py tests/integration/test_execucoes_classificacao.py -v` → `7 passed`
  - `cd backend && uv run pytest -m "not enade_real" -v` → `209 passed, 7 deselected`
  - `cd frontend && pnpm test` → `1 passed`
  - `make lint && make types` → exit code `0` (`ruff check .`, `ruff format --check .` em 92 arquivos, `lint-imports` 3/3 contratos, `tsc -b`, `eslint .`, `frontend/src/api/schema.d.ts` sincronizado)
- **Pendências**: nenhuma na Tarefa 07.
