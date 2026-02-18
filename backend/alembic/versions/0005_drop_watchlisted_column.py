"""Drop watchlisted column from assets

Now that all code uses group membership instead of the watchlisted boolean,
this column is no longer needed.

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("assets", "watchlisted")


def downgrade() -> None:
    op.add_column(
        "assets",
        sa.Column("watchlisted", sa.Boolean(), nullable=False, server_default="true"),
    )
