import json
import httpx
import pytest
from parsers import _browser
from parsers.axenta import AxentaParser
from parsers.base import find_coords
from parsers.baltgps_wialon import BaltgpsWialonParser
from parsers.registry import get_parser

def test_find_coords_variants():
    assert find_coords({"a": {"lat": 54.7, "lng": 20.5}}) == (54.7, 20.5)
    assert find_coords([{"position": {"latitude": 1.5, "longitude": 2.5}}]) == (1.5, 2.5)
    assert find_coords({"coords": {"lat": 3, "lon": 4}}) == (3.0, 4.0)
    assert find_coords({"x": 1}) is None

@pytest.mark.parametrize("url,name", [
    ("https://maps.baltgps.ru/locator/index.html?t=abc", "BaltgpsWialonParser"),
    ("https://gs.baltgps.ru/locator?authId=1", "BaltgpsWialonParser"),
    ("https://axenta.cloud/locator/uuid", "AxentaParser"),
    ("http://mt.navi39.ru/radar/index.html?token=x", "Navi39Parser"),
    ("https://maps.yandex.ru/location-sharing?token=x", "YandexSharingParser"),
])
def test_registry(url, name):
    assert type(get_parser(url)).__name__ == name

def test_registry_none():
    assert get_parser("прошел") is None and get_parser("https://example.com") is None

async def test_wialon_api():
    def handler(req: httpx.Request):
        svc = req.url.params["svc"]
        if svc == "token/login":
            return httpx.Response(200, json={"eid": "a" * 32, "token": json.dumps({"items": [5]})})
        return httpx.Response(200, json={"item": {"nm": "T", "pos": {"x": 20.5, "y": 54.7}}})
    c = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    p = await BaltgpsWialonParser(c).fetch("https://maps.baltgps.ru/locator/index.html?t=abc")
    assert (p.lat, p.lng, p.source) == (54.7, 20.5, "baltgps_wialon")

async def test_playwright_unavailable(monkeypatch):
    async def boom():
        raise ImportError("no playwright")
    monkeypatch.setattr(_browser, "_get_browser", boom)
    assert await AxentaParser().fetch("https://axenta.cloud/locator/x") is None
