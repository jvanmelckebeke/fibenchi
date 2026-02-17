from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.entity_lookups import get_pseudo_etf
from app.schemas.pseudo_etf import PerformanceBreakdownPoint, ConstituentIndicatorResponse
from app.services.compute.pseudo_etf import calculate_performance
from app.services.compute.indicators import compute_batch_indicator_snapshots

router = APIRouter(prefix="/api/pseudo-etfs", tags=["pseudo-etfs"])


@router.get("/{etf_id}/performance", response_model=list[PerformanceBreakdownPoint], summary="Get indexed performance with per-constituent breakdown")
async def get_performance(etf_id: int, db: AsyncSession = Depends(get_db)):
    etf = await get_pseudo_etf(etf_id, db)

    asset_ids = [a.id for a in etf.constituents]
    if not asset_ids:
        return []

    return await calculate_performance(
        db, asset_ids, etf.base_date, float(etf.base_value), include_breakdown=True
    )


@router.get("/{etf_id}/constituents/indicators", response_model=list[ConstituentIndicatorResponse], summary="Get technical indicators for each constituent")
async def get_constituent_indicators(etf_id: int, db: AsyncSession = Depends(get_db)):
    """Return latest indicator snapshot for each constituent of a pseudo-ETF."""
    etf = await get_pseudo_etf(etf_id, db)

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

    snapshots = await compute_batch_indicator_snapshots(symbols)
    return [
        ConstituentIndicatorResponse(
            **s,
            name=symbol_to_name.get(s["symbol"]),
            weight_pct=weight_map.get(s["symbol"]),
        )
        for s in snapshots
    ]
