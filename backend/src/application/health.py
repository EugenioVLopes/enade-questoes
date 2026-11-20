from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class WorkerStatus:
    estado: str = "ocioso"
    tarefa_ativa: str | None = None


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
    ) -> None:
        self._db_probe = db_probe
        self._worker_status = worker_status or WorkerStatus()

    def execute(self) -> HealthStatus:
        conectado = self._db_probe.ping()
        if conectado:
            return HealthStatus(
                status="ok",
                banco_dados="conectado",
                worker=self._worker_status,
            )
        return HealthStatus(
            status="degradado",
            banco_dados="indisponivel",
            worker=self._worker_status,
        )
