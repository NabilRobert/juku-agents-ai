"""A real HTTP server inside a test: a free port, a running app, and a clean stop."""

from __future__ import annotations

import asyncio
import socket
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

import uvicorn

STARTUP_POLL_SECONDS = 0.05


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@asynccontextmanager
async def serving(app: Callable[..., Any]) -> AsyncGenerator[str]:
    """Run `app` for the length of the block, stopping it however the block ends. Yields its base URL."""
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, port=port, log_level="warning"))
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(STARTUP_POLL_SECONDS)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await task
