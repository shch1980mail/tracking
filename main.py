import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone

import structlog
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy import inspect as sa_inspect, select, text

from config import settings
from db import get_engine, get_session, session_maker
from importers.excel import import_xlsx
from services.audit import audit
from services.auth import ensure_first_admin
from services.gps_service import sync_link
from models.shipment import Base, Shipment
from services.normalize import norm_status, parse_driver, parse_vehicle, to_date

log = structlog.get_logger()
templates = Jinja2Templates(directory="templates")
basic = HTTPBasic()

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with get_engine().begin() as c:
            if await c.run_sync(lambda sc: sa_inspect(sc).has_table("alembic_version")):
                log.info("alembic_applied")
            else:
                log.warning("alembic_not_applied")  # fallback: SQLite на Layero Free без шага миграций
                await c.run_sync(Base.metadata.create_all)
        async with session_maker()() as s:
            await ensure_first_admin(s)
            from api.admin_pages import load_app_settings
            await load_app_settings(s)
    except Exception as e:  # БД может быть временно недоступна (Neon auto-pause)
        log.error("db_init_failed", error=str(e))
    sch = None
    if settings.gps_scheduler_enabled:
        from workers.gps_scheduler import start
        sch = start(session_maker(), settings.gps_interval_minutes)
    yield
    if sch:
        sch.shutdown(wait=False)

app = FastAPI(title="ТПК — Отслеживание", lifespan=lifespan)

from deps import admin  # noqa: E402  (JWT-cookie / Basic / роли)

def public():
    if not settings.public_access:
        raise HTTPException(403, "Публичный доступ отключён")

def dto(s: Shipment) -> dict:
    overdue = bool(s.plan_arrival and s.plan_arrival < date.today() and s.status != "delivered")
    return {c.name: (v.isoformat() if hasattr(v := getattr(s, c.name), "isoformat") else v)
            for c in Shipment.__table__.columns if c.name not in ("driver_passport", "driver_raw")} | {"overdue": overdue}

@app.get("/healthz")
async def healthz(session=Depends(get_session)):
    await session.execute(text("select 1"))
    return {"db": "ok"}

@app.get("/", response_class=HTMLResponse, dependencies=[Depends(public)])
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")

def filtered(q: str, tab: str):
    from sqlalchemy import or_
    stmt = select(Shipment).where(Shipment.deleted_at.is_(None)).order_by(Shipment.plan_arrival)
    if tab in ("in_transit", "planned", "delivered"):
        stmt = stmt.where(Shipment.status == tab)
    elif tab == "overdue":
        stmt = stmt.where(Shipment.plan_arrival < date.today(), Shipment.status != "delivered")
    elif tab == "nogps":
        stmt = stmt.where(Shipment.gps_link.is_(None), Shipment.status != "delivered")
    if q:
        # SQLite lower()/LIKE не умеют кириллицу -> перебираем варианты регистра; в Postgres ilike работает полностью
        variants = {q, q.lower(), q.upper(), q.capitalize()}
        stmt = stmt.where(or_(*[getattr(Shipment, f).ilike(f"%{v}%") for f in
                                ("order_id", "address", "carrier", "vehicle_raw", "driver_fio", "comment") for v in variants]))
    return stmt

@app.get("/api/shipments", dependencies=[Depends(public)])
async def list_shipments(q: str = "", tab: str = "all", session=Depends(get_session)):
    return [dto(s) for s in (await session.scalars(filtered(q, tab).limit(500)))]

CSV_COLS = [("order_id", "Заказ"), ("direction", "Направление"), ("address", "Адрес"), ("weight", "Вес"),
            ("ship_date", "Дата отгрузки"), ("plan_arrival", "Дата прибытия"), ("carrier", "Перевозчик"),
            ("vehicle_raw", "Машина"), ("driver_fio", "Водитель"), ("driver_phone", "Телефон"), ("gps_link", "GPS-ссылка"),
            ("comment", "Комментарий"), ("status", "Статус"), ("rate", "Ставка"), ("rate_plan", "Ставка план"),
            ("transit_days", "Срок транзита"), ("termologer", "Термологер"), ("notes", "Примечания"),
            ("current_lat", "Широта"), ("current_lng", "Долгота"), ("last_position_update", "Последний GPS")]

def _cell(v):
    if v is None:
        return ""
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@"):
        return "'" + v  # защита от формул в Excel
    return v

@app.get("/api/shipments.csv", dependencies=[Depends(public)])
async def shipments_csv(q: str = "", tab: str = "all", session=Depends(get_session)):
    import csv, io
    from fastapi.responses import Response
    buf = io.StringIO(); w = csv.writer(buf, delimiter=";")
    w.writerow([h for _, h in CSV_COLS])
    for s in await session.scalars(filtered(q, tab).limit(5000)):
        w.writerow([_cell(getattr(s, f)) for f, _ in CSV_COLS])
    return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="shipments.csv"'})

