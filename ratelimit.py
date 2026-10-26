"""Rate-limit в памяти процесса (без Redis): скользящее окно 60 с на IP. Публичные — 60/мин, с авторизацией — 600/мин.
IP берётся из X-Forwarded-For (за прокси Layero). Счётчики не общие между воркерами."""
import time
from collections import defaultdict, deque

from fastapi.responses import JSONResponse

from config import settings

PUBLIC_LIMIT, AUTH_LIMIT, WINDOW = 60, 600, 60
_hits: dict[str, deque] = defaultdict(deque)

def reset() -> None:
    _hits.clear()

def _ip(request) -> str:
    xff = request.headers.get("x-forwarded-for")
    return xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown")

async def limiter_middleware(request, call_next):
    p = request.url.path
    if not settings.rate_limit_enabled or not (p.startswith("/api/") or p.startswith("/admin")):
        return await call_next(request)
    authed = "authorization" in request.headers or "access_token" in request.cookies
    limit = AUTH_LIMIT if authed else PUBLIC_LIMIT
    q = _hits[f"{_ip(request)}:{'a' if authed else 'p'}"]
    now = time.monotonic()
    while q and now - q[0] > WINDOW:
        q.popleft()
    if len(q) >= limit:
        return JSONResponse({"detail": "Слишком много запросов"}, status_code=429,
                            headers={"Retry-After": str(int(WINDOW - (now - q[0])) + 1)})
    q.append(now)
    return await call_next(request)
