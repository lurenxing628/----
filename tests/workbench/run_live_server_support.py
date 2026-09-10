"""Isolated paths, immutable built assets and small real v26 scheduling inputs."""

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
from contextlib import closing
from pathlib import Path

from tests.workbench.live_environment import (
    REPO,
    create_root,
    environment,
    install_path_guard,
    read_identity,
    sha256,
    write_json,
)

KIND = "workbench-run-live-v26"
BASE = "/api/workbench/v1/scheduling"
FORBIDDEN_PORTS = {51093, 56264, 52155, 51733}


def inside(root, path):
    path = Path(path).resolve()
    path.relative_to(Path(root).resolve())
    return path


def prepare_root(root=None, *, parent=None, reuse=False):
    if reuse and root is None:
        raise ValueError("--reuse-root requires --root")
    root = Path(root).resolve() if root is not None else create_root(parent)
    identity = read_identity(root)
    if root == REPO or REPO in root.parents:
        raise ValueError("Fixture root must be outside the repository")
    for path in root.rglob("*"):
        inside(root, path)
        if path.is_symlink() or (path.is_file() and path.stat().st_nlink != 1):
            raise ValueError("Fixture paths must not be symlinks or hard links: " + str(path))
    marker, db = root / "run-fixture.json", root / "db/aps-live.db"
    if reuse:
        saved = json.loads(marker.read_text(encoding="utf-8"))
        if saved != {"kind": KIND, "identity": identity} or not db.is_file():
            raise ValueError("Not an initialized run fixture")
    elif db.exists() or marker.exists():
        raise ValueError("Existing run fixture requires explicit --reuse-root")
    else:
        write_json(marker, {"kind": KIND, "identity": identity})
    return root, identity


def isolate(root):
    env = environment(root)
    env["APS_ENV"] = "production"
    os.environ.clear()
    os.environ.update(env)
    tempfile.tempdir = str(root / "tmp")
    os.chdir(str(root))
    sys.dont_write_bytecode = True
    return install_path_guard(root)


def tree_hashes(root):
    return {str(path.relative_to(root)): sha256(path.read_bytes())
            for path in sorted(root.rglob("*")) if path.is_file()}


def loaded_python_sources():
    """Observe only imported project modules, not unrelated concurrent additions."""
    paths = {}
    for module in list(sys.modules.values()):
        name = getattr(module, "__file__", None)
        if name is None:
            continue
        path = Path(name).resolve()
        if path.suffix == ".py" and REPO in path.parents:
            paths[str(path)] = sha256(path.read_bytes()) if path.is_file() else None
    return paths


def source_comparison(before, after):
    return {"binding": "on_disk_hashes_of_loaded_module_paths",
            "before": before, "after": after,
            "changed": sorted(path for path in before if after.get(path) != before[path]),
            "loaded_after_ready": sorted(set(after) - set(before))}


