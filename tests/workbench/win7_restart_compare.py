"""Compare copied Win7 snapshots across an actual application restart."""
import json
import sqlite3
import sys
from pathlib import Path


def snapshot(path):
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        schema = conn.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name").fetchall()
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return schema, {name: conn.execute('SELECT rowid,* FROM "' + name.replace('"', '""') + '" ORDER BY rowid').fetchall() for name in tables}


def main():
    before_schema, before = snapshot(sys.argv[1])
    after_schema, after = snapshot(sys.argv[2])
    assert before_schema == after_schema
    verified = []
    operational = {}
    for table, rows in before.items():
        if table in ("OperationLogs", "SystemJobState", "sqlite_sequence"):
            operational[table] = {"before_rows": len(rows), "after_rows": len(after[table]), "changed": rows != after[table]}
            if table == "OperationLogs":
                by_rowid = {row[0]: row for row in after[table]}
                assert all(by_rowid.get(row[0]) == row for row in rows), "Existing operation log changed"
            continue
        assert rows == after[table], "Restart changed persisted data: " + table
        verified.append({"table": table, "rows": len(rows)})
    result = {"passed": True, "integrity": "ok", "foreign_keys": [], "exact_tables": verified,
              "operational_tables": operational, "before": sys.argv[1], "after": sys.argv[2]}
    Path(sys.argv[3]).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": True, "exact_tables": len(verified), "operational_tables": operational}))


if __name__ == "__main__":
    main()
