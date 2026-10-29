"""One learner's weekly run, in code's fixed order (ADR-007; AG1, AG2): facts, Keiko, Tadashi, Nikki, Tadashi.

0. A learner on an older consent notice gets nothing new until they
   accept the current one: the week is skipped, and why is recorded.
1. Claim the (learner, week) run: a published week is skipped, a run
   another worker holds is left alone, a dead one is taken over (FF7).
2. Gather the facts (code, no model).
3. Keiko plans; code checks the plan against fresh facts and Tadashi
   reviews it; at most 2 revisions. An approved plan's note proposals go
   through memory's rules.
4. Nikki writes; the same checks and review.
5. Publish Nikki's report, or the facts-only one if an output never
   passed or the reports pool is spent (B1): the learner always gets one.
Every agent call is checked against the reports pool first and recorded
after (ADR-012).

The hourly cron job (`juku run-weekly --due`) runs each learner whose
Sunday 18:00 has come in their own timezone, then any queued replans.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from juku_common.delegation import Signer
from juku_common.rules import Rules
from juku_data import engine
from juku_data.engine import Databases
from juku_data.engine.models import Learner
from juku_data.memory import propose_note
from juku_ops.jobs import recorded_run
from pydantic import BaseModel
from pydantic_ai.agent import AgentRunResult
from pydantic_ai.exceptions import UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.usage import RunUsage, UsageLimits
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from juku_app.budget import BudgetGuard, BudgetRefusedError
from juku_app.consent import has_current_consent
from juku_app.pipeline import records
from juku_app.pipeline.approval import decide_approval
from juku_app.pipeline.checks import check_plan, check_report
from juku_app.pipeline.crew import Crew, KeikoRun, keiko_prompt, nikki_prompt, tadashi_prompt
from juku_app.pipeline.facts import WeekFacts, gather_facts, retired_note_ids, week_of
from juku_app.pipeline.fallback import facts_only_report
from juku_app.pipeline.outputs import Issue, KeikoPlan, Review

RunStatus = Literal["published", "fallback", "skipped", "replanned", "busy"]
JOB_NAME = "run-weekly"
CONSENT_OUTDATED = "consent_outdated"
# ISO weekdays run Monday 1 to Sunday 7; the rule file counts Monday as 0.
ISO_WEEKDAY_OFFSET = 1

DUE = """
SELECT l.public_id FROM learning.learners l
WHERE extract(isodow FROM :now AT TIME ZONE l.timezone) = :isodow
  AND extract(hour FROM :now AT TIME ZONE l.timezone) >= :hour
  AND NOT EXISTS (
      SELECT 1 FROM app.pipeline_runs r
      WHERE r.learner_id = l.id AND r.kind = 'weekly'
        AND r.week_start = (date_trunc('week', :now AT TIME ZONE l.timezone))::date
        AND r.status IN ('published', 'fallback')
  )
ORDER BY l.id
"""
QUEUED_REPLANS = """
SELECT r.id, l.public_id FROM learning.replan_requests r JOIN learning.learners l ON l.id = r.learner_id
WHERE r.handled_at IS NULL ORDER BY r.id
"""


@dataclass(frozen=True)
class PipelineServices:
    db: Databases
    rules: Rules
    guard: BudgetGuard
    signer: Signer
    crew: Crew


class RunOutcome(BaseModel):
    run_id: int | None
    status: RunStatus
    report: str | None = None
    # Why a run was skipped, when it was: consent_outdated.
    reason: str | None = None


class BudgetSpentError(Exception):
    """The reports pool can't pay for the next call: the run ends with the facts-only report."""


@dataclass(frozen=True)
class RunScope:
    services: PipelineServices
    learner: Learner
    run_id: int
    now: datetime
    via_shiori: bool = False
    # The learner's retired notes, for the stale-claim check (checks.py).
    retired: frozenset[str] = frozenset()


