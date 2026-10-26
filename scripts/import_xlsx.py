import argparse, asyncio, json, sys
sys.path.insert(0, ".")
from db import session_maker
from importers.excel import import_xlsx
from main import Base, get_engine

async def run(a):
    async with get_engine().begin() as c:
        await c.run_sync(Base.metadata.create_all)
    mapping = json.load(open(a.mapping, encoding="utf-8")) if a.mapping else None
    async with session_maker()() as s:
        r = await import_xlsx(s, a.path, sheet_name=a.sheet, mapping=mapping, filename=a.path,
                              uploaded_by="cli", dry_run=a.dry_run)
    for b in r["batches"]:
        print(f'{b["sheet_name"]}: inserted={b["inserted"]} updated={b["updated"]} errors={len(b["errors"])} [{b["status"]}]')
        for e in b["errors"][:20]:
            print("   ", e)
    print("ИТОГО", r["total"], "(dry-run, без записи)" if a.dry_run else "")

p = argparse.ArgumentParser()
p.add_argument("path", nargs="?", default="data/Отгрузки 2026.xlsx")
p.add_argument("--sheet", default="all")
p.add_argument("--dry-run", action="store_true")
p.add_argument("--mapping", help="JSON {лист: {колонка: поле}}")
asyncio.run(run(p.parse_args()))
