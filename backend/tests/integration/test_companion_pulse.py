import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
import pytest

from app.domain import AssetRef
from app.main import app
from app.models import Asset, AssetType, PriceHistory
from app.repositories.group_repo import GroupRepository
from app.services import companion_pulse_service, move_scale_service
from app.services.companion_pulse_service import CLOSES_WINDOW_DAYS, invalidate_pulse_cache
from app.services.compute.group import compute_ref_indicators, indicator_history_start
from app.services.compute.move_scale import MOVE_WINDOWS, move_scale
from app.services.price_sync import _upsert_prices
from app.services.quote_service import _reset_asset_list_cache
from tests.conftest import TestSession
from tests.helpers import seed_asset_with_prices

pytestmark = pytest.mark.asyncio(loop_scope="function")


@pytest.fixture(autouse=True)
def _clear_pulse_cache():
    companion_pulse_service._pulse_cache.clear()
    move_scale_service._move_scale_cache.clear()
    yield
    companion_pulse_service._pulse_cache.clear()
    move_scale_service._move_scale_cache.clear()


async def _seed(
    db, symbol: str, closes: list[float], dates: list[date], currency: str = "USD",
    group: bool = True,
) -> Asset:
    asset = Asset(symbol=symbol, name=symbol, type=AssetType.STOCK, currency=currency)
    db.add(asset)
    await db.flush()
    if group:
        watchlist = await GroupRepository(db).get_default()
        watchlist.assets.append(asset)
    for d, c in zip(dates, closes):
        db.add(PriceHistory(
            asset_id=asset.id, date=d, open=c, high=c * 1.01, low=c * 0.99, close=c, volume=1_000,
        ))
    await db.commit()
    return asset


def _walk(n: int, start: float = 100.0, seed: int = 7) -> list[float]:
    rng = np.random.default_rng(seed)
    return [round(float(x), 4) for x in start * np.cumprod(1 + rng.normal(0, 0.015, n))]


def _weekdays(n: int) -> list[date]:
    return [d.date() for d in pd.bdate_range(end=date.today(), periods=n)]


async def _indicators(db, symbol: str) -> pd.DataFrame:
    asset = (await db.execute(Asset.__table__.select().where(Asset.symbol == symbol))).first()
    rows = (await db.execute(
        PriceHistory.__table__.select().where(PriceHistory.asset_id == asset.id).order_by(PriceHistory.date)
    )).all()
    since = indicator_history_start()
    return compute_ref_indicators(AssetRef(symbol, asset.id), [r for r in rows if r.date >= since])


async def test_pulse_shape(client, db):
    await seed_asset_with_prices(db, symbol="AAPL", n_days=400)

    resp = await client.get("/api/companion/pulse")
    assert resp.status_code == 200
    body = resp.json()

    assert body["version"] == 1
    assert "generatedAt" in body
    assert body["missing"] == []
    assert set(body["symbols"]) == {"AAPL"}
    pulse = body["symbols"]["AAPL"]
    assert set(pulse) == {"closes", "tail", "moveScale"}
    assert set(pulse["closes"][0]) == {"date", "close"}
    assert set(pulse["tail"][0]) == {"date", "close", "vnr", "vnrSigma", "gapSessions", "returns"}


async def test_closes_cover_forty_days_before_the_latest_bar_ascending(client, db):
    dates = _weekdays(300)
    closes = _walk(300)
    await _seed(db, "MSFT", closes, dates)

    pulse = (await client.get("/api/companion/pulse")).json()["symbols"]["MSFT"]

    latest = dates[-1]
    expected = [
        {"date": d.isoformat(), "close": c}
        for d, c in zip(dates, closes)
        if d >= latest - timedelta(days=CLOSES_WINDOW_DAYS)
    ]
    assert pulse["closes"] == expected
    assert [c["date"] for c in pulse["closes"]] == sorted(c["date"] for c in pulse["closes"])
    assert pulse["closes"][-1]["date"] == latest.isoformat()


