import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from models.shipment import Base, GpsLink, Position as PositionRow, Shipment
from parsers.base import Position
from services import gps_service

URL = "https://maps.baltgps.ru/locator/index.html?t=abc"

class Fake:
    def __init__(self, pos): self.pos = pos
    async def fetch(self, url): return self.pos

@pytest.fixture
async def session():
    e = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with e.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(e, expire_on_commit=False)() as s:
        s.add(Shipment(order_id="T1", status="in_transit", gps_link=URL))
        await s.commit()
        yield s

async def test_success(session, monkeypatch):
    monkeypatch.setattr(gps_service, "get_parser", lambda u: Fake(Position(54.7, 20.5, "x")))
    assert await gps_service.refresh_order(session, "T1")
    s = await session.get(Shipment, "T1")
    assert (s.current_lat, s.ship_lat) == (54.7, 54.7) and s.first_seen_at
    assert len((await session.scalars(select(PositionRow))).all()) == 1
    monkeypatch.setattr(gps_service, "get_parser", lambda u: Fake(Position(55.0, 21.0, "x")))
    await gps_service.refresh_order(session, "T1")
    s = await session.get(Shipment, "T1")
    assert s.current_lat == 55.0 and s.ship_lat == 54.7

async def test_failures_mark_invalid(session, monkeypatch):
    monkeypatch.setattr(gps_service, "get_parser", lambda u: Fake(None))
    for _ in range(3):
        assert not await gps_service.refresh_order(session, "T1")
    assert (await session.get(Shipment, "T1")).link_invalid
    assert (await session.get(GpsLink, "T1")).is_invalid
    r = await gps_service.refresh_all(session)  # свежая ошибка -> backoff 6ч
    assert r["processed"] == 0

async def test_refresh_all(session, monkeypatch):
    monkeypatch.setattr(gps_service, "get_parser", lambda u: Fake(Position(1.0, 2.0, "x")))
    assert await gps_service.refresh_all(session) == {"processed": 1, "success": 1, "failed": 0}
