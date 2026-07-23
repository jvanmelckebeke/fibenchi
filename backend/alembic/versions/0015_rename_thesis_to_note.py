"""Rename the per-asset and pseudo-ETF "thesis" tables to "note".

The per-asset free-text "thesis" and the pseudo-ETF "thesis" were both just
free-text notes. They are renamed to "note", freeing the word "thesis" for a
new global thesis container (groups of tickers under one hypothesis — see
issues #523/#524). These are pure table renames; column shapes are unchanged.

Idempotent / self-healing: a table is only renamed if the old name exists and
the new name does not, so re-running — or running against a partially migrated
instance — is safe.

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa


revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


_RENAMES = [
    ("theses", "notes"),
    ("pseudo_etf_theses", "pseudo_etf_notes"),
]


def _rename(old: str, new: str) -> None:
    conn = op.get_bind()
    tables = set(sa.inspect(conn).get_table_names())
    if old in tables and new not in tables:
        op.rename_table(old, new)


def upgrade() -> None:
    for old, new in _RENAMES:
        _rename(old, new)


def downgrade() -> None:
    for old, new in _RENAMES:
        _rename(new, old)
