"""回归测试：甘特页 /scheduler/gantt 与 /scheduler/gantt/data 未给显式日期时，默认采用所选版本的排程时间跨度（range_source=version_span）；给了 start_date/end_date 则用 request 范围并忽略 offset，无效 offset 归零；无排程跨度时回落 request；并校验 gantt_boot.js 只向 data 端点发一种范围模式。"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

from tests._support.excel_templates import point_env_at_shared
from tests._support.gantt_current import assert_retired, navigation, prepare_read_state, read_workspace
from tests._support.gantt_retirement import _business_state
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(
    tmp_path,
    monkeypatch,
    *,
    with_schedule: bool = True,
    schedule_start: str = "2026-05-11 08:00:00",
    schedule_end: str = "2026-05-16 12:00:00",
):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_logs.mkdir(parents=True, exist_ok=True)
    test_backups.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    point_env_at_shared(monkeypatch)

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
            (op_id, "MC001", "OP001", schedule_start, schedule_end, "locked", 3),
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

    before = prepare_read_state(client)
    context = navigation(client, {"version": 3})
    assert set(context) == {"plan_ref"}
    data = read_workspace(client, context)["data"]
    assert data["plan"]["version"] == 3
    assert data["plan_span"] == {"start": "2026-05-11T08:00:00", "end": "2026-05-16T12:00:00"}
    assert data["time_scope"]["range_start"] == data["plan_span"]["start"]
    assert data["time_scope"]["range_end"] == data["plan_span"]["end"]
    assert data["time_scope"]["boundary"] == "half_open"
    assert len(data["tasks"]) == 1
    assert _business_state(client) == before


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


def test_gantt_data_without_range_ignores_bad_version_span_and_reports_degradation(tmp_path, monkeypatch) -> None:
    app = _build_app(
        tmp_path,
        monkeypatch,
        schedule_start="坏开始时间",
        schedule_end="坏结束时间",
    )
    client = app.test_client()

    resp = client.get("/scheduler/gantt/data?view=machine&version=3")
    payload = resp.get_json()
    data = payload.get("data") or {}

    assert resp.status_code == 200
    assert payload.get("success") is True
    assert data.get("version_time_span") is None
    assert data.get("range_source") == "request"
    assert data.get("degraded") is True
    assert int((data.get("degradation_counters") or {}).get("bad_time_row_skipped") or 0) == 1
    assert "开始日期写法不对" not in str(payload)
    assert "坏开始时间" not in str(payload)
    assert "坏结束时间" not in str(payload)


def test_gantt_data_returns_full_scope_ignoring_gantt_batch(tmp_path, monkeypatch) -> None:
    # finding-08：数据接口恒返回全量，不按 gantt_batch 预筛——否则带 gantt_batch 深链进入后
    # 「清筛选」回不到全量。带一个不存在的 gantt_batch 仍应返回 B001 任务（证明未被后端裁掉）。
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get("/scheduler/gantt/data?view=machine&version=3&gantt_batch=NONEXISTENT")
    payload = resp.get_json()
    data = payload.get("data") or {}

    assert resp.status_code == 200
    assert payload.get("success") is True
    assert len(data.get("tasks") or []) == 1  # 后端不按 gantt_batch 裁剪，全量任务仍在


def test_gantt_page_data_url_is_scopeless(tmp_path, monkeypatch) -> None:
    # 页面带 gantt_batch 时，注入 #gantt 的 data-url 不得带 scope（数据抓取恒全量，
    # 批次/资源筛选由前端从页面 URL 种子化后客户端过滤）。
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    before = prepare_read_state(client)
    assert_retired(client, {"version": 3, "gantt_batch": "B001", "gantt_resource": "MC001"})
    context = navigation(client, {"version": 3})
    assert set(context) == {"plan_ref"}
    data = read_workspace(client, context)["data"]
    assert len(data["tasks"]) == 1 and data["tasks"][0]["batch_id"] == "B001"
    rejected = client.get("/api/workbench/v1/plans/" + context["plan_ref"] + "/workspace?gantt_batch=NONEXISTENT")
    assert rejected.status_code == 400 and rejected.get_json()["error"]["code"] == "invalid_input"
    assert "data" not in rejected.get_json()
    # Existing unfiltered legacy data remains independent of the retired page.
    legacy = client.get("/scheduler/gantt/data?version=3&gantt_batch=NONEXISTENT")
    assert legacy.status_code == 200 and len(legacy.get_json()["data"]["tasks"]) == 1
    assert _business_state(client) == before


def test_gantt_page_and_data_respect_explicit_range(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    before = prepare_read_state(client)
    context = navigation(client, {"version": 3, "start_date": "2026-05-04", "end_date": "2026-05-10"})
    assert context["range_start"] == "2026-05-04T00:00:00"
    assert context["range_end"] == "2026-05-11T00:00:00"
    current = read_workspace(client, context)["data"]
    assert current["tasks"] == [] and current["tasks_complete"] is True
    assert current["plan_span"]["start"] == "2026-05-11T08:00:00"
    assert current["time_scope"]["range_start"] == context["range_start"]
    assert current["time_scope"]["range_end"] == context["range_end"]

    data_resp = client.get("/scheduler/gantt/data?view=machine&version=3&start_date=2026-05-04&end_date=2026-05-10")
    payload = data_resp.get_json()
    data = payload.get("data") or {}

    assert data_resp.status_code == 200
    assert data.get("tasks") == []
    assert data.get("range_source") == "request"
    assert data.get("empty_message") == "当前范围无任务，请切换到 2026-05-11 ～ 2026-05-16。"
    assert _business_state(client) == before


def test_gantt_data_rejects_explicit_range_longer_than_62_days(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get("/scheduler/gantt/data?view=machine&version=3&start_date=2026-01-01&end_date=2026-03-04")
    payload = resp.get_json()

    assert resp.status_code == 400
    assert payload.get("success") is False
    assert "62 天" in str(payload)
    assert (payload.get("error") or {}).get("details", {}).get("field") == "日期范围"


def test_gantt_default_version_span_can_be_longer_than_62_days(tmp_path, monkeypatch) -> None:
    app = _build_app(
        tmp_path,
        monkeypatch,
        schedule_start="2026-01-01 08:00:00",
        schedule_end="2026-03-15 12:00:00",
    )
    client = app.test_client()

    resp = client.get("/scheduler/gantt/data?view=machine&version=3")
    payload = resp.get_json()
    data = payload.get("data") or {}

    assert resp.status_code == 200
    assert payload.get("success") is True
    assert data.get("range_source") == "version_span"
    assert data.get("week_start") == "2026-01-01"
    assert data.get("week_end") == "2026-03-15"


def test_gantt_page_and_data_ignore_offset_when_explicit_dates_present(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    before = prepare_read_state(client)
    query = {"version": 3, "start_date": "2026-05-04", "end_date": "2026-05-10"}
    assert_retired(client, dict(query, offset=1))
    context = navigation(client, query)
    assert navigation(client, dict(query, offset_weeks=1)) == context
    assert context["range_start"] == "2026-05-04T00:00:00"
    assert context["range_end"] == "2026-05-11T00:00:00"
    current = read_workspace(client, context)["data"]
    assert current["tasks"] == []
    assert current["time_scope"]["range_start"] == context["range_start"]
    assert current["time_scope"]["range_end"] == context["range_end"]

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
    assert _business_state(client) == before


def test_gantt_page_and_data_ignore_invalid_offset_when_explicit_dates_present(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    before = prepare_read_state(client)
    query = {"version": 3, "start_date": "2026-05-04", "end_date": "2026-05-10"}
    assert_retired(client, dict(query, offset="bad"))
    context = navigation(client, query)
    assert navigation(client, dict(query, offset_weeks="bad")) == context
    assert context["range_start"] == "2026-05-04T00:00:00"
    assert context["range_end"] == "2026-05-11T00:00:00"
    assert read_workspace(client, context)["data"]["tasks"] == []

    data_resp = client.get(
        "/scheduler/gantt/data?view=machine&version=3&start_date=2026-05-04&end_date=2026-05-10&offset=bad"
    )
    payload = data_resp.get_json()
    data = payload.get("data") or {}

    assert data_resp.status_code == 200
    assert data.get("week_start") == "2026-05-04"
    assert data.get("week_end") == "2026-05-10"
    assert data.get("range_source") == "request"
    assert _business_state(client) == before


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