@app.post("/admin/import", dependencies=[Depends(admin)])
async def admin_import(file: UploadFile = File(...), session=Depends(get_session), _u: str = Depends(admin)):
    # DEPRECATED: алиас для /admin/import/commit с одним листом «Исх.логистика»
    r = await import_xlsx(session, file.file, sheet_name="Исх.логистика", filename=file.filename or "", uploaded_by=_u)
    b = r["batches"][0]
    return {"inserted": b["inserted"], "updated": b["updated"], "errors": b["errors"], "deprecated": "use /admin/import/commit"}

@app.post("/admin/shipments", dependencies=[Depends(admin)])
async def upsert(data: dict, request: Request, session=Depends(get_session)):
    oid = (data.get("order_id") or "").strip()
    if not oid:
        raise HTTPException(422, "order_id обязателен")
    for k in list(data):
        if data[k] == "" and k != "order_id":
            data[k] = None  # пустое поле = очистить
    try:
        if data.get("weight") is not None:
            data["weight"] = float(data["weight"])
        for k in ("rate", "rate_plan", "transit_days", "week_number"):
            if data.get(k) is not None:
                data[k] = int(float(data[k]))
    except (TypeError, ValueError):
        raise HTTPException(422, "Числовые поля заполнены некорректно")
    if data.get("gps_link") and not str(data["gps_link"]).startswith("http"):
        raise HTTPException(422, "gps_link должен начинаться с http")
    for k in ("ship_date", "plan_arrival"):
        if data.get(k):
            parsed = to_date(data[k])
            if not parsed:
                raise HTTPException(422, f"Некорректная дата {k}")
            data[k] = parsed
    exists = await session.get(Shipment, oid) is not None
    if data.pop("_create", False) and exists:
        raise HTTPException(409, "Заказ с таким номером уже существует")
    if data.get("status") is None:
        data.pop("status", None)
    if data.get("status") not in (None, "in_transit", "planned", "delivered"):
        raise HTTPException(422, "status: in_transit|planned|delivered")
    if "status" not in data and ("status_raw" in data or not exists):  # частичная правка не затирает статус
        data["status"] = norm_status(data.get("status_raw"), data.get("notes"))
    if data.get("vehicle_raw"):
        data.update(parse_vehicle(data["vehicle_raw"]))
    if data.get("driver_raw"):
        data.update(parse_driver(data["driver_raw"]))
    obj = await session.get(Shipment, oid)
    fields = {k: v for k, v in data.items() if k in Shipment.__table__.columns and k != "order_id"}
    if obj is None:
        session.add(Shipment(order_id=oid, **fields))
    else:
        for k, v in fields.items():
            setattr(obj, k, v)
    if fields.get("gps_link"):
        await session.flush()
        await sync_link(session, oid, fields["gps_link"])
    await session.commit()
    await audit(session, request, "shipment.create" if obj is None else "shipment.update", "shipment", oid, {"fields": sorted(fields)})
    return {"ok": True, "order_id": oid}

@app.delete("/admin/shipments/{order_id}", dependencies=[Depends(admin)])
async def soft_delete(order_id: str, request: Request, restore: bool = False, session=Depends(get_session)):
    obj = await session.get(Shipment, order_id)
    if not obj:
        raise HTTPException(404)
    obj.deleted_at = None if restore else datetime.now(timezone.utc)
    await session.commit()
    await audit(session, request, "shipment.restore" if restore else "shipment.delete", "shipment", order_id)
    return {"ok": True}

from api.gps import make_router  # noqa: E402

app.include_router(make_router(admin, public, get_session))
from api.imports import make_router as make_imports_router  # noqa: E402

app.include_router(make_imports_router(admin, public, get_session))

@app.post("/admin/shipments/bulk")
async def bulk(data: dict, request: Request, session=Depends(get_session), _u: str = Depends(admin)):
    ids, status = data.get("order_ids") or [], data.get("status")
    if not ids or status not in ("in_transit", "planned", "delivered"):
        raise HTTPException(422, "Нужны order_ids и status in_transit|planned|delivered")
    n = 0
    for oid in ids:
        s = await session.get(Shipment, oid)
        if s and not s.deleted_at:
            s.status = status; n += 1
    await session.commit()
    await audit(session, request, "shipment.bulk_status", "shipment", None, {"status": status, "ids": ids[:200], "updated": n})
    return {"updated": n}

from api.auth import make_router as make_auth_router  # noqa: E402
from ratelimit import limiter_middleware  # noqa: E402

app.include_router(make_auth_router(get_session))
app.middleware("http")(limiter_middleware)

from api.admin_pages import make_router as make_pages_router  # noqa: E402

app.include_router(make_pages_router(get_session))
