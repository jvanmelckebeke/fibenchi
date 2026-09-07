"""price_history: recover the FX closes Yahoo never sent

Yahoo's settled daily bar for an ``=X`` pair carries the session's *open* in
its ``close`` field, so every stored FX close is one session stale and every
candle is a hairline body under a full-height wick. ``normalize_fx_close``
fixes the fetch path from here on, but a fetch only rewrites what it refetches
— the nightly sync covers 1y, leaving anything older wrong forever.

The recovery is the same one the service does: in a market that trades around
the clock, the next bar's open is this bar's close. Written as SQL rather than
by importing the service, because a migration has to keep meaning the same
thing after the app moves on.

Per-row rather than per-frame: the service judges a whole frame by its median
body, but this can afford to ask each row whether it individually shows the
defect, so a genuinely flat session in an otherwise healthy series is never
touched. ``0.10`` is ``FX_BODY_CEILING`` — see that constant for the
measurement that picked it.

High/low are widened to contain the recovered close (it lands outside the
provider's own range on ~25% of FX bars), or the repaired bar would print a
body outside its own wick.

No downgrade: the old closes were wrong rather than different.

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-07
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# LIKE '%=X' — only % and _ are wildcards, so '=X' is the literal suffix.
# A no-op on instances that never tracked a currency pair.
REPAIR = """
WITH recovered AS (
    SELECT p.id,
           p.close AS stored,
           p.open AS bar_open,
           p.high AS bar_high,
           p.low AS bar_low,
           LEAD(p.open) OVER (PARTITION BY p.asset_id ORDER BY p.date) AS true_close
    FROM price_history p
    JOIN assets a ON a.id = p.asset_id
    WHERE a.symbol LIKE '%=X'
)
UPDATE price_history p
SET close = r.true_close,
    high = GREATEST(r.bar_high, r.true_close),
    low = LEAST(r.bar_low, r.true_close)
FROM recovered r
WHERE p.id = r.id
  AND r.true_close IS NOT NULL
  AND r.bar_high > r.bar_low
  AND ABS(r.stored - r.bar_open) <= 0.10 * (r.bar_high - r.bar_low)
"""


def upgrade() -> None:
    op.execute(REPAIR)


def downgrade() -> None:
    """Deliberately empty — see the module docstring."""
