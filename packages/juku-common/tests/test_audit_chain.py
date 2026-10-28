"""The hash-chained audit log: any edit, insertion or deletion is found."""

import json
from pathlib import Path

from juku_common.audit_chain import GATEWAY_GENESIS, JUKU_MCP_GENESIS, AuditLog, verify_log


def write_log(path: Path, count: int = 3) -> None:
    log = AuditLog(path, genesis=JUKU_MCP_GENESIS, fsync=False)
    for number in range(count):
        log.append("call", tool="get_progress", number=number)
    log.close()


def test_an_untouched_log_verifies(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_log(path)
    report = verify_log(path, genesis=JUKU_MCP_GENESIS)
    assert report.is_intact
    assert report.lines == 3
    assert [record["number"] for record in report.records if record] == [0, 1, 2]


def test_an_edited_line_breaks_the_chain_at_the_next_line(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_log(path)
    lines = path.read_text().splitlines(keepends=True)
    lines[1] = lines[1].replace('"number":1', '"number":7')
    path.write_text("".join(lines))
    assert verify_log(path, genesis=JUKU_MCP_GENESIS).problems == [
        "line 3: chain broken (an earlier line was changed, added or removed)"
    ]


def test_a_deleted_line_breaks_the_chain(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_log(path)
    lines = path.read_text().splitlines(keepends=True)
    path.write_text(lines[0] + lines[2])
    assert not verify_log(path, genesis=JUKU_MCP_GENESIS).is_intact


def test_a_log_checked_against_another_logs_genesis_fails(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_log(path)
    assert verify_log(path, genesis=GATEWAY_GENESIS).problems[0].startswith("line 1: chain broken")


def test_a_line_that_is_not_json_is_a_problem(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_log(path)
    with path.open("a") as file:
        file.write("not json\n")
    assert verify_log(path, genesis=JUKU_MCP_GENESIS).problems == ["line 4: not a JSON object"]


def test_a_torn_last_line_is_recovered_at_the_next_start_and_still_verifies(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_log(path)
    with path.open("a") as file:
        file.write('{"kind": "call", "torn')
    log = AuditLog(path, genesis=JUKU_MCP_GENESIS, fsync=False)
    log.append("call", tool="get_memory")
    log.close()
    report = verify_log(path, genesis=JUKU_MCP_GENESIS)
    assert report.is_intact
    assert report.recoveries == ["line 4: torn by a crash, recovered at the next start"]
    assert json.loads(path.read_text().splitlines()[-1])["tool"] == "get_memory"


def test_a_reopened_log_continues_the_chain(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    write_log(path, count=2)
    write_log(path, count=2)
    assert verify_log(path, genesis=JUKU_MCP_GENESIS).is_intact
