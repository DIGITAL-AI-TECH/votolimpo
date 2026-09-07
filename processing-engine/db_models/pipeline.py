from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db_models.base import Base


class Pipeline(Base):
    __tablename__ = "pipelines"
    __table_args__ = {"schema": "processing_engine"}

    id: Mapped[sa.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    version: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("1")
    )
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    # Ingestor config
    ingestor_type: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default=sa.text("'auto'")
    )
    max_content_chars: Mapped[int | None] = mapped_column(
        sa.Integer, nullable=True, server_default=sa.text("100000")
    )

    # Dedup config
    dedup_strategy: Mapped[str] = mapped_column(
        sa.Enum(
            "hash",
            "semantic",
            "composite",
            "none",
            name="dedup_strategy",
            schema="processing_engine",
            create_type=False,
        ),
        nullable=False,
        server_default=sa.text("'hash'"),
    )
    dedup_threshold: Mapped[float | None] = mapped_column(
        sa.Float, nullable=True, server_default=sa.text("0.90")
    )

    # LLM config
    llm_provider: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default=sa.text("'openai'")
    )
    llm_model: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default=sa.text("'gpt-4.1-mini'")
    )
    llm_temperature: Mapped[float] = mapped_column(
        sa.Float, nullable=False, server_default=sa.text("0.0")
    )
    llm_seed: Mapped[int | None] = mapped_column(
        sa.Integer, nullable=True, server_default=sa.text("42")
    )
    llm_max_tokens: Mapped[int | None] = mapped_column(
        sa.Integer, nullable=True, server_default=sa.text("16384")
    )
    system_prompt: Mapped[str] = mapped_column(sa.Text, nullable=False)
    output_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Validators
    validators: Mapped[list[str]] = mapped_column(
        sa.ARRAY(sa.Text),
        nullable=False,
        server_default=sa.text('\'{"schema"}\''),
    )

    # Sink config
    sink_type: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default=sa.text("'postgresql'")
    )
    sink_config: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, server_default=sa.text("'{}'")
    )

    # Rate limiting
    max_concurrent: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("5")
    )
    rate_limit_rpm: Mapped[int | None] = mapped_column(
        sa.Integer, nullable=True, server_default=sa.text("60")
    )

    # Budget
    budget_limit_usd: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    budget_period: Mapped[str | None] = mapped_column(
        sa.Text, nullable=True, server_default=sa.text("'month'")
    )

    # Retry config
    max_retries: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("3")
    )
    retry_backoff_base: Mapped[float] = mapped_column(
        sa.Float, nullable=False, server_default=sa.text("2.0")
    )

    # Cache
    cache_ttl_hours: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("720")
    )

    # Metadata
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("true")
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
