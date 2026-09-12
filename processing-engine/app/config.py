"""Application settings via pydantic-settings."""

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Processing Engine configuration."""

    # API
    api_key: str  # API_KEY env var required

    host: str = "0.0.0.0"
    port: int = 8000

    # Database — accepts either DATABASE_URL or DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD
    database_url: str = ""
    db_host: str = ""
    db_port: int = 5432
    db_name: str = "processing_engine"
    db_user: str = "postgres"
    db_password: str = ""

    # Project-specific target database (optional — only needed by sink plugins)
    votolimpo_database_url: str = ""

    # OpenAI
    openai_api_key: str = ""

    # Worker
    worker_concurrency: int = 3
    worker_poll_interval: float = 2.0
    worker_poll_interval_seconds: float = 0.0  # alias used in production compose

    # Engine role: "api" | "worker" | "both"
    engine_role: str = "both"

    # Pipelines directory
    pipelines_dir: str = "./pipelines"

    # Prompts directory
    prompts_dir: str = "./prompts"

    # Schemas directory
    schemas_dir: str = "./schemas"

    # Logging
    log_level: str = "INFO"

    # Batcher
    batcher_enabled: bool = False
    batcher_poll_interval_seconds: float = 5.0
    batcher_default_batch_size: int = 50

    model_config = {"env_file": ".env", "env_prefix": "PE_"}

    @model_validator(mode="after")
    def _build_database_url(self) -> "Settings":
        """Build database_url from individual DB_* vars if not set directly."""
        if not self.database_url and self.db_host:
            self.database_url = (
                f"postgresql://{self.db_user}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        if self.worker_poll_interval_seconds > 0:
            self.worker_poll_interval = self.worker_poll_interval_seconds
        return self


settings = Settings()
