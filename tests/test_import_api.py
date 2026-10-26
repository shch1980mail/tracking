from tests.conftest import files, make_xlsx

async def test_import_flow(client):
    assert (await client.post("/admin/import/preview", files=files(b"junk"))).status_code == 422
    p = (await client.post("/admin/import/preview", files=files(make_xlsx()))).json()
    assert len(p["sheets"]) == 6 and p["ignored"] == ["Лист2"]
    c = (await client.post("/admin/import/commit", files=files(make_xlsx()), data={"sheet_names": "all"})).json()
    assert len(c["batches"]) == 6
    h = (await client.get("/admin/import/history")).json()
    assert len(h) == 6 and h[0]["id"] > h[-1]["id"]
    bid = next(x["id"] for x in h if x["sheet_name"] == "Москва")
    assert (await client.get(f"/admin/import/{bid}")).json()["sheet_name"] == "Москва"
    assert (await client.post(f"/admin/import/{bid}/rollback")).json()["removed"] == 1
    assert (await client.post(f"/admin/import/{bid}/rollback")).status_code == 409
    assert (await client.post("/admin/import/9999/rollback")).status_code == 404

async def test_auth_required(client):
    r = await client.get("/admin/import/history", auth=("x", "y"))
    assert r.status_code == 401

async def test_legacy_alias(client):
    r = await client.post("/admin/import", files=files(make_xlsx()))
    assert r.json()["inserted"] == 1 and r.json()["deprecated"]