async def _call(context: RunScope, run_agent: Callable[[UsageLimits, RunUsage], Awaitable[AgentRunResult[Any]]]) -> Any:
    """One agent call, paid from the reports pool: checked before, recorded after, whatever happens."""
    guard, learner_id = context.services.guard, context.learner.id
    try:
        await guard.check("reports", learner_id, context.now)
    except BudgetRefusedError as refused:
        raise BudgetSpentError(str(refused)) from refused
    usage = RunUsage()
    try:
        return (await run_agent(guard.run_limits("reports"), usage)).output
    except UsageLimitExceeded as stopped:
        raise BudgetSpentError(str(stopped)) from stopped
    finally:
        await guard.record("reports", learner_id, usage)


async def _review(context: RunScope, author: str, output: Any, given: dict[str, Any]) -> Review | None:
    """Tadashi's review, or None if he gave no usable one (which blocks, like Pitstop's unavailable review)."""
    tadashi = context.services.crew.tadashi
    prompt = tadashi_prompt(author, output, given)
    try:
        return await _call(context, lambda limits, usage: tadashi.run(prompt, usage_limits=limits, usage=usage))
    except UnexpectedModelBehavior:
        return None


async def _reviewed(
    context: RunScope,
    author: str,
    generate: Callable[[dict[str, Any] | None], Awaitable[Any]],
    check: Callable[[Any, WeekFacts], list[Issue]],
    given: dict[str, Any],
) -> Any | None:
    """Draft, check in code, review, and revise at most `max_revisions` times; None if nothing passed."""
    revision: dict[str, Any] | None = None
    for attempt in range(1 + context.services.rules.pipeline.max_revisions):
        try:
            output = await generate(revision)
        except UnexpectedModelBehavior:
            # No valid output even after PydanticAI's retries (no model key, say): the facts-only report.
            return None
        shown = output.model_dump(mode="json") if isinstance(output, BaseModel) else output
        fresh = await gather_facts(context.services.db, context.learner, context.now)
        code_issues = check(output, fresh)
        review = await _review(context, author, shown, given)
        decision = decide_approval(review, code_issues)
        await records.record_review(
            context.services.db.app,
            context.run_id,
            context.learner.id,
            author,
            attempt,
            shown,
            review,
            code_issues,
            decision,
            context.now,
        )
        if decision.is_approved:
            return output
        issues = [*(review.issues if review else []), *code_issues]
        revision = {
            "previous": shown,
            "issues": [issue.model_dump() for issue in issues],
            "feedback": review.feedback if review else "",
        }
    return None


async def _plan(context: RunScope, facts: WeekFacts) -> KeikoPlan | None:
    services = context.services
    keiko = services.crew.keiko
    deps = KeikoRun(
        signer=services.signer,
        learner=context.learner,
        records=services.db.app,
        purpose="replan" if context.via_shiori else "weekly",
        via_shiori=context.via_shiori,
    )

    async def generate(revision: dict[str, Any] | None) -> KeikoPlan:
        prompt = keiko_prompt(facts, revision)
        return await _call(
            context, lambda limits, usage: keiko.run(prompt, deps=deps, usage_limits=limits, usage=usage)
        )

    def check(plan: KeikoPlan, fresh: WeekFacts) -> list[Issue]:
        return check_plan(plan, facts, fresh, services.rules, context.retired)

    plan = await _reviewed(context, "keiko", generate, check, {"facts": facts.model_dump(mode="json")})
    if plan is not None:
        for proposal in plan.note_proposals:
            await propose_note(
                services.db, context.learner.id, proposal, proposed_by="keiko", rules=services.rules, now=context.now
            )
    return plan


async def _report(context: RunScope, facts: WeekFacts, plan: KeikoPlan) -> str | None:
    nikki, rules = context.services.crew.nikki, context.services.rules

    async def generate(revision: dict[str, Any] | None) -> str:
        prompt = nikki_prompt(facts, plan, revision)
        return await _call(context, lambda limits, usage: nikki.run(prompt, usage_limits=limits, usage=usage))

    def check(report: str, fresh: WeekFacts) -> list[Issue]:
        return check_report(report, facts, fresh, rules, context.retired)

    given = {"facts": facts.model_dump(mode="json"), "plan": plan.model_dump(mode="json")}
    return await _reviewed(context, "nikki", generate, check, given)


