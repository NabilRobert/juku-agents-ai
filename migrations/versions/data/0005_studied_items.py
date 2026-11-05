"""What a learner has studied, for the curriculum: grammar points understood, sentences read, placement.

The curriculum (2026-11-05) needs to know, per unit, which grammar points the learner has studied and which
of its sentences they've read. Both are events (a new type, grammar_studied, and the existing
sentence_read), and so is a placement test's result (placed, the last unit placed through);
`learner_studied` is their summary, rebuilt from the events like the other learner_*
tables (engine/recompute.py) and checked against them by FF3. Pages read the summary, never the events (FF2).

The backfill fills it from the sentence_read events already recorded.

Revision ID: 0005_data
Revises: 0004_data
Create Date: 2026-11-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_data"
down_revision: str | Sequence[str] | None = "0004_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO learning.event_types (id, name) VALUES (6, 'grammar_studied'), (7, 'placed') "
        "ON CONFLICT (id) DO NOTHING"
    )
    op.execute("""
        CREATE TABLE IF NOT EXISTS learning.learner_studied (
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            kind smallint NOT NULL REFERENCES learning.event_types (id),
            item_id text NOT NULL,
            first_at timestamptz NOT NULL,
            PRIMARY KEY (learner_id, kind, item_id)
        )
    """)
    op.execute(
        "COMMENT ON TABLE learning.learner_studied IS "
        "'Derived from learning_events, the first time of each: sentence read (kind 5), grammar point studied "
        "(kind 6), placed through a curriculum unit (kind 7).'"
    )
    op.execute("""
        INSERT INTO learning.learner_studied (learner_id, kind, item_id, first_at)
        SELECT learner_id, event_type, item_id, min(occurred_at)
        FROM learning.learning_events WHERE event_type IN (5, 6)
        GROUP BY learner_id, event_type, item_id
        ON CONFLICT DO NOTHING
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON learning.learner_studied TO juku_app")
    op.execute("GRANT SELECT ON learning.learner_studied TO juku_mcp")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS learning.learner_studied")
    op.execute("DELETE FROM learning.event_types WHERE id IN (6, 7)")
