from __future__ import annotations

import importlib
import io
from pathlib import Path

import openpyxl
import pytest

from core.infrastructure.database import ensure_schema, get_connection
from core.services.personnel.operator_service import OperatorService
from core.services.scheduler.config_service import ConfigService

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(tmp_path, monkeypatch):
    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_templates = tmp_path / "templates_excel"
    test_logs.mkdir(exist_ok=True)
    test_backups.mkdir(exist_ok=True)
    test_templates.mkdir(exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(test_templates))

    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app(), str(test_db)


def _set_schedule_config_raw(db_path: str, key: str, value: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO ScheduleConfig (config_key, config_value, description)
            VALUES (?, ?, ?)
            ON CONFLICT(config_key) DO UPDATE SET
              config_value = excluded.config_value,
              description = excluded.description,
              updated_at = CURRENT_TIMESTAMP
            """,
            (key, value, "test override"),
        )
        conn.commit()
    finally:
        conn.close()


def _set_config_raw(db_path: str, value: str) -> None:
    _set_schedule_config_raw(db_path, "holiday_default_efficiency", value)


def _seed_default_scheduler_config(db_path: str) -> None:
    conn = get_connection(db_path)
    try:
        ConfigService(conn, logger=None, op_logger=None).restore_default()
    finally:
        conn.close()


def _delete_schedule_config_key(db_path: str, key: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute("DELETE FROM ScheduleConfig WHERE config_key = ?", (key,))
        conn.commit()
    finally:
        conn.close()


def _seed_operator(db_path: str, operator_id: str = "OP001") -> None:
    conn = get_connection(db_path)
    try:
        OperatorService(conn).create(operator_id=operator_id, name="测试人员", status="active")
    finally:
        conn.close()


def _count_rows(db_path: str, table_name: str) -> int:
    conn = get_connection(db_path)
    try:
        row = conn.execute(f"SELECT COUNT(*) AS c FROM {table_name}").fetchone()
        return int((row["c"] if row is not None else 0) or 0)
    finally:
        conn.close()


def _count_schedule_config_key(db_path: str, key: str) -> int:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM ScheduleConfig WHERE config_key = ?",
            (key,),
        ).fetchone()
        return int((row["c"] if row is not None else 0) or 0)
    finally:
        conn.close()


def _seed_batch(db_path: str, batch_id: str = "B001", part_no: str = "P001") -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(part_no) DO UPDATE SET
              part_name = excluded.part_name,
              route_raw = excluded.route_raw,
              route_parsed = excluded.route_parsed,
              remark = excluded.remark,
              updated_at = CURRENT_TIMESTAMP
            """,
            (part_no, "测试零件", "", "no", "route-noop"),
        )
        conn.execute(
            """
            INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(batch_id) DO UPDATE SET
              part_no = excluded.part_no,
              part_name = excluded.part_name,
              quantity = excluded.quantity,
              due_date = excluded.due_date,
              priority = excluded.priority,
              ready_status = excluded.ready_status,
              status = excluded.status,
              remark = excluded.remark,
              updated_at = CURRENT_TIMESTAMP
            """,
            (batch_id, part_no, "测试零件", 1, "2099-12-31", "normal", "yes", "pending", "read-guard"),
        )
        conn.commit()
    finally:
        conn.close()


def _make_xlsx(headers, rows) -> io.BytesIO:
    wb = openpyxl.Workbook()
    try:
        ws = wb.active
        assert ws is not None
        ws.title = "Sheet1"
        ws.append(list(headers))
        for row in rows:
            ws.append([row.get(h) for h in headers])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf
    finally:
        wb.close()


