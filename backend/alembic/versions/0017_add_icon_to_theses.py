"""Add icon column to theses table

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("theses", sa.Column("icon", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("theses", "icon")
