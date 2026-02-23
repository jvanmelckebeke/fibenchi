"""Price and indicator business logic — ensures data, caching, ephemeral fetch."""

from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

import pandas as pd

from app.constants import PERIOD_DAYS, WARMUP_DAYS
from app.models import Asset, PriceHistory
from app.repositories.price_repo import PriceRepository
from app.schemas.price import AssetDetailResponse, IndicatorResponse, PriceResponse
from app.services.compute.indicators import INDICATOR_REGISTRY, compute_indicators, safe_round
from app.services.compute.utils import prices_to_df
from app.services.price_sync import sync_asset_prices, sync_asset_prices_range
from app.services.yahoo import fetch_history
from app.utils import TTLCache

# In-memory indicator cache: keyed by "SYMBOL:period:last_price_date"
_indicator_cache: TTLCache = TTLCache(default_ttl=300, max_size=200)

# Cache of earliest known price dates per asset.  Keyed by asset_id, stores the
# earliest date available after a backfill attempt was made.  When a requested
# period starts before this date we know Yahoo has no data for the gap, so we
# skip the fetch.  TTL of 24h means at most one redundant Yahoo call per day per
# asset after a restart — acceptable since the daily cron updates prices anyway.
_earliest_date_cache: TTLCache = TTLCache(default_ttl=86400, max_size=500)


def _display_start(period: str) -> date:
    """Return the earliest date to include in the response for a given period."""
    days = PERIOD_DAYS.get(period, 90)
    return date.today() - timedelta(days=days)


def _backfill_already_attempted(asset_id: int, requested_start: date) -> bool:
    """Check if we already know that no data exists before the cached earliest date.

    Returns True if we previously attempted a backfill for this asset and the
    earliest available date in the DB is still after ``requested_start``.  This
    means Yahoo has no data for the gap, so fetching again would be a no-op.
    """
    cached_earliest = _earliest_date_cache.get_value(asset_id)
    if cached_earliest is None:
        return False
    # If the requested start is before (or equal to) what we already know is
    # the earliest available date, skip the fetch — there's nothing to get.
    return requested_start <= cached_earliest


async def _fetch_ephemeral(symbol: str, period: str, warmup: bool = False) -> pd.DataFrame:
    """Fetch price data from Yahoo without persisting to DB."""
    days = PERIOD_DAYS.get(period, 90)
    if warmup:
        days += WARMUP_DAYS
    start_date = date.today() - timedelta(days=days)
    try:
        df = await fetch_history(symbol.upper(), start=start_date, end=date.today())
    except (ValueError, KeyError):
        raise HTTPException(404, f"No price data available for {symbol}")

    if df.empty:
        raise HTTPException(404, f"No price data available for {symbol}")

    if hasattr(df.index, "date"):
        df.index = df.index.date

    return df


async def _ensure_prices(db: AsyncSession, asset: Asset, period: str) -> list[PriceHistory]:
    """Load all prices from DB, fetching from Yahoo if the requested period isn't covered."""
    price_repo = PriceRepository(db)
    prices = await price_repo.list_by_asset(asset.id)

    needed_start = _display_start(period)

    if not prices:
        count = await sync_asset_prices(db, asset, period=period)
        if count == 0:
            raise HTTPException(404, f"No price data available for {asset.symbol}")
        prices = await price_repo.list_by_asset(asset.id)
        if not prices:
            raise HTTPException(404, f"No price data available for {asset.symbol}")
    elif prices[0].date > needed_start:
        if not _backfill_already_attempted(asset.id, needed_start):
            earliest_before = prices[0].date
            await sync_asset_prices_range(db, asset, needed_start, date.today())
            prices = await price_repo.list_by_asset(asset.id)
            # If the earliest date didn't move, Yahoo has no data for the gap.
            # Cache this so future requests skip the fetch.
            if prices and prices[0].date >= earliest_before:
                _earliest_date_cache.set_value(asset.id, prices[0].date)

    return prices