def test_calendar_pages_show_degraded_warning_when_holiday_default_efficiency_invalid(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _seed_operator(db_path)
    client = app.test_client()
    warnings = []

    def _fake_warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)

    _set_config_raw(db_path, "NaN")
    resp_scheduler = client.get("/scheduler/calendar")
    scheduler_body = resp_scheduler.get_data(as_text=True)
    assert resp_scheduler.status_code == 200
    assert "假期工作效率" in scheduler_body
    assert "holiday_default_efficiency" not in scheduler_body
    assert '"holidayDefaultEfficiency": null' in scheduler_body
    assert '"holidayDefaultEfficiency": 0.8' not in scheduler_body
    assert "页面已临时按" in scheduler_body
    assert "0.8" in scheduler_body
    assert "排产参数页修复配置" in scheduler_body
    assert "继续依赖该默认值进行操作" in scheduler_body

    _set_config_raw(db_path, "0")
    resp_personnel = client.get("/personnel/OP001/calendar")
    personnel_body = resp_personnel.get_data(as_text=True)
    assert resp_personnel.status_code == 200
    assert "假期工作效率" in personnel_body
    assert "holiday_default_efficiency" not in personnel_body
    assert '"holidayDefaultEfficiency": null' in personnel_body
    assert '"holidayDefaultEfficiency": 0.8' not in personnel_body
    assert "页面已临时按" in personnel_body
    assert "0.8" in personnel_body
    assert "排产参数页修复配置" in personnel_body
    assert "继续依赖该默认值进行操作" in personnel_body
    assert any("假期工作效率" in item for item in warnings)


def test_scheduler_config_page_shows_degraded_warning_when_holiday_default_efficiency_invalid(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    warnings = []

    def _fake_warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)

    _set_config_raw(db_path, "NaN")
    resp = client.get("/scheduler/config")
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'name="holiday_default_efficiency"' in body
    assert 'value="0.8"' in body
    assert "假期工作效率 当前配置无效" in body
    assert 'class="flash-card flash-warning"' in body


def test_scheduler_config_page_shows_summary_and_inline_warnings_for_multiple_degraded_fields_in_v2(
    tmp_path, monkeypatch
) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    warnings = []

    def _fake_warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)

    _set_schedule_config_raw(db_path, "holiday_default_efficiency", "NaN")
    _set_schedule_config_raw(db_path, "objective", " BAD_OBJECTIVE ")
    _set_schedule_config_raw(db_path, "dispatch_mode", " BAD_MODE ")

    resp = client.get("/scheduler/config", headers={"Cookie": "aps_ui_mode=v2"})
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "scheduler-config-degraded-summary" in body
    assert body.count("scheduler-config-field-warning") >= 3
    assert 'name="holiday_default_efficiency"' in body
    assert 'name="objective"' in body
    assert 'name="dispatch_mode"' in body
    assert 'value="0.8"' in body


@pytest.mark.parametrize(
    ("path", "needs_batch"),
    [
        ("/scheduler/config", False),
        ("/scheduler/", False),
        ("/scheduler/calendar", False),
        ("/scheduler/batches/B001", True),
    ],
)
def test_scheduler_read_routes_do_not_repair_dirty_partial_schedule_config(
    path: str,
    needs_batch: bool,
    tmp_path,
    monkeypatch,
) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    _seed_default_scheduler_config(db_path)
    if needs_batch:
        _seed_batch(db_path)
    _delete_schedule_config_key(db_path, "objective")

    before = _count_rows(db_path, "ScheduleConfig")
    missing_before = _count_schedule_config_key(db_path, "objective")

    response = client.get(path)

    after = _count_rows(db_path, "ScheduleConfig")
    missing_after = _count_schedule_config_key(db_path, "objective")

    assert response.status_code == 200
    assert before == after
    assert missing_before == 0
    assert missing_after == 0


