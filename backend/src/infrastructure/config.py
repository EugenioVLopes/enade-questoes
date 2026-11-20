"""Configuração da aplicação via variáveis de ambiente e `.env` na raiz."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=RAIZ / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_user: str = "enade"
    postgres_password: str = "enade"  # noqa: S105
    postgres_db: str = "enade_questoes"
    postgres_port: int = 5432
    database_url: str = "postgresql+psycopg://enade:enade@localhost:5432/enade_questoes"

    data_dir: Path = Path("./data/app")

    gemini_api_key: str = ""
    llm_provider: str = "gemini_openai"
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_api_key: str = ""
    llm_model: str = "gemini-2.5-flash-lite"
    llm_max_rpm: int = 10
    llm_timeout_s: int = 60

    raiz: Path = RAIZ

    @property
    def resolved_data_dir(self) -> Path:
        if self.data_dir.is_absolute():
            return self.data_dir
        return (self.raiz / self.data_dir).resolve()
