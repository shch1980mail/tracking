from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from deps import admin, require_admin
from models.audit import AuditLog
from models.users import User
from services import auth
from services.audit import audit

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

def _udto(u: User) -> dict:
    return {"id": u.id, "login": u.login, "role": u.role, "is_active": u.is_active, "created_at": u.created_at.isoformat()}

def _set(resp, request, name, value, age):
    resp.set_cookie(name, value, max_age=age, httponly=True, samesite="lax", secure=request.url.scheme == "https")

def make_router(get_session) -> APIRouter:
    r = APIRouter()

    @r.get("/admin/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        return templates.TemplateResponse(request, "admin/login.html", {"error": ""})

    @r.post("/admin/login")
    async def login(request: Request, login: str = Form(...), password: str = Form(...), session=Depends(get_session)):
        await auth.ensure_first_admin(session)
        u = await auth.authenticate(session, login, password)
        if not u:
            return templates.TemplateResponse(request, "admin/login.html", {"error": "Неверный логин или пароль"}, status_code=401)
        resp = RedirectResponse("/admin/import", status_code=303)
        _set(resp, request, "access_token", await auth.create_token(session, u.login, "access", 15), 15 * 60)
        _set(resp, request, "refresh_token", await auth.create_token(session, u.login, "refresh", 7 * 24 * 60), 7 * 86400)
        return resp

    @r.api_route("/admin/logout", methods=["GET", "POST"])
    async def logout():
        resp = RedirectResponse("/admin/login", status_code=303)
        resp.delete_cookie("access_token"); resp.delete_cookie("refresh_token")
        return resp

    @r.post("/admin/refresh")
    async def refresh(request: Request, session=Depends(get_session)):
        u = await auth.user_from_token(session, request.cookies.get("refresh_token", ""), "refresh")
        if not u:
            raise HTTPException(401, "Refresh-токен недействителен")
        resp = JSONResponse({"ok": True})
        _set(resp, request, "access_token", await auth.create_token(session, u.login, "access", 15), 15 * 60)
        return resp

    @r.get("/admin/users")
    async def users(request: Request, _u=Depends(require_admin), session=Depends(get_session)):
        if "text/html" in request.headers.get("accept", ""):
            return templates.TemplateResponse(request, "admin/users.html")
        return [_udto(u) for u in await session.scalars(select(User).order_by(User.id))]

    @r.post("/admin/users")
    async def create(data: dict, request: Request, _u=Depends(require_admin), session=Depends(get_session)):
        try:
            u = await auth.create_user(session, data.get("login", ""), data.get("password", ""), data.get("role", "viewer"))
        except ValueError as e:
            raise HTTPException(422, str(e))
        await audit(session, request, "user.create", "user", u.id, {"login": u.login, "role": u.role})
        return _udto(u)

    @r.patch("/admin/users/{uid}")
    async def update(uid: int, data: dict, request: Request, _u=Depends(require_admin), session=Depends(get_session)):
        u = await session.get(User, uid)
        if not u:
            raise HTTPException(404)
        if u.login == request.state.user and (data.get("is_active") is False or data.get("role", u.role) != "admin"):
            raise HTTPException(409, "Нельзя заблокировать или понизить самого себя")
        changed = {}
        if "role" in data:
            if data["role"] not in auth.ROLES:
                raise HTTPException(422, "Неизвестная роль")
            u.role = changed["role"] = data["role"]
        if "is_active" in data:
            u.is_active = changed["is_active"] = bool(data["is_active"])
        if data.get("password"):
            if len(data["password"]) < 6:
                raise HTTPException(422, "Пароль ≥6 символов")
            u.password_hash = auth.hash_pw(data["password"]); changed["password_reset"] = True
        await session.commit()
        await audit(session, request, "user.update", "user", u.id, changed)
        return _udto(u)

    @r.get("/admin/audit")
    async def audit_list(request: Request, limit: int = 100, action: str = "", user: str = "", frm: str = "", to: str = "",
                         _u=Depends(require_admin), session=Depends(get_session)):
        if "text/html" in request.headers.get("accept", ""):
            return templates.TemplateResponse(request, "admin/audit.html")
        stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 1000))
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if user:
            stmt = stmt.where(AuditLog.login == user)
        try:
            if frm:
                stmt = stmt.where(AuditLog.created_at >= datetime.fromisoformat(frm))
            if to:
                stmt = stmt.where(AuditLog.created_at <= datetime.fromisoformat(to))
        except ValueError:
            raise HTTPException(422, "Даты в формате ISO (2026-10-26)")
        return [{"id": a.id, "login": a.login, "action": a.action, "entity": a.entity, "entity_id": a.entity_id,
                 "payload": a.payload, "created_at": a.created_at.isoformat()} for a in await session.scalars(stmt)]

    return r
