"""Portfolio business logic — composite index and performer ranking."""

from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import PERIOD_DAYS
from app.repositories.asset_repo import AssetRepository
from app.repositories.price_repo import PriceRepository
from app.services.compute.pseudo_etf import calculate_performance

# Minimum stock price before an asset is included in the composite index.
# Prevents low-IPO-price stocks from distorting equal-weight returns.
_MIN_ENTRY_PRICE = 10.0


async def compute_portfolio_index(
    db: AsyncSession, period: str = "1y",
) -> dict:
    """Compute equal-weight composite index of all grouped assets.

    Returns dict with keys: dates, values, current, change, change_pct.
    """
    days = PERIOD_DAYS.get(period, 365)
    start_date = date.today() - timedelta(days=days)

    asset_ids = await AssetRepository(db).list_in_any_group_ids()

    empty = {"dates": [], "values": [], "current": 0, "change": 0, "change_pct": 0}

    if not asset_ids:
        return empty

    points = await calculate_performance(
        db, asset_ids, start_date, base_value=1000.0,
        dynamic_entry=True, min_entry_price=_MIN_ENTRY_PRICE,
    )

    if not points:
        return empty

    dates = [p["date"] for p in points]
    values = [p["value"] for p in points]
    current = values[-1]
    first = values[0]
    change = current - first
    change_pct = (change / first) * 100 if first != 0 else 0

    return {
        "dates": dates,
        "values": values,
        "current": round(current, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
    }


async def compute_performers(
    db: AsyncSession, period: str = "1y",
) -> list[dict]:
    """Return grouped assets ranked by period return (best first).

    Returns list of dicts with keys: symbol, name, type, change_pct.
    """
    days = PERIOD_DAYS.get(period, 365)
    start_date = date.today() - timedelta(days=days)

    asset_repo = AssetRepository(db)
    price_repo = PriceRepository(db)

    assets = await asset_repo.list_in_any_group()

    if not assets:
        return []

    asset_map = {a.id: a for a in assets}
    asset_ids = list(asset_map.keys())

    first_dates = await price_repo.get_first_dates(asset_ids, start_date)
    last_dates = await price_repo.get_last_dates(asset_ids)

    # Collect all dates we need prices for
    all_dates: set[date] = set()
    for aid in asset_ids:
        if aid in first_dates:
            all_dates.add(first_dates[aid])
        if aid in last_dates:
            all_dates.add(last_dates[aid])

    if not all_dates:
        return []

    price_map = await price_repo.get_prices_at_dates(asset_ids, all_dates)

    performers = []
    for aid, asset in asset_map.items():
        first_d = first_dates.get(aid)
        last_d = last_dates.get(aid)
        if not first_d or not last_d or first_d == last_d:
            continue
        first_close = price_map.get((aid, first_d))
        last_close = price_map.get((aid, last_d))
        if first_close and last_close and first_close > 0:
            pct = ((last_close - first_close) / first_close) * 100
            performers.append({
                "symbol": asset.symbol,
                "name": asset.name,
                "type": asset.type.value,
                "change_pct": round(pct, 2),
            })

    performers.sort(key=lambda p: p["change_pct"], reverse=True)
    return performers
