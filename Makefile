export PYTHONUTF8 := 1
export COREPACK_ENABLE_DOWNLOAD_PROMPT := 0

.PHONY: db-up db-down migrate dev-backend dev-frontend dev lint test types

db-up:
	docker compose up -d --wait postgres

db-down:
	docker compose down

migrate:
	cd backend && uv run alembic upgrade head

dev-backend:
	cd backend && uv run uvicorn presentation.main:app --reload --host 127.0.0.1 --port 8000

dev-frontend:
	cd frontend && pnpm dev

dev:
	$(MAKE) -j2 dev-backend dev-frontend

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run lint-imports
	cd frontend && pnpm type-check && pnpm lint

test:
	cd backend && uv run pytest
	cd frontend && pnpm test

types:
	cd backend && uv run python -m presentation.openapi_export ../frontend/.openapi.json
	cd frontend && pnpm exec openapi-typescript .openapi.json -o src/api/schema.d.ts
	rm -f frontend/.openapi.json
