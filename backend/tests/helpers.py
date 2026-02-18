"""Shared test helpers — extracted from integration tests to avoid duplication."""

from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.models import Asset, AssetType, PriceHistory
from app.repositories.group_repo import GroupRepository


async def create_asset_via_api(client, symbol: str, name: str, **kwargs) -> dict:
    """Create an asset through the HTTP API and return the JSON response."""
    resp = await client.post("/api/assets", json={"symbol": symbol, "name": name, **kwargs})
    return resp.json()


async def seed_asset_with_prices(
    db, symbol: str = "AAPL", name: str | None = None, n_days: int = 500,
    base_price: float = 150.0, add_to_group: bool = True,
) -> Asset:
    """Create an asset with n_days of realistic price data.

    When add_to_group is True (default), the asset is added to the default
    default group so it appears in group/portfolio queries.
    """
    asset = Asset(
        symbol=symbol, name=name or f"{symbol} Inc.",
        type=AssetType.STOCK, currency="USD",
    )
    db.add(asset)
    await db.flush()

    if add_to_group:
        default_group = await GroupRepository(db).get_default()
        if default_group:
            default_group.assets.append(asset)

    today = date.today()
    for i in range(n_days):
        d = today - timedelta(days=n_days - 1 - i)
        if d.weekday() >= 5:
            continue
        price = base_price + i * 0.1
        db.add(PriceHistory(
            asset_id=asset.id, date=d,
            open=round(price - 0.5, 4), high=round(price + 1.0, 4),
            low=round(price - 1.0, 4), close=round(price, 4),
            volume=1_000_000 + i * 1000,
        ))
    await db.commit()
    return asset


def make_yahoo_df(n_days: int = 60, base_price: float = 100.0) -> pd.DataFrame:
    """Create a DataFrame that looks like Yahoo Finance output."""
    dates = pd.bdate_range(end=date.today(), periods=n_days)
    prices = [base_price + i * 0.5 for i in range(n_days)]
    return pd.DataFrame({
        "open": [p - 0.5 for p in prices],
        "high": [p + 1.0 for p in prices],
        "low": [p - 1.0 for p in prices],
        "close": prices,
        "volume": [1_000_000] * n_days,
    }, index=dates)


def make_price_df(n: int = 100, start_price: float = 100.0) -> pd.DataFrame:
    """Generate synthetic price data for testing (seeded for reproducibility)."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    returns = np.random.normal(0.001, 0.02, n)
    prices = start_price * np.cumprod(1 + returns)

    return pd.DataFrame({
        "open": prices * (1 - np.random.uniform(0, 0.01, n)),
        "high": prices * (1 + np.random.uniform(0, 0.02, n)),
        "low": prices * (1 - np.random.uniform(0, 0.02, n)),
        "close": prices,
        "volume": np.random.randint(1_000_000, 10_000_000, n),
    }, index=dates)
