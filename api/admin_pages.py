"""HTML-страницы админки и их JSON-эндпоинты (/admin/api/*)."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from config import settings
from deps import admin, require_admin
from importers.excel import SHEETS, get_mapping
from models.imports import ImportBatch, Setting
from models.shipment import GpsLink, Position, Shipment
from services.audit import audit
from services.gps_service import sync_link

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
APP_KEY = "app_settings"

def _apply(v: dict) -> None:
    if "gps_interval_minutes" in v:
        settings.gps_interval_minutes = int(v["gps_interval_minutes"])
    for k in ("public_access", "rate_limit_enabled"):
        if k in v:
            setattr(settings, k, bool(v[k]))

async def load_app_settings(session) -> None:
    s = await session.get(Setting, APP_KEY)
    if s and s.value:
        _apply(s.value)

def _page(name: str):
    async def handler(request: Request, _u=Depends(admin)):
        return templates.TemplateResponse(request, f"admin/{name}.html")
    return handler

def _iso(v):
    return v.isoformat() if v else None

def make_router(get_session) -> APIRouter:
    r = APIRouter()
    for name, path in (("dashboard", "/admin"), ("shipments", "/admin/shipments"),
                       ("gps_links", "/admin/gps-links"), ("settings", "/admin/settings")):
        r.add_api_route(path, _page(name), methods=["GET"], response_class=HTMLResponse)

    @r.get("/admin/api/dashboard")
    async def dashboard(_u=Depends(admin), session=Depends(get_session)):
        live = Shipment.deleted_at.is_(None)
        async def cnt(*c):
            return await session.scalar(select(func.count()).select_from(Shipment).where(live, *c))
        counts = {"in_transit": await cnt(Shipment.status == "in_transit"), "planned": await cnt(Shipment.status == "planned"),
                  "delivered": await cnt(Shipment.status == "delivered"),
                  "overdue": await cnt(Shipment.plan_arrival < date.today(), Shipment.status != "delivered"),
                  "nogps": await cnt(Shipment.gps_link.is_(None), Shipment.status != "delivered"),
                  "link_invalid": await cnt(Shipment.link_invalid.is_(True))}
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        gps = await session.scalar(select(func.count()).select_from(Position).where(Position.fetched_at >= since))
        broken = await session.scalars(select(GpsLink).where(GpsLink.is_invalid.is_(True)).order_by(GpsLink.error_count.desc()).limit(5))
        imps = await session.scalars(select(ImportBatch).order_by(ImportBatch.id.desc()).limit(10))
        return {"counts": counts, "gps_24h": gps,
                "broken": [{"order_id": l.order_id, "error_count": l.error_count, "last_error": l.last_error} for l in broken],
                "imports": [{"id": b.id, "sheet_name": b.sheet_name, "inserted": b.inserted, "updated": b.updated,
                             "status": b.status, "uploaded_at": _iso(b.uploaded_at)} for b in imps]}

    @r.get("/admin/api/options")
    async def options(_u=Depends(admin), session=Depends(get_session)):
        async def distinct(col):
            q = select(col).where(col.is_not(None), Shipment.deleted_at.is_(None)).distinct().order_by(col).limit(300)
            return [x for x in await session.scalars(q)]
        return {"carrier": await distinct(Shipment.carrier), "vehicle": await distinct(Shipment.vehicle_raw),
                "driver": await distinct(Shipment.driver_fio)}  # ФИО, без паспортных данных

    @r.get("/admin/api/shipments")
    async def shipments(q: str = "", tab: str = "all", direction: str = "", carrier: str = "", vehicle_type: str = "",
                        deleted: int = 0, page: int = 1, size: int = 50, _u=Depends(admin), session=Depends(get_session)):
        from main import dto, filtered  # ленивый импорт: main подключает этот роутер
        stmt = (select(Shipment).where(Shipment.deleted_at.is_not(None)).order_by(Shipment.deleted_at.desc())
                if deleted else filtered(q, tab))
        for col, v in (("direction", direction), ("carrier", carrier), ("vehicle_type", vehicle_type)):
            if v:
                stmt = stmt.where(getattr(Shipment, col) == v)
        size, page = min(max(size, 10), 200), max(page, 1)
        total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
        rows = await session.scalars(stmt.offset((page - 1) * size).limit(size))
        return {"total": total, "page": page, "size": size, "rows": [dto(s) for s in rows]}

    @r.get("/admin/api/gps-links")
    async def links(state: str = "all", _u=Depends(admin), session=Depends(get_session)):
        stmt = select(GpsLink).order_by(GpsLink.last_error_at.desc().nulls_last()).limit(1000)
        if state == "broken":
            stmt = stmt.where(GpsLink.is_invalid.is_(True))
        elif state == "unchecked":
            stmt = stmt.where(GpsLink.last_ok_at.is_(None), GpsLink.last_error_at.is_(None))
        return [{"order_id": l.order_id, "url": l.url, "parser_type": l.parser_type, "is_invalid": l.is_invalid,
                 "error_count": l.error_count, "last_error": l.last_error, "last_ok_at": _iso(l.last_ok_at),
                 "last_error_at": _iso(l.last_error_at)} for l in await session.scalars(stmt)]

    @r.post("/admin/gps-links")
    async def bind(data: dict, request: Request, _u=Depends(admin), session=Depends(get_session)):
        oid, url = (data.get("order_id") or "").strip(), (data.get("url") or "").strip()
        s = await session.get(Shipment, oid)
        if not s:
            raise HTTPException(404, "Заказ не найден")
        if not url.startswith("http"):
            raise HTTPException(422, "Ссылка должна начинаться с http")
        s.gps_link, s.link_invalid = url, False
        await session.flush()
        await sync_link(session, oid, url)
        await session.commit()
        await audit(session, request, "gps.bind", "shipment", oid, {"url": url[:120]})
        return {"ok": True}

    @r.get("/admin/api/settings")
    async def get_settings(_u=Depends(admin), session=Depends(get_session)):
        return {"gps_interval_minutes": settings.gps_interval_minutes, "public_access": settings.public_access,
                "rate_limit_enabled": settings.rate_limit_enabled,
                "mappings": {n: await get_mapping(session, n) for n in SHEETS}}

    @r.post("/admin/settings")
    async def save_settings(data: dict, request: Request, _u=Depends(require_admin), session=Depends(get_session)):
        try:
            v = {"gps_interval_minutes": int(data["gps_interval_minutes"]), "public_access": bool(data["public_access"]),
                 "rate_limit_enabled": bool(data["rate_limit_enabled"])}
        except (KeyError, TypeError, ValueError):
            raise HTTPException(422, "Некорректные настройки")
        if not 1 <= v["gps_interval_minutes"] <= 1440:
            raise HTTPException(422, "Интервал 1..1440 минут")
        s = await session.get(Setting, APP_KEY)
        if s:
            s.value = v
        else:
            session.add(Setting(key=APP_KEY, value=v))
        await session.commit()
        _apply(v)
        await audit(session, request, "settings.update", "settings", APP_KEY, v)
        return {"ok": True}

    return r
