"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-02-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: skip if tables already exist (existing database being migrated
    # to Alembic). The alembic_version table is still stamped so future
    # migrations apply normally.
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "assets" in inspector.get_table_names():
        return

    # -- Independent tables --

    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", sa.Enum("stock", "etf", name="assettype"), nullable=False),
        sa.Column("watchlisted", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="EUR"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("symbol"),
    )
    op.create_index("ix_assets_symbol", "assets", ["symbol"])

    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "pseudo_etfs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("base_date", sa.Date(), nullable=False),
        sa.Column("base_value", sa.Numeric(12, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_pseudo_etfs_name", "pseudo_etfs", ["name"])

    op.create_table(
        "user_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )

    # -- Tables with foreign keys to assets --

    op.create_table(
        "price_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(12, 4), nullable=False),
        sa.Column("high", sa.Numeric(12, 4), nullable=False),
        sa.Column("low", sa.Numeric(12, 4), nullable=False),
        sa.Column("close", sa.Numeric(12, 4), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.UniqueConstraint("asset_id", "date", name="uq_asset_date"),
    )
    op.create_index("ix_price_history_asset_id", "price_history", ["asset_id"])
    op.create_index("ix_price_history_date", "price_history", ["date"])

    op.create_table(
        "theses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("asset_id"),
    )

    op.create_table(
        "annotations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_annotations_asset_id", "annotations", ["asset_id"])

    # -- Association tables --

    op.create_table(
        "group_assets",
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "tag_assets",
        sa.Column(
            "tag_id",
            sa.Integer(),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_table(
        "pseudo_etf_constituents",
        sa.Column(
            "pseudo_etf_id",
            sa.Integer(),
            sa.ForeignKey("pseudo_etfs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # -- Pseudo-ETF dependent tables --

    op.create_table(
        "pseudo_etf_theses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "pseudo_etf_id",
            sa.Integer(),
            sa.ForeignKey("pseudo_etfs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("pseudo_etf_id"),
    )

    op.create_table(
        "pseudo_etf_annotations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "pseudo_etf_id",
            sa.Integer(),
            sa.ForeignKey("pseudo_etfs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_pseudo_etf_annotations_pseudo_etf_id",
        "pseudo_etf_annotations",
        ["pseudo_etf_id"],
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("pseudo_etf_annotations")
    op.drop_table("pseudo_etf_theses")
    op.drop_table("pseudo_etf_constituents")
    op.drop_table("tag_assets")
    op.drop_table("group_assets")
    op.drop_table("annotations")
    op.drop_table("theses")
    op.drop_table("price_history")
    op.drop_table("user_settings")
    op.drop_table("pseudo_etfs")
    op.drop_table("tags")
    op.drop_table("groups")
    op.drop_table("assets")
    sa.Enum(name="assettype").drop(op.get_bind())
