"""intraday_prices: (asset_id, timestamp) natural primary key, no surrogate id

Follow-up to 0018: the surrogate id existed only to be a primary key, yet
(asset_id, timestamp) is already the row's identity (it's the upsert's
conflict target). Dropping the id removes the sequence entirely, making the
sequence-exhaustion class of failure unrepresentable instead of merely
postponed. The old unique constraint and secondary index are redundant with
the new primary key and go with it.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-05
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Dropping the column also drops its primary-key constraint and the
    # owned sequence. The table holds ~2 days of bars, so the locks are brief.
    op.execute("ALTER TABLE intraday_prices DROP COLUMN id")
    op.execute("ALTER TABLE intraday_prices ADD PRIMARY KEY (asset_id, timestamp)")
    op.execute("ALTER TABLE intraday_prices DROP CONSTRAINT uq_intraday_asset_ts")
    op.execute("DROP INDEX IF EXISTS ix_intraday_asset_time")


def downgrade() -> None:
    op.execute("ALTER TABLE intraday_prices DROP CONSTRAINT intraday_prices_pkey")
    op.execute("ALTER TABLE intraday_prices ADD COLUMN id BIGSERIAL PRIMARY KEY")
    op.execute(
        "ALTER TABLE intraday_prices "
        "ADD CONSTRAINT uq_intraday_asset_ts UNIQUE (asset_id, timestamp)"
    )
    op.execute(
        "CREATE INDEX ix_intraday_asset_time ON intraday_prices (asset_id, timestamp)"
    )
