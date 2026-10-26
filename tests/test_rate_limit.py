import httpx
import ratelimit
from config import settings
from main import app

async def test_429_and_disable(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(ratelimit, "PUBLIC_LIMIT", 3)
    ratelimit.reset()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        codes = [(await c.get("/api/shipments")).status_code for _ in range(5)]
        assert codes[:3] == [200] * 3 and codes[3] == 429
        assert "retry-after" in (await c.get("/api/shipments")).headers
        monkeypatch.setattr(settings, "rate_limit_enabled", False)
        assert (await c.get("/api/shipments")).status_code == 200
