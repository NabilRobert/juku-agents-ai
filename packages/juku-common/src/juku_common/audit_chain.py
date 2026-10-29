"""Append-only, hash-chained JSONL audit logs: the writer and the verifier.

Each line carries `prev`, the SHA-256 of the previous line's bytes, so an
edited, inserted or deleted line breaks the chain. A chain shows tampering;
it can't stop someone who rewrites the whole file, and it can't show lines
cut from the end.

This is mcp-security-gateway's format (its `audit.py`), so one verifier
reads both the gateway's log and Juku's MCP server's own. It is copied, not
imported: depending on the gateway package would pull its detector
(onnxruntime, numpy, tokenizers) into every Juku image for these few lines.
What changed from the original: the genesis hash is a parameter, because
each log names its own; the report carries the parsed lines and their
hashes, for the importer; and the gateway's "forwarded but no result"
check is left to the gateway's own verifier.

A crash mid-write leaves a torn last line. The next start closes it, writes
a `recovered` line naming its hash, and carries on, so the verifier can tell
a crash from an edit.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

SCHEMA_VERSION = 1


def genesis_for(log_name: str) -> str:
    """The `prev` of a log's first line: the hash of its name."""
    return hashlib.sha256(log_name.encode()).hexdigest()


GATEWAY_GENESIS = genesis_for("mcp-gateway audit log")
JUKU_MCP_GENESIS = genesis_for("juku-mcp audit log")


class AuditError(Exception):
    """The log can't be written. Callers must refuse the action: no unaudited call."""


def line_hash(line: bytes) -> str:
    return hashlib.sha256(line).hexdigest()


class AuditLog:
    """Appends chained lines to one file. Not shared between processes."""

    def __init__(self, path: Path, *, genesis: str, fsync: bool = True) -> None:
        self.path = path
        self.fsync = fsync
        self._prev = genesis
        torn: bytes | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = path.read_bytes() if path.exists() else b""
            if data and not data.endswith(b"\n"):
                torn = data[data.rfind(b"\n") + 1 :] + b"\n"
            elif data:
                self._prev = line_hash(data.rstrip(b"\n").rsplit(b"\n", 1)[-1] + b"\n")
            self._file = path.open("ab")
            if torn is not None:
                self._file.write(b"\n")  # close the torn line so the next one doesn't merge into it
                self._prev = line_hash(torn)
        except OSError as exc:
            raise AuditError(f"can't open audit log {path}: {exc}") from exc
        if torn is not None:
            self.append("recovered", torn_line_sha256=line_hash(torn), torn_bytes=len(torn) - 1)

    def append(self, kind: str, **fields: Any) -> None:
        record = {
            "schema_version": SCHEMA_VERSION,
            "ts": datetime.now(UTC).isoformat(timespec="microseconds"),
            "kind": kind,
            **fields,
            "prev": self._prev,
        }
        line = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode() + b"\n"
        try:
            self._file.write(line)
            self._file.flush()
            if self.fsync:
                os.fsync(self._file.fileno())
        except (OSError, ValueError) as exc:  # ValueError: write to a closed file
            raise AuditError(f"can't write audit log {self.path}: {exc}") from exc
        self._prev = line_hash(line)

    def close(self) -> None:
        self._file.close()


@dataclass
class ChainReport:
    """What `verify_log` found. Only `problems` means the log was altered."""

    lines: int = 0
    problems: list[str] = field(default_factory=list[str])
    recoveries: list[str] = field(default_factory=list[str])
    records: list[dict[str, Any] | None] = field(default_factory=list[dict[str, Any] | None])
    line_hashes: list[str] = field(default_factory=list[str])

    @property
    def is_intact(self) -> bool:
        return not self.problems


def verify_log(path: Path, *, genesis: str) -> ChainReport:
    """Check every line's `prev` against the line before it.

    Returns the parsed records and each line's hash too, so an importer reads
    the file once and imports exactly what was verified.
    """
    report = ChainReport()
    raw = path.read_bytes().splitlines(keepends=True)
    for line in raw:
        try:
            parsed: Any = json.loads(line)
            report.records.append(cast(dict[str, Any], parsed) if isinstance(parsed, dict) else None)
        except ValueError:
            report.records.append(None)
    prev = genesis
    for index, (line, record) in enumerate(zip(raw, report.records, strict=True)):
        number = index + 1
        if record is None:
            after = report.records[index + 1] if index + 1 < len(report.records) else None
            if after and after.get("kind") == "recovered" and after.get("torn_line_sha256") == line_hash(line):
                report.recoveries.append(f"line {number}: torn by a crash, recovered at the next start")
            else:
                report.problems.append(f"line {number}: not a JSON object")
        elif record.get("prev") != prev:
            report.problems.append(f"line {number}: chain broken (an earlier line was changed, added or removed)")
        prev = line_hash(line)
        report.line_hashes.append(prev)
    report.lines = len(raw)
    return report
