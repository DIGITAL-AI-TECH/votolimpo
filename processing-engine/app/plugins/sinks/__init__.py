from __future__ import annotations

from app.plugins.registry import register
from app.plugins.sinks.postgresql import PostgreSQLSink

register("sink", "postgresql", PostgreSQLSink)

__all__ = ["PostgreSQLSink"]
