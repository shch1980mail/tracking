import io
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from importers.excel import (IGNORED, MAIN_SHEET, SHEETS, fields_of, get_mapping, import_xlsx, preview, rollback,
                             set_mapping, sheet_names)
from models.imports import ImportBatch
from services.audit import audit

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

def make_router(admin, public, get_session) -> APIRouter:
    r = APIRouter()

    @r.get("/admin/import", response_class=HTMLResponse, dependencies=[Depends(admin)])
    async def page(request: Request):
        return templates.TemplateResponse(request, "admin/import.html")

    @r.post("/admin/import/preview", dependencies=[Depends(admin)])
    async def prev(file: UploadFile = File(...), session=Depends(get_session)):
        data = await file.read()
        try:
            names = sheet_names(io.BytesIO(data))
        except Exception:
            raise HTTPException(422, "Не удалось прочитать .xlsx")
        out = []
        for n in names:
            if n in SHEETS:
                p = preview(io.BytesIO(data), n, await get_mapping(session, n))
                out.append({"name": n, "preview_rows": p["rows"], **p})
        return {"sheets": out, "ignored": [n for n in names if n not in SHEETS]}

    @r.post("/admin/import/commit")
    async def commit(request: Request, file: UploadFile = File(...), sheet_names: str = Form("all"), mapping: str = Form(""),
                     session=Depends(get_session), user: str = Depends(admin)):
        try:
            sheets = None if sheet_names in ("all", "") else json.loads(sheet_names)
            maps = json.loads(mapping) if mapping else None
        except ValueError:
            raise HTTPException(422, "sheet_names/mapping: некорректный JSON")
        data = await file.read()
        try:
            res = await import_xlsx(session, io.BytesIO(data), mapping=maps, sheets=sheets,
                                    filename=file.filename or "", uploaded_by=user)
        except Exception as e:
            raise HTTPException(422, f"Не удалось импортировать: {e}")
        await audit(session, request, "import.commit", "import", file.filename,
                    {"batches": [b.get("batch_id") for b in res["batches"]], "total": res["total"]})
        return res

    @r.get("/admin/import/history", dependencies=[Depends(admin)])
    async def history(limit: int = 50, session=Depends(get_session)):
        rows = await session.scalars(select(ImportBatch).order_by(ImportBatch.id.desc()).limit(min(limit, 500)))
        return [{"id": b.id, "filename": b.filename, "sheet_name": b.sheet_name, "uploaded_by": b.uploaded_by,
                 "uploaded_at": b.uploaded_at.isoformat(), "inserted": b.inserted, "updated": b.updated,
                 "errors_count": len(b.errors or []), "status": b.status} for b in rows]

    @r.get("/admin/import/mapping/{sheet}", dependencies=[Depends(admin)])
    async def get_map(sheet: str, session=Depends(get_session)):
        if sheet not in SHEETS:
            raise HTTPException(404, "Неизвестный лист")
        return {"default": SHEETS[sheet].default, "saved": await get_mapping(session, sheet)}

    @r.put("/admin/import/mapping/{sheet}", dependencies=[Depends(admin)])
    async def put_map(request: Request, sheet: str, data: dict, session=Depends(get_session)):
        if sheet not in SHEETS:
            raise HTTPException(404, "Неизвестный лист")
        if sheet == MAIN_SHEET:
            raise HTTPException(422, "Для «Исх.логистика» маппинг фиксирован (по позиции колонок)")
        bad = [f for f in data.values() if f not in fields_of(sheet)]
        if bad or "order_id" not in data.values():
            raise HTTPException(422, f"Неизвестные поля: {bad}" if bad else "Нужна колонка → order_id")
        await set_mapping(session, sheet, {k.strip().lower(): v for k, v in data.items()})
        await audit(session, request, "settings.mapping_set", "settings", sheet, data)
        return {"ok": True}

    @r.delete("/admin/import/mapping/{sheet}", dependencies=[Depends(admin)])
    async def del_map(request: Request, sheet: str, session=Depends(get_session)):
        await set_mapping(session, sheet, None)
        await audit(session, request, "settings.mapping_reset", "settings", sheet)
        return {"ok": True}

    @r.get("/admin/import/{batch_id:int}", dependencies=[Depends(admin)])
    async def detail(batch_id: int, session=Depends(get_session)):
        b = await session.get(ImportBatch, batch_id)
        if not b:
            raise HTTPException(404)
        s = b.snapshot or {}
        return {"id": b.id, "sheet_name": b.sheet_name, "status": b.status, "errors": b.errors,
                "snapshot": {"created": len(s.get("created", [])), "updated": len(s.get("updated", []))}}

    @r.post("/admin/import/{batch_id:int}/rollback", dependencies=[Depends(admin)])
    async def rb(request: Request, batch_id: int, session=Depends(get_session)):
        try:
            res = await rollback(session, batch_id)
        except LookupError:
            raise HTTPException(404, "Батч не найден")
        except ValueError as e:
            raise HTTPException(409, str(e))
        await audit(session, request, "import.rollback", "import_batch", batch_id, res)
        return res

    return r
