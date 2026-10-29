"""Import a hash-chained audit log into the monitoring schema (Phase 2 M2, SM5).

Two logs use the same chained format (juku_common.audit_chain): the
gateway's, and Juku's MCP server's own. Cron runs `juku-ops import-audit`
every few minutes; each run:

1. verifies the whole file's chain;
2. checks the last line imported before is still in the file, unchanged
   (a log that was deleted and restarted, or rewritten, is refused);
3. imports the lines after it, keeping only allow-listed metadata fields.

Any problem means nothing is imported, and the run is recorded with the
problems, which fires the "audit chain broken" alert. The allow-list is
the privacy boundary (FF9): tool arguments, outputs, error text, free-text
reasons and learner IDs stay in the log file and never reach Postgres,
where Grafana reads.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast

from juku_common.audit_chain import GATEWAY_GENESIS, JUKU_MCP_GENESIS, ChainReport, verify_log
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from juku_ops.tables import audit_imports, audit_lines

SourceName = Literal["gateway", "juku-mcp"]


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _boolean(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _texts(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    items = cast(list[Any], value)
    return [item for item in items if isinstance(item, str)]


Converter = Callable[[Any], Any]


@dataclass(frozen=True)
class AuditSource:
    """One log: its name, its chain's genesis, and the fields copied from each line.

    `columns_by_field` maps a field in the log to (column, converter). A field
    not listed is never imported.
    """

    name: SourceName
    genesis: str
    columns_by_field: Mapping[str, tuple[str, Converter]]


_SHARED_FIELDS: Mapping[str, tuple[str, Converter]] = {
    "kind": ("kind", _text),
    "call_id": ("call_id", _text),
    "caller": ("caller", _text),
    "tool": ("tool", _text),
    "decision": ("decision", _text),
}

GATEWAY = AuditSource(
    "gateway",
    GATEWAY_GENESIS,
    {
        **_SHARED_FIELDS,
        "route": ("route", _text),
        "is_error": ("is_error", _boolean),
        "suspicious": ("is_suspicious", _boolean),
        "layer": ("detector_layer", _text),
        "score": ("detector_score", _number),
    },
)
JUKU_MCP = AuditSource(
    "juku-mcp",
    JUKU_MCP_GENESIS,
    {
        **_SHARED_FIELDS,
        "reason_category": ("reason_category", _text),
        "actor_chain": ("actor_chain", _texts),
    },
)
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


@dataclass(frozen=True)
class _LastImported:
    line_number: int
    line_sha256: str


async def _last_imported(connection: AsyncConnection, source: AuditSource) -> _LastImported | None:
    newest = select(func.max(audit_lines.c.line_number)).where(audit_lines.c.source == source.name)
    query = select(audit_lines.c.line_number, audit_lines.c.line_sha256).where(
        audit_lines.c.source == source.name, audit_lines.c.line_number == newest.scalar_subquery()
    )
    row = (await connection.execute(query)).first()
    return None if row is None else _LastImported(int(row.line_number), str(row.line_sha256))


def _continuity_problem(report: ChainReport, last: _LastImported | None) -> str | None:
    """A problem if the line imported last time isn't in the file, unchanged, any more."""
    if last is None:
        return None
    if last.line_number <= report.lines and report.line_hashes[last.line_number - 1] == last.line_sha256:
        return None
    return f"line {last.line_number} no longer matches the copy imported earlier: the log was replaced or rewritten"


def _row(source: AuditSource, line_number: int, line_sha256: str, record: Mapping[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "source": source.name,
        "line_number": line_number,
        "line_sha256": line_sha256,
        "logged_at": datetime.fromisoformat(str(record["ts"])),
    }
    for log_field, (column, convert) in source.columns_by_field.items():
        row[column] = convert(record.get(log_field))
    return row


def _new_rows(source: AuditSource, report: ChainReport, after_line: int) -> tuple[list[dict[str, Any]], list[str]]:
    """The rows for lines after `after_line`, or the problems that stop the import."""
    rows: list[dict[str, Any]] = []
    problems: list[str] = []
    for index in range(after_line, report.lines):
        record = report.records[index]
        if record is None:  # a torn line the verifier accepted as recovered
            continue
        line_number = index + 1
        if not isinstance(record.get("ts"), str) or not isinstance(record.get("kind"), str):
            problems.append(f"line {line_number}: no `ts` or `kind`")
            continue
        try:
            rows.append(_row(source, line_number, report.line_hashes[index], record))
        except ValueError:
            problems.append(f"line {line_number}: `ts` isn't an ISO timestamp")
    return rows, problems


async def import_audit_log(engine: AsyncEngine, source: AuditSource, path: Path) -> ImportResult:
    """Verify `path` and import its new lines; record the run either way."""
    report = verify_log(path, genesis=source.genesis)
    async with engine.begin() as connection:
        last = await _last_imported(connection, source)
        problems = list(report.problems)
        continuity = _continuity_problem(report, last)
        if continuity:
            problems.append(continuity)
        rows: list[dict[str, Any]] = []
        if not problems:
            rows, problems = _new_rows(source, report, after_line=0 if last is None else last.line_number)
        if problems:
            rows = []
        if rows:
            await connection.execute(insert(audit_lines), rows)
        result = ImportResult(source.name, path.name, report.lines, len(rows), problems)
        await connection.execute(
            insert(audit_imports).values(
                source=result.source,
                file_name=result.file_name,
                lines_total=result.lines_total,
                lines_imported=result.lines_imported,
                is_intact=result.is_intact,
                problems=result.problems,
            )
        )
    return result
