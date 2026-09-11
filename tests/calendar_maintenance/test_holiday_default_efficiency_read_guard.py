"""回归测试：holiday_default_efficiency 配置无效（NaN/0）时，日历/人员日历/排产参数等读页须显示降级 warning 并临时按 0.8、不泄露内部键名 holiday_default_efficiency；日历 upsert 与 Excel 预览/确认链路须拒绝写入；纯读路由（config/calendar/batch 详情）不得顺手修复脏的部分配置（ScheduleConfig 行数与缺失键不变），Excel 预览首次访问可 bootstrap 出配置；日历行错误文案用纯列名口径，前端 calendar_picker.js 不重建 0.8 本地默认。"""

from __future__ import annotations

import importlib
import io
import json
from pathlib import Path

import openpyxl
import pytest

from core.errors import ValidationError
from core.infrastructure.database import ensure_schema, get_connection
from core.services.personnel.operator_service import OperatorService
from core.services.scheduler.config.config_service import ConfigService
from tests._support.excel_templates import point_env_at_shared
from tests._support.legacy_http import (
    assert_no_confirmation,
    assert_retired_response,
    canonical_navigation,
    confirmation_inputs,
    follow_legacy_post_redirect,
    notice_messages,
)
from tests._support.paths import REPO_ROOT
from tests._support.sqlite_snapshot import table_rows
from web.routes.excel_utils import encode_preview_rows_payload

SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(tmp_path, monkeypatch):
    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_logs.mkdir(exist_ok=True)
    test_backups.mkdir(exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    point_env_at_shared(monkeypatch)

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


def _encoded_preview_rows(rows) -> str:
    payload = encode_preview_rows_payload(json.dumps(rows, ensure_ascii=False))
    assert payload is not None
    return payload


def _config_rows(db_path):
    """Snapshot raw configuration including missing rows and stored text values."""
    conn = get_connection(db_path)
    try:
        return table_rows(conn, "ScheduleConfig")
    finally:
        conn.close()


def _read_config_panel(db_path):
    """Exercise the retained read model without rendering or invoking a retired page."""
    from web.routes.domains.scheduler.scheduler_config_display_state import (
        build_scheduler_config_panel_state_from_service,
    )

    conn = get_connection(db_path)
    try:
        return build_scheduler_config_panel_state_from_service(ConfigService(conn))
    finally:
        conn.close()


def _rejected_calendar_preview(client, personal):
    """Use the retained POST to prove a bad default is publicly rejected before writing."""
    row = {"日期": "2026-04-01", "类型": "holiday", "可用工时": 0, "效率": None,
           "允许普通件": "no", "允许急件": "no", "说明": "config-guard"}
    path = "/scheduler/excel/calendar"
    if personal:
        row.update({"工号": "OP001", "班次开始": "08:00", "班次结束": ""})
        path = "/personnel/excel/operator_calendar"
    response = client.post(path + "/preview", data={
        "mode": "overwrite", "file": (_make_xlsx(list(row), [row]), "calendar.xlsx"),
    }, content_type="multipart/form-data")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert_no_confirmation(body)
    assert any("假期工作效率" in message for message in notice_messages(body, "error"))
    assert "holiday_default_efficiency" not in body


def _rejected_config_preset(client):
    """Keep the real config POST rejection and public field label after GET retirement."""
    response = client.post("/scheduler/config/preset/save", data={"preset_name": "F-invalid-config"})
    body = follow_legacy_post_redirect(client, response, "/scheduler/config")
    errors = notice_messages(body, "error")
    assert errors and any("假期工作效率" in message for message in errors), body
    assert not notice_messages(body, "success")
    assert "holiday_default_efficiency" not in body


def test_calendar_excel_row_errors_use_plain_column_copy() -> None:
    from web.routes.domains.scheduler.scheduler_excel_calendar_rows import validate_calendar_import_row

    base = {
        "日期": "2026-04-01",
        "类型": "工作日",
        "可用工时": 8,
        "效率": 1,
        "允许普通件": "是",
        "允许急件": "是",
        "说明": "copy",
    }

    type_error = validate_calendar_import_row({**base, "类型": "随便写"}, holiday_default_efficiency=0.8)
    assert type_error is not None and "“类型”" in type_error and "工作日 / 假期" in type_error

    normal_error = validate_calendar_import_row({**base, "允许普通件": "随便写"}, holiday_default_efficiency=0.8)
    assert normal_error is not None and "“允许普通件”" in normal_error and "是 / 否" in normal_error

    urgent_error = validate_calendar_import_row({**base, "允许急件": "随便写"}, holiday_default_efficiency=0.8)
    assert urgent_error is not None and "“允许急件”" in urgent_error and "是 / 否" in urgent_error


def test_operator_calendar_excel_row_errors_use_plain_column_copy(tmp_path, monkeypatch) -> None:
    from core.services.common.excel_validators import get_operator_calendar_row_validate_and_normalize

    _app, db_path = _build_app(tmp_path, monkeypatch)
    _seed_operator(db_path)
    conn = get_connection(db_path)
    try:
        validate = get_operator_calendar_row_validate_and_normalize(conn, holiday_default_efficiency=0.8)
        base = {
            "工号": "OP001",
            "日期": "2026-04-01",
            "类型": "工作日",
            "班次开始": "08:00",
            "班次结束": "",
            "可用工时": 8,
            "效率": 1,
            "允许普通件": "是",
            "允许急件": "是",
            "说明": "copy",
        }

        type_error = validate({**base, "类型": "随便写"})
        assert type_error is not None and "“类型”" in type_error and "工作日 / 假期" in type_error

        normal_error = validate({**base, "允许普通件": "随便写"})
        assert normal_error is not None and "“允许普通件”" in normal_error and "是 / 否" in normal_error

        urgent_error = validate({**base, "允许急件": "随便写"})
        assert urgent_error is not None and "“允许急件”" in urgent_error and "是 / 否" in urgent_error
    finally:
        conn.close()


def test_calendar_pages_show_degraded_warning_when_holiday_default_efficiency_invalid(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _seed_operator(db_path)
    client = app.test_client()
    warnings = []

    def _fake_warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)
    for raw, path, personal in (("NaN", "/scheduler/calendar", False), ("0", "/personnel/OP001/calendar", True)):
        _set_config_raw(db_path, raw)
        before = _config_rows(db_path)
        body = assert_retired_response(client.get(path))
        assert "holidayDefaultEfficiency" not in body
        if personal:
            assert "未改查公共日历或其他人员" in body
        conn = get_connection(db_path)
        try:
            service = ConfigService(conn)
            value, degraded, warning = service.get_holiday_default_efficiency_display_state(logger=app.logger)
            assert value == 0.8 and degraded is True
            assert "假期工作效率" in warning and "holiday_default_efficiency" not in warning
            assert "页面已临时按" in warning and "0.8" in warning
            assert "排产参数页修复配置" in warning and "继续依赖该默认值进行操作" in warning
            with pytest.raises(ValidationError):
                service.get_holiday_default_efficiency(strict_mode=True)
        finally:
            conn.close()
        current = client.get("/api/workbench/v1/resources/summary")
        assert current.status_code == 200
        holiday = current.get_json()["data"]["calendar"]["holiday_default_efficiency"]
        assert holiday["status"] == "unavailable" and holiday["value"] is None
        assert holiday["issues"]
        _rejected_calendar_preview(client, personal)
        assert _config_rows(db_path) == before
        assert _count_rows(db_path, "WorkCalendar") == _count_rows(db_path, "OperatorCalendar") == 0
    assert any("假期工作效率" in item for item in warnings)


def test_scheduler_config_page_shows_degraded_warning_when_holiday_default_efficiency_invalid(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    warnings = []

    def _fake_warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)

    _seed_default_scheduler_config(db_path)
    _set_config_raw(db_path, "NaN")
    before = _config_rows(db_path)
    resp = client.get("/scheduler/config")
    assert_retired_response(resp)
    panel = _read_config_panel(db_path)
    assert panel.cfg.holiday_default_efficiency == 0.8
    assert "holiday_default_efficiency" in panel.config_field_metadata
    assert "假期工作效率 这项设置现在不能直接用" in panel.config_field_warnings["holiday_default_efficiency"]
    assert any(item.tone == "warning" for item in panel.notice_items)
    _rejected_config_preset(client)
    assert _config_rows(db_path) == before


def test_scheduler_config_page_shows_summary_and_inline_warnings_for_multiple_degraded_fields_in_v2(
    tmp_path, monkeypatch
) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    warnings = []

    def _fake_warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)

    _seed_default_scheduler_config(db_path)
    _set_schedule_config_raw(db_path, "holiday_default_efficiency", "NaN")
    _set_schedule_config_raw(db_path, "objective", " BAD_OBJECTIVE ")
    _set_schedule_config_raw(db_path, "dispatch_mode", " BAD_MODE ")

    before = _config_rows(db_path)
    assert_retired_response(client.get("/scheduler/config"))
    panel = _read_config_panel(db_path)
    expected = {"holiday_default_efficiency", "objective", "dispatch_mode"}
    assert expected.issubset(panel.config_field_metadata)
    assert expected.issubset(panel.config_degraded_fields)
    assert len(panel.config_field_warnings) >= 3
    for field in expected:
        assert panel.config_field_warnings[field]
        assert field not in panel.config_field_warnings[field]
    assert any(item.tone == "warning" and len(item.detail_items) >= 3 for item in panel.notice_items)
    assert panel.cfg.holiday_default_efficiency == 0.8
    _rejected_config_preset(client)
    assert _config_rows(db_path) == before


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

    if needs_batch:
        context = canonical_navigation(client, response, "batches")
        assert set(context) == {"entity_ref"}
        conn = get_connection(db_path)
        try:
            row = conn.execute(
                "SELECT entity_key FROM WorkbenchEntityRefs WHERE kind='batch' AND ref=? AND active=1",
                (context["entity_ref"],),
            ).fetchone()
            assert row is not None and row["entity_key"] == "B001"
        finally:
            conn.close()
    else:
        assert_retired_response(response)
    assert after == _count_rows(db_path, "ScheduleConfig")
    assert missing_after == _count_schedule_config_key(db_path, "objective")
    assert before == after
    assert missing_before == 0
    assert missing_after == 0


