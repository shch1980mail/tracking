async def test_csv(client):
    await client.post("/admin/shipments", json={"order_id": "ТПК1", "address": "=cmd", "carrier": "Лого",
                      "driver_raw": "Иванов Иван Иванович +79110000000 паспорт 2700 123456"})
    await client.post("/admin/shipments", json={"order_id": "ТПК2", "status_raw": "завершено"})
    r = await client.get("/api/shipments.csv")
    assert r.content.startswith(b"\xef\xbb\xbf") and "Заказ" in r.text.splitlines()[0]
    assert "123456" not in r.text and "'=cmd" in r.text and "Иванов Иван Иванович" in r.text
    assert len((await client.get("/api/shipments.csv?q=нет-такого")).text.splitlines()) == 1
    d = (await client.get("/api/shipments.csv?tab=delivered")).text
    assert "ТПК2" in d and "ТПК1" not in d
