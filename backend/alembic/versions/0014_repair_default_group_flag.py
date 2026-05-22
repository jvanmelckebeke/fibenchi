"""Repair the is_default flag on the groups table if it has drifted.

Migration 0004 originally seeded ``is_default = true`` on the Watchlist
group, but at least one production database has drifted such that no
group carries the flag. ``GroupRepository.get_default()`` then returns
``None`` and ``DELETE /api/assets/{symbol}`` becomes a silent no-op
(see issue #507).

This migration is idempotent and self-healing:

- If exactly one group has ``is_default = true``, do nothing.
- If multiple groups have it set, keep the lowest-id one and demote the rest.
- If zero groups have it set, promote the group named ``Watchlist`` (case
  exact, matches what 0004 seeded). If no such group exists, do nothing —
  the upgraded ``delete_asset`` raises a 500 with a clear message so the
  operator knows what to fix.

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa


revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    default_count = conn.execute(
        sa.text("SELECT COUNT(*) FROM groups WHERE is_default = true")
    ).scalar() or 0

    if default_count == 1:
        return

    if default_count > 1:
        keep_id = conn.execute(
            sa.text("SELECT MIN(id) FROM groups WHERE is_default = true")
        ).scalar()
        conn.execute(
            sa.text(
                "UPDATE groups SET is_default = false "
                "WHERE is_default = true AND id != :id"
            ),
            {"id": keep_id},
        )
        return

    watchlist = conn.execute(
        sa.text("SELECT id FROM groups WHERE name = 'Watchlist' LIMIT 1")
    ).fetchone()
    if watchlist:
        conn.execute(
            sa.text("UPDATE groups SET is_default = true WHERE id = :id"),
            {"id": watchlist[0]},
        )


def downgrade() -> None:
    pass
