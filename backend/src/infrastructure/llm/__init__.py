"""Adaptadores LLM multimodais OpenAI-compatíveis e perfis de provedor."""

from __future__ import annotations

from application.classificacao import construir_json_schema_plano
from infrastructure.llm.cliente_openai import (
    ClienteOpenAICompativel,
    SaidaBrutaLLMSchema,
    criar_classificador_multimodal,
)
from infrastructure.llm.perfis import PerfilProvedorLLM, resolver_perfil_provedor

__all__ = [
    "ClienteOpenAICompativel",
    "PerfilProvedorLLM",
    "SaidaBrutaLLMSchema",
    "construir_json_schema_plano",
    "criar_classificador_multimodal",
    "resolver_perfil_provedor",
]
