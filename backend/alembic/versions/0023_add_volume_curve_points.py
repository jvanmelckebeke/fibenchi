"""volume_curve_points: per-venue intraday volume profile

RVOL compares a session's volume to its 20-day average, which makes it blind
to the session it exists to describe: mid-morning, volume-so-far over a
whole-day average reads a fraction of what the day will finish at. Dividing by
elapsed clock time doesn't fix it — real volume is front- and back-loaded by
the opening and closing auctions, so a flat assumption reads roughly twice too
hot in the first half hour.

The fix needs to know what fraction of a typical session has traded by now,
which is a property of the venue's auction structure rather than of any one
symbol. This table holds that curve, fitted from 5-minute bars and keyed on
session progress so half days need no special case.

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "volume_curve_points",
        sa.Column("calendar", sa.String(32), primary_key=True),
        sa.Column("bucket", sa.SmallInteger(), primary_key=True),
        sa.Column("cumulative_fraction", sa.Numeric(6, 5), nullable=False),
        sa.Column("samples", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "fitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("volume_curve_points")
