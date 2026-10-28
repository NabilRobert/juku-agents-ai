"""M7: no call to Juku's MCP server can return another learner's rows (Phase 2 SM2).

Two learners with different known words. Every read tool, called with A's
token, returns exactly what the engine computes for A; nothing in the
protocol lets a call name B: no tool takes a learner, and the token is
signed.
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from juku_common.delegation import Signer
from juku_common.rules import load_rules
from juku_data.engine import (
    Databases,
    find_reading_sentences,
    get_mistakes,
    get_progress,
    get_recent_activity,
    recommend_words,
)
from mcp import Client
from mcp_helpers import Learners, call, token_for

pytestmark = [
    pytest.mark.xfail(strict=True, reason="EDD: the server lands in the next commit"),
    pytest.mark.fitness("FF8"),
]

READ_TOOLS = ["get_progress", "get_mistakes", "recommend_words", "find_reading_sentences", "get_recent_activity"]


async def engine_view(db: Databases, learner_id: int, tool: str) -> dict[str, Any]:
    now = datetime.now(UTC)
    if tool == "get_progress":
        return (await get_progress(db, learner_id)).model_dump(mode="json")
    if tool == "get_mistakes":
        return (await get_mistakes(db, learner_id, now)).model_dump(mode="json")
    if tool == "recommend_words":
        return (await recommend_words(db, learner_id)).model_dump(mode="json")
    if tool == "find_reading_sentences":
        return (await find_reading_sentences(db, learner_id)).model_dump(mode="json")
    return (await get_recent_activity(db, learner_id, now.date())).model_dump(mode="json")


@pytest.mark.parametrize("tool", READ_TOOLS)
async def test_each_tool_returns_exactly_the_token_learners_data(
    client: Client, signer: Signer, learners: Learners, engine_databases: Databases, tool: str
) -> None:
    for learner in (learners.a, learners.b):
        answer = await call(client, tool, token_for(signer, learner))
        assert not answer.is_error, answer.text
        assert answer.body == await engine_view(engine_databases, learner.id, tool)
    a_view = await engine_view(engine_databases, learners.a.id, "recommend_words")
    b_view = await engine_view(engine_databases, learners.b.id, "recommend_words")
    assert a_view != b_view, "the two learners must differ, or this test proves nothing"


@pytest.mark.parametrize("argument", ["learner_id", "public_id", "learner", "user_id"])
async def test_a_tool_called_with_a_learner_argument_is_refused(
    client: Client, signer: Signer, learners: Learners, argument: str
) -> None:
    answer = await call(client, "get_progress", token_for(signer, learners.a), {argument: learners.b.public_id})
    assert answer.is_error
    assert answer.body["refused"] == "unexpected_arguments"
    assert "words_known" not in answer.text


async def test_a_token_for_another_learner_from_another_signer_is_refused(client: Client, learners: Learners) -> None:
    forger = Signer(ed25519.Ed25519PrivateKey.generate(), load_rules())
    answer = await call(client, "get_progress", token_for(forger, learners.b))
    assert (answer.is_error, answer.body["refused"]) == (True, "bad_signature")


async def test_a_token_with_its_learner_edited_is_refused(client: Client, signer: Signer, learners: Learners) -> None:
    token = token_for(signer, learners.a)
    edited = token.replace(token.split(".")[1], token_for(signer, learners.b).split(".")[1])
    answer = await call(client, "get_progress", edited)
    assert (answer.is_error, answer.body["refused"]) == (True, "bad_signature")


async def test_a_delegated_hop_that_switches_learner_is_refused(
    client: Client, signer: Signer, learners: Learners
) -> None:
    import jwt

    child = signer.delegate(token_for(signer, learners.a), to_agent="keiko", tools=["get_progress"])
    claims = jwt.decode(child, options={"verify_signature": False}) | {"sub": learners.b.public_id}
    answer = await call(client, "get_progress", signer.sign_claims(claims))
    assert (answer.is_error, answer.body["refused"]) == (True, "learner_changed")


async def test_a_signed_token_for_a_learner_who_does_not_exist_is_refused(client: Client, signer: Signer) -> None:
    token = signer.mint(learner="nobody-here", agent="shiori", tools=["get_progress"], purpose="chat")
    answer = await call(client, "get_progress", token)
    assert (answer.is_error, answer.body["refused"]) == (True, "unknown_learner")
