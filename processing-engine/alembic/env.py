from __future__ import annotations

import asyncio
import os
import urllib.parse
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import all models so SQLAlchemy metadata is populated
import db_models.base  # noqa: F401
import db_models.cache_entry  # noqa: F401
import db_models.item  # noqa: F401
import db_models.job  # noqa: F401
import db_models.llm_call_log  # noqa: F401
import db_models.model_pricing  # noqa: F401
import db_models.pipeline  # noqa: F401
import db_models.pool  # noqa: F401
import db_models.processing_log  # noqa: F401
from alembic import context
from db_models.base import Base

# Alembic Config object — provides access to values in alembic.ini
config = context.config


def _resolve_database_url() -> str | None:
    """Build DATABASE_URL from env vars.

    Priority: DATABASE_URL (explicit) > individual DB_* params > alembic.ini.
    Individual params are URL-encoded to handle special chars in passwords.
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        return url

    db_password = os.environ.get("DB_PASSWORD")
    if db_password:
        encoded_pw = urllib.parse.quote(db_password, safe="")
        db_user = os.environ.get("DB_USER", "postgres")
        db_host = os.environ.get("DB_HOST", "localhost")
        db_port = os.environ.get("DB_PORT", "5432")
        db_name = os.environ.get("DB_NAME", "processing_engine")
        return f"postgresql://{db_user}:{encoded_pw}@{db_host}:{db_port}/{db_name}"

    return None


_db_url = _resolve_database_url()
if _db_url:
    config.set_main_option("sqlalchemy.url", _db_url)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    Calls to context.execute() emit the given string to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using asyncpg."""
    from sqlalchemy.ext.asyncio import create_async_engine

    db_password = os.environ.get("DB_PASSWORD")

    if db_password and not os.environ.get("DATABASE_URL"):
        # Build engine with individual params to avoid URL-encoding issues.
        # asyncpg receives the raw password — no encoding/decoding.
        db_user = os.environ.get("DB_USER", "postgres")
        db_host = os.environ.get("DB_HOST", "localhost")
        db_port = os.environ.get("DB_PORT", "5432")
        db_name = os.environ.get("DB_NAME", "processing_engine")

        connectable = create_async_engine(
            f"postgresql+asyncpg://{db_user}@{db_host}:{db_port}/{db_name}",
            poolclass=pool.NullPool,
            connect_args={"password": db_password},
        )
    else:
        # Use URL from config (set by _resolve_database_url or alembic.ini)
        ini_section = config.get_section(config.config_ini_section, {})
        url = ini_section.get("sqlalchemy.url", "")

        if url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql+psycopg2://"):
            url = url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)

        connectable = create_async_engine(url, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
