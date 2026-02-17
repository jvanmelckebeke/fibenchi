"""Unit tests for holdings_service — tests service logic with mocked lookups."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.holdings_service import get_holdings, get_holdings_indicators

pytestmark = pytest.mark.asyncio(loop_scope="function")


def _make_etf_asset(symbol: str = "SPY"):
    asset = MagicMock()
    asset.symbol = symbol
    asset.type = MagicMock()
    asset.type.value = "etf"
    return asset


def _make_stock_asset(symbol: str = "AAPL"):
    asset = MagicMock()
    asset.symbol = symbol
    asset.type = MagicMock()
    asset.type.value = "stock"
    return asset


def _sample_holdings():
    return {
        "top_holdings": [
            {"symbol": "AAPL", "name": "Apple", "weight": 0.07},
            {"symbol": "MSFT", "name": "Microsoft", "weight": 0.06},
        ],
        "sector_weightings": {"Technology": 0.30},
    }


@patch("app.services.holdings_service.fetch_etf_holdings", new_callable=AsyncMock)
@patch("app.services.holdings_service.get_asset", new_callable=AsyncMock)
async def test_get_holdings_returns_data_for_valid_etf(mock_get_asset, mock_fetch):
    db = AsyncMock()
    mock_get_asset.return_value = _make_etf_asset("SPY")
    holdings = _sample_holdings()
    mock_fetch.return_value = holdings

    result = await get_holdings(db, "SPY")

    mock_get_asset.assert_awaited_once_with("SPY", db)
    mock_fetch.assert_awaited_once_with("SPY")
    assert result == holdings


@patch("app.services.holdings_service.get_asset", new_callable=AsyncMock)
async def test_get_holdings_raises_400_for_non_etf(mock_get_asset):
    db = AsyncMock()
    mock_get_asset.return_value = _make_stock_asset("AAPL")

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await get_holdings(db, "AAPL")
    assert exc_info.value.status_code == 400


@patch("app.services.holdings_service.fetch_etf_holdings", new_callable=AsyncMock)
@patch("app.services.holdings_service.get_asset", new_callable=AsyncMock)
async def test_get_holdings_raises_404_when_no_holdings_data(mock_get_asset, mock_fetch):
    db = AsyncMock()
    mock_get_asset.return_value = _make_etf_asset("SPY")
    mock_fetch.return_value = None

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await get_holdings(db, "SPY")
    assert exc_info.value.status_code == 404


@patch("app.services.holdings_service.compute_batch_indicator_snapshots", new_callable=AsyncMock)
@patch("app.services.holdings_service.fetch_etf_holdings", new_callable=AsyncMock)
@patch("app.services.holdings_service.get_asset", new_callable=AsyncMock)
async def test_get_holdings_indicators_returns_snapshots(
    mock_get_asset, mock_fetch, mock_compute
):
    db = AsyncMock()
    mock_get_asset.return_value = _make_etf_asset("SPY")
    mock_fetch.return_value = _sample_holdings()
    snapshots = [{"symbol": "AAPL", "rsi": 55.0}, {"symbol": "MSFT", "rsi": 60.0}]
    mock_compute.return_value = snapshots

    result = await get_holdings_indicators(db, "SPY")

    mock_compute.assert_awaited_once_with(["AAPL", "MSFT"])
    assert result == snapshots


@patch("app.services.holdings_service.fetch_etf_holdings", new_callable=AsyncMock)
@patch("app.services.holdings_service.get_asset", new_callable=AsyncMock)
async def test_get_holdings_indicators_returns_empty_when_no_holding_symbols(
    mock_get_asset, mock_fetch
):
    db = AsyncMock()
    mock_get_asset.return_value = _make_etf_asset("SPY")
    mock_fetch.return_value = {
        "top_holdings": [{"symbol": "", "name": "Unknown", "weight": 0.01}],
        "sector_weightings": {},
    }

    result = await get_holdings_indicators(db, "SPY")

    assert result == []


@patch("app.services.holdings_service.get_asset", new_callable=AsyncMock)
async def test_get_holdings_indicators_raises_400_for_non_etf(mock_get_asset):
    db = AsyncMock()
    mock_get_asset.return_value = _make_stock_asset("AAPL")

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await get_holdings_indicators(db, "AAPL")
    assert exc_info.value.status_code == 400
