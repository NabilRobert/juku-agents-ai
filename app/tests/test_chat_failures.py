"""When a chat turn fails: what the learner is sent, and what reaches the logs."""

import asyncio
from collections.abc import AsyncIterator

from chat_helpers import NOW, citing, services
from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_app.chat import MODEL_ERROR_REPLY, ChatAnswer, ChatServices, ask_streaming
from juku_data.engine import Databases
from juku_data.engine.models import Learner
from juku_testkit.privacy import PLANTED_QUESTION
from pydantic_ai.messages import ModelMessage, ModelResponse
from pydantic_ai.models.function import AgentInfo, FunctionModel
from structlog.testing import capture_logs

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
