"""Normalize subunit currencies (GBp/GBX → GBP)

Convert British pence (and other subunit currencies) stored by Yahoo Finance
to their main currency. Divides historical prices by 100 and updates the
currency code on affected assets.

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Subunit currency codes → (main currency, divisor)
SUBUNIT_CURRENCIES = {
    "GBp": ("GBP", 100),
    "GBX": ("GBP", 100),
    "ILA": ("ILS", 100),
    "ZAc": ("ZAR", 100),
}


def upgrade() -> None:
    conn = op.get_bind()

    for subunit, (main_currency, divisor) in SUBUNIT_CURRENCIES.items():
        # Divide OHLCV prices by the divisor for affected assets
        conn.execute(sa.text("""
            UPDATE price_history
            SET open  = open  / :divisor,
                high  = high  / :divisor,
                low   = low   / :divisor,
                close = close / :divisor
            WHERE asset_id IN (
                SELECT id FROM assets WHERE currency = :subunit
            )
        """), {"divisor": divisor, "subunit": subunit})

        # Update the asset currency code
        conn.execute(sa.text("""
            UPDATE assets SET currency = :main WHERE currency = :subunit
        """), {"main": main_currency, "subunit": subunit})


def downgrade() -> None:
    conn = op.get_bind()

    for subunit, (main_currency, divisor) in SUBUNIT_CURRENCIES.items():
        # Note: downgrade cannot perfectly distinguish which assets were originally
        # in subunit currencies vs already in main currency. This is best-effort.
        pass
