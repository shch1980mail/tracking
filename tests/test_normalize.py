import sys; sys.path.insert(0, ".")
from datetime import date
from services.normalize import norm_status, parse_driver, parse_vehicle, to_date

def test_status():
    assert norm_status("завершено") == "delivered"
    assert norm_status("в плане") == "planned"
    assert norm_status("в пути") == "in_transit"
    assert norm_status("На выгрузке", "выгружен") == "delivered"

def test_dates():
    assert to_date("09.01.2026") == date(2026, 1, 9)
    assert to_date(46031) == date(2026, 1, 9)
    assert to_date(None) is None

def test_driver():
    d = parse_driver("Кипкало Николай Николаевич т.м. +79632982399")
    assert d["driver_fio"] == "Кипкало Николай Николаевич" and d["driver_phone"].startswith("+7963")

def test_vehicle():
    assert parse_vehicle("TKRU0412152")["vehicle_type"] == "контейнер"
    assert parse_vehicle("Даф О546ХУ/39 // АЕ3571/39")["vehicle_tractor"] == "Даф О546ХУ"
