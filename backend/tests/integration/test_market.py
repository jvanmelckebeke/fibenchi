"""Tests for GET /api/market/phases."""

from datetime import datetime

import pytest

from app.domain import AssetRef
from tests.helpers import seed_asset_with_prices

pytestmark = pytest.mark.asyncio(loop_scope="function")

PHASES = {"premarket", "open", "aftermarket", "closed"}


async def test_market_phases_lists_in_use_calendars(client, db):
    """Grouped assets' calendars appear, deduped, with a valid phase."""
    await seed_asset_with_prices(db, "AAPL", n_days=5)
    await seed_asset_with_prices(db, "MSFT", n_days=5)  # same calendar — must dedupe
    await seed_asset_with_prices(db, "IWDA.AS", n_days=5)
    await db.commit()

    resp = await client.get("/api/market/phases")
    assert resp.status_code == 200
    data = resp.json()

    us = AssetRef("AAPL").calendar_name
    ams = AssetRef("IWDA.AS").calendar_name
    assert set(data) == {us, ams}
    assert data[us]["symbols"] == ["AAPL", "MSFT"]
    assert data[ams]["symbols"] == ["IWDA.AS"]
    for entry in data.values():
        assert entry["phase"] in PHASES
        if entry["next_change_at"] is not None:
            # ISO datetime, parseable and tz-aware
            assert datetime.fromisoformat(entry["next_change_at"]).tzinfo is not None


async def test_market_phases_empty_without_grouped_assets(client):
    resp = await client.get("/api/market/phases")
    assert resp.status_code == 200
    assert resp.json() == {}


async def test_market_phases_skips_ungrouped_assets(client, db):
    """Assets outside any group don't contribute their calendar."""
    await seed_asset_with_prices(db, "AAPL", n_days=5, add_to_group=False)
    await db.commit()

    resp = await client.get("/api/market/phases")
    assert resp.status_code == 200
    assert resp.json() == {}
