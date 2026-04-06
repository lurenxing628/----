from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(tmp_path, monkeypatch):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_templates = tmp_path / "templates_excel"
    test_logs.mkdir(parents=True, exist_ok=True)
    test_backups.mkdir(parents=True, exist_ok=True)
    test_templates.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(test_templates))

    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    conn = get_connection(str(test_db))
    conn.execute("INSERT INTO ResourceTeams (team_id, name, status) VALUES (?, ?, ?)", ("TEAM-OP", "装配组", "active"))
    conn.execute("INSERT INTO ResourceTeams (team_id, name, status) VALUES (?, ?, ?)", ("TEAM-MC", "设备组", "active"))
    conn.execute(
        "INSERT INTO Operators (operator_id, name, status, team_id, remark) VALUES (?, ?, ?, ?, ?)",
        ("OP001", "张三", "active", "TEAM-OP", ""),
    )
    conn.execute(
        "INSERT INTO Machines (machine_id, name, status, team_id, remark) VALUES (?, ?, ?, ?, ?)",
        ("MC001", "设备 1", "active", "TEAM-MC", ""),
    )
    conn.execute("INSERT INTO Parts (part_no, part_name, route_raw) VALUES (?, ?, ?)", ("PART-001", "零件", "[]"))
    conn.execute(
        "INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("B001", "PART-001", "零件", 1, "2026-03-08", "normal", "yes", "scheduled"),
    )
    cur = conn.execute(
        "INSERT INTO BatchOperations (op_code, batch_id, piece_id, seq, op_type_name, source, machine_id, operator_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("OP-B001-10", "B001", "P1", 10, "车削", "internal", "MC001", "OP001", "scheduled"),
    )
    lastrowid = cur.lastrowid
    assert lastrowid is not None
    op_id = int(lastrowid)
    conn.execute(
        "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (op_id, "MC001", "OP001", "2026-03-02 08:00:00", "2026-03-02 12:00:00", "locked", 1),
    )
    conn.execute(
        "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1, "greedy", 1, 1, "success", "{broken json", "pytest"),
    )
    conn.commit()
    conn.close()

    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def test_resource_dispatch_invalid_summary_surfaces_overdue_degraded(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    logged = []

    def _fake_warning(message, *args, **_kwargs):
        logged.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)
    client = app.test_client()
    query = "scope_type=operator&operator_id=OP001&period_preset=week&query_date=2026-03-02&version=1"

    page_resp = client.get(f"/scheduler/resource-dispatch?{query}")
    assert page_resp.status_code == 200
    page_html = page_resp.get_data(as_text=True)
    assert 'id="rdOverdueWarning"' in page_html

    data_resp = client.get(f"/scheduler/resource-dispatch/data?{query}")
    assert data_resp.status_code == 200
    payload = json.loads(data_resp.get_data(as_text=True) or "{}")
    assert payload.get("success") is True, payload
    data = payload.get("data") or {}
    assert len(data.get("detail_rows") or []) == 1
    assert data.get("overdue_markers_degraded") is True
    assert data.get("overdue_markers_partial") is False
    assert "超期" in str(data.get("overdue_markers_message") or "")
    assert any("资源排班超期标记降级" in item for item in logged), logged
