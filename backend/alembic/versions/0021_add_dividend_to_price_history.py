"""price_history: per-bar cash dividend, for total-return σ-Move

An ex-dividend date drops the price by roughly the dividend and nothing has
happened. σ-Move scored that drop as a market move twice over: once as the
day's return, and then for weeks afterwards through the EWMA variance it was
squared into. The correction needs the cash amount at *compute* time, and
indicators are computed from stored bars — so the amount has to live beside
the bar it belongs to rather than only in the provider frame that carried it.

Nullable rather than defaulted to 0: null means "this bar predates the column,
and nobody has asked the provider about it", which is a different statement
from "the provider says this bar paid nothing". Existing rows are therefore
left null and the compute path reads null as zero, so σ-Move is corrected from
the first re-fetch onward per symbol instead of claiming a clean history it
does not have.

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "price_history",
        sa.Column("dividend", sa.Numeric(12, 6), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("price_history", "dividend")
