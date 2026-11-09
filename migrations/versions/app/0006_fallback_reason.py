"""Why a run fell back to the facts-only report (paid run 3, 2026-11-05).

Run 3's one fallback kept no reason: no review was recorded and no tool called, so it was either
Keiko's output refused after PydanticAI's retries or the run's request limit, and nothing said which
(evals/paid-run-3-results.md). `fallback_reason` names it, so the next fallback can be read:

- `output_refused`: an agent gave no valid output even after its retries;
- `request_limit`: a call hit the run's request or token limit;
- `budget_spent`: the reports pool couldn't pay for the next call;
- `not_approved`: every draft was sent back, up to the revision limit.

It's empty for a run that published. A reason, never a quote, so it holds no learner's words.

Revision ID: 0006_app
Revises: 0005_app
Create Date: 2026-11-06
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006_app"
down_revision: str | Sequence[str] | None = "0005_app"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REASONS = ("output_refused", "request_limit", "budget_spent", "not_approved")


def upgrade() -> None:
    listed = ", ".join(f"'{reason}'" for reason in REASONS)
    # A nullable column with no default is a catalog change: no table rewrite.
    op.execute(
        "ALTER TABLE app.pipeline_runs ADD COLUMN IF NOT EXISTS fallback_reason text "
        f"CONSTRAINT pipeline_runs_fallback_reason CHECK (fallback_reason IN ({listed}))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE app.pipeline_runs DROP COLUMN IF EXISTS fallback_reason")
