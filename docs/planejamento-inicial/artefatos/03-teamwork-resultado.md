# Artefato — Resultado Teamwork da Tarefa 03

Tarefa: [03 — Persistência PostgreSQL 16, Alembic, armazenamento local e seed inicial](../tarefas/03-persistencia-postgres-alembic-seed.md)
Prompt aprovado: [03-teamwork-prompt.md](./03-teamwork-prompt.md)
Veredito da auditoria independente pós-vitória: **`VICTORY CONFIRMED`** (2 iterações)

## Resumo das entregas

- **Schema PostgreSQL 16 e migrations Alembic (`R1`)**:
  - `backend/alembic/env.py`, `backend/alembic/versions/0001_schema_inicial.py`, `backend/src/infrastructure/persistence/database.py` e `backend/src/infrastructure/persistence/models.py`.
  - Extensões `unaccent` e `pg_trgm`, configuração de busca textual `pt_unaccent` (`unaccent` antes de `portuguese_stem`) e criação reversível das 12 tabelas (`provas`, `ingestoes`, `questoes`, `alternativas`, `ativos_visuais`, `alertas_extracao`, `taxonomias`, `disciplinas`, `perfis_classificacao`, `execucoes_classificacao`, `classificacoes`, `divergencias_reclassificacao`).
  - Índice único funcional `(upper(exame), curso, ano)` em `provas`, índice único parcial `(questao_id, taxonomia_id) WHERE vigente = true` em `classificacoes`, coluna `questoes.busca_tsv` mantida por trigger (`enunciado` peso A + `alternativas` peso B), índices GIN `pg_trgm` e índice GIN `jsonb_to_tsvector` em `classificacoes.topicos`.
- **9 Repositórios SQLAlchemy 2 (`R2`, `backend/src/infrastructure/persistence/`)**:
  - `repositorios.py` e `__init__.py` implementando integralmente os 9 protocolos do núcleo de persistência de `backend/src/application/ports/repositorios.py` (sem alterar `domain/` ou `application/ports/`).
  - `RepositorioQuestoesSqlAlchemy.buscar_por_texto` combinando FTS `pt_unaccent`, `jsonb_array_elements_text` + `pg_trgm` `ILIKE` e roteamento exato para tokens técnicos com pontuação (`OSPF`, `VHDL`, `O(n log n)`, `C#`, `C:\temp`, `[0]`).
  - Preservação histórica append-only com bloqueio `FOR UPDATE` + desativação prévia de `vigente` antes de inserir nova classificação humana ou resolver divergências atomicamente.
- **Armazenamento local em `DATA_DIR` (`R3`, `backend/src/infrastructure/storage/`)**:
  - `local.py` e `__init__.py` implementando `ArmazenamentoArquivosLocal` para `DATA_DIR/storage/provas/{prova_id}/` (`prova.pdf`, `gabarito.pdf`, `extracao_bruta.json`, `ativos/{ativo_id}.png`) e `DATA_DIR/cache/llm/`, com escrita atômica via arquivo temporário e rejeição de *path traversal* e escape por symlink (`ErroValidacaoDominio`).
- **Seed idempotente (`R4`)**:
  - `backend/src/application/seed.py`, `backend/src/infrastructure/persistence/seed.py` e alvo `make seed` no `Makefile`.
  - Carregamento idempotente da `Taxonomia` `enade-eng-computacao` com as 18 `Disciplina`s canônicas e ementas de [matriz-enade-dcns-eng-computacao.md](../pesquisas/matriz-enade-dcns-eng-computacao.md) e do `PerfilClassificacao` imutável `v2-fronteiras` (`versao="v1"`) com `diretrizes_gerais`, `guia_fronteiras` (14 fronteiras interdisciplinares) e `template_prompt` alinhados ao protótipo 07.
- **Testes unitários e de integração (`backend/tests/`)**:
  - `tests/integration/conftest.py`, `tests/integration/test_persistence.py` (10 testes), `tests/integration/test_seed.py` (1 teste) e `tests/unit/test_armazenamento_local.py` (16 testes).
- **Fora de escopo respeitado (`R5`)**:
  - `RepositorioConjuntoOuro` mantido para a Tarefa 14; sem novos endpoints HTTP além do healthcheck, sem Docling, `pdfplumber` ou chamadas a LLM.

## Verificações confirmadas na auditoria independente

- `make lint`: exit `0` (`ruff check .`, `ruff format --check .` em 58 arquivos, `lint-imports` 3/3 contratos, `pnpm type-check`, `pnpm lint`).
- `cd backend && uv run alembic check`: exit `0` (`No new upgrade operations detected.`).
- `make migrate`: exit `0` (`0001_schema_inicial (head)`).
- `make seed && make seed`: exit `0`, 100% idempotente (`taxonomia='enade-eng-computacao'` com 18 disciplinas ativas e `perfil='v2-fronteiras:v1'`).
- Sonda em banco PostgreSQL 16.15 temporário limpo (`alembic upgrade head` + 2x `seed_banco_dados`): passou (`CLEAN_DB_SEED_PROBE_OK True True 18`, UUIDs preservados).
- `cd backend && uv run pytest -v`: exit `0` (`138 passed`, incluindo `test_persistence.py` 10/10, `test_seed.py` 1/1, `test_health_postgres.py` 1/1 e `test_armazenamento_local.py` 16/16).
- `make test`: exit `0` (`138 passed` no backend + `1 passed` no frontend).
- Higiene e integridade: `0` alterações em `domain/`, `application/ports/` ou `presentation/`; `0` caminhos absolutos locais ou artefatos de IA/MCP no repositório.

## Notas consultivas (não bloqueantes para futuras tarefas)

- Consultas alfanuméricas mistas contendo `%` ou `&` (ex.: `"50%"`, `"AT&T"`) seguem roteadas por `websearch_to_tsquery`; tokens isolados com `%`, `_` ou `\` já são tratados de forma segura.
- 6 colunas FK secundárias ainda não possuem índice B-tree próprio (baixo impacto na carga atual append-only; podem ser indexadas sob demanda se consultas analíticas exigirem).
