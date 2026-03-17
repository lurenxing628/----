import importlib
import io
import os
import re
import sys
import tempfile
from unittest.mock import patch

COUNT_RE = re.compile(r"(?:导入完成|导入部分完成)：新增\s*(\d+)，更新\s*(\d+)，跳过\s*(\d+)，错误\s*(\d+)。")


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _extract_raw_rows_json(html: str) -> str:
    m = re.search(r'<textarea name="raw_rows_json"[^>]*>(.*?)</textarea>', html, re.S)
    if not m:
        raise RuntimeError("未能从页面提取 raw_rows_json")
    raw = m.group(1)
    return raw.replace("&quot;", '"').replace("&#34;", '"').replace("&amp;", "&").strip()


def _extract_hidden_input(html: str, name: str) -> str:
    for m in re.finditer(r"<input[^>]+>", html, re.I):
        tag = m.group(0)
        if re.search(rf'name="{re.escape(name)}"', tag):
            vm = re.search(r'value="([^"]*)"', tag)
            v = vm.group(1) if vm else ""
            return v.replace("&quot;", '"').replace("&#34;", '"').replace("&amp;", "&").strip()
    return ""


def _make_xlsx_bytes(headers, rows):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h) for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _assert_status(name: str, resp, expect_code: int = 200):
    if resp.status_code != expect_code:
        body = ""
        try:
            body = resp.data.decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect_code}；body={body[:500]}")


def _post_export_preview_confirm(
    client,
    *,
    export_url: str,
    preview_url: str,
    confirm_url: str,
    filename: str,
    mode: str = "overwrite",
    preview_extra=None,
    confirm_extra=None,
    confirm_hidden_fields=None,
):
    preview_extra = dict(preview_extra or {})
    confirm_extra = dict(confirm_extra or {})
    confirm_hidden_fields = list(confirm_hidden_fields or [])
    export_resp = client.get(export_url)
    _assert_status(f"{export_url} export", export_resp, 200)

    preview_resp = client.post(
        preview_url,
        data={"mode": mode, **preview_extra, "file": (io.BytesIO(export_resp.data), filename)},
        content_type="multipart/form-data",
    )
    _assert_status(f"{preview_url} preview", preview_resp, 200)
    preview_html = preview_resp.data.decode("utf-8", errors="ignore")

    raw_rows_json = _extract_raw_rows_json(preview_html)
    preview_baseline = _extract_hidden_input(preview_html, "preview_baseline")
    if not preview_baseline:
        raise RuntimeError(f"{preview_url} preview 缺少 preview_baseline")
    payload = {
        "mode": mode,
        "filename": filename,
        "raw_rows_json": raw_rows_json,
        "preview_baseline": preview_baseline,
    }
    for field_name in confirm_hidden_fields:
        hidden_value = _extract_hidden_input(preview_html, field_name)
        if hidden_value != "":
            payload[field_name] = hidden_value
    payload.update(confirm_extra)

    confirm_resp = client.post(confirm_url, data=payload, follow_redirects=True)
    _assert_status(f"{confirm_url} confirm", confirm_resp, 200)
    return confirm_resp.data.decode("utf-8", errors="ignore")


def _post_file_preview_confirm(
    client,
    *,
    preview_url: str,
    confirm_url: str,
    filename: str,
    headers,
    rows,
    mode: str = "overwrite",
    preview_extra=None,
    confirm_extra=None,
    confirm_hidden_fields=None,
):
    preview_extra = dict(preview_extra or {})
    confirm_extra = dict(confirm_extra or {})
    confirm_hidden_fields = list(confirm_hidden_fields or [])
    preview_resp = client.post(
        preview_url,
        data={"mode": mode, **preview_extra, "file": (_make_xlsx_bytes(headers, rows), filename)},
        content_type="multipart/form-data",
    )
    _assert_status(f"{preview_url} preview", preview_resp, 200)
    preview_html = preview_resp.data.decode("utf-8", errors="ignore")

    raw_rows_json = _extract_raw_rows_json(preview_html)
    preview_baseline = _extract_hidden_input(preview_html, "preview_baseline")
    if not preview_baseline:
        raise RuntimeError(f"{preview_url} preview 缺少 preview_baseline")
    payload = {
        "mode": mode,
        "filename": filename,
        "raw_rows_json": raw_rows_json,
        "preview_baseline": preview_baseline,
    }
    for field_name in confirm_hidden_fields:
        hidden_value = _extract_hidden_input(preview_html, field_name)
        if hidden_value != "":
            payload[field_name] = hidden_value
    payload.update(confirm_extra)

    confirm_resp = client.post(confirm_url, data=payload, follow_redirects=True)
    _assert_status(f"{confirm_url} confirm", confirm_resp, 200)
    return confirm_resp.data.decode("utf-8", errors="ignore")


