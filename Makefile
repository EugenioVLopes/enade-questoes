export PYTHONUTF8 := 1
export COREPACK_ENABLE_DOWNLOAD_PROMPT := 0

.PHONY: db-up db-down migrate seed dev-backend dev-frontend dev lint test types golden-export eval-run eval-compare eval-history

db-up:
	docker compose up -d --wait postgres

db-down:
	docker compose down

migrate:
	cd backend && uv run alembic upgrade head

seed:
	cd backend && uv run python -m infrastructure.persistence.seed

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

golden-export:
	$(eval _TAXONOMIA := $(if $(TAXONOMIA),$(TAXONOMIA),enade-eng-computacao))
	$(eval _SAIDA := $(if $(SAIDA),$(SAIDA),evals/golden/$(_TAXONOMIA).json))
	uv run --project backend enade-eval exportar-ouro --taxonomia "$(_TAXONOMIA)" --saida "$(_SAIDA)"

eval-run:
	$(eval _TAXONOMIA := $(if $(TAXONOMIA),$(TAXONOMIA),enade-eng-computacao))
	$(eval _OURO := $(if $(OURO),$(OURO),evals/golden/$(_TAXONOMIA).json))
	$(eval _PERFIL := $(if $(PERFIL),$(PERFIL),v2-fronteiras@v1))
	uv run --project backend enade-eval avaliar --ouro "$(_OURO)" --perfil "$(_PERFIL)" $(EVAL_ARGS)

eval-compare:
	@if [ -z "$(BASELINE)" ] || [ -z "$(CANDIDATO)" ]; then \
		echo "Uso: make eval-compare BASELINE=<baseline.json> CANDIDATO=<candidato.json> [MODO_MIGRACAO=1]"; \
		exit 1; \
	fi
	uv run --project backend enade-eval comparar "$(BASELINE)" "$(CANDIDATO)" $(if $(MODO_MIGRACAO),--modo-migracao,)

eval-history:
	uv run --project backend enade-eval historico $(if $(TAXONOMIA),--taxonomia "$(TAXONOMIA)",)