def test_scheduler_config_page_renders_auto_assign_persist_visibility_in_v1_and_v2(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    _set_schedule_config_raw(db_path, "auto_assign_persist", "no")

    resp_v1 = client.get("/scheduler/config", headers={"Cookie": "aps_ui_mode=v1"})
    body_v1 = resp_v1.get_data(as_text=True)
    assert resp_v1.status_code == 200
    assert "保存系统补齐的设备和人员" in body_v1
    assert "已关闭" in body_v1

    resp_v2 = client.get("/scheduler/config", headers={"Cookie": "aps_ui_mode=v2"})
    body_v2 = resp_v2.get_data(as_text=True)
    assert resp_v2.status_code == 200
    assert "保存系统补齐的设备和人员" in body_v2
    assert "已关闭" in body_v2


def test_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    _set_config_raw(db_path, "NaN")

    resp = client.post(
        "/scheduler/calendar/upsert",
        data={
            "date": "2026-04-03",
            "day_type": "holiday",
            "shift_hours": "",
            "shift_start": "",
            "shift_end": "",
            "efficiency": "",
            "allow_normal": "no",
            "allow_urgent": "no",
            "remark": "cfg",
        },
        follow_redirects=True,
    )
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "假期工作效率" in body
    assert "holiday_default_efficiency" not in body
    assert "日历配置已保存" not in body
    assert _count_rows(db_path, "WorkCalendar") == 0


def test_operator_calendar_upsert_rejects_invalid_holiday_default_efficiency_in_post_chain(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _seed_operator(db_path)
    client = app.test_client()
    _set_config_raw(db_path, "0")

    resp = client.post(
        "/personnel/OP001/calendar/upsert",
        data={
            "date": "2026-04-04",
            "day_type": "holiday",
            "shift_hours": "",
            "shift_start": "",
            "shift_end": "",
            "efficiency": "",
            "allow_normal": "no",
            "allow_urgent": "no",
            "remark": "cfg",
        },
        follow_redirects=True,
    )
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "假期工作效率" in body
    assert "holiday_default_efficiency" not in body
    assert "个人日历配置已保存" not in body
    assert _count_rows(db_path, "OperatorCalendar") == 0


def test_calendar_picker_js_does_not_rebuild_local_0_8_default() -> None:
    source = (REPO_ROOT / "static" / "js" / "calendar_picker.js").read_text(encoding="utf-8")
    assert ": 0.8;" not in source, "calendar_picker.js 不应在前端重建 0.8 本地默认值"


def test_scheduler_excel_calendar_preview_and_confirm_reject_invalid_holiday_default_efficiency(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    _set_config_raw(db_path, "NaN")

    preview_resp = client.post(
        "/scheduler/excel/calendar/preview",
        data={
            "mode": "overwrite",
            "file": (
                _make_xlsx(
                    ["日期", "类型", "可用工时", "效率", "允许普通件", "允许急件", "说明"],
                    [{"日期": "2026-04-01", "类型": "holiday", "可用工时": 0, "效率": None, "允许普通件": "no", "允许急件": "no", "说明": "cfg"}],
                ),
                "calendar.xlsx",
            ),
        },
        content_type="multipart/form-data",
    )
    preview_body = preview_resp.get_data(as_text=True)
    assert preview_resp.status_code == 200
    assert "假期工作效率" in preview_body
    assert "holiday_default_efficiency" not in preview_body
    assert "工作日历 Excel 导入" in preview_body
    assert "排产参数中修复" in preview_body
    assert 'name="raw_rows_json"' not in preview_body

    confirm_resp = client.post(
        "/scheduler/excel/calendar/confirm",
        data={
            "mode": "overwrite",
            "filename": "calendar.xlsx",
            "raw_rows_json": "[]",
            "preview_baseline": "dummy",
        },
    )
    confirm_body = confirm_resp.get_data(as_text=True)
    assert confirm_resp.status_code == 200
    assert "假期工作效率" in confirm_body
    assert "holiday_default_efficiency" not in confirm_body
    assert "工作日历 Excel 导入" in confirm_body
    assert "排产参数中修复" in confirm_body


def test_operator_calendar_excel_preview_and_confirm_reject_invalid_holiday_default_efficiency(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _seed_operator(db_path)
    client = app.test_client()
    _set_config_raw(db_path, "0")

    preview_resp = client.post(
        "/personnel/excel/operator_calendar/preview",
        data={
            "mode": "overwrite",
            "file": (
                _make_xlsx(
                    ["工号", "日期", "类型", "班次开始", "班次结束", "可用工时", "效率", "允许普通件", "允许急件", "说明"],
                    [
                        {
                            "工号": "OP001",
                            "日期": "2026-04-02",
                            "类型": "holiday",
                            "班次开始": "08:00",
                            "班次结束": "",
                            "可用工时": 0,
                            "效率": None,
                            "允许普通件": "no",
                            "允许急件": "no",
                            "说明": "cfg",
                        }
                    ],
                ),
                "operator_calendar.xlsx",
            ),
        },
        content_type="multipart/form-data",
    )
    preview_body = preview_resp.get_data(as_text=True)
    assert preview_resp.status_code == 200
    assert "假期工作效率" in preview_body
    assert "holiday_default_efficiency" not in preview_body
    assert "人员专属工作日历 Excel 导入" in preview_body
    assert "排产参数中修复" in preview_body
    assert 'name="raw_rows_json"' not in preview_body

    confirm_resp = client.post(
        "/personnel/excel/operator_calendar/confirm",
        data={
            "mode": "overwrite",
            "filename": "operator_calendar.xlsx",
            "raw_rows_json": '[{"工号":"OP001","日期":"2026-04-02","__id":"OP001|2026-04-02"}]',
            "preview_baseline": "dummy",
        },
    )
    confirm_body = confirm_resp.get_data(as_text=True)
    assert confirm_resp.status_code == 200
    assert "假期工作效率" in confirm_body
    assert "holiday_default_efficiency" not in confirm_body
    assert "人员专属工作日历 Excel 导入" in confirm_body
    assert "排产参数中修复" in confirm_body
def test_scheduler_excel_calendar_preview_bootstraps_pristine_store_without_prior_read(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    preview_resp = client.post(
        "/scheduler/excel/calendar/preview",
        data={
            "mode": "overwrite",
            "file": (
                _make_xlsx(
                    ["鏃ユ湡", "绫诲瀷", "鍙敤宸ユ椂", "鏁堢巼", "鍏佽鏅€氫欢", "鍏佽鎬ヤ欢", "璇存槑"],
                    [{"鏃ユ湡": "2026-04-01", "绫诲瀷": "holiday", "鍙敤宸ユ椂": 0, "鏁堢巼": None, "鍏佽鏅€氫欢": "no", "鍏佽鎬ヤ欢": "no", "璇存槑": "cfg"}],
                ),
                "calendar.xlsx",
            ),
        },
        content_type="multipart/form-data",
    )
    preview_body = preview_resp.get_data(as_text=True)

    assert preview_resp.status_code == 200
    assert 'name="raw_rows_json"' in preview_body
    assert _count_rows(db_path, "ScheduleConfig") > 0


def test_operator_calendar_excel_preview_bootstraps_pristine_store_without_prior_read(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _seed_operator(db_path)
    client = app.test_client()

    preview_resp = client.post(
        "/personnel/excel/operator_calendar/preview",
        data={
            "mode": "overwrite",
            "file": (
                _make_xlsx(
                    ["宸ュ彿", "鏃ユ湡", "绫诲瀷", "鐝寮€濮?", "鐝缁撴潫", "鍙敤宸ユ椂", "鏁堢巼", "鍏佽鏅€氫欢", "鍏佽鎬ヤ欢", "璇存槑"],
                    [
                        {
                            "宸ュ彿": "OP001",
                            "鏃ユ湡": "2026-04-02",
                            "绫诲瀷": "holiday",
                            "鐝寮€濮?": "08:00",
                            "鐝缁撴潫": "",
                            "鍙敤宸ユ椂": 0,
                            "鏁堢巼": None,
                            "鍏佽鏅€氫欢": "no",
                            "鍏佽鎬ヤ欢": "no",
                            "璇存槑": "cfg",
                        }
                    ],
                ),
                "operator_calendar.xlsx",
            ),
        },
        content_type="multipart/form-data",
    )
    preview_body = preview_resp.get_data(as_text=True)

    assert preview_resp.status_code == 200
    assert 'name="raw_rows_json"' in preview_body
    assert _count_rows(db_path, "ScheduleConfig") > 0
