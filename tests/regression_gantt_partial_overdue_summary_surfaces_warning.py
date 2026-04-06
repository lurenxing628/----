from __future__ import annotations

import importlib
import json
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
    conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC001", "设备 1", "active"))
    conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "张三", "active"))
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
    result_summary = json.dumps(
        {"overdue_batches": [{"batch_id": "B001", "hours": 4}, {"hours": 2}, "", None]},
        ensure_ascii=False,
    )
    conn.execute(
        "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1, "greedy", 1, 1, "success", result_summary, "pytest"),
    )
    conn.commit()
    conn.close()

    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def test_gantt_partial_overdue_summary_surfaces_warning(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    logged = []

    def _fake_warning(message, *args, **_kwargs):
        logged.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)
    client = app.test_client()

    page_resp = client.get("/scheduler/gantt?view=machine&week_start=2026-03-02&version=1")
    assert page_resp.status_code == 200
    page_html = page_resp.get_data(as_text=True)
    assert 'id="ganttOverdueWarning"' in page_html

    data_resp = client.get("/scheduler/gantt/data?view=machine&week_start=2026-03-02&version=1")
    assert data_resp.status_code == 200
    payload = json.loads(data_resp.get_data(as_text=True) or "{}")
    assert payload.get("success") is True, payload
    data = payload.get("data") or {}
    assert int(data.get("task_count") or 0) == 1
    assert data.get("overdue_markers_degraded") is False
    assert data.get("overdue_markers_partial") is True
    assert "已识别" in str(data.get("overdue_markers_message") or "")
    tasks = data.get("tasks") or []
    assert tasks and tasks[0].get("meta", {}).get("is_overdue") is True
    assert any("甘特图超期标记部分不完整" in item for item in logged), logged
