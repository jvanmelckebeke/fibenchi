import pytest


pytestmark = pytest.mark.asyncio(loop_scope="function")


async def _create_asset(client):
    resp = await client.post("/api/assets", json={"symbol": "AAPL", "name": "Apple"})
    return resp.json()


async def test_get_empty_thesis(client):
    await _create_asset(client)
    resp = await client.get("/api/assets/AAPL/thesis")
    assert resp.status_code == 200
    assert resp.json()["content"] == ""


async def test_update_thesis(client):
    await _create_asset(client)
    resp = await client.put("/api/assets/AAPL/thesis", json={"content": "# Apple Thesis\n\nStrong ecosystem."})
    assert resp.status_code == 200
    assert "Apple Thesis" in resp.json()["content"]


async def test_update_thesis_twice(client):
    await _create_asset(client)
    await client.put("/api/assets/AAPL/thesis", json={"content": "v1"})
    resp = await client.put("/api/assets/AAPL/thesis", json={"content": "v2"})
    assert resp.json()["content"] == "v2"


async def test_thesis_nonexistent_asset(client):
    resp = await client.get("/api/assets/NOPE/thesis")
    assert resp.status_code == 404


async def test_create_annotation(client):
    await _create_asset(client)
    resp = await client.post("/api/assets/AAPL/annotations", json={
        "date": "2025-01-15",
        "title": "Earnings beat",
        "body": "Beat estimates by 10%",
        "color": "#22c55e",
    })
    assert resp.status_code == 201
    assert resp.json()["title"] == "Earnings beat"


async def test_list_annotations(client):
    await _create_asset(client)
    await client.post("/api/assets/AAPL/annotations", json={"date": "2025-01-10", "title": "Event A"})
    await client.post("/api/assets/AAPL/annotations", json={"date": "2025-01-20", "title": "Event B"})

    resp = await client.get("/api/assets/AAPL/annotations")
    assert len(resp.json()) == 2
    assert resp.json()[0]["title"] == "Event A"


async def test_delete_annotation(client):
    await _create_asset(client)
    resp = await client.post("/api/assets/AAPL/annotations", json={"date": "2025-01-15", "title": "Event"})
    aid = resp.json()["id"]

    resp = await client.delete(f"/api/assets/AAPL/annotations/{aid}")
    assert resp.status_code == 204

    resp = await client.get("/api/assets/AAPL/annotations")
    assert len(resp.json()) == 0


async def test_delete_nonexistent_annotation(client):
    await _create_asset(client)
    resp = await client.delete("/api/assets/AAPL/annotations/999")
    assert resp.status_code == 404
