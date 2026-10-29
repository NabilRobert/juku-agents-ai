"""The monitoring tables, as SQLAlchemy Core objects for the jobs to write.

The schema itself is made by the Alembic migration
(migrations/versions/monitoring/0001_monitoring_schema.py); these
definitions only name the columns the jobs use, so queries are checked by
pyright instead of being strings.
"""

from __future__ import annotations

from sqlalchemy import ARRAY, BigInteger, Boolean, Column, DateTime, Float, Interval, MetaData, Table, Text

metadata = MetaData(schema="monitoring")

audit_lines = Table(
    "audit_lines",
    metadata,
    Column("source", Text, primary_key=True),
    Column("line_number", BigInteger, primary_key=True),
    Column("line_sha256", Text, nullable=False),
    Column("logged_at", DateTime(timezone=True), nullable=False),
    Column("kind", Text, nullable=False),
    Column("call_id", Text),
    Column("caller", Text),
    Column("route", Text),
    Column("tool", Text),
    Column("decision", Text),
    Column("reason_category", Text),
    Column("is_error", Boolean),
    Column("is_suspicious", Boolean),
    Column("detector_layer", Text),
    Column("detector_score", Float[float]()),
    Column("actor_chain", ARRAY[str](Text)),
)

audit_imports = Table(
    "audit_imports",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("source", Text, nullable=False),
    Column("file_name", Text, nullable=False),
    Column("imported_at", DateTime(timezone=True)),
    Column("lines_total", BigInteger, nullable=False),
    Column("lines_imported", BigInteger, nullable=False),
    Column("is_intact", Boolean, nullable=False),
    Column("problems", ARRAY[str](Text), nullable=False),
)

heartbeats = Table(
    "heartbeats",
    metadata,
    Column("source", Text, primary_key=True),
    Column("beat_at", DateTime(timezone=True), nullable=False),
)

job_runs = Table(
    "job_runs",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column("job", Text, nullable=False),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("status", Text, nullable=False),
    Column("error_category", Text),
)

expected_jobs = Table(
    "expected_jobs",
    metadata,
    Column("job", Text, primary_key=True),
    Column("every", Interval, nullable=False),
    Column("grace", Interval, nullable=False),
)
