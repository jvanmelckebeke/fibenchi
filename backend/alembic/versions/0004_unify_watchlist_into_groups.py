"""Unify watchlist into groups

Add is_default and position columns to groups table, seed a protected
"Watchlist" default group, and migrate all watchlisted assets into it
via the group_assets junction table.

The watchlisted column on assets is NOT dropped here — that happens
in migration 0005 after the backend code is updated to use group
membership instead of the boolean flag.

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new columns to groups table
    op.add_column("groups", sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("groups", sa.Column("position", sa.Integer(), nullable=False, server_default="0"))

    conn = op.get_bind()

    # 2. Seed the default "Watchlist" group (position 0, is_default=true)
    #    Use INSERT ... SELECT to handle the case where a group named "Watchlist"
    #    already exists (unlikely but safe).
    existing = conn.execute(
        sa.text("SELECT id FROM groups WHERE name = 'Watchlist'")
    ).fetchone()

    if existing:
        watchlist_id = existing[0]
        conn.execute(sa.text(
            "UPDATE groups SET is_default = true, position = 0 WHERE id = :id"
        ), {"id": watchlist_id})
    else:
        conn.execute(sa.text(
            "INSERT INTO groups (name, description, is_default, position) "
            "VALUES ('Watchlist', 'Default watchlist group', true, 0)"
        ))
        watchlist_id = conn.execute(
            sa.text("SELECT id FROM groups WHERE name = 'Watchlist'")
        ).scalar()

    # 3. Migrate watchlisted assets into the Watchlist group
    #    Only insert if the (group_id, asset_id) pair doesn't already exist.
    conn.execute(sa.text("""
        INSERT INTO group_assets (group_id, asset_id)
        SELECT :gid, a.id
        FROM assets a
        WHERE a.watchlisted = true
          AND a.id NOT IN (
              SELECT asset_id FROM group_assets WHERE group_id = :gid
          )
    """), {"gid": watchlist_id})

    # 4. Bump position of existing non-default groups to start after 0
    conn.execute(sa.text("""
        UPDATE groups SET position = id WHERE is_default = false AND position = 0
    """))


def downgrade() -> None:
    conn = op.get_bind()

    # Remove assets from the Watchlist group that were migrated
    watchlist = conn.execute(
        sa.text("SELECT id FROM groups WHERE name = 'Watchlist' AND is_default = true")
    ).fetchone()

    if watchlist:
        conn.execute(sa.text(
            "DELETE FROM group_assets WHERE group_id = :gid"
        ), {"gid": watchlist[0]})
        conn.execute(sa.text(
            "DELETE FROM groups WHERE id = :gid"
        ), {"gid": watchlist[0]})

    op.drop_column("groups", "position")
    op.drop_column("groups", "is_default")
