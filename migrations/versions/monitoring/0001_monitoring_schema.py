"""The monitoring schema: per-call records, audit imports, heartbeats and job runs.

ADR-009 and Phase 2 M1-M5. Nothing here holds content: no tool arguments,
SQL, results, questions or answers (fitness function FF9). Grafana reads
this schema through the read-only `grafana_reader` role.

`tool_calls` is partitioned by month (scale path), so retention is dropping
a partition. The first months are created here; `juku-ops ensure-partitions`
(cron) keeps a few months ahead.

Revision ID: 0001_monitoring
Revises:
Create Date: 2026-10-28
"""

import itertools
from collections.abc import Sequence
from datetime import date

from alembic import op

revision: str = "0001_monitoring"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("monitoring",)
depends_on: str | Sequence[str] | None = None

FIRST_MONTH = date(2026, 10, 1)
MONTHS_CREATED = 15  # through 2027-12; the cron job adds the rest


def month_starts(first: date, count: int) -> list[date]:
    starts: list[date] = []
    year, month = first.year, first.month
    for _ in range(count + 1):
        starts.append(date(year, month, 1))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return starts


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS monitoring")

    # M1: one row per MCP tool call, written by the app. Who called what, how
    # long it took and how it ended; never the arguments or the result.
    op.execute("""
        CREATE TABLE IF NOT EXISTS monitoring.tool_calls (
            id bigint GENERATED ALWAYS AS IDENTITY,
            called_at timestamptz NOT NULL,
            agent text NOT NULL,
            server text NOT NULL,
            tool text NOT NULL,
            duration_ms integer NOT NULL CHECK (duration_ms >= 0),
            outcome text NOT NULL CHECK (outcome IN ('ok', 'tool_error', 'refused', 'transport_error')),
            error_category text,
            row_count integer,
            trace_id text,
            actor_chain text[] NOT NULL DEFAULT '{}',
            run_id bigint,
            learner_id bigint,
            PRIMARY KEY (id, called_at)
        ) PARTITION BY RANGE (called_at)
    """)
    op.execute(
        "COMMENT ON COLUMN monitoring.tool_calls.learner_id IS "
        "'Set to NULL when the learner deletes their data, so totals still add up.'"
    )
    starts = month_starts(FIRST_MONTH, MONTHS_CREATED)
    for start, end in itertools.pairwise(starts):
        op.execute(
            f"CREATE TABLE IF NOT EXISTS monitoring.tool_calls_{start:%Y_%m} "
            f"PARTITION OF monitoring.tool_calls FOR VALUES FROM ('{start}') TO ('{end}')"
        )
    op.execute("CREATE INDEX IF NOT EXISTS tool_calls_called_at ON monitoring.tool_calls (called_at)")
    op.execute("CREATE INDEX IF NOT EXISTS tool_calls_learner ON monitoring.tool_calls (learner_id, called_at)")

    # M2 and SM5: lines imported from the hash-chained audit logs (the
    # gateway's and Juku's MCP server's), after the chain verifies. Only
    # allow-listed metadata fields; the tool arguments are never imported.
    op.execute("""
        CREATE TABLE IF NOT EXISTS monitoring.audit_lines (
            source text NOT NULL CHECK (source IN ('gateway', 'juku-mcp')),
            line_number bigint NOT NULL,
            line_sha256 text NOT NULL,
            logged_at timestamptz NOT NULL,
            kind text NOT NULL,
            call_id text,
            caller text,
            route text,
            tool text,
            decision text,
            reason_category text,
            is_error boolean,
            is_suspicious boolean,
            detector_layer text,
            detector_score double precision,
            actor_chain text[],
            imported_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (source, line_number)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS audit_lines_logged_at ON monitoring.audit_lines (logged_at)")

    # One row per import run: whether the chain verified, and where it broke.
    op.execute("""
        CREATE TABLE IF NOT EXISTS monitoring.audit_imports (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            source text NOT NULL,
            file_name text NOT NULL,
            imported_at timestamptz NOT NULL DEFAULT now(),
            lines_total bigint NOT NULL,
            lines_imported bigint NOT NULL,
            is_intact boolean NOT NULL,
            problems text[] NOT NULL DEFAULT '{}'
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS audit_imports_latest ON monitoring.audit_imports (source, imported_at DESC)")

    # The dead-man's switch (M5): each source's latest beat; stale for more
    # than 5 minutes is an alert. Beats aren't job runs, so they're not in
    # expected_jobs (a row a minute would drown the runs that matter).
    op.execute("""
        CREATE TABLE IF NOT EXISTS monitoring.heartbeats (
            source text PRIMARY KEY,
            beat_at timestamptz NOT NULL
        )
    """)

    # ADR-014: every scheduled job records its start and end.
    op.execute("""
        CREATE TABLE IF NOT EXISTS monitoring.job_runs (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            job text NOT NULL,
            started_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz,
            status text NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
            error_category text
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS job_runs_latest ON monitoring.job_runs (job, started_at DESC)")

    # What cron is expected to run, and how late a run may be before the
    # "missed run" alert fires. A test keeps this in step with ops/crontab.
    op.execute("""
        CREATE TABLE IF NOT EXISTS monitoring.expected_jobs (
            job text PRIMARY KEY,
            every interval NOT NULL,
            grace interval NOT NULL
        )
    """)
    op.execute("""
        INSERT INTO monitoring.expected_jobs (job, every, grace) VALUES
            ('import-audit', '5 minutes', '1 hour'),
            ('ensure-partitions', '1 day', '1 hour')
        ON CONFLICT (job) DO NOTHING
    """)

    # Grafana's read-only role sees this schema and nothing else. The roles
    # themselves are made once per cluster by ops/db/roles.sql.
    op.execute("GRANT USAGE ON SCHEMA monitoring TO grafana_reader, juku_app, juku_ops")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA monitoring TO grafana_reader")
    op.execute("GRANT INSERT ON monitoring.tool_calls TO juku_app")
    op.execute("GRANT SELECT, INSERT ON monitoring.audit_lines, monitoring.audit_imports TO juku_ops")
    op.execute("GRANT SELECT, INSERT, UPDATE ON monitoring.heartbeats, monitoring.job_runs TO juku_ops")
    op.execute("GRANT SELECT ON monitoring.expected_jobs TO juku_ops")


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS monitoring CASCADE")
