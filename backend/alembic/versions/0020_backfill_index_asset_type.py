"""assets: backfill type='index' for ^-prefixed symbols

Yahoo's quoteType decided an asset's type once at creation and was then
frozen in the row. For six caret symbols it answered wrong — ^GSPC, ^N225,
^HSI, ^STOXX50E, ^KS11 and ^TWII landed as 'stock', so every price surface
formatted them as currency ("$6,9xx" for the S&P 500, "¥39xxx" for the
Nikkei). Only ^TNX and ^TYX were typed correctly.

A leading caret is Yahoo's index namespace, which is exactly what
domain/instrument.py::classify() keys on. The predicate is inlined as SQL
rather than imported from the app: a migration has to keep meaning the same
thing years from now, and app code is free to change underneath it.

Note the literal is 'INDEX', not 'index'. SQLAlchemy's Enum(AssetType)
persists the member *name*, so the rows read STOCK/ETF/INDEX. The assettype
enum also carries an unused lowercase 'index' label from earlier drift —
writing that one would round-trip to a LookupError, since it matches no
AssetType member name.

There is no downgrade. The pre-migration values were wrong rather than
different, so restoring them would be restoring a bug — and 'stock' is not
recoverable per-row anyway, since we'd have to guess which rows to corrupt.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-12
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # LIKE '^%' — the caret is a literal here, only % and _ are wildcards.
    # Idempotent, and a no-op on instances that never tracked an index.
    op.execute("UPDATE assets SET type = 'INDEX' WHERE symbol LIKE '^%' AND type <> 'INDEX'")


def downgrade() -> None:
    """Deliberately empty — see the module docstring."""
