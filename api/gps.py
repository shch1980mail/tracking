from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from models.shipment import Position as PositionRow
from services.audit import audit
from services.gps_service import refresh_all, refresh_order

def make_router(admin, public, get_session) -> APIRouter:
    r = APIRouter()

    @r.post("/admin/gps/run-now", dependencies=[Depends(admin)])
    async def run_now(order_id: str, request: Request, session=Depends(get_session)):
        ok = await refresh_order(session, order_id)
        await audit(session, request, "gps.run_now", "shipment", order_id, {"ok": ok})
        return {"order_id": order_id, "ok": ok}

    @r.post("/admin/gps/run-all", dependencies=[Depends(admin)])
    async def run_all(request: Request, session=Depends(get_session)):
        res = await refresh_all(session)
        await audit(session, request, "gps.run_all", "gps", None, res)
        return res

    @r.get("/api/gps/positions/{order_id}", dependencies=[Depends(public)])
    async def positions(order_id: str, hours: int = 24, session=Depends(get_session)):
        if hours < 0:
            raise HTTPException(422, "hours >= 0")
        stmt = select(PositionRow).where(PositionRow.order_id == order_id).order_by(PositionRow.fetched_at)
        if hours:
            stmt = stmt.where(PositionRow.fetched_at >= datetime.now(timezone.utc) - timedelta(hours=hours))
        rows = await session.scalars(stmt.limit(5000))
        return [{"lat": p.lat, "lng": p.lng, "t": p.fetched_at.isoformat(), "source": p.source} for p in rows]

    return r