def test_scheduler_config_page_renders_auto_assign_persist_visibility(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    _set_schedule_config_raw(db_path, "auto_assign_persist", "no")
    before = _config_rows(db_path)
    resp = client.get("/scheduler/config")
    assert_retired_response(resp)
    panel = _read_config_panel(db_path)
    state = panel.current_auto_assign_persist_state
    assert panel.cfg.auto_assign_persist == "no"
    assert state["enabled"] is False and state["value"] == "no" and state["label"] == "已关闭"
    item = panel.current_auto_assign_persist_item
    assert item.label == "保存补齐资源" and item.value == "已关闭"
    assert "不改工序原来的资料" in item.desc
    assert _config_rows(db_path) == before


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
        follow_redirects=False,
    )
    body = follow_legacy_post_redirect(client, resp, "/scheduler/calendar")
    assert any("假期工作效率" in message for message in notice_messages(body, "error"))
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
        follow_redirects=False,
    )
    body = follow_legacy_post_redirect(client, resp, "/personnel/OP001/calendar")
    assert any("假期工作效率" in message for message in notice_messages(body, "error"))
    assert "假期工作效率" in body
    assert "holiday_default_efficiency" not in body
    assert "个人日历配置已保存" not in body
    assert _count_rows(db_path, "OperatorCalendar") == 0


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
            "raw_rows_json": _encoded_preview_rows(
                [{"日期": "2026-04-01", "类型": "holiday", "可用工时": 0, "效率": None}]
            ),
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
            "raw_rows_json": _encoded_preview_rows([{"工号": "OP001", "日期": "2026-04-02", "__id": "OP001|2026-04-02"}]),
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
    fields = confirmation_inputs(preview_body, "/scheduler/excel/calendar/confirm")
    assert fields["mode"] == "overwrite" and fields["filename"] == "calendar.xlsx"
    assert _count_rows(db_path, "ScheduleConfig") > 0
    assert _count_rows(db_path, "WorkCalendar") == 0


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
    fields = confirmation_inputs(preview_body, "/personnel/excel/operator_calendar/confirm")
    assert fields["mode"] == "overwrite" and fields["filename"] == "operator_calendar.xlsx"
    assert _count_rows(db_path, "ScheduleConfig") > 0
    assert _count_rows(db_path, "OperatorCalendar") == 0
