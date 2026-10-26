import httpx, pytest
from config import settings
from main import app

H = {"accept": "text/html"}
PAGES = ["/admin", "/admin/shipments", "/admin/gps-links", "/admin/users", "/admin/audit", "/admin/settings", "/admin/import"]

@pytest.mark.parametrize("p", PAGES)
async def test_pages_admin_and_anon(client, p):
    r = await client.get(p, headers=H)
    assert r.status_code == 200 and "<html" in r.text.lower()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as anon:
        r = await anon.get(p, headers=H)
        assert r.status_code == 307 and r.headers["location"] == "/admin/login"
        assert (await anon.get(p)).status_code == 401

async def test_viewer_rights(client):
    await client.post("/admin/users", json={"login": "v", "password": "viewer1", "role": "viewer"})
    v = ("v", "viewer1")
    assert (await client.get("/admin/shipments", headers=H, auth=v)).status_code == 200
    assert (await client.get("/admin/users", headers=H, auth=v)).status_code == 403
    assert (await client.post("/admin/settings", json={}, auth=v)).status_code == 403
    assert (await client.post("/admin/gps-links", json={}, auth=v)).status_code == 403

async def test_json_endpoints(client, monkeypatch):
    for k in ("public_access", "rate_limit_enabled", "gps_interval_minutes"):
        monkeypatch.setattr(settings, k, getattr(settings, k))  # восстановится после теста
    for i, st in enumerate(("planned", "delivered", "in_transit")):
        await client.post("/admin/shipments", json={"order_id": f"T{i}", "status": st, "carrier": "Лого", "driver_raw": "Иванов Иван Иванович +79110000000"})
    d = (await client.get("/admin/api/dashboard")).json()
    assert d["counts"]["planned"] == 1 and d["counts"]["delivered"] == 1 and d["counts"]["nogps"] == 2
    p = (await client.get("/admin/api/shipments?size=10&page=1&tab=delivered")).json()
    assert p["total"] == 1 and p["rows"][0]["order_id"] == "T1" and "driver_raw" not in p["rows"][0]
    assert (await client.get("/admin/api/options")).json()["carrier"] == ["Лого"]
    assert (await client.post("/admin/gps-links", json={"order_id": "T0", "url": "x"})).status_code == 422
    assert (await client.post("/admin/gps-links", json={"order_id": "T0", "url": "https://axenta.cloud/locator/u"})).status_code == 200
    ls = (await client.get("/admin/api/gps-links?state=unchecked")).json()
    assert ls[0]["order_id"] == "T0" and ls[0]["parser_type"] == "AxentaParser"
    assert (await client.post("/admin/settings", json={"gps_interval_minutes": 0, "public_access": True, "rate_limit_enabled": False})).status_code == 422
    assert (await client.post("/admin/settings", json={"gps_interval_minutes": 7, "public_access": True, "rate_limit_enabled": False})).status_code == 200
    assert (await client.get("/admin/api/settings")).json()["gps_interval_minutes"] == 7
