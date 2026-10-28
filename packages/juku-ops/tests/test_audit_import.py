"""The audit importer (Phase 2 M2, SM5): only verified lines, only metadata, each line once."""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from juku_common.audit_chain import GATEWAY_GENESIS, JUKU_MCP_GENESIS, AuditLog
from juku_ops.audit_import import GATEWAY, JUKU_MCP, import_audit_log
from juku_testkit.privacy import PLANTED_QUESTION, find_text
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
async def engine(app_engine: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    async with app_engine.begin() as connection:
        await connection.execute(text("TRUNCATE monitoring.audit_lines, monitoring.audit_imports"))
    yield app_engine


def gateway_call(log: AuditLog, call_id: str, *, tool: str = "get_progress", suspicious: bool = False) -> None:
    """A forwarded call and its result, as mcp-security-gateway writes them."""
    log.append(
        "call",
        call_id=call_id,
        caller="shiori",
        decision="forwarding",
        route="juku",
        tool=tool,
        arguments={"question": PLANTED_QUESTION},
    )
    log.append(
        "result",
        call_id=call_id,
        caller="shiori",
        decision="allowed",
        route="juku",
        tool=tool,
        is_error=False,
        suspicious=suspicious,
        layer="rules",
        score=0.9 if suspicious else 0.0,
        matched=[],
        output_sha256="ab" * 32,
        error=PLANTED_QUESTION,
    )


def write_gateway_log(path: Path, calls: int) -> None:
    log = AuditLog(path, genesis=GATEWAY_GENESIS, fsync=False)
    log.append("start", routes=["juku"], version="0.1.0")
    for number in range(calls):
        gateway_call(log, f"call-{number}")
    log.close()


async def scalar(engine: AsyncEngine, sql: str) -> object:
    async with engine.connect() as connection:
        return await connection.scalar(text(sql))


async def test_an_intact_gateway_log_is_imported_line_by_line(engine: AsyncEngine, tmp_path: Path) -> None:
    path = tmp_path / "gateway-audit.jsonl"
    write_gateway_log(path, calls=2)
    result = await import_audit_log(engine, GATEWAY, path)
    assert result.is_intact
    assert (result.lines_total, result.lines_imported) == (5, 5)
    assert await scalar(engine, "SELECT count(*) FROM monitoring.audit_lines WHERE source = 'gateway'") == 5
    assert await scalar(engine, "SELECT bool_and(is_intact) FROM monitoring.audit_imports") is True


async def test_a_flagged_result_keeps_the_detectors_verdict(engine: AsyncEngine, tmp_path: Path) -> None:
    path = tmp_path / "gateway-audit.jsonl"
    log = AuditLog(path, genesis=GATEWAY_GENESIS, fsync=False)
    gateway_call(log, "call-1", suspicious=True)
    log.close()
    await import_audit_log(engine, GATEWAY, path)
    row = await scalar(
        engine,
        "SELECT format('%s %s %s %s', caller, tool, detector_layer, detector_score) "
        "FROM monitoring.audit_lines WHERE kind = 'result' AND is_suspicious",
    )
    assert row == "shiori get_progress rules 0.9"


@pytest.mark.fitness("FF9")
async def test_arguments_outputs_and_errors_are_never_imported(engine: AsyncEngine, tmp_path: Path) -> None:
    path = tmp_path / "gateway-audit.jsonl"
    write_gateway_log(path, calls=1)
    await import_audit_log(engine, GATEWAY, path)
    async with engine.connect() as connection:
        assert await find_text(connection, "monitoring", "PLANTED-7f3a") == []


async def test_a_broken_chain_imports_nothing_and_is_recorded(engine: AsyncEngine, tmp_path: Path) -> None:
    path = tmp_path / "gateway-audit.jsonl"
    write_gateway_log(path, calls=2)
    lines = path.read_text().splitlines(keepends=True)
    lines[1] = lines[1].replace('"caller":"shiori"', '"caller":"keiko"')
    path.write_text("".join(lines))
    result = await import_audit_log(engine, GATEWAY, path)
    assert result.problems == ["line 3: chain broken (an earlier line was changed, added or removed)"]
    assert result.lines_imported == 0
    assert await scalar(engine, "SELECT count(*) FROM monitoring.audit_lines") == 0
    assert await scalar(engine, "SELECT problems[1] FROM monitoring.audit_imports WHERE NOT is_intact") == (
        "line 3: chain broken (an earlier line was changed, added or removed)"
    )


async def test_a_second_import_adds_only_the_new_lines(engine: AsyncEngine, tmp_path: Path) -> None:
    path = tmp_path / "gateway-audit.jsonl"
    write_gateway_log(path, calls=1)
    first = await import_audit_log(engine, GATEWAY, path)
    log = AuditLog(path, genesis=GATEWAY_GENESIS, fsync=False)
    gateway_call(log, "call-later")
    log.close()
    second = await import_audit_log(engine, GATEWAY, path)
    third = await import_audit_log(engine, GATEWAY, path)
    assert (first.lines_imported, second.lines_imported, third.lines_imported) == (3, 2, 0)
    assert third.is_intact
    assert await scalar(engine, "SELECT count(*) FROM monitoring.audit_lines") == 5


async def test_a_file_that_no_longer_matches_what_was_imported_is_refused(engine: AsyncEngine, tmp_path: Path) -> None:
    path = tmp_path / "gateway-audit.jsonl"
    write_gateway_log(path, calls=1)
    await import_audit_log(engine, GATEWAY, path)
    path.unlink()
    write_gateway_log(path, calls=2)  # a new, valid chain: e.g. the old log deleted and restarted
    result = await import_audit_log(engine, GATEWAY, path)
    assert result.problems == ["line 3 no longer matches the copy imported earlier: the log was replaced or rewritten"]
    assert result.lines_imported == 0


async def test_juku_mcp_refusals_keep_their_category_and_chain_but_not_their_detail(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    path = tmp_path / "juku-mcp-audit.jsonl"
    log = AuditLog(path, genesis=JUKU_MCP_GENESIS, fsync=False)
    log.append(
        "call",
        tool="get_progress",
        caller="keiko",
        decision="refused",
        reason_category="actor_mismatch",
        reason=f"chain's actor agent:shiori is not the calling key's agent keiko {PLANTED_QUESTION}",
        actor_chain=["agent:shiori"],
        learner="lrn_planted",
    )
    log.close()
    await import_audit_log(engine, JUKU_MCP, path)
    row = await scalar(
        engine,
        "SELECT format('%s %s %s %s', caller, decision, reason_category, actor_chain) "
        "FROM monitoring.audit_lines WHERE source = 'juku-mcp'",
    )
    assert row == "keiko refused actor_mismatch {agent:shiori}"
    async with engine.connect() as connection:
        assert await find_text(connection, "monitoring", "PLANTED-7f3a") == []
        assert await find_text(connection, "monitoring", "lrn_planted") == []


async def test_a_line_without_a_timestamp_stops_the_whole_import(engine: AsyncEngine, tmp_path: Path) -> None:
    path = tmp_path / "juku-mcp-audit.jsonl"
    log = AuditLog(path, genesis=JUKU_MCP_GENESIS, fsync=False)
    log.append("call", tool="get_progress", decision="allowed")
    log.close()
    lines = path.read_text().splitlines(keepends=True)
    log = AuditLog(path, genesis=JUKU_MCP_GENESIS, fsync=False)
    log.append("call", tool="get_memory", decision="allowed", ts=None)
    log.close()
    assert len(path.read_text().splitlines()) == len(lines) + 1
    result = await import_audit_log(engine, JUKU_MCP, path)
    assert result.problems == ["line 2: no `ts` or `kind`"]
    assert await scalar(engine, "SELECT count(*) FROM monitoring.audit_lines") == 0


async def test_the_two_logs_are_counted_separately(engine: AsyncEngine, tmp_path: Path) -> None:
    gateway_path = tmp_path / "gateway-audit.jsonl"
    write_gateway_log(gateway_path, calls=2)
    await import_audit_log(engine, GATEWAY, gateway_path)
    juku_path = tmp_path / "juku-mcp-audit.jsonl"
    log = AuditLog(juku_path, genesis=JUKU_MCP_GENESIS, fsync=False)
    log.append("call", tool="get_progress", decision="allowed")
    log.close()
    result = await import_audit_log(engine, JUKU_MCP, juku_path)
    assert (result.is_intact, result.lines_imported) == (True, 1)


async def test_a_field_of_the_wrong_type_is_stored_as_null(engine: AsyncEngine, tmp_path: Path) -> None:
    path = tmp_path / "gateway-audit.jsonl"
    log = AuditLog(path, genesis=GATEWAY_GENESIS, fsync=False)
    log.append("result", call_id="c1", caller=7, tool="get_progress", suspicious="yes", score="high")
    log.close()
    assert (await import_audit_log(engine, GATEWAY, path)).is_intact
    row = await scalar(
        engine, "SELECT format('%s|%s|%s', caller, is_suspicious, detector_score) FROM monitoring.audit_lines"
    )
    assert row == "||"


async def test_a_line_torn_by_a_crash_is_skipped_and_the_lines_after_it_imported(
    engine: AsyncEngine, tmp_path: Path
) -> None:
    path = tmp_path / "juku-mcp-audit.jsonl"
    log = AuditLog(path, genesis=JUKU_MCP_GENESIS, fsync=False)
    log.append("call", tool="get_progress", decision="allowed")
    log.close()
    with path.open("a") as file:
        file.write('{"kind": "call", "torn')
    log = AuditLog(path, genesis=JUKU_MCP_GENESIS, fsync=False)
    log.append("call", tool="get_memory", decision="allowed")
    log.close()
    result = await import_audit_log(engine, JUKU_MCP, path)
    assert (result.is_intact, result.lines_total, result.lines_imported) == (True, 4, 3)


async def test_a_timestamp_that_is_not_iso_is_a_problem(engine: AsyncEngine, tmp_path: Path) -> None:
    path = tmp_path / "juku-mcp-audit.jsonl"
    log = AuditLog(path, genesis=JUKU_MCP_GENESIS, fsync=False)
    log.append("call", tool="get_progress", decision="allowed", ts="yesterday")
    log.close()
    assert (await import_audit_log(engine, JUKU_MCP, path)).problems == ["line 1: `ts` isn't an ISO timestamp"]
