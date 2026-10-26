from tests.conftest import files, make_xlsx

async def test_manual_edit_survives_rollback(client):
    main = {"sheet_names": '["Исх.логистика"]'}
    b1 = (await client.post("/admin/import/commit", files=files(make_xlsx()), data=main)).json()["batches"][0]["batch_id"]
    assert (await client.post("/admin/shipments", json={"order_id": "ТПК1", "comment": "ручной"})).status_code == 200
    b2 = (await client.post("/admin/import/commit", files=files(make_xlsx(carrier="Новый")), data=main)).json()["batches"][0]["batch_id"]
    r2 = (await client.post(f"/admin/import/{b2}/rollback")).json()
    assert r2["restored"] == 1
    rows = (await client.get("/api/shipments?q=ТПК1")).json()
    assert rows[0]["carrier"] == "Лого" and rows[0]["comment"] == "ручной"
    r1 = (await client.post(f"/admin/import/{b1}/rollback")).json()  # запись правили позже -> не удаляется
    assert r1["removed"] == 0 and r1["kept"] == 1
    assert (await client.get("/api/shipments?q=ТПК1")).json()[0]["comment"] == "ручной"
