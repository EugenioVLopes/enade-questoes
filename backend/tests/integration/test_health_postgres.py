from __future__ import annotations

from fastapi.testclient import TestClient

from presentation.main import build_app


def test_get_health_com_postgresql_real_retorna_200() -> None:
    app = build_app()
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "banco_dados": "conectado",
        "worker": {
            "estado": "ocioso",
            "tarefa_ativa": None,
        },
    }
