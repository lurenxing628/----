"""Workbench entry errors, offline assets and read-only request integration."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from tests._support.workbench_web_contract import canonical_boot
from web.routes.workbench.assets import WorkbenchAssetsUnavailable, read_asset_manifest


def _manifest(root: Path):
    folder = root / "workbench"
    folder.mkdir(parents=True)
    for name in ("theme.js", "entry.js", "style.css"):
        (folder / name).write_text("/* fixture */", encoding="utf-8")
    value = {"schema_version": 1, "target": "chrome109", "styles": ["workbench/style.css"],
             "scripts": ["workbench/entry.js"], "theme_script": "workbench/theme.js", "files": []}
    (folder / "asset-manifest.json").write_text(json.dumps(value), encoding="utf-8")
    return value


def test_asset_manifest_requires_local_complete_files(tmp_path):
    expected = _manifest(tmp_path)
    assert read_asset_manifest(str(tmp_path)) == expected
    (tmp_path / "workbench/entry.js").unlink()
    with pytest.raises(WorkbenchAssetsUnavailable, match="资源文件缺失"):
        read_asset_manifest(str(tmp_path))


@pytest.mark.parametrize("value", ["https://example.invalid/a.js", "../a.js", "workbench/../a.js",
                                    "workbench/./entry.js", "workbench//entry.js", "workbench/entry.js?x=1", None])
def test_asset_manifest_rejects_invalid_paths(tmp_path, value):
    manifest = _manifest(tmp_path)
    manifest["scripts"] = [value]
    (tmp_path / "workbench/asset-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(WorkbenchAssetsUnavailable):
        read_asset_manifest(str(tmp_path))


def test_asset_manifest_rejects_missing_root_and_duplicate_scripts(tmp_path):
    with pytest.raises(WorkbenchAssetsUnavailable):
        read_asset_manifest(None)
    manifest = _manifest(tmp_path)
    manifest["scripts"].append(manifest["theme_script"])
    (tmp_path / "workbench/asset-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(WorkbenchAssetsUnavailable, match="重复"):
        read_asset_manifest(str(tmp_path))


def test_new_host_uses_built_entry_without_replacing_old_home(app_client, tmp_path, monkeypatch):
    static = tmp_path / "static"
    _manifest(static)
    monkeypatch.setattr(app_client.application, "static_folder", str(static))
    response = app_client.get("/workbench?view=system")
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert 'id="workbench-boot"' in text
    assert '<body class="aps-workbench">' in text
    assert "/static/workbench/entry.js" in text
    assert "text/babel" not in text and "babel-" not in text
    assert "https://" not in text
    assert response.headers["Cache-Control"] == "no-store"
    assert app_client.get("/workbench?view=not-a-page").status_code == 404
    assert app_client.get("/workbench/trial").status_code == 200
    canonical_boot(app_client, "/", "dashboard", {})


def test_new_host_reports_missing_assets_explicitly(app_client, tmp_path, monkeypatch):
    monkeypatch.setattr(app_client.application, "static_folder", str(tmp_path / "empty-static"))
    response = app_client.get("/workbench?view=system")
    assert response.status_code == 503
    assert "资源清单" in response.get_data(as_text=True)


def test_system_overview_skips_maintenance_but_normal_requests_keep_it(app_client, monkeypatch):
    from core.services.system import SystemMaintenanceService, workbench_overview

    calls = []
    monkeypatch.setattr(SystemMaintenanceService, "run_if_due", lambda *args, **kwargs: calls.append("maintenance"))
    monkeypatch.setattr(workbench_overview, "build_system_overview", lambda *args, **kwargs: {"database": {"state": "readable"}})
    first = app_client.get("/api/workbench/v1/system/overview")
    second = app_client.get("/api/workbench/v1/system/overview")
    assert first.status_code == second.status_code == 200
    data = first.get_json()
    assert data["schema_version"] == 1 and data["meta"]["source"] == "production"
    assert data["meta"]["time_basis"] == "factory_local"
    assert data["meta"]["snapshot_ref"] != second.get_json()["meta"]["snapshot_ref"]
    assert data["data"]["database"]["state"] == "readable"
    assert first.headers["Cache-Control"] == "no-store" and calls == []
    assert app_client.get("/workbench?view=system").status_code == 200
    assert app_client.get("/workbench/trial").status_code == 200
    assert calls == []
    canonical_boot(app_client, "/", "dashboard", {})
    assert calls == ["maintenance"]


def test_system_overview_failure_is_not_demo_success(app_client, monkeypatch):
    from core.services.system import workbench_overview

    def fail(*args, **kwargs):
        raise RuntimeError("private-exception-detail")

    monkeypatch.setattr(workbench_overview, "build_system_overview", fail)
    response = app_client.get("/api/workbench/v1/system/overview")
    assert response.status_code == 500
    payload = response.get_json()
    assert payload["ok"] is False and payload["committed"] is False
    assert payload["error"]["code"] == "system_read_failed"
    assert payload["error"]["request_ref"]
    assert "data" not in payload and "private-exception-detail" not in response.get_data(as_text=True)


@pytest.mark.parametrize("detection_failure,status", [(False, 503), (True, 500)])
def test_system_overview_preserves_maintenance_gate_with_read_failure_contract(app_client, monkeypatch, detection_failure, status):
    def maintenance(*args, **kwargs):
        if detection_failure:
            raise OSError("private-maintenance-detail")
        return True

    hooks = app_client.application.before_request_funcs[None]
    hook = next(item for item in hooks if item.__name__ == "_open_db")
    monkeypatch.setitem(hook.__globals__, "is_maintenance_window_active", maintenance)
    response = app_client.get("/api/workbench/v1/system/overview")
    assert response.status_code == status
    payload = response.get_json()
    assert payload["ok"] is False and payload["committed"] is False
    assert payload["error"]["request_ref"] and payload["error"]["retryable"] is True
    assert "data" not in payload and "private-maintenance-detail" not in response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"


def test_real_overview_request_reads_instance_and_preserves_database(app_client):
    config = app_client.application.config
    backup = Path(config["BACKUP_DIR"]) / "aps_backup_readonly_fixture.db"
    backup.write_bytes(b"Metadata fixture only; not a verified backup")
    conn = sqlite3.connect(config["DATABASE_PATH"])
    try:
        conn.execute("INSERT OR REPLACE INTO SystemConfig(config_key, config_value) VALUES (?, ?)",
                     ("auto_backup_interval_minutes", "333"))
        conn.commit()
        before = list(conn.iterdump())
        records = conn.execute("SELECT COUNT(*) FROM OperationLogs").fetchone()[0]
        assert app_client.get("/workbench?view=system").status_code == 200
        assert app_client.get("/workbench/trial").status_code == 200
        for _ in range(3):
            response = app_client.get("/api/workbench/v1/system/overview")
            assert response.status_code == 200
            payload = response.get_json()
            assert payload["meta"]["source"] == "production"
            data = payload["data"]
            assert data["database"]["readable"] is True
            assert data["database"]["file"]["filename"] == Path(config["DATABASE_PATH"]).name
            assert data["config"]["values"]["auto_backup_interval_minutes"] == 333
            assert data["config"]["writes_performed"] is False
            assert data["logs"]["operation_record_count"] == records
            assert data["backups"]["verification_status"] == "not_checked"
            assert any(item["filename"] == backup.name for item in data["backups"]["files"])
        assert list(conn.iterdump()) == before
        assert backup.read_bytes() == b"Metadata fixture only; not a verified backup"
    finally:
        conn.close()
