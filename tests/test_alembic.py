import os, sqlite3, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
TABLES = {"shipments", "shipment_positions", "gps_links", "inbound_shipments", "local_shipments", "moscow_shipments",
          "transit_to_tencard", "import_batches", "settings", "users", "audit_log"}

def _run(cmd, db):
    env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{db}"}
    r = subprocess.run([sys.executable, "-m", "alembic", *cmd], cwd=ROOT, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]

def _tables(db):
    return {r[0] for r in sqlite3.connect(db).execute("select name from sqlite_master where type='table'")}

def test_upgrade_downgrade(tmp_path):
    db = str(tmp_path / "m.db")
    _run(["upgrade", "head"], db)
    assert TABLES <= _tables(db)
    _run(["downgrade", "base"], db)
    assert not (TABLES & _tables(db))
