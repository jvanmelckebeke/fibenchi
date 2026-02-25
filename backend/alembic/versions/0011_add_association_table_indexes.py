"""Add indexes on asset_id columns of association tables

Revision ID: 0011
Revises: 0010
Create Date: 2026-02-25
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_group_assets_asset_id", "group_assets", ["asset_id"])
    op.create_index("ix_tag_assets_asset_id", "tag_assets", ["asset_id"])
    op.create_index("ix_pseudo_etf_constituents_asset_id", "pseudo_etf_constituents", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_pseudo_etf_constituents_asset_id", "pseudo_etf_constituents")
    op.drop_index("ix_tag_assets_asset_id", "tag_assets")
    op.drop_index("ix_group_assets_asset_id", "group_assets")
