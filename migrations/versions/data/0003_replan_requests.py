"""Replan requests: the one thing an agent's tool may write (Phase 2 SM4, ADR-006).

Shiori's `request_replan` only queues a Keiko run; the weekly pipeline
(slice 6) picks the requests up, and the result still passes Tadashi and
code. At most `replan.max_requests_per_day` a learner per local day: the
server checks the count before inserting, under the unique key.

Juku's MCP role may INSERT here and nowhere else; it still can't update or
delete, and can't read the events. Grants are the second wall behind the
tool list (Phase 2, the guardrails table: "a write attempt is refused at
the tool and at the database").

Revision ID: 0003_data
Revises: 0002_data
Create Date: 2026-10-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_data"
down_revision: str | Sequence[str] | None = "0002_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS learning.replan_requests (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            local_day date NOT NULL,
            sequence_in_day smallint NOT NULL CHECK (sequence_in_day >= 1),
            requested_at timestamptz NOT NULL DEFAULT now(),
            actor_chain text[] NOT NULL,
            handled_at timestamptz,
            UNIQUE (learner_id, local_day, sequence_in_day)
        )
    """)
    op.execute(
        "COMMENT ON TABLE learning.replan_requests IS "
        "'Queued by Shiori''s request_replan; read by the weekly pipeline. The only table an agent tool writes.'"
    )
    op.execute("GRANT SELECT, INSERT ON learning.replan_requests TO juku_mcp")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON learning.replan_requests TO juku_app")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS learning.replan_requests")
