"""The owner role (ADR-029): a role on each learner, and an audit row for each owner action.

- `learning.learners.role` is `learner` for everyone, until `juku set-role`
  makes someone `owner`. A migration can't name Arthur: his learner row
  doesn't exist until he redeems a code, and a public repo can't hold his
  ID. Being owner adds the owner pages; the owner is still a learner.
- `app.owner_actions` records who issued codes, removed a learner or
  changed a role, from which place (the owner page or the server's
  command line), and when. juku_app may only read and add rows, so the
  app can't rewrite its own audit. A removed learner's public ID stays in
  `subject`: it's random, and nothing else is left to link it to.

The column lives in the learning schema, beside the learner it describes,
but it's the app's concern (who manages learners), so it migrates here.

Revision ID: 0004_app
Revises: 0003_app
Create Date: 2026-11-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_app"
down_revision: str | Sequence[str] | None = "0003_app"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = ("owner", "learner")
ACTIONS = ("issue_codes", "remove_learner", "set_role")
PLACES = ("page", "cli")


def listed(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    # A constant default on Postgres 11+ is a catalog change: no table rewrite.
    op.execute(
        "ALTER TABLE learning.learners ADD COLUMN IF NOT EXISTS role text NOT NULL DEFAULT 'learner' "
        f"CONSTRAINT learners_role CHECK (role IN ({listed(ROLES)}))"
    )
    op.execute(
        "COMMENT ON COLUMN learning.learners.role IS "
        "'owner: may issue invite codes and remove learners (ADR-029). Set only by juku set-role.'"
    )
    op.execute(f"""
        CREATE TABLE IF NOT EXISTS app.owner_actions (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            owner_id bigint REFERENCES learning.learners (id) ON DELETE SET NULL,
            place text NOT NULL CHECK (place IN ({listed(PLACES)})),
            action text NOT NULL CHECK (action IN ({listed(ACTIONS)})),
            subject text,
            detail jsonb NOT NULL DEFAULT '{{}}',
            acted_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "COMMENT ON TABLE app.owner_actions IS "
        "'One row per owner action. owner_id is NULL for the command line, or once that owner is deleted.'"
    )
    op.execute("GRANT SELECT, INSERT ON app.owner_actions TO juku_app")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.owner_actions")
    op.execute("ALTER TABLE learning.learners DROP COLUMN IF EXISTS role")
