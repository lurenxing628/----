"""Read one owned live fixture's complete SQLite state without opening it writable."""

import argparse
import base64
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path


def capture(root, label):
    root = root.resolve(strict=True)
    identity = json.loads((root / "isolation.json").read_text(encoding="utf-8"))
    if (identity.get("kind") != "workbench-live-fixture" or Path(identity["root"]).resolve() != root
            or not root.name.startswith("aps-workbench-live-") or not label.replace("-", "").isalnum()):
        raise ValueError("Only the declared private live fixture and a simple evidence label are permitted")
    database = (root / "db/aps-live.db").resolve(strict=True)
    database.relative_to(root)
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        schema = [dict(row) for row in conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")]
        names = [row["name"] for row in schema if row["type"] == "table"]
        tables = {name: [dict(row) for row in conn.execute('SELECT * FROM "' + name.replace('"', '""') + '" ORDER BY rowid')]
                  for name in names}
        assert conn.total_changes == 0
    def encode(value):
        if isinstance(value, bytes):
            return {"sqlite_blob_base64": base64.b64encode(value).decode("ascii")}
        raise TypeError(type(value).__name__)
    content = json.dumps({"schema": schema, "tables": tables}, sort_keys=True, ensure_ascii=False, default=encode).encode("utf-8")
    target = root / "snapshots" / (label + ".json")
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        raise ValueError("Snapshot labels cannot overwrite an earlier witness")
    target.write_bytes(content)
    return {"path": str(target), "sha256": hashlib.sha256(content).hexdigest(), "tables": len(tables), "query_only": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("label")
    args = parser.parse_args()
    print(json.dumps(capture(args.root, args.label)))
