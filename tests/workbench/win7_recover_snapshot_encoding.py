"""Re-read immutable native snapshots; preserve the original failed JSON reports."""
import hashlib
import json
import shutil
import sqlite3
import sys
import uuid
from pathlib import Path


def read_db(file):
    with sqlite3.connect(file.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {
            "schema": [list(row) for row in conn.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name")],
            "version": conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0],
            "tables": {name: [dict(row) for row in conn.execute('SELECT rowid AS __oracle_rowid__,* FROM "' + name + '" ORDER BY rowid')] for name in names},
            "integrity": conn.execute("PRAGMA integrity_check").fetchone()[0],
            "foreign_keys": [list(row) for row in conn.execute("PRAGMA foreign_key_check")],
        }


def main():
    evidence, run = map(lambda value: Path(value).resolve(), sys.argv[1:3])
    report = json.loads((run / "an-process-batch-report.json").read_text(encoding="utf-8"))
    candidates = []
    for item in report["guest_snapshots"]:
        db = evidence / "exchange/snapshots" / (item["id"] + ".db")
        assert hashlib.sha256(db.read_bytes()).hexdigest() == item["sha256"]
        correct = read_db(db)
        assert correct["integrity"] == "ok" and not correct["foreign_keys"]
        serialized = json.dumps(correct, ensure_ascii=False, default=str)
        historical = json.loads(serialized.encode("cp936", errors="backslashreplace").decode("utf-8", errors="replace"))
        candidates.append((item, db, correct, historical))
    output = run / "verified-utf8-snapshots"
    output.mkdir(exist_ok=False)
    result = []
    for case in report["cases"]:
        if case.get("error"):
            continue
        target = output / case["id"]
        target.mkdir()
        (target / "db").mkdir()
        record = {"case": case["id"], "policy": case["policy"], "original_report": str(run / "an-process-batch-report.json"), "snapshots": {}}
        for side in ("before", "after"):
            old = json.loads((run / ("oracle-" + case["id"] + "-" + side + ".json")).read_text(encoding="utf-8"))
            matched = [item for item in candidates if item[3] == old]
            assert matched, "No matching immutable snapshot: " + case["id"] + "/" + side
            assert all(item[2] == matched[0][2] for item in matched), "Ambiguous Unicode state; do not infer it"
            meta, db, correct, _ = matched[0]
            (target / (side + ".json")).write_text(json.dumps(correct, ensure_ascii=False, indent=2), encoding="utf-8")
            record["snapshots"][side] = {"id": meta["id"], "sha256": meta["sha256"], "equivalent_sources": len(matched)}
            if side == "after":
                shutil.copyfile(str(db), str(target / "db/aps-live.db"))
        (target / "isolation.json").write_text(json.dumps({"schema_version": 1, "kind": "workbench-live-fixture", "root": str(target), "nonce": uuid.uuid4().hex}), encoding="utf-8")
        record["root"] = str(target)
        result.append(record)
    (output / "bindings.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"cases": len(result), "bindings": str(output / "bindings.json")}))


if __name__ == "__main__":
    main()
