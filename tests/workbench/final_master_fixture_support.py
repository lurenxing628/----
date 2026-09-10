"""Task C private full build, production factory fixture and immutable evidence."""

import csv
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

from tests.workbench.live_environment import REPO, sha256, write_json
from tests.workbench.run_live_server_support import inside, tree_hashes


def source_hashes():
    paths = [REPO / "schema.sql", REPO / "config.py", REPO / "app.py", REPO / "app_new_ui.py"]
    for name in ("core", "data", "web", "frontend/workbench/app", "scripts/workbench", "templates/workbench"):
        paths.extend(path for path in (REPO / name).rglob("*") if path.is_file() and path.suffix in (".py", ".js", ".jsx", ".json", ".html", ".cjs"))
    paths.extend((REPO / "tests/workbench").glob("final_master*"))
    paths.extend((REPO / "tests/workbench").glob("test_final_master*.py"))
    return {str(path.relative_to(REPO)): sha256(path.read_bytes()) for path in sorted(set(paths)) if path.is_file()}


def changed_sources(before, after):
    return [name for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)]


def freeze_full_build(root, _session):
    marker = root / "final-master-build.json"
    if marker.exists():
        result = json.loads(marker.read_text(encoding="utf-8"))
        assert tree_hashes(Path(result["root"])) == result["hashes"]
        manifest = json.loads(Path(result["frozen_manifest"]).read_text(encoding="utf-8"))
        result["source_differences"] = [item["path"] for item in manifest["inputs"]
                                        if not (REPO / item["path"]).is_file()
                                        or sha256((REPO / item["path"]).read_bytes()) != item["sha256"]]
        result["binding"] = "same_immutable_full_build_on_restart_current_source_differences_recorded"
        return result
    frozen = root / "frozen/full-build"
    output = frozen / "static/workbench"
    command = [sys.executable, "-B", str(REPO / "scripts/workbench/build.py"),
               "--node", os.environ["WORKBENCH_NODE"], "--output-dir", str(output)]
    with (root / "full-build.log").open("w", encoding="utf-8") as stream:
        subprocess.run(command, check=True, cwd=str(root), stdout=stream, stderr=subprocess.STDOUT, timeout=300)
    path = output / "asset-manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["target"] == "chrome109"
    for row in manifest["files"]:
        payload = inside(frozen, frozen / "static" / row["path"]).read_bytes()
        assert len(payload) == row["bytes"] and sha256(payload) == row["sha256"], row["path"]
    for row in manifest["inputs"]:
        assert sha256((REPO / row["path"]).read_bytes()) == row["sha256"], row["path"]
    shutil.copytree(str(REPO / "templates/workbench"), str(frozen / "templates/workbench"))
    result = {"root": str(frozen), "static": str(frozen / "static"), "templates": str(frozen / "templates"),
              "frozen_manifest": str(path), "sha256": sha256(path.read_bytes()), "build_id": manifest["build_id"],
              "files": len(manifest["files"]), "inputs": len(manifest["inputs"]), "hashes": tree_hashes(frozen),
              "source_differences": [], "command": command, "binding": "complete_offline_build_of_current_actual_entry"}
    write_json(marker, result)
    return result


def seed_master(app):
    from tests.workbench.process_query_support import seed_process
    from tests.workbench.resource_live_server import seed_resources

    with closing(sqlite3.connect(app.config["DATABASE_PATH"])) as conn:
        changed = conn.execute("UPDATE OpTypes SET name='FC original turning' WHERE op_type_id='T1' AND name='Turning'")
        assert changed.rowcount == 1
        conn.commit()
    seed_resources(app)
    with closing(sqlite3.connect(app.config["DATABASE_PATH"])) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        seed_process(conn)
        for number in range(1, 44):
            code = "FC-P-" + str(number).zfill(3)
            conn.execute("INSERT INTO Parts(part_no,part_name,remark) VALUES (?,?,?)",
                         (code, "验收零件 " + str(number), "原备注不能覆盖 " + str(number)))
            conn.execute("""INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date,priority,ready_status,remark)
                VALUES (?,'PROC-001',?,?,'2026-10-20','normal','yes',?)""",
                         ("FC-B-" + str(number).zfill(3), "恢复验收批次 " + str(number), number, "保留批次原备注 " + str(number)))
        for number in range(1, 22):
            code = "FC-M-" + str(number).zfill(3)
            conn.execute("INSERT INTO Machines(machine_id,name,op_type_id,status) VALUES (?,?,?,'active')",
                         (code, "验收关联设备 " + str(number), "RT-IN"))
        conn.commit()
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    return {"original_material": "MAT-011", "original_machine": "RT-M", "original_operator": "RT-O",
            "original_supplier": "RT-S", "original_process": "PROC-001", "part_count_prefix": "FC-P-",
            "part_count": 43, "original_values_policy": "Every original row retained unless an explicit per-action mutation is recorded"}


def snapshot(root):
    root = Path(root).resolve()
    db = inside(root, root / "db/aps-live.db")
    with closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        schema = [dict(row) for row in conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")]
        tables = {}
        for row in schema:
            if row["type"] == "table":
                name = row["name"].replace('"', '""')
                tables[row["name"]] = [dict(item) for item in conn.execute('SELECT rowid AS __rowid__, * FROM "' + name + '" ORDER BY rowid')]
        result = {"schema": schema, "tables": tables, "integrity": conn.execute("PRAGMA integrity_check").fetchone()[0],
                  "foreign_keys": [list(row) for row in conn.execute("PRAGMA foreign_key_check")]}
    result["sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return result


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("snapshot", "download"):
        raise ValueError("Expected snapshot ROOT or download FILE")
    if sys.argv[1] == "snapshot":
        result = snapshot(Path(sys.argv[2]))
    else:
        path = Path(sys.argv[2])
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        result = {"path": str(path), "rows": rows, "bytes": path.stat().st_size, "sha256": sha256(path.read_bytes())}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
