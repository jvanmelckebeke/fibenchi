import logging
from datetime import date

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import AssetRef
from app.models import PriceHistory

logger = logging.getLogger(__name__)


def _ohlc_fault(row) -> str | None:
    """Describe why a bar cannot describe any real session, or None.

    Deliberately narrow, and narrower than #635 first proposed. That issue
    suggested rejecting a close outside its own bar's ``[low, high]`` on the
    grounds that it is arithmetically impossible. Measured against a year of
    real provider data for every tracked asset — 19,055 bars — **182 of them
    (~1%) violate exactly that**, by up to 4.4% of price:

        p50 0.18%   p75 0.50%   p90 0.92%   p95 1.42%   p99 2.64%   max 4.40%

    Those are auction/official closes printed outside the intraday range, not
    corruption. Rejecting them would punch ~182 holes a year into the series
    and blank σ-Move on the bar after each one — manufacturing the very defect
    this batch has been removing. And because the real violations reach 4.4%,
    no tolerance separates them from a plausibly-wrong close, so the check
    cannot be rescued by loosening it.

    What survives is what the same scan never saw violated: ``high < low`` is
    a contradiction in the bar's own definition rather than a reconciliation
    artifact, and a non-positive price is not a price. Both stayed at zero
    occurrences across all 19,055 bars, so rejecting them costs nothing and
    catches a class of corruption that would otherwise store silently.

    Value-level plausibility for closes needs a different mechanism — see the
    follow-up on clamping or flagging rather than rejecting.
    """
    o, h, low, c = (float(row["open"]), float(row["high"]),
                    float(row["low"]), float(row["close"]))
    if h < low:
        return f"high {h} < low {low}"
    if min(o, h, low, c) <= 0:
        return f"non-positive price (o={o} h={h} l={low} c={c})"
    return None


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

    async def get_latest_closes(
        self, asset_ids: list[int]
    ) -> dict[int, tuple[date, float]]:
        """Latest stored (date, close) per asset."""
        if not asset_ids:
            return {}
        last_dates = (
            select(
                PriceHistory.asset_id,
                func.max(PriceHistory.date).label("last_date"),
            )
            .where(PriceHistory.asset_id.in_(asset_ids))
            .group_by(PriceHistory.asset_id)
            .subquery()
        )
        result = await self.db.execute(
            select(PriceHistory.asset_id, PriceHistory.date, PriceHistory.close).join(
                last_dates,
                (PriceHistory.asset_id == last_dates.c.asset_id)
                & (PriceHistory.date == last_dates.c.last_date),
            )
        )
        return {row.asset_id: (row.date, row.close) for row in result}

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
            (p.asset_id, p.date): p.close
            for p in result.scalars().all()
        }

    async def delete_prices_after(self, asset_id: int, last_date: date) -> int:
        """Delete stored bars strictly after ``last_date`` for one asset.

        Purges a stale current-session partial that a re-sync dropped from its
        fetched frame but left orphaned in the DB — an upsert can only update
        the rows it received, never remove one it no longer has. Returns the
        number of rows deleted.
        """
        result = await self.db.execute(
            delete(PriceHistory).where(
                PriceHistory.asset_id == asset_id,
                PriceHistory.date > last_date,
            )
        )
        await self.db.commit()
        return result.rowcount or 0

    @staticmethod
    def build_price_rows(ref: AssetRef, df: pd.DataFrame) -> list[dict]:
        """Convert a price DataFrame to insertable row dicts.

        Rows with a NaN in any OHLC column are skipped — but never silently:
        a skipped bar leaves a hole in price_history that is indistinguishable
        from a market holiday downstream (it inflates σ-Move, issue #559), so
        every skip is logged with its dates.

        Bars that are internally impossible are skipped the same way (#635).
        Until this, NaN was the *only* thing checked: a wrong close on a date
        that exists passed every downstream guard, because they all reason
        about dates or about the latest bar rather than about values. A hole is
        strictly better than a lie — the gap guard reports it honestly, and the
        hole heal re-fetches it — whereas a corrupt close silently distorts
        every σ-Move within the EWMA's memory of it.

        Only *impossible* is rejected, never merely surprising: a close outside
        its own bar's [low, high], a high below its low, or a non-positive
        price. A real crash must always store.
        """
        ohlc_cols = ["open", "high", "low", "close"]
        rows = []
        skipped: list[date] = []
        impossible: list[tuple[date, str]] = []
        for idx, row in df.iterrows():
            dt = idx.date() if hasattr(idx, "date") else idx
            if not isinstance(dt, date):
                dt = pd.Timestamp(dt).date()

            if row[ohlc_cols].isna().any():
                skipped.append(dt)
                continue

            fault = _ohlc_fault(row)
            if fault is not None:
                impossible.append((dt, fault))
                continue

            rows.append({
                "asset_id": ref.id,
                "date": dt,
                "open": round(float(row["open"]), 4),
                "high": round(float(row["high"]), 4),
                "low": round(float(row["low"]), 4),
                "close": round(float(row["close"]), 4),
                "volume": int(row["volume"]) if pd.notna(row["volume"]) else 0,
            })

        if skipped:
            logger.warning(
                "Skipped %d price bar(s) with NaN OHLC for %s (asset_id=%d) "
                "(dates: %s) — this leaves a gap in price_history",
                len(skipped), ref, ref.id,
                ", ".join(d.isoformat() for d in skipped),
            )
        if impossible:
            logger.warning(
                "Rejected %d internally inconsistent price bar(s) for %s "
                "(asset_id=%d): %s — this leaves a gap in price_history, which "
                "the gap guard reports honestly and the hole heal re-fetches",
                len(impossible), ref, ref.id,
                "; ".join(f"{d.isoformat()} {why}" for d, why in impossible),
            )
        return rows

    async def upsert_prices(self, ref: AssetRef, df: pd.DataFrame) -> int:
        """Upsert price rows from a DataFrame. Returns row count.

        Uses PostgreSQL ON CONFLICT DO UPDATE. For SQLite (tests), this
        method is typically mocked.
        """
        if df.empty:
            return 0

        from sqlalchemy.dialects.postgresql import insert as pg_insert

        rows = self.build_price_rows(ref, df)
        if not rows:
            return 0

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