def _assert_skip_semantics(case_name: str, html: str, *, expect_auto_suffix: bool = False) -> None:
    m = COUNT_RE.search(html)
    if not m:
        raise RuntimeError(f"{case_name} 未找到导入计数提示")
    new_count, update_count, skip_count, error_count = [int(x) for x in m.groups()]
    if new_count != 0 or update_count != 0 or error_count != 0 or skip_count <= 0:
        raise RuntimeError(
            f"{case_name} 结果语义异常：新增={new_count} 更新={update_count} 跳过={skip_count} 错误={error_count}"
        )
    if "alert alert-success" not in html:
        raise RuntimeError(f"{case_name} 未渲染 success 提示")
    if expect_auto_suffix and "已自动从模板生成/重建工序" not in html:
        raise RuntimeError(f"{case_name} 未保留 auto_generate_ops 提示后缀")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_excel_result_semantics_")
    test_db = os.path.join(tmpdir, "aps_test.db")
    test_logs = os.path.join(tmpdir, "logs")
    test_backups = os.path.join(tmpdir, "backups")
    test_templates = os.path.join(tmpdir, "templates_excel")
    os.makedirs(test_logs, exist_ok=True)
    os.makedirs(test_backups, exist_ok=True)
    os.makedirs(test_templates, exist_ok=True)

    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = test_db
    os.environ["APS_LOG_DIR"] = test_logs
    os.environ["APS_BACKUP_DIR"] = test_backups
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = test_templates

    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"), backup_dir=None)

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    from core.services.equipment.machine_service import MachineService
    from core.services.personnel.resource_team_service import ResourceTeamService
    from core.services.process.op_type_service import OpTypeService
    from core.services.process.part_service import PartService
    from core.services.process.supplier_service import SupplierService
    from core.services.scheduler.batch_service import BatchService
    from core.services.scheduler.calendar_service import CalendarService

    conn = get_connection(test_db)
    try:
        op_type_svc = OpTypeService(conn)
        team_svc = ResourceTeamService(conn)
        machine_svc = MachineService(conn)
        supplier_svc = SupplierService(conn)
        batch_svc = BatchService(conn)
        calendar_svc = CalendarService(conn)
        part_svc = PartService(conn)

        op_type_svc.create("OT_ROUTE", "数车", "internal")
        op_type_svc.create("OT_SUP", "外协工种", "external")
        op_type_svc.create("OT_WARN", "报警工种", "internal")
        team_svc.create("TM001", "默认班组")
        machine_svc.create("MC_SEM", "已存在设备", op_type_id="OT_ROUTE", team_id="TM001", status="active")
        supplier_svc.create("SUP_SEM", "已存在供应商", op_type_value="OT_SUP", default_days=2.0, status="active")
        part_svc.upsert_and_parse_no_tx("P_ROUTE", "路线语义件", "5数车")
        part_svc.upsert_and_parse_no_tx("P_BATCH", "批次语义件", "5数车")
        part_svc.upsert_and_parse_no_tx("P_HOURS", "工时语义件", "5数车")
        batch_svc.create(batch_id="B_SEM", part_no="P_BATCH", quantity=3, due_date="2026-05-01", priority="normal", ready_status="yes")
        calendar_svc.upsert_no_tx(
            {
                "date": "2026-05-02",
                "day_type": "workday",
                "shift_hours": 8,
                "efficiency": 1.0,
                "allow_normal": "yes",
                "allow_urgent": "yes",
                "remark": "semantics",
            }
        )
        conn.commit()
    finally:
        conn.close()

    # 1) 导出即回灌：UNCHANGED 必须计入 skip_count
    html = _post_export_preview_confirm(
        client,
        export_url="/scheduler/excel/calendar/export",
        preview_url="/scheduler/excel/calendar/preview",
        confirm_url="/scheduler/excel/calendar/confirm",
        filename="calendar.xlsx",
    )
    _assert_skip_semantics("工作日历", html)

    html = _post_export_preview_confirm(
        client,
        export_url="/process/excel/suppliers/export",
        preview_url="/process/excel/suppliers/preview",
        confirm_url="/process/excel/suppliers/confirm",
        filename="suppliers.xlsx",
    )
    _assert_skip_semantics("供应商", html)

    html = _post_export_preview_confirm(
        client,
        export_url="/equipment/excel/machines/export",
        preview_url="/equipment/excel/machines/preview",
        confirm_url="/equipment/excel/machines/confirm",
        filename="machines.xlsx",
    )
    _assert_skip_semantics("设备", html)

    html = _post_export_preview_confirm(
        client,
        export_url="/scheduler/excel/batches/export",
        preview_url="/scheduler/excel/batches/preview",
        confirm_url="/scheduler/excel/batches/confirm",
        filename="batches.xlsx",
        preview_extra={"auto_generate_ops": "1"},
        confirm_extra={"auto_generate_ops": "1"},
    )
    _assert_skip_semantics("批次（显式同态）", html, expect_auto_suffix=True)

    html = _post_export_preview_confirm(
        client,
        export_url="/scheduler/excel/batches/export",
        preview_url="/scheduler/excel/batches/preview",
        confirm_url="/scheduler/excel/batches/confirm",
        filename="batches.xlsx",
        preview_extra={"auto_generate_ops": "1"},
        confirm_hidden_fields=["auto_generate_ops"],
    )
    _assert_skip_semantics("批次（默认UI路径）", html, expect_auto_suffix=True)

    html = _post_export_preview_confirm(
        client,
        export_url="/process/excel/part-operation-hours/export",
        preview_url="/process/excel/part-operation-hours/preview",
        confirm_url="/process/excel/part-operation-hours/confirm",
        filename="part_operation_hours.xlsx",
    )
    _assert_skip_semantics("工序工时", html)

    html = _post_export_preview_confirm(
        client,
        export_url="/process/excel/routes/export",
        preview_url="/process/excel/routes/preview",
        confirm_url="/process/excel/routes/confirm",
        filename="routes.xlsx",
    )
    _assert_skip_semantics("工艺路线", html)

    html = _post_file_preview_confirm(
        client,
        preview_url="/scheduler/excel/calendar/preview",
        confirm_url="/scheduler/excel/calendar/confirm",
        filename="calendar_write_path.xlsx",
        headers=["日期", "类型", "可用工时", "效率", "允许普通件", "允许急件", "说明"],
        rows=[
            {
                "日期": "2026-05-03",
                "类型": "工作日",
                "可用工时": 10,
                "效率": 1.2,
                "允许普通件": "是",
                "允许急件": "是",
                "说明": "calendar-write-path",
            }
        ],
    )
    if "导入完成" not in html or "alert alert-success" not in html:
        raise RuntimeError("工作日历真实写路径未渲染 success 提示")
    conn = get_connection(test_db)
    try:
        row = conn.execute(
            "SELECT date, shift_hours, efficiency, allow_normal, allow_urgent, remark FROM WorkCalendar WHERE date=?",
            ("2026-05-03",),
        ).fetchone()
        if not row:
            raise RuntimeError("工作日历真实写路径未写入 WorkCalendar")
        if abs(float(row["shift_hours"] or 0.0) - 10.0) > 1e-6 or abs(float(row["efficiency"] or 0.0) - 1.2) > 1e-6:
            raise RuntimeError("工作日历真实写路径写入值不正确")
        if str(row["allow_normal"] or "").strip().lower() != "yes" or str(row["allow_urgent"] or "").strip().lower() != "yes":
            raise RuntimeError("工作日历真实写路径未正确写入允许字段")
        if row["remark"] != "calendar-write-path":
            raise RuntimeError("工作日历真实写路径未正确写入说明字段")
    finally:
        conn.close()

    # 2) 页面 warning 语义：error_count > 0 时应展示部分完成 + 错误示例
    import openpyxl

    wb = openpyxl.Workbook()
    try:
        ws = wb.active
        ws.title = "Sheet1"
        ws.append(["工种ID", "工种名称", "归属"])
        ws.append(["OT_NEW", "新工种", "internal"])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
    finally:
        wb.close()

    preview_resp = client.post(
        "/process/excel/op-types/preview",
        data={"mode": "overwrite", "file": (buf, "op_types.xlsx")},
        content_type="multipart/form-data",
    )
    _assert_status("op_types preview", preview_resp, 200)
    preview_html = preview_resp.data.decode("utf-8", errors="ignore")
    raw_rows_json = _extract_raw_rows_json(preview_html)
    preview_baseline = _extract_hidden_input(preview_html, "preview_baseline")

    with patch(
        "web.routes.process_excel_op_types.OpTypeExcelImportService.apply_preview_rows",
        return_value={
            "total_rows": 1,
            "new_count": 0,
            "update_count": 0,
            "skip_count": 0,
            "error_count": 1,
            "errors_sample": [{"row": 2, "message": "模拟部分失败"}],
        },
    ):
        confirm_resp = client.post(
            "/process/excel/op-types/confirm",
            data={
                "mode": "overwrite",
                "filename": "op_types.xlsx",
                "raw_rows_json": raw_rows_json,
                "preview_baseline": preview_baseline,
            },
            follow_redirects=True,
        )

    _assert_status("op_types confirm", confirm_resp, 200)
    warning_html = confirm_resp.data.decode("utf-8", errors="ignore")
    if "导入部分完成" not in warning_html:
        raise RuntimeError("op_types confirm 未展示“导入部分完成”")
    if "错误示例" not in warning_html or "模拟部分失败" not in warning_html:
        raise RuntimeError("op_types confirm 未展示错误示例")
    if "alert alert-warning" not in warning_html:
        raise RuntimeError("op_types confirm 未渲染 warning 提示")

    print("OK")


if __name__ == "__main__":
    main()