async def test_tail_matches_the_indicator_series_and_the_web_snapshot(client, db):
    dates = _weekdays(300)
    await _seed(db, "MSFT", _walk(300), dates)

    pulse = (await client.get("/api/companion/pulse")).json()["symbols"]["MSFT"]
    series = await _indicators(db, "MSFT")

    assert [p["date"] for p in pulse["tail"]] == [d.isoformat() for d in dates[-2:]]
    for point, (_, row) in zip(pulse["tail"], series.tail(2).iterrows()):
        assert point["close"] == pytest.approx(row["close"])
        assert point["vnr"] == round(row["vnr"], 2)
        assert point["vnrSigma"] == round(row["vnr_sigma"], 6)
        assert point["gapSessions"] is None
        assert point["vnr"] is not None and point["vnrSigma"] is not None

    groups = (await client.get("/api/groups")).json()
    watchlist = next(g for g in groups if g["is_default"])
    snapshot = (await client.get(f"/api/groups/{watchlist['id']}/indicators")).json()["MSFT"]
    assert pulse["tail"][-1]["vnr"] == snapshot["values"]["vnr"]
    assert pulse["tail"][-1]["vnrSigma"] == snapshot["values"]["vnr_sigma"]


async def test_returns_count_skips_gap_spanning_returns(client, db):
    dates = _weekdays(120)
    # A hole of three sessions mid-series, and one right before the last bar.
    dates = dates[:50] + dates[53:-4] + dates[-1:]
    await _seed(db, "MSFT", _walk(len(dates)), dates)

    tail = (await client.get("/api/companion/pulse")).json()["symbols"]["MSFT"]["tail"]
    series = await _indicators(db, "MSFT")
    gaps = int(series["vnr_gap_sessions"].notna().sum())
    assert gaps == 2

    last, prev = tail[-1], tail[-2]
    assert prev["returns"] == len(dates) - 2 - 1  # bars from the 2nd, minus the mid-series gap
    assert last["returns"] == prev["returns"]  # the last return spans a gap and does not count
    assert last["gapSessions"] == int(series["vnr_gap_sessions"].iloc[-1]) >= 2
    assert last["vnr"] is None


async def test_one_bar_gives_a_tail_of_one(client, db):
    await _seed(db, "NEW", [10.0], [date.today() - timedelta(days=1)])

    pulse = (await client.get("/api/companion/pulse")).json()["symbols"]["NEW"]
    assert pulse["closes"] == [{"date": (date.today() - timedelta(days=1)).isoformat(), "close": 10.0}]
    assert pulse["tail"] == [{
        "date": (date.today() - timedelta(days=1)).isoformat(), "close": 10.0,
        "vnr": None, "vnrSigma": None, "gapSessions": None, "returns": 0,
    }]


async def test_pence_quoted_listing_reports_pounds(client, db):
    # The Yahoo client divides GBp history by 100 before it is stored, so the
    # stored bar is already in pounds and the pulse must not divide again.
    dates = _weekdays(30)
    closes = [round(13.5 + i * 0.01, 4) for i in range(30)]
    await _seed(db, "RR.L", closes, dates, currency="GBp")

    config = (await client.get("/api/companion/config")).json()
    pulse = (await client.get("/api/companion/pulse")).json()["symbols"]["RR.L"]

    assert config["tickers"]["RR.L"]["currency"] == "GBP"
    assert pulse["tail"][-1]["close"] == closes[-1]
    assert pulse["closes"][-1]["close"] == closes[-1]


async def test_tracked_set_and_missing(client, db):
    dates = _weekdays(30)
    await _seed(db, "AAPL", _walk(30), dates)
    await _seed(db, "EMPTY", [], [])
    thesis_only = await _seed(db, "XOM", _walk(30), dates, group=False)
    await _seed(db, "LOOSE", _walk(30), dates, group=False)
    thesis = (await client.post("/api/theses", json={"name": "Energy"})).json()
    await client.post(f"/api/theses/{thesis['id']}/assets", json={"asset_ids": [thesis_only.id]})

    body = (await client.get("/api/companion/pulse")).json()
    config = (await client.get("/api/companion/config")).json()

    assert set(body["symbols"]) == {"AAPL", "XOM"}
    assert body["missing"] == ["EMPTY"]
    assert set(body["symbols"]) | set(body["missing"]) == set(config["tickers"])


