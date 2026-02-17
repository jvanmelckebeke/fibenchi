"""Tests for pseudo-ETF performance calculation logic (no DB needed)."""

from datetime import date

import pandas as pd
import pytest


def _calculate_sync(prices_by_asset: dict, base_date: date, base_value: float = 100.0):
    """Synchronous version of the calculation for testing."""
    if not prices_by_asset:
        return []

    frames = []
    for asset_id, price_list in prices_by_asset.items():
        for dt, close in price_list:
            frames.append({"date": dt, "asset_id": asset_id, "close": close})

    df = pd.DataFrame(frames)
    pivot = df.pivot_table(index="date", columns="asset_id", values="close")
    pivot = pivot.sort_index().dropna()

    if pivot.empty:
        return []

    n = len(prices_by_asset)
    allocation = base_value / n
    first_prices = pivot.iloc[0]
    shares = allocation / first_prices

    quarter_months = {1, 4, 7, 10}
    results = []
    prev_month = None

    for dt, prices in pivot.iterrows():
        if prev_month is not None and dt.month in quarter_months and dt.month != prev_month:
            total = float((shares * prices).sum())
            allocation = total / n
            shares = allocation / prices

        val = float((shares * prices).sum())
        results.append({"date": dt, "value": round(val, 4)})
        prev_month = dt.month

    return results


def test_basic_two_stocks():
    """Two stocks, both go up 10% -> portfolio should go up 10%."""
    prices = {
        1: [(date(2025, 1, 2), 100.0), (date(2025, 1, 3), 110.0)],
        2: [(date(2025, 1, 2), 50.0), (date(2025, 1, 3), 55.0)],
    }
    result = _calculate_sync(prices, date(2025, 1, 2), 100.0)
    assert len(result) == 2
    assert result[0]["value"] == 100.0
    assert result[1]["value"] == pytest.approx(110.0)


def test_one_up_one_down():
    """Stock A +20%, Stock B -20% -> portfolio 0%."""
    prices = {
        1: [(date(2025, 1, 2), 100.0), (date(2025, 1, 3), 120.0)],
        2: [(date(2025, 1, 2), 100.0), (date(2025, 1, 3), 80.0)],
    }
    result = _calculate_sync(prices, date(2025, 1, 2), 100.0)
    assert result[1]["value"] == pytest.approx(100.0)


def test_quarterly_rebalance():
    """Test that rebalance occurs at quarter boundary."""
    # Stock A doubles, Stock B stays flat from Jan to Apr
    prices = {
        1: [
            (date(2025, 1, 2), 100.0),
            (date(2025, 3, 31), 200.0),  # A doubled
            (date(2025, 4, 1), 200.0),   # Quarter boundary -> rebalance
            (date(2025, 4, 2), 200.0),   # Same price after rebalance
        ],
        2: [
            (date(2025, 1, 2), 100.0),
            (date(2025, 3, 31), 100.0),  # B flat
            (date(2025, 4, 1), 100.0),
            (date(2025, 4, 2), 100.0),
        ],
    }
    result = _calculate_sync(prices, date(2025, 1, 2), 100.0)

    # Before rebalance: A=100 (worth 50*200/100=100), B=50 -> total=150
    assert result[1]["value"] == pytest.approx(150.0)

    # At rebalance (Apr 1): total 150, re-split to 75 each
    # After: shares_A = 75/200 = 0.375, shares_B = 75/100 = 0.75
    # Value = 0.375*200 + 0.75*100 = 75 + 75 = 150
    assert result[2]["value"] == pytest.approx(150.0)


def test_empty_returns_empty():
    result = _calculate_sync({}, date(2025, 1, 1))
    assert result == []


def test_single_stock():
    """Single-stock pseudo-ETF should track that stock perfectly."""
    prices = {
        1: [(date(2025, 1, 2), 50.0), (date(2025, 1, 3), 60.0), (date(2025, 1, 4), 55.0)],
    }
    result = _calculate_sync(prices, date(2025, 1, 2), 100.0)
    assert result[0]["value"] == pytest.approx(100.0)
    assert result[1]["value"] == pytest.approx(120.0)  # 60/50 * 100
    assert result[2]["value"] == pytest.approx(110.0)  # 55/50 * 100
