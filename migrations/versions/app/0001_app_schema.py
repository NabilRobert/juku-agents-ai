"""The app schema: invite codes, consent, chat text, model costs, ratings (slice 5).

- `invite_codes` holds only a lookup prefix and an Argon2 hash of each
  code's secret (ADR-013): a stolen table doesn't log anyone in.
- `consents` keeps the version of the notice each learner accepted, and
  when; 18+ and the service terms are required by the table itself.
- `chat_messages` is text, apart from the metrics, with an expiry date
  (scale path: deleting text is cheap, and metrics stay small).
- `model_calls` is the budget guard's record of every model call's tokens
  and cost, by pool (B1, B2). Its learner ID is set to NULL when the
  learner deletes their data, so the totals still add up.
- `distress_events` and `web_vitals` hold no learner and no content: an
  alert counter (AG6) and the real-user timings (FE8).

Deleting a learner cascades to everything here that's theirs.

Revision ID: 0001_app
Revises:
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_app"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("app",)
depends_on: str | Sequence[str] | None = "0003_data"

RATING_REASONS = ("salah", "tidak_jelas", "tidak_relevan", "terlalu_panjang", "lainnya")


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS app")
    op.execute("""
        CREATE TABLE IF NOT EXISTS app.invite_codes (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            lookup text NOT NULL UNIQUE,
            secret_hash text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            learner_id bigint UNIQUE REFERENCES learning.learners (id) ON DELETE CASCADE,
            used_at timestamptz
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS app.consents (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            version text NOT NULL,
            accepted_at timestamptz NOT NULL DEFAULT now(),
            is_adult boolean NOT NULL CHECK (is_adult),
            accepts_service boolean NOT NULL CHECK (accepts_service),
            accepts_aggregates boolean NOT NULL,
            accepts_group_digest boolean NOT NULL DEFAULT false
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS consents_latest ON app.consents (learner_id, accepted_at DESC)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS app.chat_messages (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            role text NOT NULL CHECK (role IN ('learner', 'shiori')),
            body text NOT NULL,
            is_verified boolean,
            created_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS chat_messages_learner ON app.chat_messages (learner_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS chat_messages_expiry ON app.chat_messages (expires_at)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS app.model_calls (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            called_at timestamptz NOT NULL DEFAULT now(),
            pool text NOT NULL CHECK (pool IN ('chat', 'reports')),
            learner_id bigint,
            requests integer NOT NULL CHECK (requests >= 0),
            input_tokens integer NOT NULL CHECK (input_tokens >= 0),
            cached_input_tokens integer NOT NULL DEFAULT 0 CHECK (cached_input_tokens >= 0),
            output_tokens integer NOT NULL CHECK (output_tokens >= 0),
            cost_usd numeric(12, 6) NOT NULL CHECK (cost_usd >= 0)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS model_calls_pool_day ON app.model_calls (pool, called_at)")
    op.execute("CREATE INDEX IF NOT EXISTS model_calls_learner_day ON app.model_calls (learner_id, called_at)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS app.budget_pools (
            pool text PRIMARY KEY CHECK (pool IN ('chat', 'reports')),
            size_usd numeric(12, 6) NOT NULL CHECK (size_usd > 0)
        )
    """)
    op.execute(
        "COMMENT ON TABLE app.budget_pools IS "
        "'The pools'' sizes, copied from guardrails.yaml at every app start-up, for Grafana''s budget alerts.'"
    )
    reasons = ", ".join(f"'{reason}'" for reason in RATING_REASONS)
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS app.ratings (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            target_kind text NOT NULL CHECK (target_kind IN ('chat', 'report')),
            target_id bigint NOT NULL,
            is_helpful boolean NOT NULL,
            reason text CHECK (reason IN ({reasons})),
            may_quote boolean NOT NULL DEFAULT false,
            rated_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS app.distress_events (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            occurred_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "COMMENT ON TABLE app.distress_events IS "
        "'One row per message the moderation check flagged (AG6). No learner and no content: it only drives an alert.'"
    )
    op.execute("""
        CREATE TABLE IF NOT EXISTS app.web_vitals (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            recorded_at timestamptz NOT NULL DEFAULT now(),
            page text NOT NULL,
            metric text NOT NULL CHECK (metric IN ('LCP', 'INP', 'CLS')),
            value double precision NOT NULL CHECK (value >= 0)
        )
    """)

    # Grafana's views: totals only, no learner (M4).
    op.execute("""
        CREATE OR REPLACE VIEW monitoring.budget_by_pool AS
        SELECT p.pool, p.size_usd,
               coalesce(sum(c.cost_usd), 0) AS spent_usd,
               coalesce(sum(c.cost_usd), 0) / p.size_usd AS spent_share,
               coalesce(sum(c.cost_usd) FILTER (WHERE c.called_at >= date_trunc('day', now())), 0) AS spent_today_usd
        FROM app.budget_pools p LEFT JOIN app.model_calls c ON c.pool = p.pool
        GROUP BY p.pool, p.size_usd
    """)
    op.execute("""
        CREATE OR REPLACE VIEW monitoring.distress_events AS
        SELECT occurred_at FROM app.distress_events
    """)
    op.execute("""
        CREATE OR REPLACE VIEW monitoring.web_vitals_daily AS
        SELECT date_trunc('day', recorded_at) AS day, page, metric,
               percentile_cont(0.75) WITHIN GROUP (ORDER BY value) AS p75, count(*) AS samples
        FROM app.web_vitals GROUP BY 1, 2, 3
    """)
    op.execute("GRANT USAGE ON SCHEMA app TO juku_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO juku_app")
    op.execute("GRANT UPDATE (learner_id) ON monitoring.tool_calls TO juku_app")
    op.execute("GRANT SELECT (learner_id) ON monitoring.tool_calls TO juku_app")
    op.execute(
        "GRANT SELECT ON monitoring.budget_by_pool, monitoring.distress_events, monitoring.web_vitals_daily "
        "TO grafana_reader"
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS monitoring.budget_by_pool, monitoring.distress_events, monitoring.web_vitals_daily")
    op.execute("DROP SCHEMA IF EXISTS app CASCADE")
