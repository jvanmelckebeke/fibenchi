import pytest

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_get_empty(client):
    resp = await client.get("/api/settings")
    assert resp.status_code == 200
    assert resp.json() == {"data": {}}


async def test_put(client):
    payload = {"data": {"theme": "dark", "compact_mode": True}}
    resp = await client.put("/api/settings", json=payload)
    assert resp.status_code == 200
    assert resp.json()["data"]["theme"] == "dark"
    assert resp.json()["data"]["compact_mode"] is True


async def test_put_get_roundtrip(client):
    payload = {"data": {"chart_type": "line", "decimal_places": 4}}
    await client.put("/api/settings", json=payload)
    resp = await client.get("/api/settings")
    assert resp.status_code == 200
    assert resp.json()["data"] == {"chart_type": "line", "decimal_places": 4}


async def test_put_overwrites(client):
    await client.put("/api/settings", json={"data": {"theme": "dark"}})
    await client.put("/api/settings", json={"data": {"theme": "light", "extra": 1}})
    resp = await client.get("/api/settings")
    assert resp.json()["data"] == {"theme": "light", "extra": 1}


async def test_put_rejects_invalid_theme(client):
    resp = await client.put("/api/settings", json={"data": {"theme": "neon"}})
    assert resp.status_code == 422


async def test_put_rejects_invalid_chart_type(client):
    resp = await client.put("/api/settings", json={"data": {"chart_type": "bar"}})
    assert resp.status_code == 422


async def test_put_accepts_unknown_keys(client):
    resp = await client.put("/api/settings", json={"data": {"future_setting": True}})
    assert resp.status_code == 200
    assert resp.json()["data"]["future_setting"] is True
