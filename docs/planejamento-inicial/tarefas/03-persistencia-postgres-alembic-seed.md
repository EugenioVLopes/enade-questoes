# 03 — Persistência PostgreSQL 16, Alembic, armazenamento local e seed inicial

Status: `concluida`

Plano: [plano.md](../plano.md) · Pedido: [task.md](../task.md) · Pesquisas/Decisões: [matriz ENADE e 18 disciplinas](../pesquisas/matriz-enade-dcns-eng-computacao.md), [modelo de domínio](../decisoes/06-modelo-de-dominio-e-glossario.md), [arquitetura e persistência](../decisoes/08-arquitetura-e-simplificacao-stack.md)

## Contexto

Com o domínio e as portas definidos na Tarefa 02, precisamos materializar o schema relacional no **PostgreSQL 16** (incluindo busca textual nativa em português + trigramas), a camada de repositórios SQLAlchemy 2, o adaptador de armazenamento em `DATA_DIR` e o seed idempotente da `Taxonomia` oficial de Engenharia de Computação (18 `Disciplina`s + `Perfil de Classificação` `v2-fronteiras`), para que a aplicação já nasça pronta para uso no primeiro acesso.

## Entrega observável

Migration Alembic inicial aplicável via `make migrate` criando todo o schema no PostgreSQL 16 (com `unaccent`, `pg_trgm`, `TSVECTOR` e índices GIN), repositórios concretos + `ArmazenamentoArquivos` em `DATA_DIR` implementados e seed idempotente carregando as 18 `Disciplina`s e o perfil `v2-fronteiras`, verificados por testes de integração em banco real.

## Escopo e limites

- **Schema PostgreSQL 16 + Alembic**:
  - Extensões `unaccent` e `pg_trgm`.
  - Tabelas para: `provas` (constraint única `(exame, curso, ano)`), `ingestoes`, `questoes` (`editada_manualmente`, `situacao_gabarito`, `alternativa_correta`, coluna/índice `TSVECTOR` `portuguese`+`unaccent` e índices GIN `pg_trgm`), `alternativas` (única `(questao_id, letra)`), `ativos_visuais` (`origem`, `alternativa_letra` opcional, `ordem`, `pagina`, `bbox` JSONB), `alertas_extracao` (`codigo`, `severidade`, `status`, `resolvido_em`), `taxonomias`, `disciplinas` (`codigo` único por taxonomia, `ativa`), `perfis_classificacao` (`(codigo, versao)` único, imutável), `execucoes_classificacao` (`snapshot_taxonomia` JSONB, `snapshot_perfil` JSONB, contadores/métricas), `classificacoes` (histórico append-only, índice único parcial para `vigente = true` por `(questao_id, taxonomia_id)`, `disciplinas_secundarias`, `topicos`, `origem`, `status`, `revisao_prioritaria`, `substitui_classificacao_id`) e `divergencias_reclassificacao`.
- **Repositórios SQLAlchemy 2** em `backend/src/infrastructure/persistence/` implementando as portas de `application/ports/`.
- **Adaptador `ArmazenamentoArquivosLocal`** em `backend/src/infrastructure/storage/` gerenciando `DATA_DIR/storage/provas/{prova_id}/` (`prova.pdf`, `gabarito.pdf`, `extracao_bruta.json`, `ativos/{ativo_id}.png`) e `DATA_DIR/cache/llm/`.
- **Seed idempotente** (executável no boot ou via comando `make seed`):
  - `Taxonomia` `enade-eng-computacao` com as 18 `Disciplina`s canônicas e ementas de [pesquisas/matriz-enade-dcns-eng-computacao.md](../pesquisas/matriz-enade-dcns-eng-computacao.md).
  - `Perfil de Classificação` `v2-fronteiras` (v1) com `diretrizes_gerais`, `guia_fronteiras` (14 fronteiras interdisciplinares) e `template_prompt` validados no protótipo 07.
- **Fora de escopo**: endpoints HTTP além do healthcheck, Docling, `pdfplumber` e chamadas a LLM.

