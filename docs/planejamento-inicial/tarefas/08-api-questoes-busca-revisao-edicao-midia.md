# 08 — API de Questões, busca textual/trigrama, revisão humana e edição de conteúdo/mídia

Status: `concluida`

Plano: [plano.md](../plano.md) · Pedido: [task.md](../task.md) · Explicação: [explicacao.md](../explicacao.md) · Decisões: [arquitetura e contratos](../decisoes/08-arquitetura-e-simplificacao-stack.md), [fluxos de revisão e consulta](../decisoes/09-fluxos-interface-web-revisao-consulta.md), [edição de mídia e casos de borda](../decisoes/10-tratamento-edicao-midia-e-casos-borda.md)

## Contexto

Esta tarefa completa a superfície HTTP do backend para suportar as seções `Questões` e `Revisão` da SPA: listagem com busca textual (`TSVECTOR` + `pg_trgm`) e filtros combináveis, fila priorizada de revisão, aprovação/correção imutável de `Classificação`, resolução atômica de `Divergência de Reclassificação`, edição curada de conteúdo/gabarito com reavaliação automática de alertas e gestão manual de `Ativo Visual`s.

## Entrega observável

Todos os endpoints `/api/v1/questoes/...` e `/api/v1/ativos-visuais/...` implementados, cobertos por testes de integração em PostgreSQL 16 real e refletidos nos tipos TypeScript gerados por `make types`.

## Escopo e limites

- **Consulta e fila (`GET /api/v1/questoes` e `GET /api/v1/questoes/{id}`)**:
  - Filtros combináveis: `q` (combinando `TSVECTOR` `portuguese`+`unaccent` e `pg_trgm` sobre enunciado, alternativas e `Tópico`s), `prova_id`, `ano`, `taxonomia_id`, `disciplina_id`, `incluir_secundarias` (padrão `true`), `topico`, `status_revisao`, `revisao_prioritaria`, `com_divergencia`, `usa_disciplina_arquivada`, `situacao_gabarito`, `com_alerta_extracao` (apenas alertas `aberto`) + paginação e contadores de abas (`pendentes`, `divergencias`, `disciplina_arquivada`) para o badge global da `Revisão`.
  - Ordenação determinística suportando modo consulta e modo fila de revisão (**1º `revisao_prioritaria = true`** → **2º menor `confianca`** → **3º `ano desc, numero asc`**).
  - `GET /api/v1/questoes/{id}` retorna enunciado, `Alternativa`s `A`–`E`, `Ativo Visual`s ordenados (com `origem` e `alternativa_letra`), `Gabarito`, `Alerta de Extração`s (`aberto` e `resolvido`), `Classificação` vigente na `Taxonomia` solicitada, `Divergência de Reclassificação` aberta, classificações em outras `Taxonomia`s e histórico append-only.
- **Revisão humana e divergências**:
  - `POST /api/v1/questoes/{id}/classificacoes/{taxonomia_id}/aprovar`: atualiza a `Classificação` vigente da IA in-place (`pendente_revisao → aprovada`, `revisada_em`).
  - `POST /api/v1/questoes/{id}/classificacoes/{taxonomia_id}/corrigir`: cria nova `Classificação` (`origem = humana`, `vigente = true`, `status = aprovada`, `substitui_classificacao_id`), preservando intacta a predição da IA; valida `1` principal ativa + `0..2` secundárias ativas distintas da principal + `Tópico`s normalizados.
  - `POST /api/v1/questoes/{id}/divergencias/{divergencia_id}/resolver`: executa atomicamente `aceitar_candidata | manter_humana | editar_manualmente` (neste último caso criando a nova `Classificação` humana e encerrando a divergência na mesma transação).
- **Edição curada de conteúdo, alertas e gestão manual de `Ativo Visual`s**:
  - `PATCH /api/v1/questoes/{id}`: atualiza `enunciado`, `Alternativa`s `A`–`E` (criando/separando faltantes) e `Gabarito` individual (`situacao_gabarito`, `alternativa_correta`), marca `editada_manualmente = true`, reavalia automaticamente os 4 `Alerta de Extração` estruturais (`formula_nao_decodificada`, `alternativas_incompletas`, `enunciado_suspeito`, `gabarito_ausente_na_prova`) e recalcula `revisao_prioritaria` das classificações pendentes sem disparar LLM automaticamente.
  - `PATCH /api/v1/questoes/{id}/alertas/{alerta_id}`: permite marcar alertas de inspeção (`pdf_via_ocr`, `fonte_symbol_detectada`) como `resolvido` (`resolvido_em`), marca `editada_manualmente = true` e recalcula `revisao_prioritaria`.
  - `POST /api/v1/questoes/{id}/ativos-visuais` (upload PNG/JPEG validado, `origem = upload_manual`, `alternativa_letra` opcional), `PATCH /api/v1/ativos-visuais/{id}` (reordenar, alterar `alternativa_letra` ou substituir imagem) e `DELETE /api/v1/ativos-visuais/{id}` — todas marcando `editada_manualmente = true` na `Questão`.
- **Regenerar tipos TS**: rodar `make types`.

## Dependências

- [03 — Persistência PostgreSQL 16, Alembic, armazenamento local e seed inicial](03-persistencia-postgres-alembic-seed.md)
- [05 — Worker local sequencial e API de Provas, Ingestão, Gabarito e Mídia](05-worker-local-api-provas-ingestao.md)
- [07 — API de Taxonomias, Perfis de Classificação e Execuções de Classificação](07-api-taxonomias-perfis-execucoes.md)

