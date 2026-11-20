from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from application.health import HealthUseCase
from presentation.api.app import create_app


class _FakeDatabaseProbe:
    def __init__(self, online: bool) -> None:
        self._online = online

    def ping(self) -> bool:
        return self._online


@pytest.fixture
def make_fake_client() -> Callable[[bool], TestClient]:
    def _factory(db_online: bool) -> TestClient:
        app = create_app(health_use_case=HealthUseCase(db_probe=_FakeDatabaseProbe(db_online)))
        return TestClient(app)

    return _factory
