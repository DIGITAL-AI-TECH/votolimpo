from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from db_models.base import Base


class ModelPricing(Base):
    __tablename__ = "model_pricing"
    __table_args__ = {"schema": "processing_engine"}

    id: Mapped[sa.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    provider: Mapped[str] = mapped_column(sa.Text, nullable=False)
    model: Mapped[str] = mapped_column(sa.Text, nullable=False)
    input_price_per_million_tokens: Mapped[float] = mapped_column(
        sa.Float, nullable=False
    )
    output_price_per_million_tokens: Mapped[float] = mapped_column(
        sa.Float, nullable=False, server_default=sa.text("0.0")
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=sa.text("true")
    )
    effective_from: Mapped[sa.Date] = mapped_column(
        sa.Date, nullable=False, server_default=sa.text("CURRENT_DATE")
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
