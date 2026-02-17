"""Holdings business logic — ETF top-holdings and per-holding indicators."""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.compute.indicators import compute_batch_indicator_snapshots
from app.services.entity_lookups import get_asset
from app.services.yahoo import fetch_etf_holdings


async def get_holdings(db: AsyncSession, symbol: str) -> dict:
    """Return the top holdings and sector weightings for an ETF."""
    asset = await get_asset(symbol, db)
    if asset.type.value != "etf":
        raise HTTPException(400, f"{symbol} is not an ETF")
    data = await fetch_etf_holdings(symbol)
    if not data:
        raise HTTPException(404, f"No holdings data for {symbol}")
    return data


async def get_holdings_indicators(db: AsyncSession, symbol: str) -> list[dict]:
    """Return latest indicator snapshot for each of the ETF's top holdings."""
    asset = await get_asset(symbol, db)
    if asset.type.value != "etf":
        raise HTTPException(400, f"{symbol} is not an ETF")

    data = await fetch_etf_holdings(symbol)
    if not data:
        raise HTTPException(404, f"No holdings data for {symbol}")

    holding_symbols = [h["symbol"] for h in data["top_holdings"] if h["symbol"]]
    if not holding_symbols:
        return []

    return await compute_batch_indicator_snapshots(holding_symbols)
