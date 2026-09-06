"""Contract test configuration — set env vars BEFORE app import.

These tests do NOT require Docker or a real database.
They only validate the OpenAPI schema structure.
"""

from __future__ import annotations

import os

# Must be set before any app import (Settings is module-level)
os.environ.setdefault("DATABASE_URL", "postgresql://x:x@localhost/x")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("ENGINE_ROLE", "api")
