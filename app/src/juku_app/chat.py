"""One chat question, end to end (stub: lands in the next commit)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime

from juku_common.delegation import Signer
from juku_data.engine.models import Learner
from pydantic_ai import Agent
from sqlalchemy.ext.asyncio import AsyncEngine

from juku_app.budget import BudgetGuard
from juku_app.moderation import Moderator
from juku_app.shiori import ShioriRun


@dataclass(frozen=True)
class ChatServices:
    agent: Agent[ShioriRun, str]
    guard: BudgetGuard
    moderator: Moderator
    signer: Signer
    app: AsyncEngine


@dataclass(frozen=True)
class ChatAnswer:
    text: str
    is_verified: bool
    stopped_because: str | None = None


async def ask(services: ChatServices, learner: Learner, question: str, now: datetime) -> ChatAnswer:
    raise NotImplementedError


def ask_streaming(
    services: ChatServices, learner: Learner, question: str, now: datetime
) -> AsyncIterator[str | ChatAnswer]:
    raise NotImplementedError
