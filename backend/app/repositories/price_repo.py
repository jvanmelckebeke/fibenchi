from datetime import date

import pandas as pd
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PriceHistory


class PriceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_asset(self, asset_id: int) -> list[PriceHistory]:
        result = await self.db.execute(
            select(PriceHistory)
            .where(PriceHistory.asset_id == asset_id)
            .order_by(PriceHistory.date)
        )
        return list(result.scalars().all())

    async def list_by_asset_since(self, asset_id: int, start: date) -> list[PriceHistory]:
        result = await self.db.execute(
            select(PriceHistory)
            .where(PriceHistory.asset_id == asset_id, PriceHistory.date >= start)
            .order_by(PriceHistory.date)
        )
        return list(result.scalars().all())

    async def list_by_assets_since(
        self, asset_ids: list[int], start: date
    ) -> list[PriceHistory]:
        if not asset_ids:
            return []
        result = await self.db.execute(
            select(PriceHistory)
            .where(
                PriceHistory.asset_id.in_(asset_ids),
                PriceHistory.date >= start,
            )
            .order_by(PriceHistory.asset_id, PriceHistory.date)
        )
        return list(result.scalars().all())

    async def get_latest_date(self, asset_ids: list[int]) -> date | None:
        if not asset_ids:
            return None
        result = await self.db.execute(
            select(func.max(PriceHistory.date)).where(
                PriceHistory.asset_id.in_(asset_ids)
            )
        )
        return result.scalar()

    async def get_first_dates(
        self, asset_ids: list[int], since: date
    ) -> dict[int, date]:
        if not asset_ids:
            return {}
        result = await self.db.execute(
            select(
                PriceHistory.asset_id,
                func.min(PriceHistory.date).label("first_date"),
            )
            .where(PriceHistory.asset_id.in_(asset_ids))
            .where(PriceHistory.date >= since)
            .group_by(PriceHistory.asset_id)
        )
        return {row.asset_id: row.first_date for row in result}

    async def get_last_dates(self, asset_ids: list[int]) -> dict[int, date]:
        if not asset_ids:
            return {}
        result = await self.db.execute(
            select(
                PriceHistory.asset_id,
                func.max(PriceHistory.date).label("last_date"),
            )
            .where(PriceHistory.asset_id.in_(asset_ids))
            .group_by(PriceHistory.asset_id)
        )
        return {row.asset_id: row.last_date for row in result}

    async def get_prices_at_dates(
        self, asset_ids: list[int], dates: set[date]
    ) -> dict[tuple[int, date], float]:
        if not asset_ids or not dates:
            return {}
        result = await self.db.execute(
            select(PriceHistory)
            .where(
                PriceHistory.asset_id.in_(asset_ids),
                PriceHistory.date.in_(list(dates)),
            )
        )
        return {
            (p.asset_id, p.date): float(p.close)
            for p in result.scalars().all()
        }

    async def upsert_prices(self, asset_id: int, df: pd.DataFrame) -> int:
        """Upsert price rows from a DataFrame. Returns row count.

        Uses PostgreSQL ON CONFLICT DO UPDATE. For SQLite (tests), this
        method is typically mocked.
        """
        if df.empty:
            return 0

        from sqlalchemy.dialects.postgresql import insert as pg_insert

        rows = []
        for idx, row in df.iterrows():
            dt = idx.date() if hasattr(idx, "date") else idx
            if not isinstance(dt, date):
                dt = pd.Timestamp(dt).date()

            rows.append({
                "asset_id": asset_id,
                "date": dt,
                "open": round(float(row["open"]), 4),
                "high": round(float(row["high"]), 4),
                "low": round(float(row["low"]), 4),
                "close": round(float(row["close"]), 4),
                "volume": int(row["volume"]) if pd.notna(row["volume"]) else 0,
            })

        stmt = pg_insert(PriceHistory).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_asset_date",
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )
        await self.db.execute(stmt)
        await self.db.commit()
        return len(rows)
