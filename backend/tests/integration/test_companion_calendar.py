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
    # Every list field is always sent, so "empty" and "absent" can't be confused
    # by a consumer merging this over a stale cache.
    assert xnys["extraSessions"] == []
    assert isinstance(xnys["halfDays"], list)


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
    assert body["symbols"] == {"AAPL": "XNYS", "NCLR.PA": "XPAR"}

    body = (await client.get("/api/companion/calendar?venues=XPAR,NOPE")).json()
    assert set(body["venues"]) == {"XPAR"}


async def test_unknown_venue_names_never_reach_the_calendar_cache(client):
    from app.services.market_calendar.venue import _venues

    before = set(_venues)
    garbage = ",".join(f"JUNK{n}" for n in range(20))
    assert (await client.get(f"/api/companion/calendar?venues={garbage}")).status_code == 200
    assert set(_venues) == before


async def test_etag_round_trip(client):
    await create_asset_via_api(client, "AAPL", "Apple Inc.")

    first = await client.get("/api/companion/calendar")
    etag = first.headers["etag"]
    assert etag

    again = await client.get("/api/companion/calendar", headers={"If-None-Match": etag})
    assert again.status_code == 304
    assert again.headers["etag"] == etag

    assert first.json()["generatedAt"] != (await client.get("/api/companion/calendar")).json()["generatedAt"]


async def test_etag_changes_when_the_book_changes(client):
    await create_asset_via_api(client, "AAPL", "Apple Inc.")
    etag = (await client.get("/api/companion/calendar")).headers["etag"]

    # Adding a symbol on a new venue must invalidate: the digest has to cover
    # everything a client would act on, symbols and venues included.
    await create_asset_via_api(client, "NCLR.PA", "Nuclear SA")
    resp = await client.get("/api/companion/calendar", headers={"If-None-Match": etag})
    assert resp.status_code == 200
    assert resp.headers["etag"] != etag
