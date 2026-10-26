from sqlalchemy import select
from models.sheets import InboundShipment
from tests.conftest import files, make_xlsx

async def test_mapping_crud(client):
    m = {"Заказ": "order_id", "Груз": "cargo"}
    assert (await client.put("/admin/import/mapping/Входящие", json=m)).status_code == 200
    g = (await client.get("/admin/import/mapping/Входящие")).json()
    assert g["saved"] == {"заказ": "order_id", "груз": "cargo"} and g["default"]
    assert (await client.put("/admin/import/mapping/Входящие", json={"Заказ": "nope"})).status_code == 422
    assert (await client.put("/admin/import/mapping/Исх.логистика", json=m)).status_code == 422
    await client.delete("/admin/import/mapping/Входящие")
    assert (await client.get("/admin/import/mapping/Входящие")).json()["saved"] is None

async def test_commit_applies_custom_mapping(client, maker):
    import json
    mp = {"Входящие": {"Номер заказа": "order_id", "Груз": "cargo"}}
    r = await client.post("/admin/import/commit", files=files(make_xlsx(inbound_head="Номер заказа")),
                          data={"sheet_names": '["Входящие"]', "mapping": json.dumps(mp)})
    assert r.json()["batches"][0]["inserted"] == 2
    async with maker() as s:
        row = (await s.scalars(select(InboundShipment).where(InboundShipment.order_id == "ТПК19"))).one()
        assert row.cargo == "Масло" and row.weight is None  # вес не в маппинге
