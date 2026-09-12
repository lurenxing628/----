"""Disposable V backend DTOs plus independent Chromium 109 component evidence."""

import base64
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from tests.workbench.system_maintenance_support import SystemTestAPI
from tests.workbench.system_restore_host_support import restore_host as _restore_host_fixture  # noqa: F401
from tests.workbench.test_live_browser import runtime_tools

HERE = Path(__file__).resolve().parent
NAMES = ["SystemRestoreStatus.js", "SystemMaintenanceAPI.js", "SystemMaintenanceControls.jsx", "SystemRestorePanel.jsx", "SystemMaintenanceRecords.jsx",
         "SystemMaintenanceConfig.jsx", "SystemMaintenanceWorkspace.jsx", "SystemLive.jsx"]


@pytest.fixture(name="system_api")
def component_api(tmp_path, restore_host):
    # Keep the API fixture's fault-injected logs separate from the real host logs.
    root = tmp_path / "component-api"
    root.mkdir()
    return SystemTestAPI(root)


def capture(api, restore_host):
    """Restore DTO comes from an independently guarded real host; other DTOs use the API fixture."""
    conn = api.connect()
    conn.execute("INSERT INTO SystemConfig(config_key,config_value) VALUES('auto_backup_keep_days','bad-old-value')")
    conn.commit()
    conn.close()
    dto = {"config": api.read("/config")}
    api.app.config.pop("WORKBENCH_SYSTEM_JOURNAL_DIR")
    dto["disabled"] = api.read("/backups")
    api.app.config["WORKBENCH_SYSTEM_JOURNAL_DIR"] = str(api.journal_dir)
    dto["create"] = api.file_action("create", key="system-" + "a" * 48).get_json()
    assert dto["create"]["data"]["operation"]["state"] == "succeeded"
    first = api.selected()
    dto["delete"] = api.file_action("delete", first, key="system-" + "b" * 48).get_json()
    assert not list(api.backups.glob("*.db"))
    api.backup()
    body = restore_host.intent()
    body["request_key"] = "system-" + "c" * 48
    dto["enabled"] = restore_host.client.get("/api/workbench/v1/system/backups", buffered=True).get_json()
    dto["restore"] = restore_host.client.post("/api/workbench/v1/system/backups/restore", json=body, buffered=True).get_json()
    assert dto["restore"]["data"]["operation"]["state"] == "succeeded"
    assert dto["restore"]["data"]["operation"]["protection_filename"].endswith("before_restore.db")
    row = dto["restore"]["data"]["operation"]
    dto["job"] = restore_host.client.get("/api/workbench/v1/system/jobs/" + row["job_ref"], buffered=True).get_json()
    dto["not_recorded"] = api.read("/results/system-" + "f" * 48)
    original = Path(api.backup()).read_bytes()
    for index in range(13):
        (api.backups / f"aps_backup_fixture_{index:02d}_manual.db").write_bytes(original)
    dto["backups"] = api.read("/backups", page_size="50")
    before = api.read("/config")["data"]
    dto["save"] = api.post("/config/save", {**before["values"], "auto_backup_interval_minutes": 37},
                           before["write_context"]["write_token"], "system-" + "d" * 48).get_json()
    assert dto["save"]["result"] == "committed"
    dto["config_result"] = api.read("/results/system-" + "d" * 48)
    before = api.read("/config")["data"]
    dto["unchanged"] = api.post("/config/save", before["values"], before["write_context"]["write_token"],
                                "system-" + "e" * 48).get_json()
    dto["saved_config"] = api.read("/config")
    entries = [f"2026-09-09 10:{index // 60:02d}:{index % 60:02d} [INFO] fixture {index:03d}\n" for index in range(220)]
    entries[-1] = "2026-09-09 11:00:00 [ERROR] fixture bounded detail\n" + "long detail " * 1000 + "\n"
    (api.logs / "aps.log").write_text("".join(entries), encoding="utf-8")
    (api.logs / "aps_error.log").mkdir()
    conn = api.connect()
    conn.executemany("INSERT INTO OperationLogs(log_level,module,action,detail) VALUES ('INFO','fixture','event',?)",
                     [("row " + str(index),) for index in range(510)])
    conn.commit()
    conn.close()
    dto["logs"] = api.read("/logs", page_size="50")
    dto["log_pages"] = [api.read("/logs", page_size="50", page=str(page)) for page in range(1, dto["logs"]["data"]["page"]["pages"] + 1)]
    snapshot = api.read("/logs", type="runtime")["meta"]["snapshot_ref"]
    dto["downloads"] = {kind: base64.b64encode(api.get("/logs/export/" + kind, snapshot_ref=snapshot,
                                                     type="runtime").data).decode("ascii") for kind in ("csv", "zip")}
    api.app.config.pop("WORKBENCH_SYSTEM_JOURNAL_DIR")
    dto["disabled"] = api.read("/backups", page_size="50")
    api.app.config["WORKBENCH_SYSTEM_JOURNAL_DIR"] = str(api.journal_dir)
    # Separate metadata-only files and a real cleanup audit keep the existing DTOs unchanged.
    format_root = api.root / "format-size-consumers"
    format_root.mkdir()
    format_api = SystemTestAPI(format_root)
    for index, size in enumerate((0, 1024, 1536, 1264256)):
        with (format_api.backups / f"aps_backup_format_{index:02d}_manual.db").open("wb") as stream:
            stream.truncate(size)
    conn = format_api.connect()
    try:
        conn.execute("INSERT INTO OperationLogs(log_level,module,action,detail) VALUES ('INFO','system','cleanup',?)",
                     (json.dumps({"removed_count": 0}),))
        conn.commit()
    finally:
        conn.close()
    dto["format_backups"] = format_api.read("/backups", page_size="10")
    assert dto["format_backups"]["data"]["page"]["total"] == 5
    return dto