def freeze_built_assets(root, session):
    """Pin the current build, even while its next source revision is being edited."""
    manifest_path = REPO / "static/workbench/asset-manifest.json"
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    if manifest.get("schema_version") != 1 or manifest.get("target") != "chrome109":
        raise ValueError("Expected a chrome109 workbench asset manifest")
    frozen = root / "frozen" / session
    static = frozen / "static"
    for item in manifest["files"]:
        source = inside(REPO / "static", REPO / "static" / item["path"])
        target = inside(static, static / item["path"])
        data = source.read_bytes()
        if sha256(data) != item["sha256"] or len(data) != item["bytes"]:
            raise ValueError("Build changed during freeze; retry: " + item["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (static / "workbench/asset-manifest.json").write_bytes(raw)
    shutil.copytree(str(REPO / "templates/workbench"), str(frozen / "templates/workbench"))
    if manifest_path.read_bytes() != raw:
        raise ValueError("Manifest changed during freeze; retry after build finishes")
    stale = [item["path"] for item in manifest.get("inputs", [])
             if not inside(REPO, REPO / item["path"]).is_file()
             or sha256((REPO / item["path"]).read_bytes()) != item["sha256"]]
    hashes = tree_hashes(frozen)
    return {"build_id": manifest["build_id"], "sha256": sha256(raw),
            "frozen_manifest": str(static / "workbench/asset-manifest.json"),
            "static": str(static), "templates": str(frozen / "templates"),
            "root": str(frozen), "hashes": hashes, "source_differences": stale}


def protect_frozen_assets(assets):
    frozen = Path(assets["root"])

    def guard(event, args):
        paths = []
        if event == "open":
            mode, flags = args[1], args[2]
            if (isinstance(mode, str) and any(char in mode for char in "wax+")) or (
                    isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
                paths = args[:1]
        elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.truncate"):
            paths = args[:1]
        elif event in ("os.rename", "os.link", "os.symlink"):
            paths = args[:2]
        for value in paths:
            if not isinstance(value, int):
                path = Path(os.fsdecode(value)).resolve()
                if path == frozen or frozen in path.parents:
                    raise PermissionError("Frozen assets are immutable: " + str(path))

    sys.addaudithook(guard)


def database_state(db):
    with closing(sqlite3.connect(str(db))) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {table: [dict(row) for row in conn.execute('SELECT * FROM "' + table.replace('"', '""') + '" ORDER BY rowid')]
                for table in tables}


def seed_run_data(app, *, include_formal=True, calibration=False, outsourcing=False):
    from core.services.scheduler.config.config_field_spec import default_snapshot_values
    from tests.workbench.plan_read_support import seed_plans
    from tests.workbench.report_api_support import event
    from tests.workbench.test_run_jobs_support import JobCase

    if calibration and include_formal:
        raise ValueError("Calibration fixture owns its original sample plan")
    with closing(sqlite3.connect(app.config["DATABASE_PATH"])) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
        conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Lathe','T1')")
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
        conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
        conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Run fixture part')")
        for key, value in default_snapshot_values().items():
            conn.execute("INSERT OR REPLACE INTO ScheduleConfig(config_key,config_value) VALUES (?,?)", (key, str(value)))
        case = JobCase(conn)
        case.batch("B1")
        case.operation()
        case.config(algo_mode="greedy", graph_candidate_weight_count=3, time_budget_seconds=60,
                    ortools_enabled="no", freeze_window_enabled="no")
        if include_formal:
            op = seed_plans(conn)
            conn.execute("UPDATE Batches SET status='completed',ready_status='yes',due_date='2026-09-08' WHERE batch_id='CAT-B'")
            conn.execute("UPDATE BatchOperations SET op_type_id='T1',source='internal',setup_hours=0,unit_hours=.25,machine_id='M1',operator_id='O1' WHERE id=?", (op,))
            conn.execute("UPDATE Schedule SET start_time='2026-09-07 08:00:00',end_time='2026-09-07 08:15:00',machine_id='M1',operator_id='O1'")
            event(conn, op, "start", "2026-09-07 08:00:00", actual_machine_id="M1", actual_operator_id="O1")
            event(conn, op, "finish", "2026-09-07 08:15:00", quantity_done=1)
        calibration_info = None
        if calibration:
            from tests.workbench.calibration_adoption_host_support import prepare_calibration

            case.path = Path(app.config["DATABASE_PATH"])
            prepared = prepare_calibration(case)
            calibration_info = {"template_ref": prepared.template_ref, "sample_count": 5,
                                "part_ref": prepared.ref("part", "P1")}
        outsourcing_info = None
        if outsourcing:
            from tests.workbench.outsourcing_live_support import seed_outsourcing_data

            outsourcing_info = seed_outsourcing_data(conn)
        for key in ("auto_backup_enabled", "auto_backup_cleanup_enabled", "auto_log_cleanup_enabled"):
            conn.execute("INSERT OR REPLACE INTO SystemConfig(config_key,config_value) VALUES (?, 'no')", (key,))
        conn.commit()
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Fixture foreign keys are invalid")
        return {"batch_code": "B1", "settings": case.settings(), "candidate_count": 4,
                "official_version": 3 if include_formal else 1 if calibration else None,
                "execution_events": 2 if include_formal else 0, "calibration": calibration_info,
                "outsourcing": outsourcing_info}


def attach_journal(app, path):
    lock = threading.Lock()

    @app.after_request
    def record(response):
        from flask import request

        if not request.path.startswith("/static/"):
            row = {"method": request.method, "path": request.path, "status": response.status_code}
            if request.is_json:
                data = request.get_json(silent=True)
                if isinstance(data, dict):
                    row["request_key"] = data.get("request_key")
            if response.is_json:
                body = response.get_json(silent=True) or {}
                row.update(source=body.get("meta", {}).get("source"), run_ref=body.get("run_ref"),
                           committed=body.get("committed"), result=body.get("result"))
            with lock, path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row) + "\n")
        return response


def write_manifest(root, before, session):
    after = tree_hashes(root)
    result = {"schema_version": 1, "root": str(root), "session": session,
              "created": sorted(set(after) - set(before)), "deleted": sorted(set(before) - set(after)),
              "changed": sorted(name for name in before if name in after and before[name] != after[name]),
              "before": before, "after": after}
    write_json(root / "write-manifest.json", result)
    write_json(root / "sessions" / session / "write-manifest.json", result)
    return result
