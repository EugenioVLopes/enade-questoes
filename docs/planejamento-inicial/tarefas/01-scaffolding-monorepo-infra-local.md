# 01 — Scaffolding do monorepo, infraestrutura local e healthcheck

Status: `pendente`

Plano: [plano.md](../plano.md) · Pedido: [task.md](../task.md) · Explicação: [explicacao.md](../explicacao.md) · Decisão: [arquitetura e simplificação da stack](../decisoes/08-arquitetura-e-simplificacao-stack.md)

## Contexto

O repositório atualmente contém apenas a documentação de planejamento (`docs/`, `GLOSSARY.md`), `.env.example`, `.gitignore` e protótipos descartáveis em `prototypes/`. Antes de implementar o domínio e as fatias funcionais, precisamos da espinha dorsal do monorepo (`backend/` + `frontend/`), do banco local **PostgreSQL 16** via `compose.yaml`, da automação de comandos no `Makefile` e das travas mecânicas de qualidade (`ruff`, `pytest`, `import-linter`, `vitest`, `eslint`/`tsc`).

## Entrega observável

Monorepo inicializável localmente com `make db-up`, `make lint`, `make test` e `make dev`, backend FastAPI expondo `GET /api/v1/health` (verificando PostgreSQL e estado do worker), contrato de 4 camadas hexagonais validado pelo `import-linter` e shell inicial do frontend Vite + React + TypeScript + Tailwind + shadcn/ui compilando limpo.

## Escopo e limites

- **Raiz do monorepo**:
  - `compose.yaml` enxuto com serviço `postgres` (`postgres:16-alpine`, volume local persistente e healthcheck).
  - `Makefile` com alvos base (`db-up`, `db-down`, `migrate`, `dev-backend`, `dev-frontend`, `dev`, `lint`, `test`, `types`).
  - Atualizar `.env.example` incluindo `DATABASE_URL`, `DATA_DIR` (padrão `./data/app`) e as variáveis `LLM_*` já existentes.
- **Backend (`backend/`)**:
  - `pyproject.toml` com Python 3.13, `uv`, FastAPI, Uvicorn, Pydantic v2, `pydantic-settings`, `psycopg[binary]`, SQLAlchemy 2, Alembic, `ruff`, `pytest`, `httpx` e `import-linter`.
  - Estrutura vazia inicial das 4 camadas em `backend/src/{domain,application,infrastructure,presentation}/`.
  - Configuração do `import-linter` proibindo imports de `application`/`infrastructure`/`presentation` e de bibliotecas externas (`fastapi`, `sqlalchemy`, `docling`, `pdfplumber`, `openai`) dentro de `src/domain/`.
  - `GET /api/v1/health` retornando status do serviço, conectividade com PostgreSQL e estado inicial do worker local (`ocioso`).
- **Frontend (`frontend/`)**:
  - Projeto Vite + React + TypeScript gerenciado com `pnpm`, Tailwind CSS, configuração base de shadcn/ui, TanStack Query, React Router, Zod, Vitest + Testing Library e script `openapi-typescript` apontando para o schema OpenAPI do backend (`make types`).
- **Fora de escopo desta tarefa**: entidades de domínio, migrations de tabelas, adaptadores de PDF/LLM e telas funcionais da SPA.

## Dependências

Nenhuma.

## Critérios de aceite

- [ ] `docker compose up -d postgres` sobe o PostgreSQL 16 com healthcheck saudável.
- [ ] `backend/` possui as 4 camadas (`domain`, `application`, `infrastructure`, `presentation`) e `import-linter` valida o isolamento de `src/domain/` com exit code `0`.
- [ ] `GET /api/v1/health` responde `200 OK` indicando conectividade com PostgreSQL e estado do worker local (coberto por teste automatizado).
- [ ] `frontend/` compila (`pnpm build`), passa no type-check (`pnpm type-check`) e executa ao menos 1 teste smoke no Vitest.
- [ ] `make types` gera o arquivo de tipos TypeScript em `frontend/src/api/` a partir do OpenAPI exportado pelo FastAPI sem erro.
- [ ] `make lint` e `make test` passam integralmente.

## Verificação

- Subir banco: `make db-up` e confirmar container `healthy`.
- Backend: `uv run ruff check .`, `uv run lint-imports`, `uv run pytest`.
- Frontend: `pnpm type-check`, `pnpm lint`, `pnpm test`, `pnpm build`.
- Geração de tipos: `make types` e confirmar geração do arquivo de schema TS.

## Evidências e pendências

Pendente de execução.
