from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db_models.base import Base


class ProcessingLog(Base):
    __tablename__ = "processing_logs"
    __table_args__ = {"schema": "processing_engine"}

    id: Mapped[sa.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    item_id: Mapped[sa.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("processing_engine.items.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Denormalized for query performance
    job_id: Mapped[sa.UUID] = mapped_column(sa.UUID(as_uuid=True), nullable=False)
    pipeline_id: Mapped[sa.UUID] = mapped_column(sa.UUID(as_uuid=True), nullable=False)

    step: Mapped[str] = mapped_column(
        sa.Enum(
            "ingest",
            "dedup",
            "process",
            "validate",
            "persist",
            name="log_step",
            schema="processing_engine",
            create_type=False,
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(sa.Text, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    # Named 'log_metadata' to avoid conflict with SQLAlchemy's reserved 'metadata'
    log_metadata: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        server_default=sa.text("'{}'"),
    )

    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
