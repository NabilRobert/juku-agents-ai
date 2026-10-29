"""Alembic's environment for the `app` database.

Online (`alembic upgrade heads`) it connects with the migrator role's URL:
`config.attributes["database_url"]` when a test passes one, otherwise
`$JUKU_MIGRATOR_DATABASE_URL`. Offline (`--sql`) it prints the SQL instead;
`make check` lints that output with Squawk (fitness function FF4).

Every migration runs in its own transaction, with short lock and statement
timeouts: a migration that would wait on a busy table fails fast instead of
queueing every query behind it (scale path, gap 10).
"""

from __future__ import annotations

import asyncio
import os

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL_ENV = "JUKU_MIGRATOR_DATABASE_URL"
LOCK_TIMEOUT = "5s"
STATEMENT_TIMEOUT = "60s"
TIMEOUTS = {"lock_timeout": LOCK_TIMEOUT, "statement_timeout": STATEMENT_TIMEOUT}

config = context.config


def database_url() -> str:
    url = config.attributes.get("database_url") or os.environ.get(DATABASE_URL_ENV)
    if not url:
        raise RuntimeError(
            f"{DATABASE_URL_ENV} is not set: point it at the app database as the migrator role, "
            "e.g. postgresql+asyncpg://juku_migrator:...@localhost:5432/app"
        )
    return str(url)


def run_offline() -> None:
    context.configure(
        url=config.attributes.get("database_url") or "postgresql+asyncpg://offline/app",
        literal_binds=True,
        transaction_per_migration=True,
        dialect_opts={"paramstyle": "named"},
    )
    # Printed first, so the SQL a reviewer (or Squawk) reads sets them too.
    for name, value in TIMEOUTS.items():
        context.execute(f"SET {name} = '{value}'")
    with context.begin_transaction():
        context.run_migrations()


def _run_with(connection: Connection) -> None:
    context.configure(connection=connection, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(database_url(), connect_args={"server_settings": TIMEOUTS})
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run_with)
            await connection.commit()
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_offline()
else:
    asyncio.run(run_online())
