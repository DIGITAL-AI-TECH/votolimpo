from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from db_models.base import Base


class LLMCallLog(Base):
    __tablename__ = "llm_call_log"
    __table_args__ = {"schema": "processing_engine"}

    id: Mapped[sa.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    item_id: Mapped[sa.UUID | None] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("processing_engine.items.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Denormalized
    job_id: Mapped[sa.UUID | None] = mapped_column(sa.UUID(as_uuid=True), nullable=True)
    pipeline_id: Mapped[sa.UUID] = mapped_column(sa.UUID(as_uuid=True), nullable=False)

    # Call details
    provider: Mapped[str] = mapped_column(sa.Text, nullable=False)
    model: Mapped[str] = mapped_column(sa.Text, nullable=False)
    call_type: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default=sa.text("'completion'")
    )
    prompt_tokens: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    completion_tokens: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    total_tokens: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )

    # Cost
    cost_usd: Mapped[float] = mapped_column(
        sa.Float, nullable=False, server_default=sa.text("0.0")
    )

    # Performance
    latency_ms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        sa.Enum(
            "success",
            "error",
            name="call_status",
            schema="processing_engine",
            create_type=False,
        ),
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    is_retry: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("false")
    )
    retry_number: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )

    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