## Dependências

- [02 — Núcleo de domínio, regras determinísticas e portas](02-nucleo-dominio-regras-deterministicas.md)

## Critérios de aceite

- [x] `alembic upgrade head` (e `downgrade base` → `upgrade head`) executam sem erro em PostgreSQL 16 limpo.
- [x] Restrições de integridade funcionam no banco: unicidade de `(exame, curso, ano)` em `Prova`, unicidade de `Classificação` `vigente = true` por `(questao_id, taxonomia_id)` e preservação histórica ao criar nova `Classificação` humana.
- [x] Busca textual combinada (`TSVECTOR` `portuguese`+`unaccent` + `pg_trgm`) encontra acentuação/flexões em português e termos técnicos exatos (`OSPF`, `VHDL`, `O(n log n)`) em teste de integração real.
- [x] Seed executado 2 vezes seguidas é 100% idempotente, resultando exatamente em 1 `Taxonomia`, 18 `Disciplina`s ativas e 1 `Perfil de Classificação` `v2-fronteiras`.
- [x] `ArmazenamentoArquivosLocal` grava, lê e remove arquivos respeitando a árvore de `DATA_DIR` e rejeitando *path traversal*.

## Verificação

- Subir PostgreSQL (`make db-up`), rodar `make migrate` e `uv run pytest tests/integration/test_persistence.py tests/integration/test_seed.py`.

## Evidências e pendências

- **Artefatos locais do Teamwork (fora do Git)**: `docs/planejamento-inicial/artefatos/03-teamwork/` (`prompt.md`, `resultado.md` e relatórios de auditoria; veredito: `VICTORY CONFIRMED`).
- **Schema PostgreSQL 16 e Alembic**: `backend/alembic/env.py`, `backend/alembic/versions/0001_schema_inicial.py`, `backend/src/infrastructure/persistence/database.py` e `backend/src/infrastructure/persistence/models.py` (extensões `unaccent` e `pg_trgm`, configuração `pt_unaccent`, 12 tabelas, índice único funcional em `provas`, índice único parcial `vigente = true` em `classificacoes`, trigger `questoes.busca_tsv` e índices GIN).
- **Repositórios SQLAlchemy 2**: `backend/src/infrastructure/persistence/repositorios.py` implementando os 9 repositórios do núcleo de persistência definidos em `backend/src/application/ports/repositorios.py` e busca textual combinada (`pt_unaccent` + `pg_trgm` + correspondência exata para tokens técnicos).
- **Armazenamento local**: `backend/src/infrastructure/storage/local.py` (`ArmazenamentoArquivosLocal`) com escrita atômica e rejeição de *path traversal* / escape por symlink.
- **Seed idempotente**: `backend/src/application/seed.py`, `backend/src/infrastructure/persistence/seed.py` e alvo `make seed` no `Makefile` carregando `enade-eng-computacao` (18 disciplinas ativas) e `v2-fronteiras:v1` (14 fronteiras interdisciplinares).
- **Verificações executadas**:
  - `make lint` → exit code `0` (`ruff check .`, `ruff format --check .` em 58 arquivos, `lint-imports` 3/3 contratos, `pnpm type-check`, `pnpm lint`)
  - `cd backend && uv run alembic check` → `No new upgrade operations detected.`
  - `make migrate && make seed && make seed` → `0001_schema_inicial (head)` e seed idempotente (1 taxonomia, 18 disciplinas ativas, 1 perfil `v2-fronteiras:v1`)
  - `cd backend && uv run pytest -v` → `138 passed` (incluindo `tests/integration/test_persistence.py` 10/10, `tests/integration/test_seed.py` 1/1, `tests/integration/test_health_postgres.py` 1/1 e `tests/unit/test_armazenamento_local.py` 16/16)
  - `make test` → `138 passed` (backend) + `1 passed` (frontend)
- **Pendências**: nenhuma na Tarefa 03 (`RepositorioConjuntoOuro` permanece previsto para a Tarefa 14, conforme escopo acordado).