async def test_empty_book(client):
    body = (await client.get("/api/companion/pulse")).json()
    assert body["symbols"] == {}
    assert body["missing"] == []


async def test_cache_hit_until_a_price_write(client, db):
    await _seed(db, "AAPL", _walk(60), _weekdays(60))

    with patch(
        "app.services.companion_pulse_service.compute_ref_indicators", wraps=compute_ref_indicators,
    ) as compute:
        first = (await client.get("/api/companion/pulse")).json()
        second = (await client.get("/api/companion/pulse")).json()
        assert compute.call_count == 1
        assert first == second

        assert invalidate_pulse_cache(["AAPL"]) == 1
        await client.get("/api/companion/pulse")
        assert compute.call_count == 2


async def test_price_upsert_invalidates_the_pulse(client, db):
    from app.services.price_sync import _upsert_prices

    asset = await _seed(db, "AAPL", _walk(60), _weekdays(60))
    await client.get("/api/companion/pulse")
    assert len(companion_pulse_service._pulse_cache._data) == 1

    df = pd.DataFrame(
        {"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0], "volume": [1]},
        index=pd.Index([date.today() - timedelta(days=400)], name="date"),
    )
    await _upsert_prices(db, AssetRef("AAPL", asset.id), df)
    assert len(companion_pulse_service._pulse_cache._data) == 0


async def test_warm_up_runs_at_startup_and_after_the_refresh():
    from app.background_tasks import jobs

    with (
        patch.object(jobs, "warm_all_group_caches", AsyncMock(return_value=0)),
        patch.object(jobs, "bootstrap_volume_curves", AsyncMock()),
        patch.object(jobs, "warm_pulse_cache", AsyncMock()) as warm,
    ):
        await jobs.startup_warmup()
        assert warm.await_count == 1

    with (
        patch.object(jobs, "async_session", TestSession),
        patch.object(jobs, "sync_all_prices", AsyncMock(return_value={"AAPL": 1})),
        patch.object(jobs, "warm_all_group_caches", AsyncMock(return_value=1)),
        patch.object(jobs, "cleanup_old_intraday", AsyncMock(return_value=0)),
        patch.object(jobs, "warm_pulse_cache", AsyncMock()) as warm,
    ):
        await jobs.scheduled_refresh()
        assert warm.await_count == 1


async def test_lifespan_starts_the_warm_up_without_waiting_for_it():
    from app import main

    started = asyncio.Event()

    async def slow_warmup():
        started.set()
        await asyncio.sleep(3600)

    with (
        patch.object(main, "startup_warmup", slow_warmup),
        patch.object(main, "async_session", TestSession),
        patch.object(main, "all_tasks", lambda: []),
        patch.object(main.scheduler, "start"),
        patch.object(main.scheduler, "shutdown"),
        patch.object(main, "engine", AsyncMock()),
    ):
        async with asyncio.timeout(5):
            async with main.lifespan(app):
                await asyncio.wait_for(started.wait(), 1)


async def test_warm_pulse_cache_fills_the_cache(db):
    from app.background_tasks import jobs

    await _seed(db, "AAPL", _walk(60), _weekdays(60))
    with patch.object(jobs, "async_session", TestSession):
        await jobs.warm_pulse_cache()
    assert len(companion_pulse_service._pulse_cache._data) == 1


async def test_large_response_is_gzipped(client, db):
    for i in range(10):
        await _seed(db, f"S{i}", _walk(60, seed=i), _weekdays(60))

    resp = await client.get("/api/companion/pulse", headers={"Accept-Encoding": "gzip"})
    assert resp.headers["content-encoding"] == "gzip"
    assert len(resp.json()["symbols"]) == 10

    small = await client.get("/api/health", headers={"Accept-Encoding": "gzip"})
    assert "content-encoding" not in small.headers


async def test_sse_stream_is_neither_compressed_nor_buffered():
    """Each SSE event must reach the socket before the generator moves on.

    GZipMiddleware would hold a streamed chunk inside its compressor, so this
    drives the ASGI app directly and checks what has been sent at the moment
    the generator first sleeps.
    """
    sent: list[dict] = []
    seen_at_sleep: list[bytes] = []

    async def send(message):
        sent.append(message)

    async def receive():
        await asyncio.Event().wait()

    async def sleep(_seconds):
        seen_at_sleep.append(b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body"))
        raise asyncio.CancelledError

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
        "scheme": "http", "path": "/api/quotes/stream", "raw_path": b"/api/quotes/stream",
        "query_string": b"", "root_path": "", "server": ("test", 80), "client": ("test", 1),
        "headers": [(b"host", b"test"), (b"accept-encoding", b"gzip")],
    }
    _reset_asset_list_cache()
    with (
        patch("app.services.quote_service.async_session", TestSession),
        patch("app.services.quote_service.asyncio.sleep", sleep),
    ):
        try:
            await app(scope, receive, send)
        except asyncio.CancelledError:
            pass

    start = next(m for m in sent if m["type"] == "http.response.start")
    headers = {k.decode(): v.decode() for k, v in start["headers"]}
    assert headers["content-type"].startswith("text/event-stream")
    assert "content-encoding" not in headers
    assert seen_at_sleep and b"event: quotes" in seen_at_sleep[0]


async def test_move_scale_rides_on_each_symbol(client, db):
    dates = _weekdays(600)
    closes = _walk(600)
    await _seed(db, "MSFT", closes, dates)
    await _seed(db, "NEWCO", _walk(150, seed=9), _weekdays(150))

    body = (await client.get("/api/companion/pulse")).json()
    scale = body["symbols"]["MSFT"]["moveScale"]
    assert set(scale) == {"1wk", "2wk", "1mo"}
    assert set(scale["1mo"]) == {"quantiles", "samples", "lookbackDays"}

    series = pd.Series(closes, index=dates)
    for key, w in MOVE_WINDOWS.items():
        assert scale[key] == move_scale(series, w).model_dump(by_alias=True)

    # About 30 weeks of history: enough for the weekly windows, not for 1mo.
    short = body["symbols"]["NEWCO"]["moveScale"]
    assert short["1wk"] is not None and short["2wk"] is not None
    assert short["1wk"]["lookbackDays"] < 364
    assert short["1mo"] is None

    # The web board reads the same scales.
    web = (await client.get("/api/move-scales")).json()
    assert web["MSFT"] == scale
    assert web["NEWCO"] == short


async def test_move_scales_follow_a_price_write(client, db):
    dates = _weekdays(400)
    asset = await _seed(db, "MSFT", _walk(400), dates)
    before = (await client.get("/api/move-scales")).json()["MSFT"]["1wk"]

    # A corrected interior close does not move the latest bar date, so only the
    # write's invalidation can refresh the cached scale.
    frame = pd.DataFrame(
        {"open": [500.0], "high": [500.0], "low": [500.0], "close": [500.0], "volume": [1]},
        index=[dates[-20]],
    )
    with patch(
        "app.services.price_sync.PriceRepository.upsert_prices", new=AsyncMock(return_value=1),
    ):
        await db.execute(
            PriceHistory.__table__.update()
            .where(PriceHistory.asset_id == asset.id, PriceHistory.date == dates[-20])
            .values(close=500.0)
        )
        await db.commit()
        await _upsert_prices(db, AssetRef("MSFT", asset.id), frame)

    after = (await client.get("/api/move-scales")).json()["MSFT"]["1wk"]
    assert after["quantiles"][-1] > before["quantiles"][-1]
