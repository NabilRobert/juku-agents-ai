"""Reports and chat only for learners who accepted the current consent notice (Phase 2, privacy).

A new notice version means everyone who accepted an older one is asked
again before anything new happens: the weekly run skips them and records
why (no report), and the chat sends them to the consent page. Once they
accept, both come back. An "old-version learner" here is one whose stored
consent names an earlier version: what every learner becomes the moment
CONSENT_VERSION moves on.
"""

import uuid
from datetime import timedelta

import pytest
from juku_app.consent import CONSENT_VERSION, ConsentAnswers, record_consent
from juku_app.invites import issue_codes
from juku_app.pipeline.run import due_learners, run_due, run_weekly
from juku_common.rules import Rules
from juku_data.engine import Databases
from juku_data.engine.models import Learner
from juku_testkit.memory_fixtures import load_memory_fixture
from pipeline_helpers import crew_of, services_for, sunday_evening
from sqlalchemy import text
from web_helpers import client_for, csrf_header, csrf_of, deps, sign_up

EDD = pytest.mark.xfail(strict=True, reason="EDD: the consent gate lands in the next commit")

OLDER_VERSION = "2026-01-01"
ACCEPTED = ConsentAnswers(is_adult=True, accepts_service=True, accepts_aggregates=False, accepts_group_digest=False)


async def learner_on_an_older_notice(db: Databases, rules: Rules) -> Learner:
    loaded = await load_memory_fixture(db, rules, "joko", suffix=f"-{uuid.uuid4().hex[:6]}", source="pipeline")
    await record_consent(db.app, loaded.learner.id, ACCEPTED, version=OLDER_VERSION)
    return loaded.learner


async def reports_of(db: Databases, learner: Learner) -> int:
    async with db.app.connect() as connection:
        return int(
            await connection.scalar(text("SELECT count(*) FROM app.reports WHERE learner_id = :l"), {"l": learner.id})
        )


@EDD
async def test_the_weekly_run_skips_a_learner_on_an_older_notice_and_says_why(
    engine_databases: Databases, rules: Rules
) -> None:
    learner = await learner_on_an_older_notice(engine_databases, rules)
    outcome = await run_weekly(
        services_for(engine_databases, rules, crew_of()), learner, sunday_evening(learner.timezone)
    )
    assert (outcome.status, outcome.reason) == ("skipped", "consent_outdated")
    assert await reports_of(engine_databases, learner) == 0
    async with engine_databases.app.connect() as connection:
        reason = await connection.scalar(
            text("SELECT reason FROM app.pipeline_skips WHERE learner_id = :l"), {"l": learner.id}
        )
    assert reason == "consent_outdated"


@EDD
async def test_once_they_accept_the_current_notice_the_next_run_gives_them_their_report(
    engine_databases: Databases, rules: Rules
) -> None:
    learner = await learner_on_an_older_notice(engine_databases, rules)
    services = services_for(engine_databases, rules, crew_of())
    now = sunday_evening(learner.timezone)
    assert (await run_weekly(services, learner, now)).status == "skipped"
    await record_consent(engine_databases.app, learner.id, ACCEPTED)
    later = await run_weekly(services, learner, now + timedelta(hours=1))
    assert later.status == "published"
    assert await reports_of(engine_databases, learner) == 1


@EDD
async def test_a_learner_waiting_to_re_consent_is_not_an_overdue_run(engine_databases: Databases, rules: Rules) -> None:
    learner = await learner_on_an_older_notice(engine_databases, rules)
    late = sunday_evening(learner.timezone) + timedelta(minutes=rules.pipeline.overdue_after_minutes + 1)

    async def overdue() -> int:
        async with engine_databases.app.connect() as connection:
            return int(
                await connection.scalar(text("SELECT overdue FROM monitoring.pipeline_overdue_at(:at)"), {"at": late})
            )

    before = await overdue()
    await run_weekly(services_for(engine_databases, rules, crew_of()), learner, sunday_evening(learner.timezone))
    assert await reports_of(engine_databases, learner) == 0
    assert await overdue() == before - 1, "skipped for consent, and recorded: not a missing run"


@EDD
async def test_the_hourly_job_records_the_skip_and_still_succeeds(engine_databases: Databases, rules: Rules) -> None:
    learner = await learner_on_an_older_notice(engine_databases, rules)
    now = sunday_evening(learner.timezone)
    assert learner.id in {due.id for due in await due_learners(engine_databases, rules, now)}
    outcomes = await run_due(services_for(engine_databases, rules, crew_of()), engine_databases.app, now)
    assert any(outcome.reason == "consent_outdated" for outcome in outcomes)
    assert await reports_of(engine_databases, learner) == 0


async def test_chat_sends_an_old_version_learner_to_the_consent_page_until_they_accept(
    engine_databases: Databases, juku_mcp_url: str
) -> None:
    code = (await issue_codes(engine_databases.app, 1))[0]
    async with client_for(deps(engine_databases, juku_mcp_url)) as client:
        await sign_up(client, code, nickname="Versi")
        async with engine_databases.app.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE app.consents SET version = :old WHERE learner_id = "
                    "(SELECT id FROM learning.learners WHERE nickname = 'Versi')"
                ),
                {"old": OLDER_VERSION},
            )
        page = await client.get("/chat")
        assert (page.status_code, page.headers["location"]) == (303, "/persetujuan")
        notice = await client.get("/persetujuan")
        sent = await client.post("/chat/kirim", json={"question": "apa itu 食べる?"}, headers=csrf_header(notice))
        assert (sent.status_code, sent.headers["location"]) == (303, "/persetujuan")

        answers = {"is_adult": "on", "accepts_service": "on", "csrf": csrf_of(notice)}
        accepted = await client.post("/persetujuan", data=answers)
        assert accepted.status_code == 303
        page = await client.get("/chat")
        assert page.status_code == 200
        answer = await client.post("/chat/kirim", json={"question": "apa itu 食べる?"}, headers=csrf_header(page))
    assert answer.headers["content-type"].startswith("text/event-stream")
    async with engine_databases.app.connect() as connection:
        versions = list(
            await connection.scalars(
                text(
                    "SELECT version FROM app.consents WHERE learner_id = "
                    "(SELECT id FROM learning.learners WHERE nickname = 'Versi') ORDER BY id"
                )
            )
        )
    assert versions == [OLDER_VERSION, CONSENT_VERSION]
