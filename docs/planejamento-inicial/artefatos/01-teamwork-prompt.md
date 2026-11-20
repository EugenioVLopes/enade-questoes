Implementar a Tarefa 01 (`docs/planejamento-inicial/tarefas/01-scaffolding-monorepo-infra-local.md`) do projeto **Enade Questões**, entregando o scaffolding inicial do monorepo (`backend/` + `frontend/`), PostgreSQL 16 local via `compose.yaml`, automação no `Makefile`, endpoint `GET /api/v1/health`, contrato de 4 camadas hexagonais validado por `import-linter` e shell inicial do frontend compilando limpo. O propósito é estabelecer a fundação local de desenvolvimento/produção da v1.

Working directory: `.` (raiz do repositório `enade-questoes`)
Integrity mode: development

## Verification Resources

- Especificação e planejamento do repositório: `docs/planejamento-inicial/tarefas/01-scaffolding-monorepo-infra-local.md`, `docs/planejamento-inicial/plano.md`, `docs/planejamento-inicial/explicacao.md`, `docs/planejamento-inicial/decisoes/08-arquitetura-e-simplificacao-stack.md`, `GLOSSARY.md`, `AGENTS.md`, `.env.example` e `.gitignore`.

## Requirements

### R1. Raiz do monorepo e infraestrutura local
- Criar `compose.yaml` enxuto com o serviço `postgres` (`postgres:16-alpine`, volume local persistente e healthcheck).
- Criar `Makefile` na raiz com os alvos base: `db-up`, `db-down`, `migrate`, `dev-backend`, `dev-frontend`, `dev`, `lint`, `test` e `types` (ficando a cargo do time como tratar `make migrate` / Alembic nesta tarefa, desde que sem criar migrations de tabelas).
- Atualizar `.env.example` incluindo `DATABASE_URL`, `DATA_DIR` (padrão `./data/app`) e mantendo as variáveis `LLM_*` já existentes.

### R2. Backend FastAPI em arquitetura hexagonal de 4 camadas
- Configurar `backend/pyproject.toml` com Python 3.13, `uv`, FastAPI, Uvicorn, Pydantic v2, `pydantic-settings`, `psycopg[binary]`, SQLAlchemy 2, Alembic, `ruff`, `pytest`, `httpx` e `import-linter`.
- Criar a estrutura inicial das 4 camadas em `backend/src/{domain,application,infrastructure,presentation}/`.
- Configurar o `import-linter` proibindo imports de `application`, `infrastructure`, `presentation` e de bibliotecas externas (`fastapi`, `sqlalchemy`, `docling`, `pdfplumber`, `openai`) dentro de `src/domain/`.
- Expor `GET /api/v1/health` retornando status do serviço, conectividade com PostgreSQL e estado inicial do worker local (`ocioso`), ficando a cargo do time o comportamento quando o PostgreSQL estiver indisponível e a estratégia dos testes automatizados contra PostgreSQL, desde que o critério de teste automatizado de `200 OK` seja atendido.

### R3. Shell inicial do Frontend e geração de tipos
- Configurar projeto em `frontend/` com Vite + React + TypeScript gerenciado com `pnpm`, Tailwind CSS, configuração base de shadcn/ui, TanStack Query, React Router, Zod, Vitest + Testing Library e script `openapi-typescript` apontando para o schema OpenAPI do backend (`make types`).

### R4. Limites de escopo, controle de versão e documentação
- Fora de escopo desta tarefa: entidades de domínio, migrations de tabelas, adaptadores de PDF/LLM e telas funcionais da SPA.
- Nunca executar `git push` nem alterar recursos remotos sem autorização explícita.
- Manter artefatos de IA/MCP (`.serena/`, `.codebase-memory/`, `.cbmignore`, `.claude/`, `.gemini/`, `.agents/`), `.env` e `data/` fora do Git.
- Manter todas as alterações apenas na *working tree* para revisão do usuário antes de qualquer commit (não executar `git commit`).
- Atualizar `docs/planejamento-inicial/tarefas/01-scaffolding-monorepo-infra-local.md` (status, checklist e evidências) conforme os critérios forem verificados.

## Acceptance Criteria

### Infraestrutura e Automação
- [ ] `docker compose up -d postgres` (e `make db-up`) sobe o PostgreSQL 16 com healthcheck saudável.
- [ ] `make types` gera o arquivo de tipos TypeScript em `frontend/src/api/` a partir do OpenAPI exportado pelo FastAPI sem erro.
- [ ] `make lint` e `make test` passam integralmente.

### Backend
- [ ] `backend/` possui as 4 camadas (`domain`, `application`, `infrastructure`, `presentation`) e `import-linter` (`uv run lint-imports`) valida o isolamento de `src/domain/` com exit code `0`.
- [ ] `GET /api/v1/health` responde `200 OK` indicando conectividade com PostgreSQL e estado do worker local (`ocioso`), coberto por teste automatizado.
- [ ] `uv run ruff check .` e `uv run pytest` passam sem erros.

### Frontend
- [ ] `frontend/` compila (`pnpm build`), passa no type-check (`pnpm type-check`), passa no lint (`pnpm lint`) e executa ao menos 1 teste smoke no Vitest (`pnpm test`).

### Documentação e Controle
- [ ] `docs/planejamento-inicial/tarefas/01-scaffolding-monorepo-infra-local.md` atualizado com status, checklist preenchido e evidências dos comandos executados.
- [ ] Nenhuma alteração remota (`git push`) nem `git commit` realizados, e nenhum artefato proibido (`.env`, `data/`, `.serena/`, `.codebase-memory/`, `.cbmignore`, `.claude/`, `.gemini/`, `.agents/`) rastreado ou adicionado no Git.