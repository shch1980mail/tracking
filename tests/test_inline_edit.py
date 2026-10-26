async def test_partial_update_keeps_fields(client):
    await client.post("/admin/shipments", json={"order_id": "A1", "carrier": "Лого", "comment": "c", "status": "in_transit", "weight": "20000", "gps_link": "https://axenta.cloud/locator/u"})
    assert (await client.post("/admin/shipments", json={"order_id": "A1", "comment": "новый"})).status_code == 200
    r = (await client.get("/admin/api/shipments?q=A1")).json()["rows"][0]
    assert (r["comment"], r["carrier"], r["status"], r["weight"]) == ("новый", "Лого", "in_transit", 20000.0)
    await client.post("/admin/shipments", json={"order_id": "A1", "gps_link": ""})  # пусто = очистить
    assert (await client.get("/admin/api/shipments?q=A1")).json()["rows"][0]["gps_link"] is None

async def test_validation_and_create_only(client):
    await client.post("/admin/shipments", json={"order_id": "A2"})
    assert (await client.post("/admin/shipments", json={"order_id": "A2", "_create": True})).status_code == 409
    assert (await client.post("/admin/shipments", json={"order_id": "A2", "status": "bad"})).status_code == 422
    assert (await client.post("/admin/shipments", json={"order_id": "A2", "gps_link": "ftp://x"})).status_code == 422
    assert (await client.post("/admin/shipments", json={"order_id": "A2", "weight": "abc"})).status_code == 422
