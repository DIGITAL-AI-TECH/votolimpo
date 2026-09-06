from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    DATABASE_URL: str
    OPENAI_API_KEY: str = ""
    API_KEY: str = "dev-key"
    ENGINE_ROLE: Literal["api", "worker", "both"] = "both"
    WORKER_POLL_INTERVAL_SECONDS: float = 1.0
    LOG_LEVEL: str = "INFO"
    APP_VERSION: str = "1.0.0"


settings = Settings()
