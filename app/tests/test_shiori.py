"""Shiori end to end at $0: PydanticAI with scripted models (TestModel, FunctionModel), Juku's server over HTTP.

What slice 5's "done when" asks of the chat: the guard stops before the
model is called; per-call records and traces hold no content; a
fabricated citation is flagged. Also AG6's fixed reply, and the run cap.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_app.budget import BudgetGuard
from juku_app.chat import MODEL_ERROR_REPLY, ChatAnswer, ChatServices, ask, ask_streaming
from juku_app.moderation import Verdict
from juku_app.shiori import build_shiori, juku_toolset
from juku_common.delegation import Signer
from juku_common.rules import load_rules
from juku_data.engine import Databases, mark_known, recommend_words
from juku_data.engine.models import Learner
from juku_testkit.privacy import PLANTED_QUESTION, find_text
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, DeltaToolCall, DeltaToolCalls, FunctionModel
from sqlalchemy import text
from structlog.testing import capture_logs

NOW = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)


class AllowAll:
    async def check(self, message: str) -> Verdict:
        assert message
        return Verdict(suggests_self_harm=False)


class FlagAll:
    async def check(self, message: str) -> Verdict:
        assert message
        return Verdict(suggests_self_harm=True)


@pytest.fixture
async def studying(engine_databases: Databases, learner: Learner) -> Learner:
    async with engine_databases.app.connect() as connection:
        words = list(
            await connection.scalars(text("SELECT word_id FROM learning.dictionary_words ORDER BY word_id LIMIT 20"))
        )
    for word in words:
        await mark_known(engine_databases, learner.id, str(word), datetime(2026, 11, 2, tzinfo=UTC))
    return learner


def services(
    model: Model, url: str, key: ed25519.Ed25519PrivateKey, db: Databases, moderator: Any = None
) -> ChatServices:
    rules = load_rules()
    return ChatServices(
        agent=build_shiori(model, juku_toolset(url)),
        guard=BudgetGuard(db.app, rules),
        moderator=moderator or AllowAll(),
        signer=Signer(key, rules),
        app=db.app,
    )


def tool_returns(messages: list[ModelMessage]) -> list[ToolReturnPart]:
    return [part for message in messages for part in getattr(message, "parts", []) if isinstance(part, ToolReturnPart)]


def citing(word_id: str | None) -> FunctionModel:
    """Asks for recommendations, then answers citing `word_id` (or the first word returned, if None)."""

    def answer_text(messages: list[ModelMessage]) -> str | None:
        returns = tool_returns(messages)
        if not returns:
            return None
        returned: Any = returns[-1].content
        body = returned if isinstance(returned, dict) else json.loads(str(returned))
        return f"Pelajari kata ini dulu [ref:{word_id or body['words'][0]['word_id']}]."

    def step(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        answer = answer_text(messages)
        if answer is None:
            return ModelResponse(parts=[ToolCallPart(tool_name="recommend_words", args={})])
        return ModelResponse(parts=[TextPart(answer)])

    async def stream(messages: list[ModelMessage], _info: AgentInfo) -> AsyncIterator[str | DeltaToolCalls]:
        answer = answer_text(messages)
        if answer is None:
            yield {0: DeltaToolCall(name="recommend_words", json_args="{}")}
            return
        for word in answer.split(" "):
            yield word + " " if not answer.endswith(word) else word

    return FunctionModel(step, stream_function=stream)


def never_called() -> FunctionModel:
    def step(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        raise AssertionError(f"the model was called: {messages}")

    return FunctionModel(step)


async def test_an_answer_citing_a_returned_word_is_verified(
    juku_mcp_url: str,
    key: ed25519.Ed25519PrivateKey,
    engine_databases: Databases,
    studying: Learner,
    clean_budget: object,
) -> None:
    assert clean_budget
    answer = await ask(services(citing(None), juku_mcp_url, key, engine_databases), studying, "kata apa dulu?", NOW)
    first = (await recommend_words(engine_databases, studying.id)).words[0].word_id
    assert (answer.is_verified, answer.stopped_because) == (True, None)
    assert first in answer.text


async def test_a_fabricated_citation_is_flagged_unverified(
    juku_mcp_url: str,
    key: ed25519.Ed25519PrivateKey,
    engine_databases: Databases,
    studying: Learner,
    clean_budget: object,
) -> None:
    assert clean_budget
    answer = await ask(services(citing("ffffffffff"), juku_mcp_url, key, engine_databases), studying, "kata apa?", NOW)
    assert answer.is_verified is False


async def test_each_tool_call_leaves_a_per_call_record_and_the_run_its_cost(
    juku_mcp_url: str,
    key: ed25519.Ed25519PrivateKey,
    engine_databases: Databases,
    studying: Learner,
    clean_budget: object,
) -> None:
    assert clean_budget
    await ask(services(citing(None), juku_mcp_url, key, engine_databases), studying, "kata apa?", NOW)
    async with engine_databases.app.connect() as connection:
        record = (
            await connection.execute(
                text(
                    "SELECT agent, server, tool, outcome, actor_chain, duration_ms >= 0 FROM monitoring.tool_calls "
                    "WHERE learner_id = :id ORDER BY id DESC LIMIT 1"
                ),
                {"id": studying.id},
            )
        ).one()
        cost = await connection.scalar(
            text("SELECT sum(cost_usd) FROM app.model_calls WHERE learner_id = :id AND pool = 'chat'"),
            {"id": studying.id},
        )
    assert tuple(record) == ("shiori", "juku", "recommend_words", "ok", ["shiori"], True)
    assert cost is not None and cost >= Decimal(0)


@pytest.mark.fitness("FF9")
async def test_the_question_reaches_no_record_and_no_span(
    juku_mcp_url: str,
    key: ed25519.Ed25519PrivateKey,
    engine_databases: Databases,
    studying: Learner,
    clean_budget: object,
    spans: InMemorySpanExporter,
) -> None:
    assert clean_budget
    await ask(services(citing(None), juku_mcp_url, key, engine_databases), studying, PLANTED_QUESTION, NOW)
    async with engine_databases.app.connect() as connection:
        assert await find_text(connection, "monitoring", "PLANTED-7f3a") == []
    finished = spans.get_finished_spans()
    assert finished, "the run made no spans: the probe proves nothing"
    for span in finished:
        values = [str(value) for value in (span.attributes or {}).values()]
        values += [str(value) for event in span.events for value in (event.attributes or {}).values()]
        assert not any("PLANTED-7f3a" in value for value in values), span.name


async def test_the_guard_stops_chat_before_the_model_is_called(
    juku_mcp_url: str,
    key: ed25519.Ed25519PrivateKey,
    engine_databases: Databases,
    studying: Learner,
    clean_budget: object,
) -> None:
    assert clean_budget
    async with engine_databases.app.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO app.model_calls (called_at, pool, requests, input_tokens, output_tokens, cost_usd) "
                "VALUES (:at, 'chat', 1, 0, 0, 5)"
            ),
            {"at": NOW},
        )
    answer = await ask(services(never_called(), juku_mcp_url, key, engine_databases), studying, "halo", NOW)
    assert answer.stopped_because == "chat_pool_spent"
    assert "fitur gratis" in answer.text.lower()  # the $0 features keep working, and the learner is told


async def test_a_message_suggesting_self_harm_gets_the_fixed_reply_and_no_model_call(
    juku_mcp_url: str,
    key: ed25519.Ed25519PrivateKey,
    engine_databases: Databases,
    studying: Learner,
    clean_budget: object,
) -> None:
    assert clean_budget
    async with engine_databases.app.connect() as connection:
        before = int(await connection.scalar(text("SELECT count(*) FROM app.distress_events")) or 0)
    answer = await ask(services(never_called(), juku_mcp_url, key, engine_databases, FlagAll()), studying, "...", NOW)
    async with engine_databases.app.connect() as connection:
        after = int(await connection.scalar(text("SELECT count(*) FROM app.distress_events")) or 0)
    assert answer.stopped_because == "distress"
    assert after == before + 1


async def test_a_runaway_loop_stops_at_the_run_cap(
    juku_mcp_url: str,
    key: ed25519.Ed25519PrivateKey,
    engine_databases: Databases,
    studying: Learner,
    clean_budget: object,
) -> None:
    def forever(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[ToolCallPart(tool_name="get_progress", args={})])

    assert clean_budget
    answer = await ask(services(FunctionModel(forever), juku_mcp_url, key, engine_databases), studying, "halo", NOW)
    assert answer.stopped_because == "run_limit"
    async with engine_databases.app.connect() as connection:
        requests = await connection.scalar(
            text("SELECT sum(requests) FROM app.model_calls WHERE learner_id = :id"), {"id": studying.id}
        )
    assert requests == load_rules().budget.chat_run_request_limit


async def test_the_answer_streams_then_ends_with_its_check(
    juku_mcp_url: str,
    key: ed25519.Ed25519PrivateKey,
    engine_databases: Databases,
    studying: Learner,
    clean_budget: object,
) -> None:
    assert clean_budget
    pieces: list[str | ChatAnswer] = [
        piece
        async for piece in ask_streaming(
            services(citing(None), juku_mcp_url, key, engine_databases), studying, "?", NOW
        )
    ]
    final = pieces[-1]
    assert isinstance(final, ChatAnswer) and final.is_verified
    assert "".join(piece for piece in pieces if isinstance(piece, str)) == final.text


# PydanticAI hands text over in 0.1 s batches, so text is only "sent" once its batch has passed.
PAST_STREAM_BATCH_SECONDS = 0.15


def failing(*, after: str | None = None) -> FunctionModel:
    """A model that fails while streaming, after writing `after`; its error quotes the learner's question."""

    def step(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        raise AssertionError("only the stream is used")

    async def stream(_messages: list[ModelMessage], _info: AgentInfo) -> AsyncIterator[str]:
        if after:
            yield after
            await asyncio.sleep(PAST_STREAM_BATCH_SECONDS)
        raise RuntimeError(f"provider refused: {PLANTED_QUESTION}")

    return FunctionModel(step, stream_function=stream)


async def stream_to_the_end(chat: ChatServices, learner: Learner) -> tuple[str, ChatAnswer]:
    """Everything the learner is sent: the text, and the final answer."""
    pieces = [piece async for piece in ask_streaming(chat, learner, PLANTED_QUESTION, NOW)]
    final = pieces[-1]
    assert isinstance(final, ChatAnswer)
    return "".join(piece for piece in pieces if isinstance(piece, str)), final


async def test_a_model_failure_ends_the_stream_with_a_plain_reply(
    juku_mcp_url: str,
    key: ed25519.Ed25519PrivateKey,
    engine_databases: Databases,
    studying: Learner,
    clean_budget: object,
) -> None:
    assert clean_budget
    sent, final = await stream_to_the_end(services(failing(), juku_mcp_url, key, engine_databases), studying)
    assert sent == final.text == MODEL_ERROR_REPLY
    assert final.stopped_because == "model_error"
    assert final.is_verified


async def test_a_tool_server_that_cannot_be_reached_ends_the_stream_with_a_plain_reply(
    key: ed25519.Ed25519PrivateKey, engine_databases: Databases, studying: Learner, clean_budget: object
) -> None:
    assert clean_budget
    unreachable = "http://127.0.0.1:1/mcp"
    sent, final = await stream_to_the_end(services(citing(None), unreachable, key, engine_databases), studying)
    assert sent == MODEL_ERROR_REPLY
    assert final.stopped_because == "model_error"


async def test_an_answer_cut_off_midway_is_kept_and_labelled_unverified(
    juku_mcp_url: str,
    key: ed25519.Ed25519PrivateKey,
    engine_databases: Databases,
    studying: Learner,
    clean_budget: object,
) -> None:
    assert clean_budget
    model = failing(after="Pelajari kata")
    sent, final = await stream_to_the_end(services(model, juku_mcp_url, key, engine_databases), studying)
    assert sent == final.text == f"Pelajari kata {MODEL_ERROR_REPLY}"
    assert not final.is_verified


async def test_a_failed_turn_logs_the_error_type_and_no_content(
    juku_mcp_url: str,
    key: ed25519.Ed25519PrivateKey,
    engine_databases: Databases,
    studying: Learner,
    clean_budget: object,
) -> None:
    assert clean_budget
    with capture_logs() as logged:
        await stream_to_the_end(services(failing(), juku_mcp_url, key, engine_databases), studying)
    assert logged == [{"event": "chat_run_failed", "error": "RuntimeError", "log_level": "warning"}]
