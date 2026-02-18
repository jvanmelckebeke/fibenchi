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
from app.services.price_sync import sync_asset_prices, sync_asset_prices_range
from app.services.yahoo import fetch_history
from app.utils import TTLCache

# In-memory indicator cache: keyed by "SYMBOL:period:last_price_date"
_indicator_cache: TTLCache = TTLCache(default_ttl=300, max_size=200)


def _display_start(period: str) -> date:
    """Return the earliest date to include in the response for a given period."""
    days = PERIOD_DAYS.get(period, 90)
    return date.today() - timedelta(days=days)


async def _fetch_ephemeral(symbol: str, period: str, warmup: bool = False) -> pd.DataFrame:
    """Fetch price data from Yahoo without persisting to DB."""
    days = PERIOD_DAYS.get(period, 90)
    if warmup:
        days += WARMUP_DAYS
    start_date = date.today() - timedelta(days=days)
    try:
        df = await fetch_history(symbol.upper(), start=start_date, end=date.today())
    except (ValueError, Exception):
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
    elif prices[0].date > needed_start:
        await sync_asset_prices_range(db, asset, needed_start, date.today())

    if not prices or prices[0].date > needed_start:
        prices = await price_repo.list_by_asset(asset.id)

    return prices


def _prices_to_df(prices: list[PriceHistory]) -> pd.DataFrame:
    return pd.DataFrame([{
        "date": p.date,
        "open": float(p.open),
        "high": float(p.high),
        "low": float(p.low),
        "close": float(p.close),
        "volume": p.volume,
    } for p in prices]).set_index("date")


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
                values[col] = safe_round(row[col], defn.decimals)
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


async def get_indicators(db: AsyncSession, asset: Asset | None, symbol: str, period: str):
    start = _display_start(period)

    if asset:
        prices = await _ensure_prices(db, asset, period)
        last_date = prices[-1].date if prices else None

        cache_key = f"{symbol}:{period}:{last_date}"
        cached = _indicator_cache.get_value(cache_key)
        if cached is not None:
            return cached

        warmup_start = start - timedelta(days=WARMUP_DAYS)

        if prices and prices[0].date > warmup_start:
            await sync_asset_prices_range(db, asset, warmup_start, date.today())
            prices = await PriceRepository(db).list_by_asset(asset.id)

        df = _prices_to_df(prices)
    else:
        cache_key = None
        df = await _fetch_ephemeral(symbol, period, warmup=True)

    rows = _df_to_indicator_rows(compute_indicators(df), start)

    if cache_key:
        _indicator_cache.set_value(cache_key, rows)

    return rows


async def get_detail(db: AsyncSession, asset: Asset | None, symbol: str, period: str):
    start = _display_start(period)

    if asset:
        prices = await _ensure_prices(db, asset, period)
        price_rows = [p for p in prices if p.date >= start]

        last_date = prices[-1].date if prices else None
        cache_key = f"{symbol}:{period}:{last_date}"
        cached = _indicator_cache.get_value(cache_key)
        if cached is not None:
            return AssetDetailResponse(prices=price_rows, indicators=cached)

        warmup_start = start - timedelta(days=WARMUP_DAYS)
        if prices and prices[0].date > warmup_start:
            await sync_asset_prices_range(db, asset, warmup_start, date.today())
            prices = await PriceRepository(db).list_by_asset(asset.id)

        df = _prices_to_df(prices)
    else:
        cache_key = None
        df = await _fetch_ephemeral(symbol, period, warmup=True)
        price_rows = _df_to_price_rows(df, start)

    indicator_rows = _df_to_indicator_rows(compute_indicators(df), start)

    if cache_key:
        _indicator_cache.set_value(cache_key, indicator_rows)

    return AssetDetailResponse(prices=price_rows, indicators=indicator_rows)


async def refresh_prices(db: AsyncSession, asset: Asset, period: str):
    count = await sync_asset_prices(db, asset, period=period)
    return {"symbol": asset.symbol, "synced": count}
