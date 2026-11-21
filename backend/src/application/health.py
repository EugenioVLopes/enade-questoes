from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class WorkerStatus:
    estado: str = "ocioso"
    tarefa_ativa: str | None = None
    tipo: str | None = None
    alvo: str | None = None
    processadas: int | None = None
    total: int | None = None


@dataclass(frozen=True, slots=True)
class HealthStatus:
    status: str
    banco_dados: str
    worker: WorkerStatus = field(default_factory=WorkerStatus)


class DatabaseProbe(Protocol):
    def ping(self) -> bool: ...


class HealthUseCase:
    def __init__(
        self,
        db_probe: DatabaseProbe,
        worker_status: WorkerStatus | None = None,
        worker_status_provider: Callable[[], WorkerStatus] | None = None,
    ) -> None:
        self._db_probe = db_probe
        self._worker_status = worker_status or WorkerStatus()
        self._worker_status_provider = worker_status_provider

    def execute(self) -> HealthStatus:
        worker = self._worker_status_provider() if self._worker_status_provider is not None else self._worker_status
        conectado = self._db_probe.ping()
        if conectado:
            return HealthStatus(
                status="ok",
                banco_dados="conectado",
                worker=worker,
            )
        return HealthStatus(
            status="degradado",
            banco_dados="indisponivel",
            worker=worker,
        )
