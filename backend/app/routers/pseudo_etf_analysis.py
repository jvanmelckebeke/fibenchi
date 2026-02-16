from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.pseudo_etf import PseudoETF
from app.schemas.pseudo_etf import PerformanceBreakdownPoint, ConstituentIndicatorResponse
from app.services.pseudo_etf import calculate_performance
from app.services.indicators import compute_indicators, build_indicator_snapshot
from app.services.yahoo import batch_fetch_currencies, batch_fetch_history

router = APIRouter(prefix="/api/pseudo-etfs", tags=["pseudo-etfs"])


@router.get("/{etf_id}/performance", response_model=list[PerformanceBreakdownPoint], summary="Get indexed performance with per-constituent breakdown")
async def get_performance(etf_id: int, db: AsyncSession = Depends(get_db)):
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    asset_ids = [a.id for a in etf.constituents]
    if not asset_ids:
        return []

    return await calculate_performance(
        db, asset_ids, etf.base_date, float(etf.base_value), include_breakdown=True
    )


@router.get("/{etf_id}/constituents/indicators", response_model=list[ConstituentIndicatorResponse], summary="Get technical indicators for each constituent")
async def get_constituent_indicators(etf_id: int, db: AsyncSession = Depends(get_db)):
    """Return latest indicator snapshot for each constituent of a pseudo-ETF."""
    etf = await db.get(PseudoETF, etf_id)
    if not etf:
        raise HTTPException(404, "Pseudo-ETF not found")

    if not etf.constituents:
        return []

    # Get latest performance breakdown for weight calculation
    asset_ids = [a.id for a in etf.constituents]
    perf = await calculate_performance(
        db, asset_ids, etf.base_date, float(etf.base_value), include_breakdown=True
    )
    weight_map: dict[str, float] = {}
    if perf:
        last_point = perf[-1]
        breakdown = last_point.get("breakdown", {})
        total = last_point["value"]
        if total > 0:
            weight_map = {sym: round(val / total * 100, 2) for sym, val in breakdown.items()}

    symbols = [a.symbol for a in etf.constituents]
    symbol_to_name = {a.symbol: a.name for a in etf.constituents}

    histories = batch_fetch_history(symbols, period="3mo")
    currencies = batch_fetch_currencies(symbols)

    results = []
    for sym in symbols:
        currency = currencies.get(sym, "USD")
        df = histories.get(sym)
        if df is None or df.empty or len(df) < 2:
            results.append(ConstituentIndicatorResponse(
                symbol=sym,
                name=symbol_to_name.get(sym),
                currency=currency,
                weight_pct=weight_map.get(sym),
            ))
            continue

        snapshot = build_indicator_snapshot(compute_indicators(df))
        results.append(ConstituentIndicatorResponse(
            symbol=sym,
            name=symbol_to_name.get(sym),
            currency=currency,
            weight_pct=weight_map.get(sym),
            **snapshot,
        ))

    return results
