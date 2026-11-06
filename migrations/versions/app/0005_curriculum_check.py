"""Keiko's weekly curriculum check (2026-11-05): her approved notes, and the checks learners' visits queue.

Arthur chose a weekly check by Keiko of where he is on the curriculum: a short note on the plan page,
citing his numbers. The weekly run already reaches every learner on Sunday (ops/crontab); a learner who
opens Juku with no run this week and none in the last 7 days queues one sooner (`check_requests`), so the
note appears on a laptop with no Sunday cron. The hourly job takes the queue and clears each row it runs.

`curriculum_notes` keeps one note per learner and week, as long as the report it came with.

Revision ID: 0005_app
Revises: 0004_app
Create Date: 2026-11-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_app"
down_revision: str | Sequence[str] | None = "0004_app"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS app.curriculum_notes (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            run_id bigint NOT NULL REFERENCES app.pipeline_runs (id) ON DELETE CASCADE,
            week_start date NOT NULL,
            body text NOT NULL,
            created_at timestamptz NOT NULL,
            expires_at timestamptz NOT NULL,
            UNIQUE (learner_id, week_start)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS app.check_requests (
            learner_id bigint PRIMARY KEY REFERENCES learning.learners (id) ON DELETE CASCADE,
            requested_at timestamptz NOT NULL
        )
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.curriculum_notes, app.check_requests TO juku_app")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.check_requests")
    op.execute("DROP TABLE IF EXISTS app.curriculum_notes")
