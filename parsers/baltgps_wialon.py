import json
import re
import time
from contextlib import nullcontext
from urllib.parse import parse_qs, urlparse

import httpx
import structlog

from parsers._browser import browse
from parsers.base import GpsParser, Position

log = structlog.get_logger()
HOSTS = ("maps.baltgps.ru", "wl.baltgps.ru", "m.baltgps.ru", "gs.baltgps.ru")
SID_RE = re.compile(r"[?&]sid=([a-f0-9]{20,})")
SID_TTL = 30 * 60
_sid_cache: dict[str, tuple[str, float]] = {}  # host -> (sid, ts); в памяти процесса, TTL 30 мин

class WialonError(Exception):
    pass

def _cached(host: str) -> str | None:
    v = _sid_cache.get(host)
    return v[0] if v and time.time() - v[1] < SID_TTL else None

class BaltgpsWialonParser(GpsParser):
    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    def supports(self, url: str) -> bool:
        return urlparse(url).hostname in HOSTS

    async def _api(self, c, base, svc, params, sid=None):
        q = {"svc": svc, "params": json.dumps(params)}
        if sid:
            q["sid"] = sid
        d = (await c.get(f"{base}/wialon/ajax.html", params=q)).json()
        if isinstance(d, dict) and d.get("error"):
            raise WialonError(d["error"])
        return d

    async def _via_api(self, base, host, token, sid=None):
        cm = nullcontext(self._client) if self._client else httpx.AsyncClient(timeout=15)
        async with cm as c:
            ids: list = []
            if not sid:
                login = await self._api(c, base, "token/login", {"token": token})
                sid = login["eid"]
                try:
                    ids = list(json.loads(login.get("token") or "{}").get("items") or [])
                except (ValueError, AttributeError):
                    ids = []
            if ids:
                item = (await self._api(c, base, "core/search_item", {"id": ids[0], "flags": 1025}, sid)).get("item")
            else:
                spec = {"itemsType": "avl_unit", "propName": "sys_name", "propValueMask": "*", "sortType": "sys_name"}
                r = await self._api(c, base, "core/search_items",
                                    {"spec": spec, "force": 1, "flags": 1025, "from": 0, "to": 1}, sid)
                item = (r.get("items") or [None])[0]
            pos = (item or {}).get("pos")
            if not pos:
                return None
            _sid_cache[host] = (sid, time.time())
            return Position(lat=pos["y"], lng=pos["x"], source="baltgps_wialon",
                            raw_payload={"unit": item.get("nm"), "pos": pos})

    async def fetch(self, url: str) -> Position | None:
        u = urlparse(url)
        token = parse_qs(u.query).get("t", [None])[0]
        if not token:
            log.warning("baltgps_no_token", url=url[:60])
            return None
        base = f"https://{u.hostname}"
        for sid in (_cached(u.hostname), None):  # 1) кэшированный sid, 2) новый login
            try:
                return await self._via_api(base, u.hostname, token, sid)
            except (WialonError, httpx.HTTPError, KeyError, ValueError) as e:
                log.info("wialon_api_failed", error=str(e)[:100], had_sid=bool(sid))
                _sid_cache.pop(u.hostname, None)
        # Playwright-фолбэк: перехват sid из запросов страницы
        sid = await browse(url, lambda ru, _b: (m.group(1) if (m := SID_RE.search(ru)) else None))
        if not sid:
            return None
        try:
            return await self._via_api(base, u.hostname, token, sid)
        except Exception as e:
            log.warning("wialon_fallback_failed", error=str(e)[:100])
            return None
