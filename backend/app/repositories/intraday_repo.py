from datetime import datetime
from typing import NamedTuple

from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.intraday import IntradayPrice


class StoredBars(NamedTuple):
    """What the table holds for one asset, as far as a refresh needs to know."""

    oldest: datetime
    # The newest stored bar, the one that may still have been forming when it
    # was stored.
    newest: datetime
    newest_values: tuple[float, int, str]


class IntradayRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def load_stored_edges(self, asset_ids: list[int]) -> dict[int, StoredBars]:
        """Per asset: its oldest stored timestamp and its newest stored bar.

        Both are single probes of the (asset_id, timestamp) primary key, one per
        asset: a ``MIN`` subquery and a ``LATERAL ... ORDER BY timestamp DESC
        LIMIT 1``. A ``GROUP BY`` or a plain ``IN`` would read every stored row of
        the asset instead. Assets with nothing stored are absent from the result.
        """
        if not asset_ids:
            return {}
        newest = (
            select(
                IntradayPrice.timestamp,
                IntradayPrice.price,
                IntradayPrice.volume,
                IntradayPrice.session,
            )
            .where(IntradayPrice.asset_id == Asset.id)
            .order_by(IntradayPrice.timestamp.desc())
            .limit(1)
            .lateral()
        )
        oldest = select(func.min(IntradayPrice.timestamp)).where(IntradayPrice.asset_id == Asset.id).scalar_subquery()
        result = await self.db.execute(
            select(Asset.id, oldest, newest.c.timestamp, newest.c.price, newest.c.volume, newest.c.session)
            .join(newest, true())
            .where(Asset.id.in_(asset_ids))
        )
        return {
            asset_id: StoredBars(first, last, (float(price), int(volume or 0), session))
            for asset_id, first, last, price, volume, session in result
        }
