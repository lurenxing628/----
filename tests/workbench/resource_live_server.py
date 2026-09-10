"""Isolated write-capable fixture server; no production database is ever opened."""

import argparse
import atexit
import importlib
import json
import os
import signal
import sqlite3
import sys
import tempfile
import threading
from pathlib import Path

from live_environment import (
    REPO,
    environment,
    file_snapshot,
    freeze_assets,
    install_path_guard,
    read_identity,
    write_json,
)
from live_server import seed_fixture


def seed_resources(app):
    with sqlite3.connect(app.config["DATABASE_PATH"]) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executemany("INSERT INTO Materials(material_id,name,spec,unit,stock_qty,status,remark) VALUES (?,?,?,?,?,?,?)", [
            (f"MAT-{n:03d}", f"Material {n}", "Round", "kg", None if n == 11 else n + .25,
             "inactive" if n == 12 else "active", "Retained material note") for n in range(1, 51)])
        conn.executemany("INSERT INTO OpTypes(op_type_id,name,category,default_hours,remark) VALUES (?,?,?,?,?)", [
            ("RT-IN", "Turning", "internal", 2.75, "Preserved internal hours"),
            ("RT-IN2", "Inspection", "internal", 1.5, "Inspection note"),
            ("RT-EX", "Heat treatment", "external", 4, "Preserved external hours")])
        conn.execute("INSERT INTO ResourceTeams(team_id,name,status,remark) VALUES ('RT-T','Legacy team','active','Kept')")
        conn.execute("INSERT INTO Machines(machine_id,name,op_type_id,status,category,remark,team_id) VALUES ('RT-M','Lathe','RT-IN','active','legacy-category','Hidden machine note','RT-T')")
        conn.execute("INSERT INTO Operators(operator_id,name,status,remark,team_id) VALUES ('RT-O','Original operator','active','Original note','RT-T')")
        conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id,skill_level,is_primary) VALUES ('RT-O','RT-M','expert','yes')")
        conn.execute("INSERT INTO OperatorSkill(operator_id,op_type_id,skill_level,is_primary) VALUES ('RT-O','RT-IN','expert','yes')")
        conn.execute("INSERT INTO WorkbenchMachineGroups(group_id,name,status) VALUES ('RT-G','Group A','active')")
        conn.execute("INSERT INTO WorkbenchMachineGroupMembers(machine_id,group_id) VALUES ('RT-M','RT-G')")
        conn.execute("INSERT INTO WorkbenchShiftProfiles(profile_id,name,anchor_date,cycle_days,status) VALUES ('RT-SH','Night shift','2026-09-09',1,'active')")
        conn.execute("INSERT INTO WorkbenchShiftPatternDays(profile_id,day_offset,is_rest,shift_start,shift_end) VALUES ('RT-SH',0,0,'22:30','06:30')")
        conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id,skills_declared) VALUES ('RT-O','RT-SH',1)")
        conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id,default_days,status,remark) VALUES ('RT-S','Original supplier','RT-EX',3.25,'active','Retained supplier note')")
        conn.execute("INSERT INTO WorkCalendar(date,day_type,shift_start,shift_end,shift_hours,efficiency,allow_normal,allow_urgent,remark) VALUES ('2026-09-09','workday','22:30','06:30',8,.875,'no','yes','Retained night')")
        conn.execute("INSERT INTO OperatorCalendar(operator_id,date,day_type,shift_start,shift_end,shift_hours,efficiency,allow_normal,allow_urgent,remark) VALUES ('RT-O','2026-09-09','workday','23:15','07:45',8.5,.625,'yes','no','Personal override')")
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def business_state(db):
    tables = ("Materials", "OpTypes", "Machines", "Operators", "Suppliers", "ResourceTeams", "OperatorMachine", "OperatorSkill",
              "WorkbenchMachineGroups", "WorkbenchShiftProfiles", "WorkbenchOperatorProfiles", "WorkbenchSupplierProfiles",
              "WorkbenchSupplierOpTypes", "WorkbenchMachineGroupMembers", "WorkbenchShiftPatternDays", "WorkbenchOpTypePolicies",
              "WorkCalendar", "OperatorCalendar", "WorkbenchCommandReceipts")
    with sqlite3.connect(str(db)) as conn:
        conn.row_factory = sqlite3.Row
        return {table: [dict(row) for row in conn.execute('SELECT * FROM "' + table + '" ORDER BY rowid')] for table in tables}


