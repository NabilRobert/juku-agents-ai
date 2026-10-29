"""The learning schema: learners, their events, and the summaries derived from them.

The scale path's data design, from day one:
- `learning_events` is the narrow, append-only source of truth (about 40
  bytes a row, no text), partitioned by month;
- `learner_state`, `learner_kanji`, `learner_coverage`,
  `learner_candidate` and `learner_daily_activity` are summaries kept up
  to date as each event arrives, so the $0 pages and the agents' tools
  never scan history (fitness function FF2), and checked against a full
  recompute (FF3);
- `bigint` keys inside, a random `public_id` outside; a `cohort_id` and a
  timezone on every learner; `timestamptz` everywhere.

The `dictionary_*` tables mirror the few dictionary columns the summaries
need (levels, each word's kanji, kanji leverage), copied from the `dict`
database by `juku-data sync-index`, so learner state can be computed in
one database (ADR-026).

Juku's MCP server's role can read the summaries and the mirror, and a
learner's level and timezone, but not the events and not the nickname:
FF2 holds in the grants as well as in the tests.

Revision ID: 0001_data
Revises:
Create Date: 2026-10-28
"""

import itertools
from collections.abc import Sequence
from datetime import date

from alembic import op

revision: str = "0001_data"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("data",)
depends_on: str | Sequence[str] | None = "0001_monitoring"

FIRST_MONTH = date(2026, 10, 1)
MONTHS_CREATED = 15  # through 2027-12; `juku-ops ensure-partitions` adds the rest
# EV2's privacy floor: an aggregate over fewer learners than this isn't shown.
MIN_LEARNERS_PER_CELL = 5
SUMMARY_TABLES = (
    "learner_state",
    "learner_kanji",
    "learner_coverage",
    "learner_candidate",
    "learner_daily_activity",
)
MIRROR_TABLES = (
    "dictionary_words",
    "dictionary_word_kanji",
    "dictionary_kanji",
    "kanji_leverage",
    "dictionary_version",
)


def month_starts(first: date, count: int) -> list[date]:
    starts: list[date] = []
    year, month = first.year, first.month
    for _ in range(count + 1):
        starts.append(date(year, month, 1))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return starts


def create_learners() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS learning.learners (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            public_id text NOT NULL UNIQUE,
            cohort_id bigint NOT NULL DEFAULT 1,
            nickname text NOT NULL,
            target_level smallint NOT NULL CHECK (target_level BETWEEN 2 AND 5),
            exam_date date,
            timezone text NOT NULL DEFAULT 'Asia/Jakarta',
            created_at timestamptz NOT NULL DEFAULT now(),
            last_active_at timestamptz
        )
    """)
    op.execute(
        "COMMENT ON COLUMN learning.learners.target_level IS "
        "'OpenJLPT''s numbering: 5 = N5 (easiest) ... 2 = N2. A larger number is an easier level.'"
    )
    op.execute(
        "COMMENT ON COLUMN learning.learners.public_id IS "
        "'Random and URL-safe; the only learner ID that leaves the database (URLs, tokens).'"
    )


def create_events() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS learning.event_types (
            id smallint PRIMARY KEY,
            name text NOT NULL UNIQUE
        )
    """)
    op.execute("""
        INSERT INTO learning.event_types (id, name) VALUES
            (1, 'marked_known'), (2, 'unmarked_known'), (3, 'quiz_meaning'), (4, 'quiz_reading'),
            (5, 'sentence_read')
        ON CONFLICT (id) DO NOTHING
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS learning.learning_events (
            id bigint GENERATED ALWAYS AS IDENTITY,
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            cohort_id bigint NOT NULL,
            event_type smallint NOT NULL REFERENCES learning.event_types (id),
            item_id text NOT NULL,
            result smallint CHECK (result IN (0, 1)),
            occurred_at timestamptz NOT NULL,
            PRIMARY KEY (id, occurred_at)
        ) PARTITION BY RANGE (occurred_at)
    """)
    op.execute(
        "COMMENT ON TABLE learning.learning_events IS "
        "'Append-only. The source of truth for learner activity; everything in learner_* is derived from it.'"
    )
    starts = month_starts(FIRST_MONTH, MONTHS_CREATED)
    for start, end in itertools.pairwise(starts):
        op.execute(
            f"CREATE TABLE IF NOT EXISTS learning.learning_events_{start:%Y_%m} "
            f"PARTITION OF learning.learning_events FOR VALUES FROM ('{start}') TO ('{end}')"
        )
    op.execute(
        "CREATE INDEX IF NOT EXISTS learning_events_learner_time ON learning.learning_events (learner_id, occurred_at)"
    )


