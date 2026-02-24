"""Add intraday_prices table for live day view

Revision ID: 0010
Revises: 0009
Create Date: 2026-02-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "intraday_prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price", sa.Numeric(12, 4), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("session", sa.String(7), nullable=False, server_default=sa.text("'regular'")),
        sa.UniqueConstraint("asset_id", "timestamp", name="uq_intraday_asset_ts"),
    )
    op.create_index("ix_intraday_asset_time", "intraday_prices", ["asset_id", "timestamp"])


def downgrade() -> None:
    op.drop_index("ix_intraday_asset_time", table_name="intraday_prices")
    op.drop_table("intraday_prices")
