from __future__ import annotations

import importlib
import io
from pathlib import Path

import openpyxl

from core.infrastructure.database import ensure_schema, get_connection
from core.services.personnel.operator_service import OperatorService

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



def _set_config_raw(db_path: str, value: str) -> None:
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
            ("holiday_default_efficiency", value, "test override"),
        )
        conn.commit()
    finally:
        conn.close()



def _seed_operator(db_path: str, operator_id: str = "OP001") -> None:
    conn = get_connection(db_path)
    try:
        OperatorService(conn).create(operator_id=operator_id, name="测试人员", status="active")
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
    assert "配置项 holiday_default_efficiency 当前非法，页面已临时按 0.8 展示默认值；请先到排产参数页修复配置，再继续依赖该默认值进行操作。" in scheduler_body

    _set_config_raw(db_path, "0")
    resp_personnel = client.get("/personnel/OP001/calendar")
    personnel_body = resp_personnel.get_data(as_text=True)
    assert resp_personnel.status_code == 200
    assert "配置项 holiday_default_efficiency 当前非法，页面已临时按 0.8 展示默认值；请先到排产参数页修复配置，再继续依赖该默认值进行操作。" in personnel_body
    assert any("holiday_default_efficiency 非法" in item for item in warnings)



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
    assert "系统配置项 holiday_default_efficiency 非法，无法继续工作日历 Excel 导入，请先在排产参数中修复。" in preview_body
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
    assert "系统配置项 holiday_default_efficiency 非法，无法继续工作日历 Excel 导入，请先在排产参数中修复。" in confirm_body



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
    assert "系统配置项 holiday_default_efficiency 非法，无法继续人员专属工作日历 Excel 导入，请先在排产参数中修复。" in preview_body
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
    assert "系统配置项 holiday_default_efficiency 非法，无法继续人员专属工作日历 Excel 导入，请先在排产参数中修复。" in confirm_body