def create_summaries() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS learning.learner_state (
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            item_id text NOT NULL,
            is_known boolean NOT NULL DEFAULT false,
            correct_days smallint NOT NULL DEFAULT 0,
            last_correct_day date,
            correct_count integer NOT NULL DEFAULT 0,
            wrong_count integer NOT NULL DEFAULT 0,
            box smallint CHECK (box BETWEEN 1 AND 5),
            due_at timestamptz,
            last_seen_at timestamptz NOT NULL,
            PRIMARY KEY (learner_id, item_id)
        )
    """)
    op.execute(
        "COMMENT ON COLUMN learning.learner_state.correct_days IS "
        "'Separate local days with a correct quiz answer since the word was last unmarked (LE1: two make it known).'"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS learner_state_mistakes ON learning.learner_state (learner_id, due_at) "
        "WHERE box IS NOT NULL"
    )
    op.execute("""
        CREATE TABLE IF NOT EXISTS learning.learner_kanji (
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            kanji text NOT NULL,
            known_words integer NOT NULL CHECK (known_words >= 0),
            PRIMARY KEY (learner_id, kanji)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS learning.learner_coverage (
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            level smallint NOT NULL CHECK (level BETWEEN 1 AND 5),
            words_known integer NOT NULL DEFAULT 0 CHECK (words_known >= 0),
            kanji_known integer NOT NULL DEFAULT 0 CHECK (kanji_known >= 0),
            PRIMARY KEY (learner_id, level)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS learning.learner_candidate (
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            word_id text NOT NULL,
            level smallint NOT NULL,
            new_kanji text,
            leverage integer NOT NULL,
            commonness smallint NOT NULL,
            PRIMARY KEY (learner_id, word_id)
        )
    """)
    op.execute(
        "COMMENT ON TABLE learning.learner_candidate IS "
        "'Words the recommender may suggest: at the learner''s level or easier, not known, with at most one "
        "unknown kanji (new_kanji). Kept as words become known (ADR-010; spike 2 timed the per-call version).'"
    )
    op.execute("""
        CREATE TABLE IF NOT EXISTS learning.learner_daily_activity (
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            day date NOT NULL,
            quiz_answers integer NOT NULL DEFAULT 0,
            quiz_correct integer NOT NULL DEFAULT 0,
            words_marked integer NOT NULL DEFAULT 0,
            sentences_read integer NOT NULL DEFAULT 0,
            PRIMARY KEY (learner_id, day)
        )
    """)
    op.execute("COMMENT ON COLUMN learning.learner_daily_activity.day IS 'The learner''s local date.'")


def create_dictionary_mirror() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS learning.dictionary_words (
            word_id text PRIMARY KEY,
            level smallint NOT NULL CHECK (level BETWEEN 1 AND 5),
            commonness smallint NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS learning.dictionary_word_kanji (
            word_id text NOT NULL,
            kanji text NOT NULL,
            PRIMARY KEY (word_id, kanji)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS dictionary_word_kanji_kanji ON learning.dictionary_word_kanji (kanji, word_id)"
    )
    op.execute("""
        CREATE TABLE IF NOT EXISTS learning.dictionary_kanji (
            kanji text PRIMARY KEY,
            level smallint NOT NULL CHECK (level BETWEEN 1 AND 5)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS learning.kanji_leverage (
            kanji text NOT NULL,
            level smallint NOT NULL,
            words integer NOT NULL,
            PRIMARY KEY (kanji, level)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS learning.dictionary_version (
            singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
            openjlpt_commit text NOT NULL,
            sqlite_sha256 text NOT NULL,
            synced_at timestamptz NOT NULL DEFAULT now()
        )
    """)


def create_activity_view() -> None:
    # Grafana's "activity per day" (M4): totals over all learners, and only
    # for days with enough of them that no one learner can be picked out.
    op.execute(f"""
        CREATE OR REPLACE VIEW monitoring.activity_by_day AS
        SELECT day,
               count(DISTINCT learner_id) AS active_learners,
               sum(quiz_answers) AS quiz_answers,
               sum(quiz_correct) AS quiz_correct,
               sum(words_marked) AS words_marked,
               sum(sentences_read) AS sentences_read
        FROM learning.learner_daily_activity
        GROUP BY day
        HAVING count(DISTINCT learner_id) >= {MIN_LEARNERS_PER_CELL}
    """)


def grant() -> None:
    op.execute("GRANT USAGE ON SCHEMA learning TO juku_app, juku_mcp")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA learning TO juku_app")
    # The MCP server: the summaries and the mirror; from learners, only what a tool needs.
    op.execute(f"GRANT SELECT ON {', '.join(f'learning.{name}' for name in SUMMARY_TABLES)} TO juku_mcp")
    op.execute(f"GRANT SELECT ON {', '.join(f'learning.{name}' for name in MIRROR_TABLES)} TO juku_mcp")
    op.execute(
        "GRANT SELECT (id, public_id, cohort_id, target_level, exam_date, timezone) ON learning.learners TO juku_mcp"
    )
    op.execute("GRANT SELECT ON monitoring.activity_by_day TO grafana_reader")


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS learning")
    create_learners()
    create_events()
    create_summaries()
    create_dictionary_mirror()
    create_activity_view()
    grant()


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS monitoring.activity_by_day")
    op.execute("DROP SCHEMA IF EXISTS learning CASCADE")
