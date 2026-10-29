"""One chat question, end to end (Phase 2 AG5, AG6, B1).

In order, each step able to end the turn without calling the model:
1. the moderation check (AG6): a message suggesting self-harm gets the
   fixed reply, and an alert with no content;
2. the budget guard (B1): a reached cap gets a plain explanation, and the
   $0 features keep working;
3. Shiori's run, capped by PydanticAI's UsageLimits; its usage is
   recorded whatever happens, so a stopped run still counts;
4. the citation check (AG5): an answer whose citations don't all match
   rows returned in this turn is labelled unverified;
5. the question and the answer are stored as text, apart from the
   metrics, with an expiry date.

`ask_streaming` does the same, yielding the answer's text as the model
writes it, then the checked ChatAnswer last, for the page's server-sent
events.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta

from juku_common.delegation import Signer
from juku_data.engine.models import Learner
from pydantic_ai import Agent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.usage import RunUsage
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from juku_app.budget import BudgetGuard, BudgetRefusedError
from juku_app.citations import check_citations
from juku_app.moderation import Moderator, distress_reply
from juku_app.shiori import ShioriRun

# The 4-week window plus the 60 days after it that Phase 2's retention allows, rounded up.
TEXT_RETENTION = timedelta(days=90)
FREE_FEATURES = " Fitur gratis (kuis, rekomendasi, bacaan, rencana) tetap bisa dipakai."
RUN_LIMIT_REPLY = "Maaf, pertanyaan ini butuh terlalu banyak langkah. Coba tanyakan bagian yang lebih kecil."
UNSET_CRISIS_LINE = "(nomor belum diisi: lihat JUKU_CRISIS_LINE)"


@dataclass(frozen=True)
class ChatServices:
    agent: Agent[ShioriRun, str]
    guard: BudgetGuard
    moderator: Moderator
    signer: Signer
    app: AsyncEngine
    crisis_line: str = UNSET_CRISIS_LINE


@dataclass(frozen=True)
class ChatAnswer:
    text: str
    is_verified: bool
    stopped_because: str | None = None
    # The stored answer's ID, for rating it (UI3); None when the turn ended before the model.
    message_id: int | None = None


async def _before_the_model(
    services: ChatServices, learner: Learner, question: str, now: datetime
) -> ChatAnswer | None:
    """The answer, if moderation or the budget ends the turn here; None to go on to the model."""
    verdict = await services.moderator.check(question)
    if verdict.suggests_self_harm:
        async with services.app.begin() as connection:
            await connection.execute(text("INSERT INTO app.distress_events DEFAULT VALUES"))
        return ChatAnswer(distress_reply(services.crisis_line), is_verified=True, stopped_because="distress")
    try:
        await services.guard.check("chat", learner.id, now)
    except BudgetRefusedError as refused:
        return ChatAnswer(str(refused) + FREE_FEATURES, is_verified=True, stopped_because=refused.reason)
    return None


async def _store(services: ChatServices, learner: Learner, question: str, answer: ChatAnswer, now: datetime) -> int:
    """Store the question and the answer; return the answer's ID."""
    stored = 0
    async with services.app.begin() as connection:
        for role, body, verified in (("learner", question, None), ("shiori", answer.text, answer.is_verified)):
            stored = await connection.scalar(
                text(
                    "INSERT INTO app.chat_messages (learner_id, role, body, is_verified, created_at, expires_at) "
                    "VALUES (:learner, :role, :body, :verified, :at, :expires) RETURNING id"
                ),
                {
                    "learner": learner.id,
                    "role": role,
                    "body": body,
                    "verified": verified,
                    "at": now,
                    "expires": now + TEXT_RETENTION,
                },
            )
    return int(stored)


async def _finish(services: ChatServices, question: str, run: ShioriRun, output: str, now: datetime) -> ChatAnswer:
    check = check_citations(output, run.tool_results)
    answer = ChatAnswer(output, is_verified=check.is_verified)
    message_id = await _store(services, run.learner, question, answer, now)
    return ChatAnswer(output, is_verified=check.is_verified, message_id=message_id)


async def ask(services: ChatServices, learner: Learner, question: str, now: datetime) -> ChatAnswer:
    stopped = await _before_the_model(services, learner, question, now)
    if stopped is not None:
        return stopped
    run = ShioriRun(signer=services.signer, learner=learner, records=services.app)
    usage = RunUsage()
    try:
        result = await services.agent.run(
            question, deps=run, usage_limits=services.guard.run_limits("chat"), usage=usage
        )
    except UsageLimitExceeded:
        return ChatAnswer(RUN_LIMIT_REPLY, is_verified=True, stopped_because="run_limit")
    finally:
        await services.guard.record("chat", learner.id, usage)
    return await _finish(services, question, run, result.output, now)


async def ask_streaming(
    services: ChatServices, learner: Learner, question: str, now: datetime
) -> AsyncIterator[str | ChatAnswer]:
    stopped = await _before_the_model(services, learner, question, now)
    if stopped is not None:
        yield stopped.text
        yield stopped
        return
    run = ShioriRun(signer=services.signer, learner=learner, records=services.app)
    usage = RunUsage()
    pieces: list[str] = []
    try:
        async with services.agent.run_stream(
            question, deps=run, usage_limits=services.guard.run_limits("chat"), usage=usage
        ) as result:
            async for piece in result.stream_text(delta=True):
                pieces.append(piece)
                yield piece
    except UsageLimitExceeded:
        yield RUN_LIMIT_REPLY
        yield ChatAnswer(RUN_LIMIT_REPLY, is_verified=True, stopped_because="run_limit")
        return
    finally:
        await services.guard.record("chat", learner.id, usage)
    yield await _finish(services, question, run, "".join(pieces), now)
