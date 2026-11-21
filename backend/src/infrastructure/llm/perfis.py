"""Perfis de provedores OpenAI-compatíveis (extra_body e cabeçalhos)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PerfilProvedorLLM:
    """Parâmetros específicos de provedor aplicados às chamadas Chat Completions."""

    nome: str
    extra_body: Mapping[str, Any] | None = None
    default_headers: Mapping[str, str] | None = None


def resolver_perfil_provedor(provider: str, model: str = "") -> PerfilProvedorLLM:
    """Resolve `extra_body` e cabeçalhos por `LLM_PROVIDER` (e modelo quando aplicável)."""
    prov = provider.strip().lower()
    mod = model.strip().lower()

    if prov == "vllm_qwen" or (prov == "vllm" and "qwen" in mod):
        return PerfilProvedorLLM(
            nome="vllm_qwen",
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            default_headers=None,
        )

    if prov == "gemini_openai":
        return PerfilProvedorLLM(
            nome="gemini_openai",
            extra_body=None,
            default_headers=None,
        )

    if prov in {"openrouter", "reasoning", "openrouter_reasoning", "vllm_reasoning"} or (
        prov != "openai" and any(marcador in mod for marcador in (":thinking", "-thinking", "deepseek-r1", "qwq"))
    ):
        return PerfilProvedorLLM(
            nome=prov or "reasoning",
            extra_body={"reasoning": {"effort": "low"}},
            default_headers=None,
        )

    return PerfilProvedorLLM(
        nome=prov or "openai",
        extra_body=None,
        default_headers=None,
    )
