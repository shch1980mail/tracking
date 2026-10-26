import io
from sqlalchemy import select
from importers.excel import import_xlsx, preview, rollback
from models.sheets import InboundShipment, TransitToTencard
from models.shipment import Shipment
from tests.conftest import make_xlsx

def test_preview():
    p = preview(io.BytesIO(make_xlsx()), "Входящие")
    assert "Заказ" in p["headers"] and len(p["rows"]) <= 5 and p["mapping_default"]["заказ"] == "order_id"

async def test_import_all_sheets(maker):
    async with maker() as s:
        r = await import_xlsx(s, io.BytesIO(make_xlsx()))
        names = {b["sheet_name"]: b for b in r["batches"]}
        assert len(names) == 6 and "Лист2" not in names
        inb = names["Входящие"]
        assert inb["inserted"] == 1 and inb["status"] == "partial"
        assert any("дубль" in e for e in inb["errors"]) and any("невалидная дата" in e for e in inb["errors"])
        sh = await s.get(Shipment, "ТПК1")
        assert sh.status == "planned" and str(sh.plan_arrival) == "2026-10-24" and sh.notes == "Инмар"  # ПланНеделя
        assert (await s.get(Shipment, "ТПК2")).status == "planned"
        assert (await s.get(InboundShipment, "ТПК18")).transit_days == 14
        assert (await s.get(TransitToTencard, "ТПК55")).vehicle_type == "ПАРОМ прицеп"

async def test_dry_run_and_no_delete(maker):
    async with maker() as s:
        r = await import_xlsx(s, io.BytesIO(make_xlsx()), dry_run=True)
        assert r["total"]["inserted"] > 0 and not (await s.scalars(select(Shipment))).all()
        await import_xlsx(s, io.BytesIO(make_xlsx()))
        await import_xlsx(s, io.BytesIO(make_xlsx()), sheet_name="Входящие")  # повтор: ничего не удаляется
        assert len((await s.scalars(select(Shipment))).all()) == 2

async def test_rollback_created_and_updated(maker):
    async with maker() as s:
        b1 = (await import_xlsx(s, io.BytesIO(make_xlsx()), sheet_name="Исх.логистика"))["batches"][0]["batch_id"]
        b2 = (await import_xlsx(s, io.BytesIO(make_xlsx(carrier="Новый")), sheet_name="Исх.логистика"))["batches"][0]["batch_id"]
        assert (await s.get(Shipment, "ТПК1")).carrier == "Новый"
        assert (await rollback(s, b2))["restored"] == 1 and (await s.get(Shipment, "ТПК1")).carrier == "Лого"
        r = await rollback(s, b1)  # запись менялась позже батча -> остаётся
        assert r["removed"] == 0 and r["kept"] == 1

async def test_rollback_removes_created(maker):
    async with maker() as s:
        b = (await import_xlsx(s, io.BytesIO(make_xlsx()), sheet_name="Исх.логистика"))["batches"][0]["batch_id"]
        assert (await rollback(s, b))["removed"] == 1 and await s.get(Shipment, "ТПК1") is None
