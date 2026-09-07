from __future__ import annotations

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db_models.base import Base


class Item(Base):
    __tablename__ = "items"
    __table_args__ = {"schema": "processing_engine"}

    id: Mapped[sa.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    job_id: Mapped[sa.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("processing_engine.jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        sa.Enum(
            "pending",
            "ingesting",
            "deduplicating",
            "processing",
            "validating",
            "persisting",
            "completed",
            "failed",
            "duplicate",
            "similar",
            name="item_status",
            schema="processing_engine",
            create_type=False,
        ),
        nullable=False,
        server_default=sa.text("'pending'"),
    )

    # Input
    source_url: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    url_hash: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    content_type: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default=sa.text("'text/plain'")
    )
    raw_content: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    content_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536), nullable=True
    )

    # Output
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    dedup_result: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    dedup_matched_item_id: Mapped[sa.UUID | None] = mapped_column(
        sa.UUID(as_uuid=True), nullable=True
    )

    # Metadata — named 'item_metadata' to avoid conflict with SQLAlchemy's reserved 'metadata'
    item_metadata: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
        server_default=sa.text("'{}'"),
    )
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )
    cached: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("false")
    )
    processing_started_at: Mapped[sa.DateTime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    processing_completed_at: Mapped[sa.DateTime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
