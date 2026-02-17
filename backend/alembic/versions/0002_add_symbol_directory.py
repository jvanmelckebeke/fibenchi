"""Add symbol_directory table

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "symbol_directory",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("exchange", sa.String(100), nullable=False, server_default=""),
        sa.Column("type", sa.String(10), nullable=False, server_default="stock"),
        sa.Column("last_seen", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_symbol_directory_symbol", "symbol_directory", ["symbol"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_symbol_directory_symbol", table_name="symbol_directory")
    op.drop_table("symbol_directory")
