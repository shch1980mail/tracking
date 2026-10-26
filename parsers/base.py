from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class Position:
    lat: float
    lng: float
    source: str
    raw_payload: dict | None = None

class GpsParser(ABC):
    @abstractmethod
    def supports(self, url: str) -> bool: ...

    @abstractmethod
    async def fetch(self, url: str) -> Position | None: ...

LAT_KEYS, LNG_KEYS = ("lat", "latitude"), ("lng", "lon", "longitude")

def _num(o: dict, keys):
    return next((o[k] for k in keys if isinstance(o.get(k), (int, float)) and not isinstance(o.get(k), bool)), None)

def find_coords(obj) -> tuple[float, float] | None:
    """Рекурсивный поиск lat/lng, latitude/longitude, position.lat, coords.{lat,lng} и т.п."""
    if isinstance(obj, dict):
        lat, lng = _num(obj, LAT_KEYS), _num(obj, LNG_KEYS)
        if lat is not None and lng is not None and (lat or lng):
            return float(lat), float(lng)
        for v in obj.values():
            if (r := find_coords(v)):
                return r
    elif isinstance(obj, list):
        for v in obj:
            if (r := find_coords(v)):
                return r
    return None
