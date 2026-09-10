"""Shared test configuration — sets required env vars before any app module import."""

import os

# Set dummy env vars BEFORE any app module is imported (pydantic-settings reads at import time)
os.environ.setdefault("PE_API_KEY", "test-key")
os.environ.setdefault("PE_DATABASE_URL", "postgres://test:test@localhost:5432/test")
os.environ.setdefault(
    "PE_VOTOLIMPO_DATABASE_URL", "postgres://test:test@localhost:5432/vl"
)
