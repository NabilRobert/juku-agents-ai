"""Import a hash-chained audit log into the monitoring schema (stub: lands in the next commit)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from juku_common.audit_chain import GATEWAY_GENESIS, JUKU_MCP_GENESIS
from sqlalchemy.ext.asyncio import AsyncEngine

SourceName = Literal["gateway", "juku-mcp"]


@dataclass(frozen=True)
class AuditSource:
    name: SourceName
    genesis: str
    columns_by_field: Mapping[str, str]


GATEWAY = AuditSource("gateway", GATEWAY_GENESIS, {})
JUKU_MCP = AuditSource("juku-mcp", JUKU_MCP_GENESIS, {})
AUDIT_SOURCES: Mapping[str, AuditSource] = {source.name: source for source in (GATEWAY, JUKU_MCP)}


@dataclass(frozen=True)
class ImportResult:
    source: SourceName
    file_name: str
    lines_total: int
    lines_imported: int
    problems: list[str] = field(default_factory=list[str])

    @property
    def is_intact(self) -> bool:
        return not self.problems


async def import_audit_log(engine: AsyncEngine, source: AuditSource, path: Path) -> ImportResult:
    raise NotImplementedError