class ResourceRuntime:
    """Own real launcher locks, worker and restore host inside this fixture."""

    def __init__(self, root):
        from web.bootstrap.launcher_runtime_lock import acquire_runtime_lock

        self.root, self.db = root, root / "db/aps-live.db"
        self.runtime = self.final = None
        self.lock = acquire_runtime_lock(str(root), str(root / "logs"), db_path=str(self.db))
        atexit.register(self.close)

    def attach(self, app):
        from web.bootstrap import factory
        from web.bootstrap.workbench_run_runtime import install_workbench_run_runtime
        from web.bootstrap.workbench_system_restore import install_workbench_system_restore_host

        atexit.unregister(factory._run_exit_backup)
        self.runtime = install_workbench_run_runtime(app, runtime_lock=self.lock)
        assert self.runtime.ready, self.runtime.status
        host = install_workbench_system_restore_host(app, runtime=self.runtime)
        assert host.status["operations_available"] is True
        return {"runtime": self.runtime.status, "restore_host": host.status, "runtime_lock": self.lock}

    def close(self):
        from web.bootstrap.launcher_runtime_lock import release_runtime_lock
        from web.bootstrap.workbench_run_lifecycle import stop_run_runtime

        if self.final is not None:
            return self.final
        stop_run_runtime(self.runtime)
        if self.runtime is not None:
            self.runtime.proof.verify()
        release_runtime_lock(self.lock["state_dir"], os.getpid(), str(self.db))
        assert not Path(self.lock["path"]).exists()
        assert not Path(str(self.db) + ".lock").exists()
        self.final = {"runtime_joined": True, "locks_released": True}
        atexit.unregister(self.close)
        return self.final


def serve(root, *, fixture_seed=seed_resources, state_reader=business_state):
    root = Path(root).resolve()
    identity = read_identity(root)
    if (root / "db/aps-live.db").exists():
        raise ValueError("Write probes require a fresh fixture database")
    assets = freeze_assets(root)
    env = environment(root)
    env["APS_ENV"] = "production"
    os.environ.clear()
    os.environ.update(env)
    tempfile.tempdir = str(root / "tmp")
    os.chdir(str(root))
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(REPO))
    evidence = install_path_guard(root)
    runtime_owner = ResourceRuntime(root)
    app = importlib.import_module("app").app
    from jinja2 import ChoiceLoader, FileSystemLoader
    from werkzeug.serving import make_server

    from web.bootstrap.workbench_request_lifecycle import WorkbenchRequestHandler

    app.static_folder = str(root / "static")
    app.jinja_loader = ChoiceLoader([FileSystemLoader(str(root / "templates")), app.jinja_loader])
    paths = {"DATABASE_PATH": root / "db/aps-live.db", "LOG_DIR": root / "logs", "BACKUP_DIR": root / "backups", "EXCEL_TEMPLATE_DIR": root / "templates_excel"}
    assert all(Path(app.config[key]).resolve() == value for key, value in paths.items())
    app.config["WORKBENCH_INSTANCE_LABEL"] = "Isolated resource fixture " + identity["nonce"][:12]
    expected = seed_fixture(app, root)
    fixture_seed(app)
    runtime_evidence = runtime_owner.attach(app)
    write_json(root / "business-before.json", state_reader(paths["DATABASE_PATH"]))
    before_files = file_snapshot(root)
    journal_lock = threading.Lock()

    @app.after_request
    def record(response):
        from flask import request

        if request.path.startswith("/static/"):
            return response
        row = {"method": request.method, "path": request.path, "status": response.status_code}
        if request.is_json:
            body = request.get_json(silent=True)
            if isinstance(body, dict) and "request_key" in body:
                row["request_key"] = body["request_key"]
        if response.is_json:
            body = response.get_json(silent=True) or {}
            row.update(source=body.get("meta", {}).get("source"), snapshot_ref=body.get("meta", {}).get("snapshot_ref"),
                       result=body.get("result"), receipt_ref=body.get("receipt_ref"), committed=body.get("committed"))
        with journal_lock, (root / "server-requests.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row) + "\n")
        return response

    server = make_server("127.0.0.1", 0, app, threaded=True, request_handler=WorkbenchRequestHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_args: stop.set())
    signal.signal(signal.SIGINT, lambda *_args: stop.set())
    worker.start()
    ready = {"schema_version": 1, "url": "http://127.0.0.1:" + str(server.server_port), "root": str(root),
             "pid": os.getpid(), "expected": expected, "assets": assets, "paths": {key: str(value) for key, value in paths.items()},
             **runtime_evidence}
    ready["resource_url"] = ready["url"] + "/workbench?view=process"
    write_json(root / "server-ready.json", ready)
    print("WB_RESOURCE_READY " + json.dumps(ready), flush=True)
    try:
        stop.wait()
    finally:
        server.shutdown()
        worker.join(timeout=10)
        server.server_close()
        runtime_final = runtime_owner.close()
        write_json(root / "business-after.json", state_reader(paths["DATABASE_PATH"]))
        final = {"stopped": not worker.is_alive(), "backups_and_templates_unchanged": file_snapshot(root) == before_files,
                 "sqlite_connections": sorted(set(evidence["sqlite_connections"])), "isolation_violations": evidence["violations"],
                 **runtime_final}
        write_json(root / "server-final.json", final)
    return 0 if final["stopped"] and final["backups_and_templates_unchanged"] and not final["isolation_violations"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    sys.exit(serve(parser.parse_args().root))
