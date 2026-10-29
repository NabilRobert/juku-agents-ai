"""Weeks the pipeline skipped on purpose, with why: so far, a learner on an older consent notice.

A learner who accepted an earlier version of the consent notice gets no
new report until they accept the current one (Phase 2, privacy). The run
records the skip here, one row per (learner, week), updated if the hourly
job tries again; a run that goes ahead clears it. The dead-man's switch
counts a recorded skip as accounted for, not as a missing run.

Revision ID: 0003_app
Revises: 0002_app
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_app"
down_revision: str | Sequence[str] | None = "0002_app"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DUE_WEEKDAY = 6
DUE_HOUR = 18
OVERDUE_AFTER_MINUTES = 60
OVERDUE = """
CREATE OR REPLACE FUNCTION monitoring.pipeline_overdue_at(
    at timestamptz,
    due_weekday integer DEFAULT {weekday},
    due_hour integer DEFAULT {hour},
    overdue_minutes integer DEFAULT {minutes}
) RETURNS TABLE (overdue bigint)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
    SELECT count(*) FROM learning.learners l
    WHERE (at AT TIME ZONE l.timezone) >= date_trunc('week', at AT TIME ZONE l.timezone)
            + make_interval(days => due_weekday, hours => due_hour, mins => overdue_minutes)
      AND NOT EXISTS (
          SELECT 1 FROM app.pipeline_runs r
          WHERE r.learner_id = l.id AND r.kind = 'weekly'
            AND r.week_start = (date_trunc('week', at AT TIME ZONE l.timezone))::date
            AND r.status IN ('published', 'fallback')
      ){skips}
$$
"""
SKIPS_ACCOUNTED_FOR = """
      AND NOT EXISTS (
          SELECT 1 FROM app.pipeline_skips s
          WHERE s.learner_id = l.id AND s.week_start = (date_trunc('week', at AT TIME ZONE l.timezone))::date
      )"""


def overdue_function(skips: str) -> str:
    return OVERDUE.format(weekday=DUE_WEEKDAY, hour=DUE_HOUR, minutes=OVERDUE_AFTER_MINUTES, skips=skips)


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS app.pipeline_skips (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            week_start date NOT NULL,
            reason text NOT NULL CHECK (reason IN ('consent_outdated')),
            skipped_at timestamptz NOT NULL,
            UNIQUE (learner_id, week_start)
        )
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.pipeline_skips TO juku_app")
    op.execute(overdue_function(SKIPS_ACCOUNTED_FOR))


def downgrade() -> None:
    op.execute(overdue_function(""))
    op.execute("DROP TABLE IF EXISTS app.pipeline_skips")
