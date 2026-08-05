"""Widen intraday_prices.id to BIGINT — the int32 sequence ran out

The intraday upsert uses ON CONFLICT DO UPDATE, and PostgreSQL consumes a
sequence value for every *attempted* row, conflicting or not. Each 60s sync
re-upserts the whole day's 1m bars for every symbol (~20M nextvals/day), so
the SERIAL sequence hit 2147483647 after ~3 months and every intraday sync
failed with SequenceGeneratorLimitExceededError.

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-05
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE intraday_prices ALTER COLUMN id TYPE BIGINT")
    # SERIAL created the sequence AS integer, which is what capped it at
    # int4 max; switching it to bigint also lifts its maxvalue accordingly.
    op.execute("ALTER SEQUENCE intraday_prices_id_seq AS BIGINT")


def downgrade() -> None:
    # Not reversible in practice: the sequence is already past int4 max, so
    # narrowing back would immediately re-break. Intentional no-op.
    pass
