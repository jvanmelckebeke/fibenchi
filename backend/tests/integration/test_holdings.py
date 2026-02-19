"""Tests for the holdings router (ETF holdings + holding indicators)."""

import pytest
from unittest.mock import patch

from app.services.compute.indicators import bb_position
from tests.helpers import make_price_df

pytestmark = pytest.mark.asyncio(loop_scope="function")


# ── Pure unit tests for bb_position ───────────────────────────────────

def test_bb_position_above():
    assert bb_position(close=110, upper=105, middle=100, lower=95) == "above"


def test_bb_position_upper():
    assert bb_position(close=103, upper=105, middle=100, lower=95) == "upper"


def test_bb_position_lower():
    assert bb_position(close=97, upper=105, middle=100, lower=95) == "lower"


def test_bb_position_below():
    assert bb_position(close=90, upper=105, middle=100, lower=95) == "below"


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
        "AAPL": make_price_df(100, 180.0),
        "MSFT": make_price_df(100, 400.0),
    }

    with (
        patch("app.services.holdings_service.fetch_etf_holdings", return_value=_MOCK_HOLDINGS),
        patch("app.services.compute.indicators._batch_fetch_history_sync", return_value=histories),
        patch("app.services.compute.indicators.batch_fetch_currencies", return_value={"AAPL": "USD", "MSFT": "USD"}),
    ):
        resp = await client.get("/api/assets/SPY/holdings/indicators")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["symbol"] == "AAPL"
    assert data[0]["close"] is not None
    assert data[1]["symbol"] == "MSFT"

    # Verify indicator values are nested under 'values'
    from app.services.compute.indicators import get_all_output_fields
    expected_fields = set(get_all_output_fields())
    for item in data:
        assert "values" in item
        values = item["values"]
        # All registry output fields should be present
        for field in expected_fields:
            assert field in values
        # With 100 data points, all indicators should have values
        assert isinstance(values["macd"], float)
        assert isinstance(values["macd_signal"], float)
        assert isinstance(values["bb_upper"], float)
        # Derived fields still present
        assert "macd_signal_dir" in values
        assert "bb_position" in values


async def test_holdings_indicators_not_etf(client):
    """Holdings indicators endpoint returns 400 for stock assets."""
    await client.post("/api/assets", json={"symbol": "AAPL", "name": "Apple", "type": "stock"})

    resp = await client.get("/api/assets/AAPL/holdings/indicators")
    assert resp.status_code == 400


async def test_holdings_indicators_no_data(client):
    """Holdings indicators endpoint returns 404 when no holdings found."""
    await client.post("/api/assets", json={"symbol": "SPY", "name": "SPDR S&P 500", "type": "etf"})

    with patch("app.services.holdings_service.fetch_etf_holdings", return_value=None):
        resp = await client.get("/api/assets/SPY/holdings/indicators")

    assert resp.status_code == 404
