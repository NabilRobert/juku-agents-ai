"""Juku's MCP server (stub: lands in the next commit)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from juku_common.audit_chain import AuditLog
from juku_common.delegation import Verifier
from juku_common.rules import Rules
from juku_data.engine import Databases
from mcp.server import Server


class WordSearch(Protocol):
    async def search(self, query: str) -> list[dict[str, object]]: ...


@dataclass(frozen=True)
class ServerDeps:
    db: Databases
    verifier: Verifier
    audit: AuditLog
    rules: Rules
    words: WordSearch


def build_server(deps: ServerDeps) -> Server[object]:
    raise NotImplementedError


def local_day(at: datetime, timezone: str) -> date:
    raise NotImplementedError
