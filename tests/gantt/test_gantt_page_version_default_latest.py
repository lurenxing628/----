"""回归测试：/scheduler/gantt 页面与 /data 接口不带 version 时默认取最新排产版本（第 7 版），version=latest 同义；非法 version（0/-1）返回 400 中文提示、不存在的 version 返回 404、无任何 ScheduleHistory 时即便残留孤儿 Schedule 也不臆造 v1（显示暂无排产版本、不渲染 None）；选中版本标签按 completion_status 显示部分成功，且 GanttService 抛 BusinessError/未预期异常时走统一的 app error HTTP 映射（404/500）。"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

from core.infrastructure.errors import BusinessError, ErrorCode
from tests._support.excel_templates import point_env_at_shared
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(
    tmp_path,
    monkeypatch,
    *,
    with_history: bool = True,
    orphan_schedule: bool = False,
    result_status: str = "success",
    result_summary=None,
    extra_histories=None,
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
    if with_history:
        summary_obj = {} if result_summary is None else result_summary
        conn.execute(
            "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (7, "greedy", 0, 0, result_status, json.dumps(summary_obj, ensure_ascii=False), "pytest"),
        )
        for raw_history in list(extra_histories or []):
            extra_summary = dict(raw_history.get("result_summary") or {})
            conn.execute(
                "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    int(raw_history.get("version")),
                    raw_history.get("strategy") or "greedy",
                    0,
                    0,
                    raw_history.get("result_status") or "success",
                    json.dumps(extra_summary, ensure_ascii=False),
                    "pytest",
                ),
            )
    if orphan_schedule:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute(
            "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, version) VALUES (?, ?, ?, ?, ?, ?)",
            (999, "M-ORPHAN", "OP-ORPHAN", "2026-03-02 08:00:00", "2026-03-02 09:00:00", 1),
        )
    conn.commit()
    conn.close()

    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def test_gantt_page_version_default_latest(tmp_path, monkeypatch) -> None:
    from contextlib import closing

    from core.infrastructure.database import get_connection
    from core.models.workbench_plan_reference import WorkbenchPlanLocator
    from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
    from tests._support.gantt_current import assert_retired, navigation, prepare_read_state
    from tests._support.gantt_retirement import _business_state

    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    before = prepare_read_state(client)
    assert_retired(client, {"view": "machine", "week_start": "2026-03-02"})
    assert_retired(client, {"view": "machine", "week_start": "2026-03-02", "version": "latest"})
    default_context = navigation(client, {"week_start": "2026-03-02"})
    latest_context = navigation(client, {"week_start": "2026-03-02", "version": "latest"})
    assert latest_context == default_context
    with closing(get_connection(app.config["DATABASE_PATH"])) as conn:
        locator = WorkbenchPlanIdentityRepository(conn).resolve_plan(default_context["plan_ref"])
    assert locator == WorkbenchPlanLocator(7, "adopted")
    assert default_context["range_start"] == "2026-03-02T00:00:00"
    assert default_context["range_end"] == "2026-03-09T00:00:00"

    data_resp = client.get("/scheduler/gantt/data?view=machine&week_start=2026-03-02")
    assert data_resp.status_code == 200
    payload = json.loads(data_resp.get_data(as_text=True) or "{}")
    assert payload.get("success") is True, payload
    assert int((payload.get("data") or {}).get("version") or 0) == 7

    invalid_page_resp = client.get("/scheduler/gantt?view=machine&week_start=2026-03-02&version=0")
    invalid_page_html = invalid_page_resp.get_data(as_text=True)
    assert invalid_page_resp.status_code == 400
    assert "地址里的计划编号、日期或筛选不对，页面没有打开；系统没有替你换记录或放宽范围。请从侧栏重新进入。" in invalid_page_html
    assert "Location" not in invalid_page_resp.headers

    invalid_data_resp = client.get("/scheduler/gantt/data?view=machine&week_start=2026-03-02&version=-1")
    invalid_payload = invalid_data_resp.get_json()
    assert invalid_data_resp.status_code == 400
    assert invalid_payload["success"] is False
    assert invalid_payload["error"]["message"] == "版本号不对。请填写大于 0 的数字版本号；如果想看最新版本，可以不填版本。"

    missing_page_resp = client.get("/scheduler/gantt?view=machine&week_start=2026-03-02&version=999")
    missing_page_html = missing_page_resp.get_data(as_text=True)
    assert missing_page_resp.status_code == 404
    assert "页面不存在或已被删除" in missing_page_html
    assert "data-version=\"None\"" not in missing_page_html
    assert "Location" not in missing_page_resp.headers
    assert _business_state(client) == before


def test_gantt_no_history_does_not_synthesize_v1_even_with_orphan_schedule(tmp_path, monkeypatch) -> None:
    from tests._support.gantt_current import prepare_read_state
    from tests._support.gantt_retirement import _business_state

    app = _build_app(tmp_path, monkeypatch, with_history=False, orphan_schedule=True)
    client = app.test_client()
    before = prepare_read_state(client)

    page_resp = client.get("/scheduler/gantt?view=machine&week_start=2026-03-02")
    page_html = page_resp.get_data(as_text=True)
    assert page_resp.status_code == 404
    assert "页面不存在或已被删除" in page_html
    assert "Location" not in page_resp.headers
    assert "第 1 版" not in page_html
    assert "第 0 版" not in page_html
    assert "第 None 版" not in page_html
    assert "value=\"None\"" not in page_html
    assert "data-version=\"None\"" not in page_html

    data_resp = client.get("/scheduler/gantt/data?view=machine&week_start=2026-03-02")
    payload = data_resp.get_json()
    data = payload.get("data") or {}
    assert data_resp.status_code == 200
    assert payload.get("success") is True, payload
    assert data.get("status") == "no_history", data
    assert data.get("version") is None, data
    assert data.get("tasks") == [], data

    missing_resp = client.get("/scheduler/gantt/data?view=machine&week_start=2026-03-02&version=1")
    missing_payload = missing_resp.get_json()
    assert missing_resp.status_code == 404
    assert missing_payload["success"] is False
    catalog = client.get("/api/workbench/v1/plans?collection=history")
    assert catalog.status_code == 200
    assert catalog.get_json()["data"]["plans"] == []
    assert _business_state(client) == before


def test_gantt_no_history_explicit_dates_ignore_offset(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch, with_history=False)
    client = app.test_client()

    data_resp = client.get(
        "/scheduler/gantt/data?view=machine&start_date=2026-03-10&end_date=2026-03-12&offset=1"
    )
    payload = data_resp.get_json()
    data = payload.get("data") or {}

    assert data_resp.status_code == 200
    assert payload.get("success") is True, payload
    assert data.get("status") == "no_history", data
    assert data.get("week_start") == "2026-03-10", data
    assert data.get("week_end") == "2026-03-12", data


def test_gantt_service_no_history_explicit_dates_ignore_offset(tmp_path, monkeypatch) -> None:
    _build_app(tmp_path, monkeypatch, with_history=False)

    from core.infrastructure.database import get_connection
    from core.services.scheduler.gantt_service import GanttService

    conn = get_connection(os.environ["APS_DB_PATH"])
    try:
        data = GanttService(conn, logger=None, op_logger=None).get_gantt_tasks(
            view="machine",
            start_date="2026-03-10",
            end_date="2026-03-12",
            offset_weeks=1,
        )
    finally:
        conn.close()

    assert data.get("status") == "no_history", data
    assert data.get("week_start") == "2026-03-10", data
    assert data.get("week_end") == "2026-03-12", data


def test_gantt_page_selected_version_label_includes_simulated_completion_status(tmp_path, monkeypatch) -> None:
    from contextlib import closing

    from core.infrastructure.database import get_connection
    from tests._support.gantt_current import assert_retired, navigation, prepare_read_state
    from tests._support.gantt_retirement import _business_state
    from web.viewmodels.scheduler_history_summary import build_history_summary_display, decorate_history_version_options

    app = _build_app(
        tmp_path,
        monkeypatch,
        result_status="simulated",
        result_summary={"completion_status": "partial", "counts": {"op_count": 3, "scheduled_ops": 2, "failed_ops": 1}},
    )
    client = app.test_client()
    before = prepare_read_state(client)
    assert_retired(client, {"view": "machine", "week_start": "2026-03-02", "version": 7})
    context = navigation(client, {"version": 7})
    # The legacy dropdown is retired. Its shared summary formatter and stored
    # simulated/partial facts remain contracts, not claims about the new label.
    with closing(get_connection(app.config["DATABASE_PATH"])) as conn:
        row = dict(conn.execute("SELECT * FROM ScheduleHistory WHERE version = 7").fetchone())
    display = build_history_summary_display(raw_summary=row["result_summary"], result_status=row["result_status"])
    option = decorate_history_version_options([row])[0]
    assert display["result_status_label"] == "模拟排产 / 部分成功"
    assert option["version_option_label"] == "v7 · 模拟排产 / 部分成功"
    assert option["version_option_label"] != "v7 · 部分成功"
    catalog = client.get("/api/workbench/v1/plans?collection=history")
    assert catalog.status_code == 200
    assert any(plan["version"] == 7 and plan["plan_ref"] == context["plan_ref"]
               for plan in catalog.get_json()["data"]["plans"])
    assert _business_state(client) == before


def test_gantt_page_non_selected_version_option_uses_completion_status_label(tmp_path, monkeypatch) -> None:
    from contextlib import closing

    from core.infrastructure.database import get_connection
    from tests._support.gantt_current import assert_retired, prepare_read_state
    from tests._support.gantt_retirement import _business_state
    from web.viewmodels.scheduler_history_summary import decorate_history_version_options

    app = _build_app(
        tmp_path,
        monkeypatch,
        result_status="success",
        result_summary={"completion_status": "success"},
        extra_histories=[
            {
                "version": 6,
                "result_status": "simulated",
                "result_summary": {"completion_status": "partial", "counts": {"op_count": 3, "scheduled_ops": 2, "failed_ops": 1}},
            }
        ],
    )
    client = app.test_client()
    before = prepare_read_state(client)
    assert_retired(client, {"view": "machine", "week_start": "2026-03-02", "version": 7})
    with closing(get_connection(app.config["DATABASE_PATH"])) as conn:
        rows = [dict(row) for row in conn.execute("SELECT * FROM ScheduleHistory ORDER BY version DESC")]
    options = decorate_history_version_options(rows)
    assert [option["version"] for option in options] == [7, 6]
    assert options[1]["version_option_label"] == "v6 · 模拟排产 / 部分成功"
    assert options[1]["version_option_label"] != "v6 · 部分成功"
    catalog = client.get("/api/workbench/v1/plans?collection=history")
    assert catalog.status_code == 200
    assert [plan["version"] for plan in catalog.get_json()["data"]["plans"]] == [7, 6]
    assert _business_state(client) == before


def test_gantt_data_uses_app_error_http_mapping(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    from core.services.scheduler.gantt_service import GanttService

    def _raise_not_found(self, **_kwargs):
        raise BusinessError(ErrorCode.NOT_FOUND, "甘特图版本不存在")

    monkeypatch.setattr(GanttService, "get_gantt_tasks", _raise_not_found)

    response = client.get("/scheduler/gantt/data?view=machine&week_start=2026-03-02&version=7")

    payload = response.get_json()
    assert response.status_code == 404
    assert payload["success"] is False
    assert payload["error"]["code"] == ErrorCode.NOT_FOUND.value
    assert payload["error"]["message"] == "甘特图版本不存在"


def test_gantt_data_unexpected_error_uses_unified_unknown_error_contract(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    from core.services.scheduler.gantt_service import GanttService

    def _raise_bug(self, **_kwargs):
        raise RuntimeError("gantt exploded")

    monkeypatch.setattr(GanttService, "get_gantt_tasks", _raise_bug)

    response = client.get("/scheduler/gantt/data?view=machine&week_start=2026-03-02&version=7")

    payload = response.get_json()
    assert response.status_code == 500
    assert payload["success"] is False
    assert payload["error"]["code"] == ErrorCode.UNKNOWN_ERROR.value
    assert payload["error"]["message"] == "甘特图数据生成失败，请稍后重试。"
