"""
Equal-weight pseudo-ETF performance calculation with quarterly rebalancing.

Algorithm:
1. Fetch daily close prices for all constituents from base_date onward.
2. At base_date, split base_value equally across constituents.
3. Track each constituent's share count (units = allocation / price).
4. At each quarter boundary (Jan 1, Apr 1, Jul 1, Oct 1), rebalance:
   - Compute total portfolio value
   - Re-split equally across constituents
5. Return daily indexed values.
"""

from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.price import PriceHistory


QUARTER_MONTHS = {1, 4, 7, 10}


async def calculate_performance(
    db: AsyncSession,
    asset_ids: list[int],
    base_date: date,
    base_value: float = 100.0,
    include_breakdown: bool = False,
) -> list[dict]:
    """Calculate equal-weight indexed performance for a basket of assets."""
    if not asset_ids:
        return []

    # Build asset_id -> symbol map if breakdown requested
    symbol_map: dict[int, str] = {}
    if include_breakdown:
        asset_stmt = select(Asset).where(Asset.id.in_(asset_ids))
        asset_result = await db.execute(asset_stmt)
        for a in asset_result.scalars().all():
            symbol_map[a.id] = a.symbol

    # Fetch all price history from base_date for the constituents
    stmt = (
        select(PriceHistory)
        .where(PriceHistory.asset_id.in_(asset_ids))
        .where(PriceHistory.date >= base_date)
        .order_by(PriceHistory.date)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    if not rows:
        return []

    # Build a DataFrame: rows=dates, columns=asset_id, values=close price
    data = [(r.date, r.asset_id, float(r.close)) for r in rows]
    df = pd.DataFrame(data, columns=["date", "asset_id", "close"])
    pivot = df.pivot_table(index="date", columns="asset_id", values="close")
    pivot = pivot.sort_index()

    # Forward-fill gaps (weekends, holidays, cross-exchange schedule differences)
    # then drop leading rows where any constituent hasn't started yet
    pivot = pivot.ffill()
    pivot = pivot.dropna()

    if pivot.empty:
        return []

    n = len(asset_ids)
    allocation_per_asset = base_value / n

    # Initialize: compute shares for each constituent at first available date
    first_prices = pivot.iloc[0]
    shares = allocation_per_asset / first_prices  # Series of share counts per asset

    results = []
    prev_month = None

    for dt, prices in pivot.iterrows():
        current_date = dt if isinstance(dt, date) else dt.date() if hasattr(dt, 'date') else dt

        # Check for quarterly rebalance
        if prev_month is not None and current_date.month in QUARTER_MONTHS and current_date.month != prev_month:
            # Rebalance: compute total value, re-split equally
            total_value = float((shares * prices).sum())
            allocation_per_asset = total_value / n
            shares = allocation_per_asset / prices

        portfolio_value = float((shares * prices).sum())
        point: dict = {"date": current_date, "value": round(portfolio_value, 4)}

        if include_breakdown:
            constituent_values = shares * prices
            point["breakdown"] = {
                symbol_map.get(aid, str(aid)): round(float(val), 4)
                for aid, val in constituent_values.items()
            }

        results.append(point)
        prev_month = current_date.month

    return results
