"""回归测试：甘特页 /scheduler/gantt 与 /scheduler/gantt/data 未给显式日期时，默认采用所选版本的排程时间跨度（range_source=version_span）；给了 start_date/end_date 则用 request 范围并忽略 offset，无效 offset 归零；无排程跨度时回落 request；并校验 gantt_boot.js 只向 data 端点发一种范围模式。"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(tmp_path, monkeypatch, *, with_schedule: bool = True):
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
    conn.execute(
        "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (3, "greedy", 1, 1, "success", json.dumps({"overdue_batches": []}, ensure_ascii=False), "pytest"),
    )
    if with_schedule:
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC001", "设备 1", "active"))
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "张三", "active"))
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("PART-001", "零件", "yes"))
        conn.execute(
            "INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("B001", "PART-001", "零件", 1, "2026-05-20", "normal", "yes", "scheduled"),
        )
        cur = conn.execute(
            "INSERT INTO BatchOperations (op_code, batch_id, piece_id, seq, op_type_name, source, machine_id, operator_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("OP-B001-10", "B001", "P1", 10, "车削", "internal", "MC001", "OP001", "scheduled"),
        )
        op_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (op_id, "MC001", "OP001", "2026-05-11 08:00:00", "2026-05-16 12:00:00", "locked", 3),
        )
    conn.commit()
    conn.close()

    for name in list(sys.modules):
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)
    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def test_gantt_page_without_range_uses_selected_version_span(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get("/scheduler/gantt?version=3")
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'data-start-date="2026-05-11"' in html
    assert 'data-end-date="2026-05-16"' in html
    assert 'data-range-source="version_span"' in html
    assert "2026年5月11日 ～ 2026年5月16日" in html
    assert 'name="week_start"' not in html


def test_gantt_data_without_range_uses_selected_version_span(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get("/scheduler/gantt/data?view=machine&version=3")
    payload = resp.get_json()
    data = payload.get("data") or {}

    assert resp.status_code == 200
    assert payload.get("success") is True
    assert data.get("week_start") == "2026-05-11"
    assert data.get("week_end") == "2026-05-16"
    assert data.get("range_source") == "version_span"
    assert (data.get("version_time_span") or {}).get("start_date") == "2026-05-11"
    assert (data.get("version_time_span") or {}).get("end_date") == "2026-05-16"
    assert len(data.get("tasks") or []) == 1


def test_gantt_page_and_data_respect_explicit_range(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    page_resp = client.get("/scheduler/gantt?version=3&start_date=2026-05-04&end_date=2026-05-10")
    html = page_resp.get_data(as_text=True)

    assert page_resp.status_code == 200
    assert 'data-start-date="2026-05-04"' in html
    assert 'data-end-date="2026-05-10"' in html
    assert 'data-range-source="request"' in html

    data_resp = client.get("/scheduler/gantt/data?view=machine&version=3&start_date=2026-05-04&end_date=2026-05-10")
    payload = data_resp.get_json()
    data = payload.get("data") or {}

    assert data_resp.status_code == 200
    assert data.get("tasks") == []
    assert data.get("range_source") == "request"
    assert data.get("empty_message") == "当前范围无任务，请切换到 2026-05-11 ～ 2026-05-16。"


def test_gantt_page_and_data_ignore_offset_when_explicit_dates_present(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    page_resp = client.get("/scheduler/gantt?version=3&start_date=2026-05-04&end_date=2026-05-10&offset=1")
    html = page_resp.get_data(as_text=True)

    assert page_resp.status_code == 200
    assert 'data-start-date="2026-05-04"' in html
    assert 'data-end-date="2026-05-10"' in html
    assert 'data-range-source="request"' in html
    assert (
        "view=operator&amp;version=3&amp;plan_role=adopted&amp;start_date=2026-05-04&amp;end_date=2026-05-10"
    ) in html
    assert "view=operator&amp;week_start=" not in html
    assert "week_start=2026-05-04&amp;offset=1&amp;version=3" in html
    assert "week_start=2026-05-04&amp;offset=1&amp;version=3&amp;start_date" not in html

    data_resp = client.get(
        "/scheduler/gantt/data?view=machine&version=3&start_date=2026-05-04&end_date=2026-05-10&offset=1"
    )
    payload = data_resp.get_json()
    data = payload.get("data") or {}

    assert data_resp.status_code == 200
    assert data.get("week_start") == "2026-05-04"
    assert data.get("week_end") == "2026-05-10"
    assert data.get("range_source") == "request"
    assert data.get("tasks") == []


def test_gantt_page_and_data_ignore_invalid_offset_when_explicit_dates_present(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    page_resp = client.get("/scheduler/gantt?version=3&start_date=2026-05-04&end_date=2026-05-10&offset=bad")
    html = page_resp.get_data(as_text=True)

    assert page_resp.status_code == 200
    assert 'data-start-date="2026-05-04"' in html
    assert 'data-end-date="2026-05-10"' in html
    assert 'data-offset="0"' in html

    data_resp = client.get(
        "/scheduler/gantt/data?view=machine&version=3&start_date=2026-05-04&end_date=2026-05-10&offset=bad"
    )
    payload = data_resp.get_json()
    data = payload.get("data") or {}

    assert data_resp.status_code == 200
    assert data.get("week_start") == "2026-05-04"
    assert data.get("week_end") == "2026-05-10"
    assert data.get("range_source") == "request"


def test_gantt_data_start_date_only_ignores_offset(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    data_resp = client.get("/scheduler/gantt/data?view=machine&version=3&start_date=2026-05-04&offset=1")
    payload = data_resp.get_json()
    data = payload.get("data") or {}

    assert data_resp.status_code == 200
    assert data.get("week_start") == "2026-05-04"
    assert data.get("week_end") == "2026-05-10"
    assert data.get("range_source") == "request"


def test_gantt_without_version_span_keeps_request_range_source(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch, with_schedule=False)
    client = app.test_client()

    resp = client.get("/scheduler/gantt/data?view=machine&version=3")
    payload = resp.get_json()
    data = payload.get("data") or {}

    assert resp.status_code == 200
    assert data.get("version_time_span") is None
    assert data.get("range_source") == "request"
    assert "empty_message" not in data
