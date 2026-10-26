"""Единая авторизация: JWT-cookie -> Basic из env -> Basic из таблицы users -> 401.
Роли: viewer не может менять (POST/PUT/PATCH/DELETE -> 403)."""
import secrets

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from config import settings
from db import get_session
from services import auth

basic = HTTPBasic(auto_error=False)
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}

def _eq(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode(), b.encode())

async def admin(request: Request, session=Depends(get_session),
                cr: HTTPBasicCredentials | None = Depends(basic)) -> str:
    login = role = uid = None
    if (tok := request.cookies.get("access_token")):
        if (u := await auth.user_from_token(session, tok, "access")):
            login, role, uid = u.login, u.role, u.id
    if login is None and request.method == "GET" and (rt := request.cookies.get("refresh_token")):
        if (u := await auth.user_from_token(session, rt, "refresh")):  # access истёк — страницы не выкидывают на логин
            login, role, uid = u.login, u.role, u.id
    if login is None and cr is not None:
        if _eq(cr.username, settings.admin_login) and _eq(cr.password, settings.admin_password):
            login, role = cr.username, "admin"
        elif (u := await auth.authenticate(session, cr.username, cr.password)):
            login, role, uid = u.login, u.role, u.id
    if login is None:
        if cr is None and "text/html" in request.headers.get("accept", ""):
            raise HTTPException(307, headers={"Location": "/admin/login"})
        raise HTTPException(401, headers={"WWW-Authenticate": "Basic"})
    if role == "viewer" and request.method in UNSAFE:
        raise HTTPException(403, "Недостаточно прав (роль viewer)")
    request.state.user, request.state.role, request.state.user_id = login, role, uid
    return login

async def require_admin(request: Request, user: str = Depends(admin)) -> str:
    if request.state.role != "admin":
        raise HTTPException(403, "Только для admin")
    return user