async def run_weekly(services: PipelineServices, learner: Learner, now: datetime) -> RunOutcome:
    week_start, _ = week_of(now, learner.timezone)
    if not await has_current_consent(services.db.app, learner.id):
        await records.record_skip(services.db.app, learner.id, week_start, CONSENT_OUTDATED, now)
        return RunOutcome(run_id=None, status="skipped", reason=CONSENT_OUTDATED)
    lease = timedelta(minutes=services.rules.pipeline.run_lease_minutes)
    claimed = await records.claim_weekly_run(services.db.app, learner.id, week_start, now, lease)
    if claimed.claim == "done":
        return RunOutcome(run_id=claimed.run_id, status="skipped")
    if claimed.claim == "busy":
        return RunOutcome(run_id=claimed.run_id, status="busy")
    await records.clear_skip(services.db.app, learner.id, week_start)
    retired = await retired_note_ids(services.db, learner.id)
    context = RunScope(services=services, learner=learner, run_id=claimed.run_id, now=now, retired=retired)
    facts = await gather_facts(services.db, learner, now)
    await records.save_facts(services.db.app, claimed.run_id, facts)
    report: str | None = None
    try:
        plan = await _plan(context, facts)
        report = await _report(context, facts, plan) if plan is not None else None
    except BudgetSpentError:
        report = None
    body = report if report is not None else facts_only_report(facts)
    await records.publish_report(services.db.app, claimed.run_id, learner.id, week_start, body, report is None, now)
    return RunOutcome(run_id=claimed.run_id, status="published" if report is not None else "fallback", report=body)


async def due_learners(db: Databases, rules: Rules, now: datetime) -> list[Learner]:
    """Learners whose Sunday 18:00 (the rule file's day and hour) has come in their own timezone, not yet run."""
    async with db.app.connect() as connection:
        public_ids = list(
            await connection.scalars(
                text(DUE),
                {
                    "now": now,
                    "isodow": rules.pipeline.due_weekday + ISO_WEEKDAY_OFFSET,
                    "hour": rules.pipeline.due_hour,
                },
            )
        )
    return [await engine.get_learner(db, str(public_id)) for public_id in public_ids]


async def run_replans(services: PipelineServices, now: datetime) -> list[RunOutcome]:
    """Each queued request_replan (SM4): a Keiko run under a chain delegated from Shiori; no report."""
    async with services.db.app.connect() as connection:
        queued = (await connection.execute(text(QUEUED_REPLANS))).all()
    outcomes: list[RunOutcome] = []
    for request_id, public_id in queued:
        learner = await engine.get_learner(services.db, str(public_id))
        if not await has_current_consent(services.db.app, learner.id):
            continue  # stays queued: it runs once they accept the current notice
        week_start, _ = week_of(now, learner.timezone)
        run_id = await records.start_replan_run(services.db.app, learner.id, week_start, int(request_id), now)
        retired = await retired_note_ids(services.db, learner.id)
        context = RunScope(services=services, learner=learner, run_id=run_id, now=now, via_shiori=True, retired=retired)
        facts = await gather_facts(services.db, learner, now)
        await records.save_facts(services.db.app, run_id, facts)
        try:
            plan = await _plan(context, facts)
        except BudgetSpentError:
            plan = None
        status: RunStatus = "replanned" if plan is not None else "fallback"
        await records.finish_run(services.db.app, run_id, status, now)
        async with services.db.app.begin() as connection:
            await connection.execute(
                text("UPDATE learning.replan_requests SET handled_at = :now WHERE id = :id"),
                {"now": now, "id": request_id},
            )
        outcomes.append(RunOutcome(run_id=run_id, status=status))
    return outcomes


async def run_due(services: PipelineServices, ops: AsyncEngine, now: datetime) -> list[RunOutcome]:
    """The hourly job: every due learner, then the queued replans; recorded for the "missed run" alert."""
    outcomes: list[RunOutcome] = []
    failures: list[str] = []
    async with recorded_run(ops, JOB_NAME):
        for learner in await due_learners(services.db, services.rules, now):
            try:
                outcomes.append(await run_weekly(services, learner, now))
            except Exception as error:
                failures.append(f"learner {learner.id}: {type(error).__name__}")
        outcomes += await run_replans(services, now)
        if failures:
            raise RuntimeError(f"{len(failures)} weekly runs failed: " + "; ".join(failures))
    return outcomes