async def _ensure_warmup_prices(
    db: AsyncSession, asset: Asset, prices: list[PriceHistory], start: date,
) -> list[PriceHistory]:
    """Backfill warmup-period prices if the stored history doesn't reach far enough back.

    Checks whether the earliest stored price is after the warmup start date.
    If so, attempts to sync the missing range from Yahoo.  Returns the
    (possibly updated) price list.
    """
    warmup_start = start - timedelta(days=WARMUP_DAYS)

    if prices and prices[0].date > warmup_start:
        if not _backfill_already_attempted(asset.id, warmup_start):
            earliest_before = prices[0].date
            await sync_asset_prices_range(db, asset, warmup_start, date.today())
            prices = await PriceRepository(db).list_by_asset(asset.id)
            if prices and prices[0].date >= earliest_before:
                _earliest_date_cache.set_value(asset.id, prices[0].date)

    return prices


def _df_to_price_rows(df: pd.DataFrame, start: date) -> list[PriceResponse]:
    rows = []
    for dt, row in df.iterrows():
        if dt < start:
            continue
        rows.append(PriceResponse(
            date=dt,
            open=round(float(row["open"]), 4),
            high=round(float(row["high"]), 4),
            low=round(float(row["low"]), 4),
            close=round(float(row["close"]), 4),
            volume=int(row["volume"]),
        ))
    return rows


def _df_to_indicator_rows(indicators: pd.DataFrame, start: date) -> list[IndicatorResponse]:
    rows = []
    for dt, row in indicators.iterrows():
        if dt < start:
            continue
        values: dict[str, float | None] = {}
        for defn in INDICATOR_REGISTRY.values():
            for col in defn.output_fields:
                decimals = defn.field_decimals.get(col, defn.decimals)
                values[col] = safe_round(row[col], decimals)
        rows.append(IndicatorResponse(
            date=dt,
            close=round(row["close"], 4),
            values=values,
        ))
    return rows


async def get_prices(db: AsyncSession, asset: Asset | None, symbol: str, period: str):
    if asset:
        prices = await _ensure_prices(db, asset, period)
        start = _display_start(period)
        return [p for p in prices if p.date >= start]

    df = await _fetch_ephemeral(symbol, period)
    return _df_to_price_rows(df, _display_start(period))


async def _compute_or_cached_indicators(
    db: AsyncSession, asset: Asset | None, symbol: str, period: str,
) -> tuple[list[IndicatorResponse], pd.DataFrame | None]:
    """Shared indicator computation with caching.

    Returns (indicator_rows, df_or_none).  ``df_or_none`` is the full
    DataFrame (including warmup) when indicators were freshly computed
    (callers may need it for price rows), or ``None`` when the result
    came from the cache.
    """
    start = _display_start(period)

    if asset:
        prices = await _ensure_prices(db, asset, period)
        last_date = prices[-1].date

        cache_key = f"{symbol}:{period}:{last_date}"
        cached = _indicator_cache.get_value(cache_key)
        if cached is not None:
            return cached, None

        prices = await _ensure_warmup_prices(db, asset, prices, start)
        df = prices_to_df(prices)
    else:
        cache_key = None
        df = await _fetch_ephemeral(symbol, period, warmup=True)

    rows = _df_to_indicator_rows(compute_indicators(df), start)

    if cache_key:
        _indicator_cache.set_value(cache_key, rows)

    return rows, df


async def get_indicators(db: AsyncSession, asset: Asset | None, symbol: str, period: str):
    rows, _ = await _compute_or_cached_indicators(db, asset, symbol, period)
    return rows


async def get_detail(db: AsyncSession, asset: Asset | None, symbol: str, period: str):
    start = _display_start(period)

    indicator_rows, df = await _compute_or_cached_indicators(db, asset, symbol, period)

    if asset:
        if df is not None:
            # Freshly computed — we have the full warmup DF; filter price rows
            price_rows = _df_to_price_rows(df, start)
        else:
            # Cache hit — fetch display prices from DB directly
            prices = await _ensure_prices(db, asset, period)
            price_rows = [p for p in prices if p.date >= start]
    else:
        # Ephemeral — df was computed fresh, use it for price rows
        price_rows = _df_to_price_rows(df, start)

    return AssetDetailResponse(prices=price_rows, indicators=indicator_rows)


async def refresh_prices(db: AsyncSession, asset: Asset, period: str):
    count = await sync_asset_prices(db, asset, period=period)
    return {"symbol": asset.symbol, "synced": count}
