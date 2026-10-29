"""A hand-run command's connections (ADR-016's connection budget): small pools, retried briefly when refused.

The weekly run, `juku invite`, `juku delete-learner` and the feedback job
run beside the app as juku_app, inside its CONNECTION LIMIT, with
database.app_commands connections between them. Two in the same minute can
find the role at its limit, and Postgres refuses the connection. Rather
than fail, a command waits a moment and tries again (tenacity), a few
times, then fails with the refusal so cron's alert sees it. Only that
refusal is retried: any other connection error, such as a wrong password,
fails at once.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

import asyncpg  # pyright: ignore[reportMissingTypeStubs] (no stubs; only connect() and one exception are used)
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

# About 15 s in all (0.5, 1, 2, 4 and 8 s): long enough for a short command to finish, short enough for cron.
RETRY_ATTEMPTS = 5
RETRY_WAIT_SECONDS = 0.5
RETRY_WAIT_MAX_SECONDS = 8


async def connect_with_retry(url: str) -> Any:
    """An asyncpg connection for `url` (a SQLAlchemy URL), retried while the role is at its connection limit."""
    sqlalchemy_url = make_url(url)
    args, kwargs = sqlalchemy_url.get_dialect()().create_connect_args(sqlalchemy_url)
    attempts = AsyncRetrying(
        retry=retry_if_exception_type(asyncpg.exceptions.TooManyConnectionsError),
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=RETRY_WAIT_SECONDS, max=RETRY_WAIT_MAX_SECONDS),
        reraise=True,
    )
    async for attempt in attempts:
        with attempt:
            connect = cast(Callable[..., Awaitable[Any]], asyncpg.connect)  # pyright: ignore[reportUnknownMemberType]
            return await connect(*args, **kwargs)
    raise AssertionError("tenacity either returns a connection or re-raises the last refusal")


def command_engine(url: str, pool_size: int) -> AsyncEngine:
    """A fixed pool, no overflow, whose every new connection waits out a full role (connect_with_retry)."""

    async def connect() -> Any:
        return await connect_with_retry(url)

    return create_async_engine(url, pool_size=pool_size, max_overflow=0, async_creator=connect)
