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

Dynamic entry mode (for portfolio overview):
- Assets join the composite when their price first exceeds min_entry_price.
- On entry, the current portfolio value is re-split equally among all active
  assets (existing + new).  This prevents low-IPO-price stocks from getting
  an outsized allocation that distorts returns.
"""

from datetime import date

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.asset_repo import AssetRepository
from app.repositories.price_repo import PriceRepository


QUARTER_MONTHS = {1, 4, 7, 10}


async def calculate_performance(
    db: AsyncSession,
    asset_ids: list[int],
    base_date: date,
    base_value: float = 100.0,
    include_breakdown: bool = False,
    dynamic_entry: bool = False,
    min_entry_price: float = 10.0,
) -> list[dict]:
    """Calculate equal-weight indexed performance for a basket of assets.

    When dynamic_entry=True, assets are added to the composite only once
    their price first exceeds min_entry_price.  This avoids distortion from
    penny-stock IPOs receiving a large equal-weight allocation.
    """
    if not asset_ids:
        return []

    # Build asset_id -> symbol map if breakdown requested
    symbol_map: dict[int, str] = {}
    if include_breakdown:
        assets = await AssetRepository(db).get_by_ids(asset_ids)
        for a in assets:
            symbol_map[a.id] = a.symbol

    # Fetch all price history from base_date for the constituents
    rows = await PriceRepository(db).list_by_assets_since(asset_ids, base_date)

    if not rows:
        return []

    # Build a DataFrame: rows=dates, columns=asset_id, values=close price
    data = [(r.date, r.asset_id, r.close) for r in rows]
    df = pd.DataFrame(data, columns=["date", "asset_id", "close"])
    pivot = df.pivot_table(index="date", columns="asset_id", values="close")
    pivot = pivot.sort_index()

    # Forward-fill gaps (weekends, holidays, cross-exchange schedule differences)
    pivot = pivot.ffill()

    if dynamic_entry:
        return _calc_dynamic(pivot, base_value, min_entry_price, include_breakdown, symbol_map)
    else:
        return _calc_static(pivot, asset_ids, base_value, include_breakdown, symbol_map)


def _calc_static(
    pivot: pd.DataFrame,
    asset_ids: list[int],
    base_value: float,
    include_breakdown: bool,
    symbol_map: dict[int, str],
) -> list[dict]:
    """Original algorithm: all constituents must be present from day 1."""
    pivot = pivot.dropna()
    if pivot.empty:
        return []

    n = len(asset_ids)
    allocation_per_asset = base_value / n
    first_prices = pivot.iloc[0]
    shares = allocation_per_asset / first_prices

    results = []
    prev_month = None

    for dt, prices in pivot.iterrows():
        current_date = dt if isinstance(dt, date) else dt.date() if hasattr(dt, "date") else dt

        if prev_month is not None and current_date.month in QUARTER_MONTHS and current_date.month != prev_month:
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


def _calc_dynamic(
    pivot: pd.DataFrame,
    base_value: float,
    min_entry_price: float,
    include_breakdown: bool,
    symbol_map: dict[int, str],
) -> list[dict]:
    """Dynamic entry: assets join when their price first exceeds the threshold."""
    active: set[int] = set()
    shares = pd.Series(dtype=float)
    portfolio_value = base_value
    results: list[dict] = []
    prev_month = None

    for dt, prices in pivot.iterrows():
        current_date = dt if isinstance(dt, date) else dt.date() if hasattr(dt, "date") else dt

        # Identify new assets that qualify on this date
        new_assets: set[int] = set()
        for aid in pivot.columns:
            if aid in active:
                continue
            price = prices.get(aid)
            if pd.notna(price) and price >= min_entry_price:
                new_assets.add(aid)

        if new_assets:
            # Compute current portfolio value from existing holdings
            if active:
                portfolio_value = float((shares * prices.reindex(list(active))).sum())

            active |= new_assets
            n_active = len(active)
            allocation = portfolio_value / n_active
            # Re-allocate across ALL active assets (existing + new)
            active_prices = prices.reindex(list(active))
            shares = allocation / active_prices

        if not active:
            continue

        # Quarterly rebalance (only among already-active assets)
        if prev_month is not None and current_date.month in QUARTER_MONTHS and current_date.month != prev_month:
            n_active = len(active)
            portfolio_value = float((shares * prices.reindex(list(active))).sum())
            allocation = portfolio_value / n_active
            shares = allocation / prices.reindex(list(active))

        portfolio_value = float((shares * prices.reindex(list(active))).sum())
        point: dict = {"date": current_date, "value": round(portfolio_value, 4)}

        if include_breakdown:
            constituent_values = shares * prices.reindex(list(active))
            point["breakdown"] = {
                symbol_map.get(aid, str(aid)): round(float(val), 4)
                for aid, val in constituent_values.items()
            }

        results.append(point)
        prev_month = current_date.month

    return results
