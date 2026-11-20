"""Exporta o schema OpenAPI da aplicação FastAPI sem exigir banco ativo."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from application.health import HealthUseCase
from presentation.api.app import create_app


class _OfflineDatabaseProbe:
    def ping(self) -> bool:
        return True


def export_openapi(output_path: Path) -> None:
    app = create_app(health_use_case=HealthUseCase(db_probe=_OfflineDatabaseProbe()))
    schema = app.openapi()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
    export_openapi(target)


if __name__ == "__main__":
    main()
