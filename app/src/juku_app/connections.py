"""Stub until the fix lands (EDD1): a hand-run command's connections, retried when its role is at its limit."""

from __future__ import annotations

from typing import Any

import asyncpg  # pyright: ignore[reportMissingTypeStubs] (no stubs; only connect() and one exception are used)
from sqlalchemy.ext.asyncio import AsyncEngine

RETRY_ATTEMPTS = 5
RETRY_WAIT_SECONDS = 0.5
__all__ = ["asyncpg"]


async def connect_with_retry(url: str) -> Any:
    raise NotImplementedError


def command_engine(url: str, pool_size: int) -> AsyncEngine:
    raise NotImplementedError
