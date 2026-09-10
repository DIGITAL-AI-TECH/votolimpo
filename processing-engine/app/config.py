"""Application settings via pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Processing Engine configuration."""

    # API
    api_key: str  # W1 fix: no insecure default — PE_API_KEY env var required
    host: str = "0.0.0.0"
    port: int = 8000

    # Database (engine internal schema) — PE_DATABASE_URL env var required
    database_url: str

    # VotoLimpo target database (sink writes here) — PE_VOTOLIMPO_DATABASE_URL env var required
    votolimpo_database_url: str

    # OpenAI
    openai_api_key: str = ""

    # Worker
    worker_concurrency: int = 3
    worker_poll_interval: float = 2.0

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

    model_config = {"env_prefix": "PE_", "env_file": ".env"}


settings = Settings()
