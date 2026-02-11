import pytest


pytestmark = pytest.mark.asyncio(loop_scope="function")


async def _create_asset(client, symbol, name):
    resp = await client.post("/api/assets", json={"symbol": symbol, "name": name})
    return resp.json()


async def test_create_tag(client):
    resp = await client.post("/api/tags", json={"name": "tech", "color": "#3b82f6"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "tech"
    assert resp.json()["color"] == "#3b82f6"
    assert resp.json()["assets"] == []


async def test_list_tags(client):
    await client.post("/api/tags", json={"name": "tech"})
    await client.post("/api/tags", json={"name": "growth"})

    resp = await client.get("/api/tags")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_update_tag(client):
    resp = await client.post("/api/tags", json={"name": "tech"})
    tid = resp.json()["id"]

    resp = await client.put(f"/api/tags/{tid}", json={"name": "technology", "color": "#ef4444"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "technology"
    assert resp.json()["color"] == "#ef4444"


async def test_delete_tag(client):
    resp = await client.post("/api/tags", json={"name": "tech"})
    tid = resp.json()["id"]

    resp = await client.delete(f"/api/tags/{tid}")
    assert resp.status_code == 204


async def test_duplicate_tag_name(client):
    await client.post("/api/tags", json={"name": "tech"})
    resp = await client.post("/api/tags", json={"name": "tech"})
    assert resp.status_code == 400


async def test_attach_tag_to_asset(client):
    asset = await _create_asset(client, "AAPL", "Apple")
    tag_resp = await client.post("/api/tags", json={"name": "tech"})
    tid = tag_resp.json()["id"]

    resp = await client.post(f"/api/assets/AAPL/tags/{tid}")
    assert resp.status_code == 200
    tags = resp.json()
    assert len(tags) == 1
    assert tags[0]["name"] == "tech"


async def test_detach_tag_from_asset(client):
    asset = await _create_asset(client, "AAPL", "Apple")
    t1 = (await client.post("/api/tags", json={"name": "tech"})).json()
    t2 = (await client.post("/api/tags", json={"name": "growth"})).json()

    await client.post(f"/api/assets/AAPL/tags/{t1['id']}")
    await client.post(f"/api/assets/AAPL/tags/{t2['id']}")

    resp = await client.delete(f"/api/assets/AAPL/tags/{t1['id']}")
    assert resp.status_code == 200
    tags = resp.json()
    assert len(tags) == 1
    assert tags[0]["name"] == "growth"


async def test_tags_appear_in_asset_response(client):
    asset = await _create_asset(client, "AAPL", "Apple")
    tag_resp = await client.post("/api/tags", json={"name": "tech"})
    tid = tag_resp.json()["id"]

    await client.post(f"/api/assets/AAPL/tags/{tid}")

    resp = await client.get("/api/assets")
    assert resp.status_code == 200
    aapl = [a for a in resp.json() if a["symbol"] == "AAPL"][0]
    assert len(aapl["tags"]) == 1
    assert aapl["tags"][0]["name"] == "tech"


async def test_update_nonexistent_tag(client):
    resp = await client.put("/api/tags/999", json={"name": "nope"})
    assert resp.status_code == 404


async def test_delete_nonexistent_tag(client):
    resp = await client.delete("/api/tags/999")
    assert resp.status_code == 404


async def test_attach_tag_nonexistent_asset(client):
    tag = (await client.post("/api/tags", json={"name": "tech"})).json()
    resp = await client.post(f"/api/assets/NOPE/tags/{tag['id']}")
    assert resp.status_code == 404


async def test_attach_nonexistent_tag_to_asset(client):
    await _create_asset(client, "AAPL", "Apple")
    resp = await client.post("/api/assets/AAPL/tags/999")
    assert resp.status_code == 404


async def test_detach_tag_nonexistent_asset(client):
    resp = await client.delete("/api/assets/NOPE/tags/1")
    assert resp.status_code == 404


async def test_attach_tag_idempotent(client):
    await _create_asset(client, "AAPL", "Apple")
    tag = (await client.post("/api/tags", json={"name": "tech"})).json()

    await client.post(f"/api/assets/AAPL/tags/{tag['id']}")
    resp = await client.post(f"/api/assets/AAPL/tags/{tag['id']}")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_create_tag_default_color(client):
    resp = await client.post("/api/tags", json={"name": "growth"})
    assert resp.status_code == 201
    assert resp.json()["color"] == "#3b82f6"


async def test_delete_tag_cleans_asset_association(client):
    await _create_asset(client, "AAPL", "Apple")
    tag = (await client.post("/api/tags", json={"name": "tech"})).json()
    await client.post(f"/api/assets/AAPL/tags/{tag['id']}")

    await client.delete(f"/api/tags/{tag['id']}")

    resp = await client.get("/api/assets")
    aapl = [a for a in resp.json() if a["symbol"] == "AAPL"][0]
    assert aapl["tags"] == []


async def test_attach_tag_case_insensitive_symbol(client):
    await _create_asset(client, "AAPL", "Apple")
    tag = (await client.post("/api/tags", json={"name": "tech"})).json()

    resp = await client.post(f"/api/assets/aapl/tags/{tag['id']}")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
