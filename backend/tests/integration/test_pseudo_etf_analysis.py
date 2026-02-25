"""Integration tests for pseudo-ETF analysis router (performance + constituent indicators)."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import Asset, AssetType, PriceHistory
from app.models.pseudo_etf import PseudoETF

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def _seed_pseudo_etf(db, name: str = "Tech ETF", n_days: int = 60) -> PseudoETF:
    """Create a pseudo-ETF with two constituents and price data."""
    aapl = Asset(symbol="AAPL", name="Apple", type=AssetType.STOCK, currency="USD")
    msft = Asset(symbol="MSFT", name="Microsoft", type=AssetType.STOCK, currency="USD")
    db.add_all([aapl, msft])
    await db.flush()

    etf = PseudoETF(
        name=name,
        base_date=date.today() - timedelta(days=n_days),
        base_value=100.0,
    )
    etf.constituents = [aapl, msft]
    db.add(etf)
    await db.flush()

    today = date.today()
    for asset in [aapl, msft]:
        for i in range(n_days):
            d = today - timedelta(days=n_days - 1 - i)
            if d.weekday() >= 5:
                continue
            price = 100.0 + i * 0.5
            db.add(PriceHistory(
                asset_id=asset.id, date=d,
                open=price - 0.5, high=price + 1.0,
                low=price - 1.0, close=price,
                volume=1_000_000,
            ))
    await db.commit()
    return etf


class TestGetPerformance:
    async def test_returns_performance_data(self, client, db):
        etf = await _seed_pseudo_etf(db)
        resp = await client.get(f"/api/pseudo-etfs/{etf.id}/performance")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        assert "date" in data[0]
        assert "value" in data[0]

    async def test_404_for_nonexistent_etf(self, client):
        resp = await client.get("/api/pseudo-etfs/999/performance")
        assert resp.status_code == 404

    async def test_empty_constituents(self, client, db):
        etf = PseudoETF(
            name="Empty ETF",
            base_date=date.today() - timedelta(days=30),
            base_value=100.0,
        )
        db.add(etf)
        await db.commit()

        resp = await client.get(f"/api/pseudo-etfs/{etf.id}/performance")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_performance_starts_near_base_value(self, client, db):
        etf = await _seed_pseudo_etf(db)
        resp = await client.get(f"/api/pseudo-etfs/{etf.id}/performance")
        data = resp.json()
        assert data[0]["value"] == pytest.approx(100.0, abs=0.5)


class TestGetConstituentIndicators:
    @patch("app.routers.pseudo_etf_analysis.merge_fundamentals_into_batch")
    @patch("app.routers.pseudo_etf_analysis.compute_batch_indicator_snapshots", new_callable=AsyncMock)
    async def test_returns_indicator_data(self, mock_compute, mock_merge, client, db):
        etf = await _seed_pseudo_etf(db)
        mock_compute.return_value = [
            {"symbol": "AAPL", "currency": "USD", "values": {"rsi": 55.0}},
            {"symbol": "MSFT", "currency": "USD", "values": {"rsi": 48.0}},
        ]

        resp = await client.get(f"/api/pseudo-etfs/{etf.id}/constituents/indicators")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        symbols = {d["symbol"] for d in data}
        assert symbols == {"AAPL", "MSFT"}

    async def test_404_for_nonexistent_etf(self, client):
        resp = await client.get("/api/pseudo-etfs/999/constituents/indicators")
        assert resp.status_code == 404

    @patch("app.routers.pseudo_etf_analysis.merge_fundamentals_into_batch")
    @patch("app.routers.pseudo_etf_analysis.compute_batch_indicator_snapshots", new_callable=AsyncMock)
    async def test_empty_constituents(self, mock_compute, mock_merge, client, db):
        etf = PseudoETF(
            name="Empty ETF 2",
            base_date=date.today() - timedelta(days=30),
            base_value=100.0,
        )
        db.add(etf)
        await db.commit()

        resp = await client.get(f"/api/pseudo-etfs/{etf.id}/constituents/indicators")
        assert resp.status_code == 200
        assert resp.json() == []

    @patch("app.routers.pseudo_etf_analysis.merge_fundamentals_into_batch")
    @patch("app.routers.pseudo_etf_analysis.compute_batch_indicator_snapshots", new_callable=AsyncMock)
    async def test_includes_weight_and_name(self, mock_compute, _mock_merge, client, db):
        etf = await _seed_pseudo_etf(db)
        mock_compute.return_value = [
            {"symbol": "AAPL", "currency": "USD", "values": {"rsi": 55.0}},
            {"symbol": "MSFT", "currency": "USD", "values": {"rsi": 48.0}},
        ]

        resp = await client.get(f"/api/pseudo-etfs/{etf.id}/constituents/indicators")
        data = resp.json()
        for item in data:
            assert "name" in item
            assert "weight_pct" in item
