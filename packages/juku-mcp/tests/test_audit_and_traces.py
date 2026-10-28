"""SM5 and FF9: every call is in the chained audit log and in a span, and neither holds content."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from juku_common.audit_chain import JUKU_MCP_GENESIS, verify_log
from juku_common.delegation import Signer
from juku_mcp.telemetry import CONTENT_ATTRIBUTE_PREFIXES, install_tracing
from juku_ops.audit_import import JUKU_MCP, import_audit_log
from juku_testkit.privacy import PLANTED_QUESTION, find_text
from mcp import Client
from mcp_helpers import Learners, call, token_for
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture(scope="module")
def spans() -> Iterator[InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    install_tracing(exporter)
    yield exporter


async def test_every_call_allowed_or_refused_is_logged_in_an_intact_chain(
    client: Client, signer: Signer, learners: Learners, audit_path: Path
) -> None:
    await call(client, "get_progress", token_for(signer, learners.a))
    await call(client, "get_progress", None)
    report = verify_log(audit_path, genesis=JUKU_MCP_GENESIS)
    assert report.is_intact
    calls = [record for record in report.records if record and record["kind"] == "call"]
    assert [(record["decision"], record.get("reason_category")) for record in calls] == [
        ("allowed", None),
        ("refused", "no_token"),
    ]
    assert calls[0]["actor_chain"] == ["agent:shiori"]
    assert "token" not in calls[0], "the token itself is never logged"


@pytest.mark.fitness("FF9")
async def test_a_question_typed_into_a_tool_reaches_no_record_in_postgres(
    client: Client, signer: Signer, learners: Learners, audit_path: Path, app_engine: AsyncEngine
) -> None:
    await call(client, "search_words", token_for(signer, learners.a), {"query": PLANTED_QUESTION})
    async with app_engine.begin() as connection:
        await connection.execute(text("DELETE FROM monitoring.audit_lines WHERE source = 'juku-mcp'"))
    await import_audit_log(app_engine, JUKU_MCP, audit_path)
    async with app_engine.connect() as connection:
        assert await find_text(connection, "monitoring", "PLANTED-7f3a") == []


@pytest.mark.fitness("FF9")
async def test_spans_carry_the_decision_but_never_arguments_or_results(
    spans: InMemorySpanExporter, client: Client, signer: Signer, learners: Learners
) -> None:
    spans.clear()
    await call(client, "search_words", token_for(signer, learners.a), {"query": PLANTED_QUESTION})
    await call(client, "get_progress", None)
    finished = spans.get_finished_spans()
    decisions = [span.attributes.get("juku.decision") for span in finished if span.attributes]
    assert "allowed" in decisions and "refused" in decisions
    for span in finished:
        values = [str(value) for value in (span.attributes or {}).values()]
        values += [str(value) for event in span.events for value in (event.attributes or {}).values()]
        assert not any("PLANTED-7f3a" in value for value in values), span.name
        assert not any(key.startswith(CONTENT_ATTRIBUTE_PREFIXES) for key in (span.attributes or {})), span.name
