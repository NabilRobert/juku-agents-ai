"""Expect the nightly state check (FF3 in production) in the schedule.

Revision ID: 0002_data
Revises: 0001_data
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_data"
down_revision: str | Sequence[str] | None = "0001_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO monitoring.expected_jobs (job, every, grace) VALUES ('verify-state', '1 day', '1 hour') "
        "ON CONFLICT (job) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM monitoring.expected_jobs WHERE job = 'verify-state'")
