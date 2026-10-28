"""The weekly pipeline's records (Phase 2 AG1 to AG4; ADR-014): runs, outputs, reviews, reports, feedback drafts.

- `pipeline_runs`: one weekly run per (learner, week), enforced by a unique
  index (FF7), with a lease so a killed run can be taken over. Replans are
  runs too, any number of them.
- `agent_outputs` and `critic_reviews`: each draft and each review, with
  code's issues beside Tadashi's, for the Run Inspector (Arthur only).
- `reports`: what the learner reads; one per (learner, week), so a rerun
  never duplicates it. Text, with an expiry date, like chat.
- `prompt_feedback`: the feedback job's drafts (AG4), built from issue
  reasons and counts, never quotes, so they hold no learner's words.
- `monitoring.pipeline_overdue_at`: the dead-man's switch's query, for
  Grafana; it counts learners whose run is overdue, and nothing else.

Revision ID: 0002_app
Revises: 0001_app
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_app"
down_revision: str | Sequence[str] | None = "0001_app"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = "0004_data"

# guardrails.yaml's pipeline section, as the overdue function's defaults; a test keeps them equal.
DUE_WEEKDAY = 6
DUE_HOUR = 18
OVERDUE_AFTER_MINUTES = 60


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS app.pipeline_runs (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            week_start date NOT NULL,
            kind text NOT NULL CHECK (kind IN ('weekly', 'replan')),
            status text NOT NULL CHECK (status IN ('running', 'published', 'fallback', 'replanned')),
            started_at timestamptz NOT NULL,
            claimed_at timestamptz,
            attempts smallint NOT NULL DEFAULT 1,
            finished_at timestamptz,
            facts jsonb,
            replan_request_id bigint REFERENCES learning.replan_requests (id) ON DELETE SET NULL
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS pipeline_runs_one_weekly ON app.pipeline_runs (learner_id, week_start) "
        "WHERE kind = 'weekly'"
    )
    op.execute("""
        CREATE TABLE IF NOT EXISTS app.agent_outputs (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            run_id bigint NOT NULL REFERENCES app.pipeline_runs (id) ON DELETE CASCADE,
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            agent text NOT NULL CHECK (agent IN ('keiko', 'nikki')),
            attempt smallint NOT NULL,
            content jsonb NOT NULL,
            created_at timestamptz NOT NULL,
            expires_at timestamptz NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS agent_outputs_run ON app.agent_outputs (run_id)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS app.critic_reviews (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            run_id bigint NOT NULL REFERENCES app.pipeline_runs (id) ON DELETE CASCADE,
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            output_id bigint NOT NULL REFERENCES app.agent_outputs (id) ON DELETE CASCADE,
            agent text NOT NULL CHECK (agent IN ('keiko', 'nikki')),
            grade text,
            issues jsonb NOT NULL,
            code_issues jsonb NOT NULL,
            is_approved boolean NOT NULL,
            reason text NOT NULL,
            created_at timestamptz NOT NULL,
            expires_at timestamptz NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS critic_reviews_run ON app.critic_reviews (run_id)")
    op.execute("CREATE INDEX IF NOT EXISTS critic_reviews_created ON app.critic_reviews (created_at)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS app.reports (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            run_id bigint NOT NULL REFERENCES app.pipeline_runs (id) ON DELETE CASCADE,
            week_start date NOT NULL,
            body text NOT NULL,
            is_fallback boolean NOT NULL,
            created_at timestamptz NOT NULL,
            expires_at timestamptz NOT NULL,
            UNIQUE (learner_id, week_start)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS app.prompt_feedback (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            week_start date NOT NULL,
            agent text NOT NULL,
            patterns jsonb NOT NULL,
            draft text NOT NULL,
            status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'dismissed')),
            created_at timestamptz NOT NULL
        )
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO juku_app")
    op.execute(f"""
        CREATE OR REPLACE FUNCTION monitoring.pipeline_overdue_at(
            at timestamptz,
            due_weekday integer DEFAULT {DUE_WEEKDAY},
            due_hour integer DEFAULT {DUE_HOUR},
            overdue_minutes integer DEFAULT {OVERDUE_AFTER_MINUTES}
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
              )
        $$
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION monitoring.pipeline_overdue_at(timestamptz, integer, integer, integer) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION monitoring.pipeline_overdue_at(timestamptz, integer, integer, integer) "
        "TO grafana_reader"
    )
    # The hourly job (run-weekly) and the weekly feedback draft, watched by the "missed run" alert.
    op.execute(
        "INSERT INTO monitoring.expected_jobs (job, every, grace) VALUES "
        "('run-weekly', '1 hour', '30 minutes'), ('draft-feedback', '7 days', '1 day') ON CONFLICT (job) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM monitoring.expected_jobs WHERE job IN ('run-weekly', 'draft-feedback')")
    op.execute("DROP FUNCTION IF EXISTS monitoring.pipeline_overdue_at(timestamptz, integer, integer, integer)")
    for table in ("prompt_feedback", "reports", "critic_reviews", "agent_outputs", "pipeline_runs"):
        op.execute(f"DROP TABLE IF EXISTS app.{table}")
