import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import func, select

from config import settings
from models.imports import Setting
from models.users import User

ROLES = ("admin", "manager", "viewer")
_secret: str | None = None

def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt()).decode()

def check_pw(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode()[:72], h.encode())
    except ValueError:
        return False

async def get_secret(session) -> str:
    """SECRET_KEY из env, иначе генерируется один раз и хранится в settings (jwt_secret)."""
    global _secret
    if settings.secret_key:
        return settings.secret_key
    if _secret:
        return _secret
    s = await session.get(Setting, "jwt_secret")
    if s is None:
        s = Setting(key="jwt_secret", value={"v": secrets.token_urlsafe(48)})
        session.add(s); await session.commit()
    _secret = s.value["v"]
    return _secret

async def create_user(session, login: str, password: str, role: str = "viewer") -> User:
    login = (login or "").strip()
    if not login or len(password or "") < 6 or role not in ROLES:
        raise ValueError("Нужны логин, пароль (≥6 символов) и роль admin|manager|viewer")
    if await session.scalar(select(User).where(User.login == login)):
        raise ValueError("Логин занят")
    u = User(login=login, password_hash=hash_pw(password), role=role, is_active=True)
    session.add(u); await session.commit()
    return u

async def authenticate(session, login: str, password: str) -> User | None:
    u = await session.scalar(select(User).where(User.login == login))
    return u if u and u.is_active and check_pw(password, u.password_hash) else None

async def create_token(session, login: str, kind: str = "access", minutes: int = 15) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode({"sub": login, "typ": kind, "exp": exp}, await get_secret(session), algorithm="HS256")

async def user_from_token(session, token: str, kind: str = "access") -> User | None:
    try:
        p = jwt.decode(token, await get_secret(session), algorithms=["HS256"])
    except JWTError:
        return None
    if p.get("typ") != kind:
        return None
    u = await session.scalar(select(User).where(User.login == p.get("sub")))
    return u if u and u.is_active else None

async def ensure_first_admin(session) -> None:
    if await session.scalar(select(func.count()).select_from(User)) == 0:
        await create_user(session, settings.admin_login, settings.admin_password, "admin")
