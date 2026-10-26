"""Общий Playwright-хелпер: один браузер, Semaphore(3), без mouse.click/wait_for_timeout.
Ждём первый ответ, подходящий под предикат (аналог page.wait_for_response)."""
import asyncio
from urllib.parse import urlparse

import structlog

from parsers.base import GpsParser, Position, find_coords

log = structlog.get_logger()
_sem = asyncio.Semaphore(3)
_pw = None
_browser = None

async def _get_browser():
    global _pw, _browser
    if _browser is None:
        from playwright.async_api import async_playwright  # ImportError -> graceful None
        _pw = await async_playwright().start()
        _browser = await _pw.chromium.launch()
    return _browser

async def browse(url: str, want, timeout: float = 15.0):
    """want(response_url, json_or_None) -> значение или None. Возвращает первое значение либо None."""
    try:
        async with _sem:
            ctx = await (await _get_browser()).new_context()
            try:
                page = await ctx.new_page()
                fut = asyncio.get_running_loop().create_future()

                async def on_resp(resp):
                    if fut.done():
                        return
                    try:
                        body = await resp.json()
                    except Exception:
                        body = None
                    val = want(resp.url, body)
                    if val is not None and not fut.done():
                        fut.set_result(val)

                page.on("response", lambda r: asyncio.ensure_future(on_resp(r)))
                await page.goto(url, wait_until="domcontentloaded")
                return await asyncio.wait_for(fut, timeout)
            finally:
                await ctx.close()
    except Exception as e:
        log.warning("playwright_unavailable_or_failed", error=str(e)[:200])
        return None

class XhrParser(GpsParser):
    """Перехват XHR/JSON с координатами."""
    source = ""
    host = ""
    path_hint = ""

    def supports(self, url: str) -> bool:
        u = urlparse(url)
        return u.hostname == self.host and self.path_hint in u.path + "?" + u.query

    async def fetch(self, url: str) -> Position | None:
        res = await browse(url, lambda _u, body: find_coords(body) if body else None)
        return Position(res[0], res[1], self.source, {"url": url}) if res else None
