import pytest

from tests.helpers import create_asset_via_api

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_calendar_endpoint_shape(client):
    await create_asset_via_api(client, "AAPL", "Apple Inc.")
    await create_asset_via_api(client, "NCLR.PA", "Nuclear SA")

    resp = await client.get("/api/companion/calendar")
    assert resp.status_code == 200
    body = resp.json()

    assert body["version"] == 1
    assert "generatedAt" in body
    assert body["window"]["from"] < body["window"]["to"]

    assert body["symbols"] == {"AAPL": "XNYS", "NCLR.PA": "XPAR"}
    assert set(body["venues"]) == {"XNYS", "XPAR"}
    xnys = body["venues"]["XNYS"]
    assert xnys["timezone"] == "America/New_York"
    assert xnys["tradingDays"] == [1, 2, 3, 4, 5]
    assert all(isinstance(d, str) for d in xnys["closures"])


async def test_unmapped_venue_is_null_and_absent(client):
    # Qatar is Listing(None, "QAR") — exchange_calendars models no such venue,
    # so the symbol maps to null and no venue entry is invented for it.
    await create_asset_via_api(client, "QNBK.QA", "Qatar National Bank")

    body = (await client.get("/api/companion/calendar")).json()
    assert body["symbols"] == {"QNBK.QA": None}
    assert body["venues"] == {}


async def test_venues_filter(client):
    await create_asset_via_api(client, "AAPL", "Apple Inc.")
    await create_asset_via_api(client, "NCLR.PA", "Nuclear SA")

    body = (await client.get("/api/companion/calendar?venues=XPAR,XETR")).json()
    assert set(body["venues"]) == {"XPAR", "XETR"}
    # The symbol map ignores the filter: it is the only place the ticker -> venue
    # mapping exists, and a client needs all of it to use any of it.
    assert body["symbols"] == {"AAPL": "XNYS", "NCLR.PA": "XPAR"}

    # An unknown name in the filter is dropped, not a 400 — same fail-safe
    # posture as the rest of market_calendar.
    body = (await client.get("/api/companion/calendar?venues=XPAR,NOPE")).json()
    assert set(body["venues"]) == {"XPAR"}


async def test_etag_round_trip(client):
    await create_asset_via_api(client, "AAPL", "Apple Inc.")

    first = await client.get("/api/companion/calendar")
    etag = first.headers["etag"]
    assert etag

    again = await client.get("/api/companion/calendar", headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.headers["etag"] == etag

    # generatedAt moves every request and must not be part of the identity,
    # otherwise the ETag would never match and the app would re-download weekly.
    assert first.json()["generatedAt"] != (await client.get("/api/companion/calendar")).json()["generatedAt"]
