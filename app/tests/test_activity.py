"""The activity calendar (activity.py): each day's own actions, in the learner's timezone, and nobody else's."""

from datetime import UTC, date, datetime, timedelta

from juku_app.activity import active_days
from juku_app.invites import issue_codes
from juku_data.engine import Databases, create_learner, mark_known
from sqlalchemy import text
from web_helpers import client_for, csrf_header, deps, page_props, sign_up


async def a_question(db: Databases, learner_id: int, at: datetime) -> None:
    async with db.app.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO app.chat_messages (learner_id, role, body, is_verified, created_at, expires_at) "
                "VALUES (:learner, 'learner', 'Apa arti 本?', NULL, :at, :expires)"
            ),
            {"learner": learner_id, "at": at, "expires": at + timedelta(days=60)},
        )


async def some_word(db: Databases) -> str:
    async with db.dictionary.connect() as connection:
        found = await connection.scalar(text("SELECT id FROM ojlpt.vocab WHERE level = 5 ORDER BY id LIMIT 1"))
    assert isinstance(found, str)
    return found


async def test_a_day_counts_words_marked_and_questions_asked(engine_databases: Databases) -> None:
    learner = await create_learner(engine_databases, nickname="aktif", target_level=5, timezone="Asia/Jakarta")
    now = datetime(2026, 11, 5, 3, 0, tzinfo=UTC)  # 10:00 in Jakarta
    await mark_known(engine_databases, learner.id, await some_word(engine_databases), now)
    await a_question(engine_databases, learner.id, now)
    [day] = await active_days(engine_databases, learner, date(2026, 11, 5))
    assert (day.day, day.count, day.words_marked, day.questions) == (date(2026, 11, 5), 2, 1, 1)


async def test_a_late_question_counts_on_the_learners_own_day(engine_databases: Databases) -> None:
    learner = await create_learner(engine_databases, nickname="malam", target_level=5, timezone="Asia/Jakarta")
    await a_question(engine_databases, learner.id, datetime(2026, 11, 4, 20, 0, tzinfo=UTC))  # 03:00 next day there
    [day] = await active_days(engine_databases, learner, date(2026, 11, 5))
    assert day.day == date(2026, 11, 5)


async def test_a_day_older_than_half_a_year_is_left_out(engine_databases: Databases) -> None:
    learner = await create_learner(engine_databases, nickname="lama", target_level=5, timezone="Asia/Jakarta")
    await a_question(engine_databases, learner.id, datetime(2026, 1, 1, 3, 0, tzinfo=UTC))
    assert await active_days(engine_databases, learner, date(2026, 11, 5)) == []


async def test_the_home_page_shows_only_the_learners_own_activity(engine_databases: Databases) -> None:
    first, second = await issue_codes(engine_databases.app, 2)
    async with client_for(deps(engine_databases)) as busy, client_for(deps(engine_databases)) as idle:
        await sign_up(busy, first, nickname="Rajin")
        await sign_up(idle, second, nickname="Santai")
        home = await busy.get("/kuis")
        quiz = page_props(home)["quiz"]["items"][0]
        answer = {"word_id": quiz["word_id"], "kind": quiz["kind"], "chosen": quiz["options"][0]}
        await busy.post("/kuis/jawab", json=answer, headers=csrf_header(home))
        busy_days = page_props(await busy.get("/beranda"))["activity"]["days"]
        idle_days = page_props(await idle.get("/beranda"))["activity"]["days"]
    assert [day["quiz_answers"] for day in busy_days] == [1]
    assert idle_days == []
