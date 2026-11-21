Implementar a camada de persistência em PostgreSQL 16 (schema e migrations Alembic), os 9 repositórios SQLAlchemy 2 do núcleo de persistência, o adaptador de armazenamento local em `DATA_DIR` (`ArmazenamentoArquivosLocal`) e o seed idempotente da `Taxonomia` oficial de Engenharia de Computação (`enade-eng-computacao` com 18 `Disciplina`s) e do `Perfil de Classificação` `v2-fronteiras` para a Tarefa 03 do projeto Enade Questões.

Integrity mode: development

Referências do projeto:
- `docs/planejamento-inicial/tarefas/03-persistencia-postgres-alembic-seed.md`
- `docs/planejamento-inicial/pesquisas/matriz-enade-dcns-eng-computacao.md`
- `docs/planejamento-inicial/decisoes/06-modelo-de-dominio-e-glossario.md`
- `docs/planejamento-inicial/decisoes/08-arquitetura-e-simplificacao-stack.md`
- `prototypes/07-classificacao-llm/run_prototype.py`

## Requirements

### R1. Schema PostgreSQL 16 e migrations Alembic
Criar migration Alembic inicial aplicável via `make migrate` em PostgreSQL 16 limpo habilitando as extensões `unaccent` e `pg_trgm` e criando as tabelas: `provas` (constraint única `(exame, curso, ano)`), `ingestoes`, `questoes` (`editada_manualmente`, `situacao_gabarito`, `alternativa_correta`, coluna/índice `TSVECTOR` `portuguese`+`unaccent` e índices GIN `pg_trgm`), `alternativas` (única `(questao_id, letra)`), `ativos_visuais` (`origem`, `alternativa_letra` opcional, `ordem`, `pagina`, `bbox` JSONB), `alertas_extracao` (`codigo`, `severidade`, `status`, `resolvido_em`), `taxonomias`, `disciplinas` (`codigo` único por taxonomia, `ativa`), `perfis_classificacao` (`(codigo, versao)` único, imutável), `execucoes_classificacao` (`snapshot_taxonomia` JSONB, `snapshot_perfil` JSONB, contadores/métricas), `classificacoes` (histórico append-only, índice único parcial para `vigente = true` por `(questao_id, taxonomia_id)`, `disciplinas_secundarias`, `topicos`, `origem`, `status`, `revisao_prioritaria`, `substitui_classificacao_id`) e `divergencias_reclassificacao`.

### R2. Repositórios SQLAlchemy 2 do núcleo de persistência
Implementar em `backend/src/infrastructure/persistence/` os 9 repositórios concretos do núcleo de persistência que implementam as portas correspondentes em `application/ports/repositorios.py`: `RepositorioProvas`, `RepositorioIngestoes`, `RepositorioQuestoes`, `RepositorioAtivosVisuais`, `RepositorioTaxonomias`, `RepositorioPerfisClassificacao`, `RepositorioExecucoesClassificacao`, `RepositorioClassificacoes` e `RepositorioDivergenciasReclassificacao`.

### R3. Armazenamento local em DATA_DIR
Implementar `ArmazenamentoArquivosLocal` em `backend/src/infrastructure/storage/` gerenciando `DATA_DIR/storage/provas/{prova_id}/` (`prova.pdf`, `gabarito.pdf`, `extracao_bruta.json`, `ativos/{ativo_id}.png`) e `DATA_DIR/cache/llm/`, respeitando a árvore de `DATA_DIR` e rejeitando *path traversal*.

### R4. Seed idempotente
Implementar seed idempotente (executável no boot ou via comando `make seed`, ficando a forma de acionamento a critério da equipe) carregando a `Taxonomia` `enade-eng-computacao` com as 18 `Disciplina`s canônicas e ementas de `docs/planejamento-inicial/pesquisas/matriz-enade-dcns-eng-computacao.md` e o `Perfil de Classificação` `v2-fronteiras` (v1) com `diretrizes_gerais`, `guia_fronteiras` (14 fronteiras interdisciplinares) e `template_prompt` validados no protótipo 07 (`prototypes/07-classificacao-llm/run_prototype.py`).

### R5. Fora de escopo
Não fazem parte desta tarefa: `RepositorioConjuntoOuro` (previsto para a Tarefa 14), endpoints HTTP além do healthcheck, Docling, `pdfplumber` e chamadas a LLM.

## Verification Resources

- `make db-up` (PostgreSQL 16 via `compose.yaml`)
- `make migrate`
- `make lint`
- `uv run pytest` (suíte completa, incluindo `tests/integration/test_persistence.py` e `tests/integration/test_seed.py`)

## Acceptance Criteria

### Migrações e esquema PostgreSQL 16
- [ ] `alembic upgrade head` (e `downgrade base` -> `upgrade head`) executam sem erro em PostgreSQL 16 limpo.

### Integridade relacional e histórico
- [ ] Restrições de integridade funcionam no banco: unicidade de `(exame, curso, ano)` em `Prova`, unicidade de `Classificação` `vigente = true` por `(questao_id, taxonomia_id)` e preservação histórica ao criar nova `Classificação` humana.

### Busca textual combinada
- [ ] Busca textual combinada (`TSVECTOR` `portuguese`+`unaccent` + `pg_trgm`) encontra acentuação/flexões em português e termos técnicos exatos (`OSPF`, `VHDL`, `O(n log n)`) em teste de integração real.

### Idempotência do seed
- [ ] Seed executado 2 vezes seguidas é 100% idempotente, resultando exatamente em 1 `Taxonomia`, 18 `Disciplina`s ativas e 1 `Perfil de Classificação` `v2-fronteiras`.

### Armazenamento seguro em DATA_DIR
- [ ] `ArmazenamentoArquivosLocal` grava, lê e remove arquivos respeitando a árvore de `DATA_DIR` e rejeitando *path traversal*.

### Qualidade, arquitetura e suíte de testes
- [ ] `make lint` (`ruff check`, `ruff format --check`, `lint-imports`) e a suíte completa `uv run pytest` (incluindo `tests/integration/test_persistence.py` e `tests/integration/test_seed.py`) executam e passam sem erros.
