import httpx
from main import app
from services import auth

async def test_hash_tokens(maker):
    async with maker() as s:
        await auth.create_user(s, "bob", "secret1", "manager")
        assert await auth.authenticate(s, "bob", "secret1") and not await auth.authenticate(s, "bob", "bad")
        t = await auth.create_token(s, "bob", "access", 15)
        assert (await auth.user_from_token(s, t, "access")).login == "bob"
        assert await auth.user_from_token(s, t, "refresh") is None and await auth.user_from_token(s, "junk") is None

async def test_roles(client):
    for lg, pw, role in (("v", "viewer1", "viewer"), ("m", "manager1", "manager")):
        assert (await client.post("/admin/users", json={"login": lg, "password": pw, "role": role})).status_code == 200
    assert (await client.post("/admin/shipments", json={"order_id": "A1"}, auth=("v", "viewer1"))).status_code == 403
    assert (await client.get("/admin/import/history", auth=("v", "viewer1"))).status_code == 200
    assert (await client.post("/admin/shipments", json={"order_id": "A1"}, auth=("m", "manager1"))).status_code == 200
    assert (await client.get("/admin/users", auth=("m", "manager1"))).status_code == 403
    uid = next(u["id"] for u in (await client.get("/admin/users")).json() if u["login"] == "v")
    assert (await client.patch(f"/admin/users/{uid}", json={"is_active": False})).status_code == 200
    assert (await client.get("/admin/import/history", auth=("v", "viewer1"))).status_code == 401

async def test_cookie_login(client):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as c:
        assert (await c.get("/admin/import/history")).status_code == 401
        assert (await c.post("/admin/login", data={"login": "admin", "password": "x"})).status_code == 401
        r = await c.post("/admin/login", data={"login": "admin", "password": "change-me"}, follow_redirects=False)
        assert r.status_code == 303 and "access_token" in r.cookies
        assert (await c.get("/admin/import/history")).status_code == 200  # только cookie
        assert (await c.post("/admin/refresh")).status_code == 200
        await c.get("/admin/logout")
        assert (await c.get("/admin/import/history")).status_code == 401
