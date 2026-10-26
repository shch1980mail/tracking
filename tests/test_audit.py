from tests.conftest import files, make_xlsx

async def test_audit_and_bulk(client):
    await client.post("/admin/shipments", json={"order_id": "A1", "comment": "x"})
    await client.post("/admin/shipments", json={"order_id": "A1", "comment": "y"})
    assert (await client.post("/admin/shipments/bulk", json={"order_ids": ["A1"], "status": "delivered"})).json()["updated"] == 1
    assert (await client.get("/api/shipments?tab=delivered")).json()[0]["order_id"] == "A1"
    assert (await client.post("/admin/shipments/bulk", json={"order_ids": ["A1"], "status": "bad"})).status_code == 422
    await client.delete("/admin/shipments/A1")
    b = (await client.post("/admin/import/commit", files=files(make_xlsx()), data={"sheet_names": '["Москва"]'})).json()["batches"][0]
    await client.post(f"/admin/import/{b['batch_id']}/rollback")
    await client.put("/admin/import/mapping/Входящие", json={"Заказ": "order_id"})
    acts = [a["action"] for a in (await client.get("/admin/audit")).json()]
    for x in ("shipment.create", "shipment.update", "shipment.bulk_status", "shipment.delete", "import.commit",
              "import.rollback", "settings.mapping_set"):
        assert x in acts, x
    f = (await client.get("/admin/audit?action=import.commit&user=admin")).json()
    assert len(f) == 1 and f[0]["login"] == "admin"
