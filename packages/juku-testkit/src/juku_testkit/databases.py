"""Throwaway Postgres databases for tests: a pytest plugin.

Tests that need Postgres take the `app_database` fixture: a fresh `app`
database for the whole run, migrated to every Alembic head, dropped at the
end. They talk to a local `postgres:16` started by `make db-up` (loopback
only, no password, never real data), or to `$JUKU_TEST_ADMIN_URL`.

Locally, with no server running, those tests are skipped with a message
saying how to start one. CI sets `JUKU_REQUIRE_DB=1`, which turns the skip
into a failure, so a missing database can't pass CI silently.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

ADMIN_URL_ENV = "JUKU_TEST_ADMIN_URL"
REQUIRE_DB_ENV = "JUKU_REQUIRE_DB"
# `make db-up` publishes the test server on this loopback port.
DEFAULT_ADMIN_URL = "postgresql://postgres@127.0.0.1:55440/postgres"
CONNECT_TIMEOUT_SECONDS = 3


@dataclass(frozen=True)
class TestDatabase:
    """One throwaway database. `url` is for asyncpg; `sqlalchemy_url` names the driver."""

    __test__ = False  # not a test class, despite the name

    name: str
    url: str

    @property
    def sqlalchemy_url(self) -> str:
        return as_sqlalchemy_url(self.url)


def admin_url() -> str:
    return os.environ.get(ADMIN_URL_ENV, DEFAULT_ADMIN_URL)


def url_for(database: str) -> str:
    base, _, _ = admin_url().rpartition("/")
    return f"{base}/{database}"


def _skip_or_fail(reason: str) -> None:
    message = f"{reason}. Start the test database with `make db-up`, or set {ADMIN_URL_ENV}."
    if os.environ.get(REQUIRE_DB_ENV) == "1":
        pytest.fail(message)
    pytest.skip(message)


def as_sqlalchemy_url(url: str) -> str:
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


async def _admin_execute(*statements: str) -> None:
    """Run statements as the admin, outside a transaction (CREATE DATABASE needs that)."""
    engine = create_async_engine(
        as_sqlalchemy_url(admin_url()), isolation_level="AUTOCOMMIT", connect_args={"timeout": CONNECT_TIMEOUT_SECONDS}
    )
    try:
        async with engine.connect() as connection:
            raw = await connection.get_raw_connection()
            driver = raw.driver_connection
            if driver is None:
                raise RuntimeError("the admin connection has no driver connection")
            for statement in statements:
                # The driver's own execute runs a whole script (roles.sql has DO blocks).
                await driver.execute(statement)
    finally:
        await engine.dispose()


def create_database(prefix: str) -> TestDatabase:
    """A new, empty database named `<prefix>_<random>`; skips (or fails in CI) without a server."""
    name = f"{prefix}_{uuid.uuid4().hex[:8]}"
    try:
        asyncio.run(_admin_execute(f'CREATE DATABASE "{name}"'))
    except (OSError, TimeoutError, DBAPIError, InterfaceError, OperationalError) as exc:
        _skip_or_fail(f"no test Postgres at {admin_url()} ({type(exc).__name__})")
    return TestDatabase(name=name, url=url_for(name))


def drop_database(database: TestDatabase) -> None:
    asyncio.run(_admin_execute(f'DROP DATABASE IF EXISTS "{database.name}" WITH (FORCE)'))


def repo_root() -> Path:
    for folder in Path(__file__).resolve().parents:
        if (folder / "alembic.ini").is_file():
            return folder
    raise RuntimeError("can't find alembic.ini above juku_testkit: run the tests from the repository")


def create_roles() -> None:
    """Juku's roles (ops/db/roles.sql): cluster-wide and idempotent, so safe to run every session."""
    roles_sql = (repo_root() / "ops" / "db" / "roles.sql").read_text(encoding="utf-8")
    asyncio.run(_admin_execute(roles_sql))


def migrate_to_heads(database: TestDatabase) -> None:
    """Run every Alembic branch's migrations, as a deploy would."""
    from alembic import command
    from alembic.config import Config

    config = Config(str(repo_root() / "alembic.ini"))
    config.attributes["database_url"] = database.sqlalchemy_url
    command.upgrade(config, "heads")


@pytest.fixture(scope="session")
def app_database() -> Iterator[TestDatabase]:
    """A migrated `app` database shared by the run's tests. Tests clean up their own rows."""
    database = create_database("juku_test_app")
    try:
        create_roles()
        migrate_to_heads(database)
        yield database
    finally:
        drop_database(database)


@pytest.fixture
def empty_database() -> Iterator[TestDatabase]:
    """A fresh, unmigrated database for one test (migration tests start from nothing)."""
    database = create_database("juku_test_empty")
    try:
        yield database
    finally:
        drop_database(database)


@pytest.fixture
async def app_engine(app_database: TestDatabase) -> AsyncIterator[AsyncEngine]:
    """An engine on the migrated `app` database, as the admin (tests switch role with SET ROLE)."""
    engine = create_async_engine(app_database.sqlalchemy_url)
    try:
        yield engine
    finally:
        await engine.dispose()


OPENJLPT_DIR_ENV = "JUKU_OPENJLPT_DIR"


def openjlpt_dir() -> Path:
    """Where the pinned OpenJLPT files are: `$JUKU_OPENJLPT_DIR`, or data/raw/openjlpt-bf4e1ee (git-ignored)."""
    return Path(os.environ.get(OPENJLPT_DIR_ENV, str(repo_root() / "data" / "raw" / "openjlpt-bf4e1ee")))


def require_openjlpt() -> Path:
    folder = openjlpt_dir()
    if not (folder / "openjlpt.sqlite").is_file():
        _skip_or_fail(f"no OpenJLPT files in {folder}: run `juku-data fetch-dictionary --to {folder}`")
    return folder


@pytest.fixture(scope="session")
def dictionary_database() -> Iterator[TestDatabase]:
    """A `dict` database loaded from the pinned OpenJLPT build, shared by the run's tests (read-only)."""
    from juku_data.dictionary.load import load_dictionary
    from juku_data.dictionary.source import verify_source

    folder = require_openjlpt()
    database = create_database("juku_test_dict")
    try:
        create_roles()

        async def load() -> None:
            engine = create_async_engine(database.sqlalchemy_url)
            try:
                await load_dictionary(engine, verify_source(folder))
            finally:
                await engine.dispose()

        asyncio.run(load())
        yield database
    finally:
        drop_database(database)


@pytest.fixture
async def dict_engine(dictionary_database: TestDatabase) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(dictionary_database.sqlalchemy_url)
    try:
        yield engine
    finally:
        await engine.dispose()
