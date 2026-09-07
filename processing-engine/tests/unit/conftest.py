from __future__ import annotations

"""Conftest para testes unitários.

Sobrescreve as fixtures de banco/container do conftest.py da raiz para que os
testes unitários não precisem de Docker nem de PostgreSQL.
"""

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def postgres_container():
    """Stub: testes unitários não precisam de container Postgres."""
    return None


@pytest.fixture(scope="session")
def database_url(postgres_container) -> str:
    """Stub: testes unitários não precisam de URL de banco."""
    return "postgresql://stub/stub"


@pytest.fixture(scope="session", autouse=True)
def run_migrations(database_url) -> None:  # type: ignore[override]
    """Stub: testes unitários não executam migrações."""
    return
