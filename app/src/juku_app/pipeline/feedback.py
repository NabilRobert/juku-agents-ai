"""The weekly feedback job (Phase 2 AG4): it drafts prompt changes for Arthur, and never applies them.

Ported in spirit from Pitstop's weekly feedback (gads-case-study e15697e,
backend/src/pipeline/weeklyFeedback.ts). It reads the past week's reviews,
counts each agent's issues by reason (Tadashi's reasons, and code's check
names), and for an agent with a reason recurring at least the rule file's
threshold, asks a model to draft a change to that agent's instructions.

What the drafting model sees is reasons and counts only: an issue's quote
is the learner's own report text, so it never leaves the run records. The
drafts go to `app.prompt_feedback` for the Run Inspector; nothing reads
them back into an agent, and the instructions live in code (crew.py).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from juku_common.rules import Rules
from pydantic_ai import Agent
from pydantic_ai.models import Model
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from juku_app.pipeline.crew import FEEDBACK_INSTRUCTIONS

JOB_NAME = "draft-feedback"
WEEK = timedelta(days=7)
WEEK_REVIEWS = """
SELECT agent, issues, code_issues FROM app.critic_reviews
WHERE created_at > :since AND created_at <= :now ORDER BY id
"""


@dataclass(frozen=True)
class FeedbackDraft:
    agent: str
    status: str
    text: str


def recurring_reasons(rows: list[tuple[str, Any, Any]], threshold: int) -> dict[str, list[dict[str, Any]]]:
    """Per agent, each reason seen at least `threshold` times, with its count; quotes are dropped here."""
    counts: dict[str, Counter[str]] = {}
    for agent, issues, code_issues in rows:
        reasons = [str(issue["reason"]) for issue in cast(list[dict[str, Any]], issues)]
        reasons += [f"code: {issue['kind']}" for issue in cast(list[dict[str, Any]], code_issues)]
        counts.setdefault(str(agent), Counter()).update(reasons)
    return {
        agent: [{"reason": reason, "count": count} for reason, count in counter.most_common() if count >= threshold]
        for agent, counter in sorted(counts.items())
        if any(count >= threshold for count in counter.values())
    }


async def draft_feedback(app: AsyncEngine, model: Model, rules: Rules, now: datetime) -> list[FeedbackDraft]:
    async with app.connect() as connection:
        rows = [
            tuple(row)
            for row in (await connection.execute(text(WEEK_REVIEWS), {"since": now - WEEK, "now": now})).all()
        ]
    patterns = recurring_reasons(cast(list[tuple[str, Any, Any]], rows), rules.pipeline.feedback_min_occurrences)
    drafter = Agent(model, output_type=str, instructions=FEEDBACK_INSTRUCTIONS)
    drafts: list[FeedbackDraft] = []
    for agent, recurring in patterns.items():
        prompt = json.dumps({"agent": agent, "recurring_issues": recurring}, ensure_ascii=False)
        draft = (await drafter.run(prompt)).output
        async with app.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO app.prompt_feedback (week_start, agent, patterns, draft, created_at) "
                    "VALUES (:week, :agent, CAST(:patterns AS jsonb), :draft, :now)"
                ),
                {
                    "week": (now - WEEK).date(),
                    "agent": agent,
                    "patterns": json.dumps(recurring, ensure_ascii=False),
                    "draft": draft,
                    "now": now,
                },
            )
        drafts.append(FeedbackDraft(agent=agent, status="draft", text=draft))
    return drafts
