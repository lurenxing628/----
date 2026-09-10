"""Current React components + real Flask routes, restricted to disposable SQLite."""

import hashlib
import json
import os
import subprocess
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.test_system_maintenance_support import system_api as _system_api_fixture  # noqa: F401

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def database_state(api):
    conn = api.connect()
    try:
        names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {name: [list(row) for row in conn.execute('SELECT * FROM "' + name.replace('"', '""') + '"')]
                for name in names}
    finally:
        conn.close()


def run_browser(api, scenario):
    initial = api.read("/config")["data"]
    values = {**initial["values"], "auto_backup_interval_minutes": 120}
    seeded = api.post("/config/save", values, initial["write_context"]["write_token"], "system-" + "0" * 48)
    assert seeded.status_code == 200
    if scenario == "metadata":
        conn = api.connect()
        conn.execute("UPDATE SystemConfig SET config_value='bad-old-value' WHERE config_key='auto_backup_keep_days'")
        conn.execute("DELETE FROM SystemConfig WHERE config_key='auto_log_cleanup_keep_days'")
        conn.commit()
        conn.close()
    before = database_state(api)
    output = api.root / ("system_config_saved_" + scenario)
    output.mkdir()
    server = make_server("127.0.0.1", 0, api.app, threaded=True)
    assert server.server_port != 60086
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    node, browser, modules = runtime_tools()
    thread.start()
    print("SYSTEM_CONFIG_SAVED_ARTIFACTS " + str(output), flush=True)
    try:
        result = subprocess.run(
            [node, str(HERE / "system_config_saved_probe.cjs"), str(output), scenario,
             "http://127.0.0.1:" + str(server.server_port)],
            cwd=str(ROOT), env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
            capture_output=True, text=True, timeout=240,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)
    assert not thread.is_alive()
    after = database_state(api)
    changed = sorted(name for name in before if before[name] != after[name])
    evidence = {"database": str(api.database), "changed_tables": changed,
                "config": [list(row) for row in after["SystemConfig"]],
                "added_audits": len(after["OperationLogs"]) - len(before["OperationLogs"]),
                "added_receipts": len(after["WorkbenchCommandReceipts"]) - len(before["WorkbenchCommandReceipts"]),
                "server_stopped": True, "production_database_opened": False}
    (output / "sqlite-evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    assert set(changed) <= {"SystemConfig", "OperationLogs", "WorkbenchCommandReceipts", "sqlite_sequence"}
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)
    report = json.loads((output / "system_config_saved_result.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.")
    assert report["errors"] == [] and report["external"] == []
    assert report["cases"] and all(row["passed"] for row in report["cases"])
    assert report["data_source"] == "real-temporary-flask-api"
    for name, digest in report["source_sha256"].items():
        assert hashlib.sha256((ROOT / "frontend/workbench/app" / name).read_bytes()).hexdigest() == digest
    assert {row[1] for row in after["SystemConfig"]} == set(values)
    if scenario == "minimal":
        assert api.read("/config")["data"]["values"]["auto_backup_interval_minutes"] == 121
        assert len(after["OperationLogs"]) == len(before["OperationLogs"]) + 1
        assert len(after["WorkbenchCommandReceipts"]) == len(before["WorkbenchCommandReceipts"]) + 1
    print(result.stdout, flush=True)
    return report


def test_system_config_saved_confirmed_readback(system_api):
    run_browser(system_api, "minimal")


@pytest.mark.parametrize("scenario", ["fields", "states", "races", "metadata"])
def test_system_config_saved_state_boundaries(system_api, scenario):
    run_browser(system_api, scenario)
