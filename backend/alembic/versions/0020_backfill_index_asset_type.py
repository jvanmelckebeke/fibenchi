"""assets: unit_kind + provenance, and backfill the drifted index rows

Two related corrections in one revision, because they are the same mistake
seen from two sides.

**The data.** Yahoo's quoteType decided an asset's type once at creation and
was then frozen in the row. For six caret symbols it answered wrong —
^GSPC, ^N225, ^HSI, ^STOXX50E, ^KS11 and ^TWII landed as 'stock', so every
price surface formatted them as currency ("$6,9xx" for the S&P 500,
"¥39xxx" for the Nikkei). Only ^TNX and ^TYX were typed correctly.

**The model.** Even typed as indices they were still wrong, because
``currency`` is non-null and answers only *which* currency — there was no
way to say "this is a rate" or "this has no unit". Percent-ness lived as a
hardcoded four-ticker set in the frontend's format.ts, unreachable from the
API. ``unit_kind`` gives that its own field.

``type_source`` / ``unit_source`` record whether Fibenchi worked a value out
or a human chose it. Everything predating this revision is by definition
auto-detected — no UI ever wrote provenance — so AUTO is the correct
backfill for every existing row, including the six being repaired here.

Enum literals are the member *names* (INDEX, CURRENCY, AUTO), matching
SQLAlchemy's default Enum() persistence and the rest of this schema. Note
the assettype enum also carries an unused lowercase 'index' label from
earlier drift; writing that one would round-trip to a LookupError.

The predicate is inlined SQL rather than an import of classify(): a
migration has to keep meaning the same thing after the app moves on.

No downgrade for the type repair — the old values were wrong rather than
different, so restoring them would be restoring a bug.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UNIT_KIND = sa.Enum("CURRENCY", "PERCENT", "POINTS", name="unitkind")
FIELD_SOURCE = sa.Enum("AUTO", "USER", name="fieldsource")

# Indices quoted as a rate, not a level — mirrors PERCENT_QUOTED_INDICES in
# market_calendar/listings.py. Duplicated on purpose: see the note on inlining.
PERCENT_INDICES = ("^TYX", "^TNX", "^FVX", "^IRX")


def upgrade() -> None:
    bind = op.get_bind()
    UNIT_KIND.create(bind, checkfirst=True)
    FIELD_SOURCE.create(bind, checkfirst=True)

    op.add_column("assets", sa.Column("unit_kind", UNIT_KIND, nullable=False, server_default="CURRENCY"))
    op.add_column("assets", sa.Column("type_source", FIELD_SOURCE, nullable=False, server_default="AUTO"))
    op.add_column("assets", sa.Column("unit_source", FIELD_SOURCE, nullable=False, server_default="AUTO"))

    # LIKE '^%' — the caret is a literal here, only % and _ are wildcards.
    # Idempotent, and a no-op on instances that never tracked an index.
    op.execute("UPDATE assets SET type = 'INDEX' WHERE symbol LIKE '^%' AND type <> 'INDEX'")

    # Order matters: percent first would be undone by the points sweep.
    op.execute(
        "UPDATE assets SET unit_kind = 'POINTS' WHERE symbol LIKE '^%'"
    )
    op.execute(
        "UPDATE assets SET unit_kind = 'PERCENT' WHERE symbol IN "
        f"({', '.join(repr(s) for s in PERCENT_INDICES)})"
    )


def downgrade() -> None:
    """Drops the new columns only — the type repair is deliberately kept.

    IF EXISTS throughout: a downgrade should be able to run against a
    partially-applied revision without needing hand-repair first.
    """
    op.execute("ALTER TABLE assets DROP COLUMN IF EXISTS unit_source")
    op.execute("ALTER TABLE assets DROP COLUMN IF EXISTS type_source")
    op.execute("ALTER TABLE assets DROP COLUMN IF EXISTS unit_kind")
    bind = op.get_bind()
    FIELD_SOURCE.drop(bind, checkfirst=True)
    UNIT_KIND.drop(bind, checkfirst=True)
