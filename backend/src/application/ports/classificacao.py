"""Porta e DTOs do classificador multimodal de questões."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class IdentidadeClassificador:
    """Identidade do provedor e modelo utilizados na chamada ao LLM."""

    provider: str
    model: str
    base_url: str = ""


@dataclass(frozen=True, slots=True)
class ResultadoChamada:
    """Resposta bruta estruturada e telemetria retornadas pelo classificador multimodal."""

    dados_brutos: Mapping[str, Any]
    prompt_tokens: int
    completion_tokens: int
    latencia_ms: float
    from_cache: bool
    cache_key: str
    tentativas: int = 1
    modelo_efetivo: str = ""
    modo_schema: str = "json_schema"


@runtime_checkable
class ClassificadorMultimodal(Protocol):
    """Porta única de chamada estruturada e multimodal a modelos de linguagem."""

    @property
    def identidade(self) -> IdentidadeClassificador: ...

    def classificar_estruturado(
        self,
        *,
        system: str,
        user: str,
        imagens_png: Sequence[bytes],
        schema: Mapping[str, Any],
        nome_schema: str,
        max_tokens: int = 4096,
        usar_cache: bool = True,
    ) -> ResultadoChamada: ...
