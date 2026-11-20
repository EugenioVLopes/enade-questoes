# 07 — API de Taxonomias, Perfis de Classificação e Execuções de Classificação

Status: `pendente`

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

- [ ] CRUD de `Taxonomia` e `Disciplina` funciona, impedindo exclusão física e expondo contagem de classificações vigentes ao arquivar uma `Disciplina`.
- [ ] `POST /api/v1/perfis-classificacao` gera versões imutáveis sem alterar snapshots de execuções passadas.
- [ ] `Execução de Classificação` com `incluir_revisadas = false` pula questões já aprovadas por humano sem consumir o classificador.
- [ ] `Execução de Classificação` com `incluir_revisadas = true` nunca sobrescreve a `Classificação` humana vigente e abre `Divergência de Reclassificação` apenas quando mudam `Disciplina` principal ou secundárias.
- [ ] `POST /api/v1/execucoes-classificacao/{id}/retomar` reprocessa apenas itens faltantes/falhos de uma execução `interrompida` ou `concluida_com_erros`.
- [ ] Encadeamento pós-`Ingestão` funciona e uma falha simulada do LLM preserva 100% da `Prova` e `Questão`s ingeridas.
- [ ] `make types` atualiza os tipos TypeScript sem erros.

## Verificação

- `uv run pytest tests/integration/test_api_taxonomias.py tests/integration/test_execucoes_classificacao.py` (usando `ClassificadorMultimodal` fake determinístico).
- `make lint && make types`.

## Evidências e pendências

Pendente de execução.
