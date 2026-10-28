"""Agent notes (ADR-008; Phase 2 MEM-R1 to MEM-R5): the notes, the refused proposals, and each consolidation decision.

A note keeps a copy of its evidence (`evidence`, with each row's word), so
Juku's MCP server reads memory without reading the events, which its role
can't. Every table has `learner_id`, so "Hapus data saya" and the export
reach them without a list to keep up to date.

The allowed categories are checked here as well as in code
(guardrails.yaml's `memory.allowed_categories`), a second wall: a test
keeps the two lists equal.

Revision ID: 0004_data
Revises: 0003_data
Create Date: 2026-10-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_data"
down_revision: str | Sequence[str] | None = "0003_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALLOWED_CATEGORIES = ("recurring_confusion", "preferred_example", "pace", "avoided_level")
# guardrails.yaml's memory.max_text_chars, as a database check too.
MAX_TEXT_CHARS = 160


def upgrade() -> None:
    categories = ", ".join(f"'{category}'" for category in ALLOWED_CATEGORIES)
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS learning.memory_notes (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            category text NOT NULL CHECK (category IN ({categories})),
            text text NOT NULL CHECK (char_length(text) BETWEEN 1 AND {MAX_TEXT_CHARS}),
            evidence_event_ids bigint[] NOT NULL CHECK (cardinality(evidence_event_ids) >= 1),
            evidence jsonb NOT NULL,
            proposed_by text NOT NULL,
            created_at timestamptz NOT NULL,
            last_evidence_at timestamptz NOT NULL,
            status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'lapsed', 'removed', 'wrong')),
            status_reason text,
            status_changed_at timestamptz
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS memory_notes_learner ON learning.memory_notes (learner_id, status)")
    op.execute(
        "COMMENT ON TABLE learning.memory_notes IS "
        "'Notes agents proposed and code accepted, each with a copy of its evidence. Learners see, remove "
        "or mark them wrong.'"
    )
    op.execute("""
        CREATE TABLE IF NOT EXISTS learning.memory_note_rejections (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            proposed_by text NOT NULL,
            category text NOT NULL,
            reason text NOT NULL,
            rejected_at timestamptz NOT NULL
        )
    """)
    op.execute(
        "COMMENT ON TABLE learning.memory_note_rejections IS "
        "'Refused note proposals, by reason (Phase 1 MEM2). Never the proposed text.'"
    )
    op.execute("""
        CREATE TABLE IF NOT EXISTS learning.memory_consolidations (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            learner_id bigint NOT NULL REFERENCES learning.learners (id) ON DELETE CASCADE,
            note_id bigint NOT NULL REFERENCES learning.memory_notes (id) ON DELETE CASCADE,
            decided_at timestamptz NOT NULL,
            decision text NOT NULL CHECK (decision IN ('kept', 'lapsed')),
            reason text NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS memory_consolidations_note ON learning.memory_consolidations (note_id)")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON learning.memory_notes, learning.memory_note_rejections, "
        "learning.memory_consolidations TO juku_app"
    )
    # Juku's MCP server reads the notes for get_memory, and nothing else here.
    op.execute("GRANT SELECT ON learning.memory_notes TO juku_mcp")
    # The nightly consolidation (juku-ops consolidate-memory), watched by the "missed run" alert.
    op.execute(
        "INSERT INTO monitoring.expected_jobs (job, every, grace) VALUES ('consolidate-memory', '1 day', '1 hour') "
        "ON CONFLICT (job) DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DELETE FROM monitoring.expected_jobs WHERE job = 'consolidate-memory'")
    op.execute("DROP TABLE IF EXISTS learning.memory_consolidations")
    op.execute("DROP TABLE IF EXISTS learning.memory_note_rejections")
    op.execute("DROP TABLE IF EXISTS learning.memory_notes")
