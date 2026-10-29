"""A hand-run command's connections (ADR-016's budget): one per database, retried briefly when refused.

The weekly run, `juku invite` and the nightly check run beside the app as
juku_app, inside its CONNECTION LIMIT. Two of them in the same minute can
find the role at its limit; Postgres refuses the connection, and the
command waits briefly and tries again instead of failing.
"""

import asyncio
import uuid
from typing import Any

import asyncpg
import pytest
from juku_app import connections
from juku_testkit.databases import admin_url, as_sqlalchemy_url
from sqlalchemy import text
from sqlalchemy.engine import make_url

URL = "postgresql+asyncpg://juku_app@db.example.invalid:6543/app?ssl=require"


def refused() -> asyncpg.exceptions.TooManyConnectionsError:
    return asyncpg.exceptions.TooManyConnectionsError('too many connections for role "juku_app"')


async def test_a_refused_connection_is_retried_until_it_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    async def connect(**kwargs: Any) -> str:
        calls.append(kwargs)
        if len(calls) < 3:
            raise refused()
        return "connected"

    monkeypatch.setattr(asyncpg, "connect", connect)
    monkeypatch.setattr(connections, "RETRY_WAIT_SECONDS", 0)
    assert await connections.connect_with_retry(URL) == "connected"
    assert len(calls) == 3
    assert (calls[0]["host"], calls[0]["port"], calls[0]["ssl"]) == ("db.example.invalid", 6543, "require")


async def test_a_role_still_full_after_the_last_attempt_fails_with_the_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    async def connect(**_kwargs: Any) -> str:
        calls.append(1)
        raise refused()

    monkeypatch.setattr(asyncpg, "connect", connect)
    monkeypatch.setattr(connections, "RETRY_WAIT_SECONDS", 0)
    with pytest.raises(asyncpg.exceptions.TooManyConnectionsError):
        await connections.connect_with_retry(URL)
    assert len(calls) == connections.RETRY_ATTEMPTS


async def test_other_connection_errors_fail_at_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    async def connect(**_kwargs: Any) -> str:
        calls.append(1)
        raise asyncpg.exceptions.InvalidPasswordError("password authentication failed")

    monkeypatch.setattr(asyncpg, "connect", connect)
    with pytest.raises(asyncpg.exceptions.InvalidPasswordError):
        await connections.connect_with_retry(URL)
    assert len(calls) == 1, "a wrong password won't fix itself: no retry"


def test_a_command_engine_has_its_size_and_no_overflow() -> None:
    engine = connections.command_engine(URL, 1)
    pool: Any = engine.pool
    assert (pool.size(), pool._max_overflow) == (1, 0)


async def test_against_a_real_connection_limit_a_command_waits_for_a_free_connection() -> None:
    """A login capped at one connection: while another session holds it, the command waits, then connects."""
    role = f"juku_retry_probe_{uuid.uuid4().hex[:8]}"
    admin = make_url(as_sqlalchemy_url(admin_url()))
    database = str(admin.database)
    holder_dsn = admin.set(username=role).render_as_string(hide_password=False).replace("+asyncpg", "")
    command_url = admin.set(username=role).render_as_string(hide_password=False)
    setup = await asyncpg.connect(admin_url())
    try:
        await setup.execute(f'CREATE ROLE "{role}" LOGIN CONNECTION LIMIT 1')
        await setup.execute(f'GRANT CONNECT ON DATABASE "{database}" TO "{role}"')
        holder = await asyncpg.connect(holder_dsn)
        engine = connections.command_engine(command_url, 1)

        async def release_soon() -> None:
            await asyncio.sleep(0.3)
            await holder.close()

        try:
            release = asyncio.create_task(release_soon())
            async with engine.connect() as connection:
                assert await connection.scalar(text("SELECT current_user")) == role
            await release
        finally:
            await engine.dispose()
            if not holder.is_closed():
                await holder.close()
    finally:
        await setup.execute(f'REVOKE CONNECT ON DATABASE "{database}" FROM "{role}"')
        await setup.execute(f'DROP ROLE IF EXISTS "{role}"')
        await setup.close()
