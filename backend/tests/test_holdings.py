"""Tests for the holdings router (ETF holdings + holding indicators)."""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from app.services.indicators import bb_position


# ── Pure unit tests for bb_position ───────────────────────────────────

def test_bb_position_above():
    assert bb_position(close=110, upper=105, middle=100, lower=95) == "above"


def test_bb_position_upper():
    assert bb_position(close=103, upper=105, middle=100, lower=95) == "upper"


def test_bb_position_lower():
    assert bb_position(close=97, upper=105, middle=100, lower=95) == "lower"


def test_bb_position_below():
    assert bb_position(close=90, upper=105, middle=100, lower=95) == "below"


# ── Helpers ───────────────────────────────────────────────────────────

def _make_price_df(n: int = 100, start_price: float = 100.0) -> pd.DataFrame:
    """Generate synthetic price data for testing."""
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


_MOCK_HOLDINGS = {
    "top_holdings": [
        {"symbol": "AAPL", "name": "Apple Inc.", "percent": 7.0},
        {"symbol": "MSFT", "name": "Microsoft Corp.", "percent": 6.5},
    ],
    "sector_weightings": [{"sector": "Technology", "percent": 30.0}],
    "total_percent": 13.5,
}


# ── Integration tests ────────────────────────────────────────────────

async def test_holdings_indicators_success(client):
    """Holdings indicators endpoint returns data for ETF with mocked Yahoo."""
    # Create an ETF asset
    await client.post("/api/assets", json={"symbol": "SPY", "name": "SPDR S&P 500", "type": "etf"})

    histories = {
        "AAPL": _make_price_df(100, 180.0),
        "MSFT": _make_price_df(100, 400.0),
    }

    with (
        patch("app.routers.holdings.fetch_etf_holdings", return_value=_MOCK_HOLDINGS),
        patch("app.routers.holdings.batch_fetch_history", return_value=histories),
    ):
        resp = await client.get("/api/assets/SPY/holdings/indicators")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["symbol"] == "AAPL"
    assert data[0]["close"] is not None
    assert data[1]["symbol"] == "MSFT"

    # Verify raw numeric indicator fields are present
    for item in data:
        assert "macd" in item
        assert "macd_signal" in item
        assert "macd_hist" in item
        assert "bb_upper" in item
        assert "bb_middle" in item
        assert "bb_lower" in item
        # With 100 data points, all indicators should have values
        assert isinstance(item["macd"], float)
        assert isinstance(item["macd_signal"], float)
        assert isinstance(item["macd_hist"], float)
        assert isinstance(item["bb_upper"], float)
        assert isinstance(item["bb_middle"], float)
        assert isinstance(item["bb_lower"], float)
        # Classified fields still present
        assert "macd_signal_dir" in item
        assert "bb_position" in item


async def test_holdings_indicators_not_etf(client):
    """Holdings indicators endpoint returns 400 for stock assets."""
    await client.post("/api/assets", json={"symbol": "AAPL", "name": "Apple", "type": "stock"})

    resp = await client.get("/api/assets/AAPL/holdings/indicators")
    assert resp.status_code == 400


async def test_holdings_indicators_no_data(client):
    """Holdings indicators endpoint returns 404 when no holdings found."""
    await client.post("/api/assets", json={"symbol": "SPY", "name": "SPDR S&P 500", "type": "etf"})

    with patch("app.routers.holdings.fetch_etf_holdings", return_value=None):
        resp = await client.get("/api/assets/SPY/holdings/indicators")

    assert resp.status_code == 404
