from __future__ import annotations

from pathlib import Path

import pytest

from infrastructure.config import RAIZ, Settings


def test_settings_raiz_aponta_para_raiz_do_monorepo() -> None:
    assert (RAIZ / "compose.yaml").exists()
    assert (RAIZ / ".env.example").exists()


def test_settings_defaults_correspondem_ao_env_example(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("DATABASE_URL", "DATA_DIR", "LLM_PROVIDER", "LLM_MODEL"):
        monkeypatch.delenv(var, raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://enade:enade@localhost:5432/enade_questoes"
    assert settings.data_dir == Path("./data/app")
    assert settings.llm_provider == "gemini_openai"
    assert settings.llm_model == "gemini-2.5-flash-lite"
    assert settings.llm_max_tokens == 4096
    assert settings.resolved_data_dir == (RAIZ / "data" / "app").resolve()


def test_settings_respeita_piso_minimo_llm_max_tokens_e_effective_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_MAX_TOKENS", "1024")
    monkeypatch.setenv("GEMINI_API_KEY", "gem-key")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    settings_piso = Settings(_env_file=None)
    assert settings_piso.llm_max_tokens == 4096
    assert settings_piso.effective_llm_api_key == "gem-key"

    monkeypatch.setenv("LLM_MAX_TOKENS", "8192")
    monkeypatch.setenv("LLM_API_KEY", "override-key")
    settings_maior = Settings(_env_file=None)
    assert settings_maior.llm_max_tokens == 8192
    assert settings_maior.effective_llm_api_key == "override-key"


def test_settings_respeita_sobrescrita_por_variavel_de_ambiente(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://custom:pass@localhost:5439/db_test")
    monkeypatch.setenv("DATA_DIR", "/tmp/enade-test-data")  # noqa: S108

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://custom:pass@localhost:5439/db_test"
    assert settings.resolved_data_dir == Path("/tmp/enade-test-data")  # noqa: S108
