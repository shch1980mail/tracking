from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.shipment import GpsLink, Position as PositionRow, Shipment
from parsers.registry import get_parser

log = structlog.get_logger()
INVALID_AFTER = 3
RETRY_INVALID = timedelta(hours=6)

def _now() -> datetime:
    return datetime.now(timezone.utc)

def _aware(dt: datetime | None) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)

async def sync_link(session: AsyncSession, order_id: str, url: str) -> None:
    p = get_parser(url)
    ptype = type(p).__name__ if p else None
    gl = await session.get(GpsLink, order_id)
    if gl is None:
        session.add(GpsLink(order_id=order_id, url=url, parser_type=ptype, error_count=0, is_invalid=False))
    elif gl.url != url:
        gl.url, gl.parser_type, gl.error_count, gl.is_invalid, gl.last_error = url, ptype, 0, False, None

async def refresh_order(session: AsyncSession, order_id: str) -> bool:
    s = await session.get(Shipment, order_id)
    if not s or not s.gps_link:
        return False
    await sync_link(session, order_id, s.gps_link)
    await session.flush()
    gl = await session.get(GpsLink, order_id)
    parser, pos, err = get_parser(s.gps_link), None, None
    if parser is None:
        err = "unsupported_url"
    else:
        try:
            pos = await parser.fetch(s.gps_link)
        except Exception as e:  # парсер не должен ронять батч
            err = str(e)[:300]
        if pos is None and err is None:
            err = "no_position"
    t = _now()
    if pos is None:
        gl.error_count = (gl.error_count or 0) + 1
        gl.last_error, gl.last_error_at = err, t
        if gl.error_count >= INVALID_AFTER:
            gl.is_invalid = s.link_invalid = True
        await session.commit()
        log.info("gps_failed", order_id=order_id, error=err)
        return False
    session.add(PositionRow(order_id=order_id, lat=pos.lat, lng=pos.lng, source=pos.source,
                            fetched_at=t, raw_payload=pos.raw_payload))
    if s.first_seen_at is None:
        s.first_seen_at, s.ship_lat, s.ship_lng = t, pos.lat, pos.lng
    s.current_lat, s.current_lng, s.last_position_update, s.link_invalid = pos.lat, pos.lng, t, False
    gl.error_count, gl.is_invalid, gl.last_ok_at, gl.last_error = 0, False, t, None
    await session.commit()
    return True

async def refresh_all(session: AsyncSession, limit: int = 50) -> dict:
    """Активные заказы с gps_link. «Сгоревшие» ссылки повторяются раз в 6 ч.
    Лимит параллельных Playwright-сессий (Semaphore(3)) — в parsers/_browser.py."""
    rows = (await session.scalars(
        select(Shipment).where(Shipment.status.in_(("in_transit", "planned")),
                               Shipment.gps_link.is_not(None), Shipment.deleted_at.is_(None))
        .order_by(Shipment.last_position_update.asc().nulls_first()))).all()
    ids = []
    for s in rows:
        if s.link_invalid:
            gl = await session.get(GpsLink, s.order_id)
            last = _aware(gl.last_error_at) if gl else None
            if last and _now() - last < RETRY_INVALID:
                continue
        ids.append(s.order_id)
        if len(ids) >= limit:
            break
    ok = 0
    for oid in ids:
        ok += await refresh_order(session, oid)
    return {"processed": len(ids), "success": ok, "failed": len(ids) - ok}
