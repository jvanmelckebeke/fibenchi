"""Add the global ``theses`` table and ``thesis_assets`` membership table.

A thesis is a cross-cutting thematic basket of tickers tracked under one
hypothesis, with a lifecycle status and an open date (see #524). The ``theses``
name was freed by migration 0015, which renamed the old per-asset note table.

``status`` is stored as a plain string (not a Postgres ENUM) on purpose — see
``ThesisStatus`` in ``app/models/thesis.py``.

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa


revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "theses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("color", sa.String(7), nullable=False, server_default="#3b82f6"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="watching"),
        sa.Column("opened_at", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_theses_name", "theses", ["name"], unique=True)

    op.create_table(
        "thesis_assets",
        sa.Column(
            "thesis_id",
            sa.Integer(),
            sa.ForeignKey("theses.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("thesis_assets")
    op.drop_index("ix_theses_name", table_name="theses")
    op.drop_table("theses")
