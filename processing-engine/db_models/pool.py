from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db_models.base import Base


class Pool(Base):
    __tablename__ = "pool"
    __table_args__ = {"schema": "processing_engine"}

    id: Mapped[sa.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    pipeline_id: Mapped[sa.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("processing_engine.pipelines.id"),
        nullable=False,
    )

    source_url: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    content: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    content_type: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default=sa.text("'text/plain'")
    )
    pool_metadata: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True, server_default=sa.text("'{}'")
    )

    url_hash: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    status: Mapped[str] = mapped_column(
        sa.Text, nullable=False, server_default=sa.text("'pending'")
    )
    priority: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=sa.text("0")
    )

    source_id: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    batch_ref: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    job_id: Mapped[sa.UUID | None] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("processing_engine.jobs.id"),
        nullable=True,
    )

    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    claimed_at: Mapped[sa.DateTime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=True
    )