def test_system_maintenance_widgets(restore_host, system_api):
    dto = capture(system_api, restore_host)
    output = Path(tempfile.mkdtemp(prefix="aps-system-maintenance-widgets-"))
    dto_path = output / "temporary-backend-dto.json"
    dto_path.write_text(json.dumps(dto, ensure_ascii=False, indent=2), encoding="utf-8")
    source = HERE.parents[1] / "frontend" / "workbench" / "app"
    hashes = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in NAMES}
    manifest = HERE.parents[1] / "static" / "workbench" / "asset-manifest.json"
    before_manifest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    node, browser, modules = runtime_tools()
    print("SYSTEM_MAINTENANCE_WIDGET_ARTIFACTS " + str(output), flush=True)
    result = subprocess.run([node, str(HERE / "system_maintenance_widgets_probe.cjs"), str(output)],
                            cwd=str(HERE.parents[1]), env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
                            input=json.dumps(dto), capture_output=True, text=True, timeout=900)
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)
    report = json.loads((output / "system-maintenance-ui-result.json").read_text(encoding="utf-8"))
    assert report["data_source"] == "mock-with-temporary-backend-dto"
    assert report["production_persistence_tested"] is False
    assert report["browser"].startswith("109.")
    assert not report["errors"] and not report["external"] and not report["dialogs"]
    assert len(report["variants"]) == 4
    assert len(report["cases"]) >= 40
    assert all(item["passed"] for item in report["cases"])
    assert {"system-live-backups-size-format", "system-live-logs-size-format",
            "maintenance-backup-size-format-preserves-event-and-dto"} <= {item["name"] for item in report["cases"]}
    assert hashes == {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in NAMES}
    report["source_sha256"] = hashes
    report["asset_manifest_sha256_at_start"] = before_manifest
    report["asset_manifest_sha256_at_end"] = hashlib.sha256(manifest.read_bytes()).hexdigest()
    report["temporary_backend_restore"] = {"state": dto["restore"]["data"]["operation"]["state"],
                                            "protection_created": True, "sqlite_fixture_guard": "directory-only"}
    (output / "system-maintenance-ui-result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(result.stdout, flush=True)
