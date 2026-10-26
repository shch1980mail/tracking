import re
from datetime import date, datetime, timedelta

DELIVERED = ("завершено", "выгружен", "выгрузил")
PLANNED = ("в плане", "выход", "планиру")
CONTAINER = re.compile(r"\b[A-Z]{3}U\d{6,7}\b")
PHONE = re.compile(r"(\+7|8)[\s\-\(\)0-9]{10,}")
PASSPORT = re.compile(r"\d{2}\s?\d{2}\s?\d{6}|\d{4}\s?\d{6}")
STOP = re.compile(r"(?i)^(тел|т\.м|паспорт|пасп|\+7|8\d|\d)")

def clean(v) -> str | None:
    if v is None:
        return None
    s = re.sub(r"<br\s*/?>", " ", str(v), flags=re.I).strip()
    return re.sub(r"\s+", " ", s) or None

def norm_status(raw, notes=None) -> str:
    s, n = (clean(raw) or "").lower(), (clean(notes) or "").lower()
    if any(k in s for k in DELIVERED) or "выгружен" in n:
        return "delivered"
    if any(k in s for k in PLANNED) or not s:
        return "planned"
    return "in_transit"  # в пути, транзит*, прогноз*, паром, оформление и т.д.

def to_date(v) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)):
        return (datetime(1899, 12, 30) + timedelta(days=float(v))).date()
    s = str(v).strip()
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None

def parse_driver(raw) -> dict:
    s = clean(raw)
    if not s:
        return {}
    words = []
    for w in s.split():
        if STOP.match(w) or len(words) == 3:
            break
        words.append(w)
    ph, pp = PHONE.search(s), PASSPORT.search(s)
    return {"driver_raw": s, "driver_fio": " ".join(words) or None,
            "driver_phone": ph.group(0).strip() if ph else None,
            "driver_passport": pp.group(0) if pp else None}

def parse_vehicle(raw) -> dict:
    s = clean(raw)
    if not s:
        return {}
    s = s.replace("//", "/")
    out = {"vehicle_raw": s}
    m = CONTAINER.search(s.upper())
    if m:
        out.update(vehicle_container=m.group(0), vehicle_type="контейнер")
    elif "/" in s:
        a, b = s.split("/", 1)
        out.update(vehicle_tractor=a.strip(), vehicle_trailer=b.strip())
    else:
        out["vehicle_tractor"] = s
    return out

def is_url(v) -> bool:
    return isinstance(v, str) and v.strip().lower().startswith("http")
