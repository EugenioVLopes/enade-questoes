from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient

from application.health import HealthUseCase, WorkerStatus
from presentation.api.app import create_app


class _StubProbe:
    def __init__(self, online: bool) -> None:
        self._online = online

    def ping(self) -> bool:
        return self._online


def test_health_use_case_retorna_ok_quando_banco_conectado() -> None:
    use_case = HealthUseCase(db_probe=_StubProbe(online=True))
    result = use_case.execute()

    assert result.status == "ok"
    assert result.banco_dados == "conectado"
    assert result.worker == WorkerStatus(
        estado="ocioso",
        tarefa_ativa=None,
        tipo=None,
        alvo=None,
        processadas=None,
        total=None,
    )


def test_health_use_case_retorna_degradado_quando_banco_indisponivel() -> None:
    use_case = HealthUseCase(db_probe=_StubProbe(online=False))
    result = use_case.execute()

    assert result.status == "degradado"
    assert result.banco_dados == "indisponivel"
    assert result.worker == WorkerStatus(
        estado="ocioso",
        tarefa_ativa=None,
        tipo=None,
        alvo=None,
        processadas=None,
        total=None,
    )


def test_health_use_case_consulta_provedor_dinamico_de_status_do_worker() -> None:
    estado_dinamico = WorkerStatus(
        estado="ocupado",
        tarefa_ativa="Classificando ENADE 2023: 14/29",
        tipo="classificacao",
        alvo="ENADE 2023",
        processadas=14,
        total=29,
    )
    app = create_app(
        health_use_case=HealthUseCase(
            db_probe=_StubProbe(online=True),
            worker_status_provider=lambda: estado_dinamico,
        )
    )
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "banco_dados": "conectado",
        "worker": {
            "estado": "ocupado",
            "tarefa_ativa": "Classificando ENADE 2023: 14/29",
            "tipo": "classificacao",
            "alvo": "ENADE 2023",
            "processadas": 14,
            "total": 29,
        },
    }


def test_get_health_retorna_200_quando_banco_conectado(
    make_fake_client: Callable[[bool], TestClient],
) -> None:
    client = make_fake_client(True)
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "banco_dados": "conectado",
        "worker": {
            "estado": "ocioso",
            "tarefa_ativa": None,
            "tipo": None,
            "alvo": None,
            "processadas": None,
            "total": None,
        },
    }


def test_get_health_retorna_503_quando_banco_indisponivel(
    make_fake_client: Callable[[bool], TestClient],
) -> None:
    client = make_fake_client(False)
    response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degradado",
        "banco_dados": "indisponivel",
        "worker": {
            "estado": "ocioso",
            "tarefa_ativa": None,
            "tipo": None,
            "alvo": None,
            "processadas": None,
            "total": None,
        },
    }