## Critérios de aceite

- [x] `GET /api/v1/questoes` aplica corretamente a combinação de filtros, encontra termos em português acentuado e siglas/código (`OSPF`, `VHDL`), inclui secundárias por padrão (`incluir_secundarias=true`) e respeita a ordenação da fila priorizada.
- [x] `aprovar` atualiza o registro da IA in-place; `corrigir` cria novo registro `origem=humana` mantendo a saída original da IA intacta no histórico.
- [x] `resolver` divergência com `editar_manualmente` grava a nova `Classificação` humana e fecha a divergência atomicamente (rollback completo em erro de validação).
- [x] `PATCH /api/v1/questoes/{id}` fecha automaticamente `formula_nao_decodificada` e `alternativas_incompletas` quando corrigidos (ou reabre se quebrados), marca `editada_manualmente=true` e não enfileira nenhuma `Execução de Classificação`.
- [x] `PATCH /api/v1/questoes/{id}/alertas/{alerta_id}` resolve `pdf_via_ocr` e remove a questão de `com_alerta_extracao=true` (e de `revisao_prioritaria` quando não houver outro gatilho).
- [x] CRUD manual de `Ativo Visual` (`POST`, `PATCH`, `DELETE`) grava/remove arquivos via `ArmazenamentoArquivos`, registra `origem=upload_manual` e atualiza `editada_manualmente=true`.
- [x] `make types` completa sem erros.

## Verificação

- `uv run pytest tests/integration/test_api_questoes.py tests/integration/test_api_revisao_divergencias.py tests/integration/test_api_edicao_midia.py`.
- `make lint && make types`.

## Evidências e pendências

- **Artefatos locais do Teamwork (fora do Git)**: `docs/planejamento-inicial/artefatos/08-teamwork/` (`prompt.md`, `resultado.md` e o estado do run com decisões D1–D28, handoffs e gates). Veredito: `VICTORY CONFIRMED` após 4 iterações.
- **Consulta, busca e fila (R1)**:
  - `backend/src/application/questoes.py`, `backend/src/application/busca.py` e `backend/src/application/ports/consulta_questoes.py`.
  - `backend/src/infrastructure/persistence/consulta_questoes.py` e `backend/src/infrastructure/persistence/predicados.py`.
  - `backend/alembic/versions/0003_indice_trigrama_topicos.py`: índice GIN de trigramas sobre `Tópico`s.
  - Ordenação da fila: `prioridade_efetiva DESC, confianca ASC NULLS LAST, ano DESC, numero ASC`.
- **Revisão humana e divergências (R2)**:
  - `backend/src/application/revisao.py` e `backend/src/domain/classificacao.py`.
  - `aprovar` grava por UPDATE condicional e responde 409 se perder uma corrida.
  - `resolver` roda numa só transação, com rollback completo em erro.
- **Edição curada, alertas e ativos visuais (R3)**:
  - Arquivos:
    - `backend/src/domain/prova.py`, `backend/src/application/ports/imagem.py` e `backend/src/infrastructure/imagem.py`;
    - `backend/src/presentation/api/v1/ativos_visuais.py` e `backend/src/presentation/api/tipos.py`;
    - `backend/alembic/versions/0004_versao_questao.py`: lock otimista em `questoes.versao`.
  - Ingestão, reprocessamento e gabarito (`backend/src/application/worker.py` e `backend/src/application/provas.py`) não usam a checagem de versão do revisor: travam as linhas e preservam a edição dele.
  - A borda HTTP rejeita com 422:
    - NUL e surrogates;
    - listas e textos acima dos limites.
- **Rotas, wiring e tipos (R4)**:
  - `backend/src/presentation/api/v1/questoes.py` e `backend/src/presentation/api/schemas_questoes.py`;
  - `backend/src/presentation/api/app.py` e `backend/src/presentation/main.py`;
  - `frontend/src/api/schema.d.ts`, regenerado por `make types`.
- **Testes automatizados**:
  - Aceite: `backend/tests/integration/test_api_questoes.py`, `test_api_revisao_divergencias.py` e `test_api_edicao_midia.py`.
  - Complementares: `test_api_questoes_validacoes.py`, `test_api_questoes_entradas_textuais.py`, `test_api_questoes_complementos.py`, `test_api_concorrencia_questoes.py` e `test_concorrencia_sistema.py`, além de `backend/tests/unit/test_curadoria_topicos.py`.
- **Verificações reexecutadas no victory audit** (PostgreSQL 16 real, banco isolado):
  - `cd backend && uv run pytest tests/integration/test_api_questoes.py tests/integration/test_api_revisao_divergencias.py tests/integration/test_api_edicao_midia.py` → `18 passed`
  - `cd backend && uv run pytest` → `307 passed`
  - `make lint && make types` → exit code `0`; `frontend/src/api/schema.d.ts` ficou idêntico depois da regeneração.
- **Pendências**:
  - Validação manual: pendente.
  - Notas consultivas não bloqueantes, como nomes, helpers duplicados, mensagens de 422 e a divergência de `DATA_DIR/provas` na documentação: listadas em `artefatos/08-teamwork/resultado.md`.
