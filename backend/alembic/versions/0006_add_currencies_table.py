"""Add currencies lookup table

Create a currencies table for O(1) divisor/display lookups, seed it with
all known currencies (subunit + exchange map), and backfill assets.currency
to raw Yahoo codes where the original subunit code can be derived.

Revision ID: 0006
Revises: 0005
Create Date: 2026-02-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Subunit currencies: raw Yahoo code → (display_code, divisor)
SUBUNIT_CURRENCIES = {
    "GBp": ("GBP", 100),
    "GBX": ("GBP", 100),
    "ILA": ("ILS", 100),
    "ZAc": ("ZAR", 100),
}

# All main currencies from EXCHANGE_CURRENCY_MAP (deduplicated)
MAIN_CURRENCIES = sorted({
    "KRW", "JPY", "HKD", "CNY", "TWD", "SGD", "AUD", "NZD", "INR",
    "IDR", "THB", "GBP", "EUR", "NOK", "SEK", "DKK", "ISK", "PLN",
    "CZK", "HUF", "CHF", "TRY", "ILS", "SAR", "QAR", "ZAR", "CAD",
    "BRL", "MXN", "CLP", "ARS", "USD",
})

# Suffix → raw subunit code for backfilling assets.currency
# These reverse migration 0003's normalization for known suffix→subunit mappings
SUFFIX_TO_RAW = {
    ".L": "GBp",
    ".IL": "GBp",
    ".TA": "ILA",
    ".JO": "ZAc",
}


def upgrade() -> None:
    # Create currencies table
    op.create_table(
        "currencies",
        sa.Column("code", sa.String(10), primary_key=True),
        sa.Column("display_code", sa.String(10), nullable=False),
        sa.Column("divisor", sa.Integer, nullable=False, server_default="1"),
    )

    conn = op.get_bind()

    # Seed subunit currencies
    for code, (display, divisor) in SUBUNIT_CURRENCIES.items():
        conn.execute(sa.text(
            "INSERT INTO currencies (code, display_code, divisor) VALUES (:code, :display, :divisor)"
        ), {"code": code, "display": display, "divisor": divisor})

    # Seed main currencies (display_code == code, divisor == 1)
    for code in MAIN_CURRENCIES:
        # Skip if already inserted as a subunit code (e.g. GBP is separate from GBp)
        existing = conn.execute(
            sa.text("SELECT 1 FROM currencies WHERE code = :code"), {"code": code}
        ).fetchone()
        if not existing:
            conn.execute(sa.text(
                "INSERT INTO currencies (code, display_code, divisor) VALUES (:code, :display, 1)"
            ), {"code": code, "display": code})

    # Backfill assets.currency to raw Yahoo codes where derivable.
    # Migration 0003 normalized GBp→GBP, ILA→ILS, ZAc→ZAR.
    # We reverse this for assets with known exchange suffixes.
    for suffix, raw_code in SUFFIX_TO_RAW.items():
        display_code = SUBUNIT_CURRENCIES[raw_code][0]
        # Use LIKE for suffix matching (standard SQL)
        conn.execute(sa.text(
            "UPDATE assets SET currency = :raw "
            "WHERE symbol LIKE :pattern AND currency = :display"
        ), {"raw": raw_code, "pattern": f"%{suffix}", "display": display_code})


def downgrade() -> None:
    conn = op.get_bind()

    # Restore normalized currency codes on assets
    for raw_code, (display_code, _) in SUBUNIT_CURRENCIES.items():
        conn.execute(sa.text(
            "UPDATE assets SET currency = :display WHERE currency = :raw"
        ), {"display": display_code, "raw": raw_code})

    op.drop_table("currencies")
