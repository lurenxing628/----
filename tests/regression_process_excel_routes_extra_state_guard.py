import io
import os
import re
import sys
import tempfile
from html import unescape


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _make_xlsx_bytes(headers, rows):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    if ws is None:
        raise RuntimeError("openpyxl Workbook.active 不应为空")
    ws.title = "Sheet1"
    ws.append(headers)
    for row in rows:
        ws.append([row.get(header) for header in headers])
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    buf.seek(0)
    return buf


def _extract_raw_rows_json(html: str) -> str:
    match = re.search(r'<textarea name="raw_rows_json"[^>]*>(.*?)</textarea>', html, re.S)
    if not match:
        raise RuntimeError("未能从页面提取 raw_rows_json")
    return unescape(match.group(1)).strip()



def _extract_hidden_input(html: str, name: str) -> str:
    for match in re.finditer(r"<input[^>]+>", html, re.I):
        tag = match.group(0)
        if re.search(rf'name="{re.escape(name)}"', tag):
            value_match = re.search(r'value="([^"]*)"', tag)
            return unescape(value_match.group(1)).strip() if value_match else ""
    raise RuntimeError(f"未能从页面提取隐藏字段：{name}")



def _assert_status(name: str, resp, expect_code: int = 200) -> None:
    if resp.status_code != expect_code:
        body = ""
        try:
            body = resp.data.decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect_code}；body={body[:500]}")



def _preview_routes(client, *, part_no: str, part_name: str, route_raw: str, strict_mode: str) -> dict:
    resp = client.post(
        "/process/excel/routes/preview",
        data={
            "mode": "overwrite",
            "strict_mode": strict_mode,
            "file": (
                _make_xlsx_bytes(
                    ["图号", "名称", "工艺路线字符串"],
                    [{"图号": part_no, "名称": part_name, "工艺路线字符串": route_raw}],
                ),
                f"{part_no}.xlsx",
            ),
        },
        content_type="multipart/form-data",
    )
    _assert_status(f"{part_no} preview", resp, 200)
    html = resp.data.decode("utf-8", errors="ignore")
    return {
        "raw_rows_json": _extract_raw_rows_json(html),
        "preview_baseline": _extract_hidden_input(html, "preview_baseline"),
    }



def _confirm_routes(client, *, part_no: str, preview: dict, strict_mode: str) -> str:
    resp = client.post(
        "/process/excel/routes/confirm",
        data={
            "mode": "overwrite",
            "filename": f"{part_no}.xlsx",
            "raw_rows_json": preview["raw_rows_json"],
            "preview_baseline": preview["preview_baseline"],
            "strict_mode": strict_mode,
        },
        follow_redirects=True,
    )
    _assert_status(f"{part_no} confirm", resp, 200)
    return resp.data.decode("utf-8", errors="ignore")



def _assert_need_repreview(case_name: str, html: str) -> None:
    if "需重新预览" not in html:
        raise RuntimeError(f"{case_name} 未提示“需重新预览”")


def _assert_no_repreview(case_name: str, html: str) -> None:
    if "需重新预览" in html:
        raise RuntimeError(f"{case_name} 不应提示“需重新预览”")



def _assert_part_absent(test_db: str, part_no: str, case_name: str) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(test_db)
    try:
        row = conn.execute("SELECT COUNT(1) AS cnt FROM Parts WHERE part_no=?", (part_no,)).fetchone()
        if row is None or int(row["cnt"] or 0) != 0:
            raise RuntimeError(f"{case_name} 被拦截后不应写入 Parts：{dict(row) if row else None!r}")
    finally:
        conn.close()


def _assert_part_present(test_db: str, part_no: str, case_name: str) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(test_db)
    try:
        row = conn.execute("SELECT COUNT(1) AS cnt FROM Parts WHERE part_no=?", (part_no,)).fetchone()
        if row is None or int(row["cnt"] or 0) != 1:
            raise RuntimeError(f"{case_name} 应成功写入 Parts：{dict(row) if row else None!r}")
    finally:
        conn.close()



def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_process_routes_guard_")
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

    import importlib

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    from core.services.process.op_type_service import OpTypeService
    from core.services.process.supplier_service import SupplierService

    conn = get_connection(test_db)
    try:
        op_type_svc = OpTypeService(conn)
        supplier_svc = SupplierService(conn)

        op_type_svc.create("OT_STRICT", "表处理", "external")
        supplier_svc.create("SUP_STRICT", "严格模式供应商", op_type_value="OT_STRICT", default_days=2.0, status="active")

        op_type_svc.create("OT_RENAME", "喷砂", "external")
        supplier_svc.create("SUP_RENAME", "改名供应商", op_type_value="OT_RENAME", default_days=2.5, status="active")

        op_type_svc.create("OT_DAYS", "热处理", "external")
        supplier_svc.create("SUP_DAYS", "默认周期供应商", op_type_value="OT_DAYS", default_days=2.0, status="active")

        op_type_svc.create("OT_STATUS", "电镀", "external")
        supplier_svc.create("SUP_STATUS", "状态变化供应商", op_type_value="OT_STATUS", default_days=1.5, status="active")
    finally:
        conn.close()

    preview = _preview_routes(client, part_no="P_STRICT_GUARD", part_name="严格模式件", route_raw="5表处理", strict_mode="yes")
    html = _confirm_routes(client, part_no="P_STRICT_GUARD", preview=preview, strict_mode="no")
    _assert_need_repreview("strict_mode 漂移", html)
    _assert_part_absent(test_db, "P_STRICT_GUARD", "strict_mode 漂移")

    preview = _preview_routes(client, part_no="P_OPTYPE_GUARD", part_name="工种漂移件", route_raw="5喷砂", strict_mode="no")
    conn = get_connection(test_db)
    try:
        OpTypeService(conn).update("OT_RENAME", name="喷砂改名")
    finally:
        conn.close()
    html = _confirm_routes(client, part_no="P_OPTYPE_GUARD", preview=preview, strict_mode="no")
    _assert_need_repreview("工种配置漂移", html)
    _assert_part_absent(test_db, "P_OPTYPE_GUARD", "工种配置漂移")

    preview = _preview_routes(client, part_no="P_SUPPLIER_STATUS_GUARD", part_name="供应商状态漂移件", route_raw="5电镀", strict_mode="no")
    conn = get_connection(test_db)
    try:
        SupplierService(conn).update("SUP_STATUS", status="inactive")
    finally:
        conn.close()
    html = _confirm_routes(client, part_no="P_SUPPLIER_STATUS_GUARD", preview=preview, strict_mode="no")
    _assert_need_repreview("供应商状态变化", html)
    _assert_part_absent(test_db, "P_SUPPLIER_STATUS_GUARD", "供应商状态变化")

    preview = _preview_routes(client, part_no="P_SUPPLIER_GUARD", part_name="供应商漂移件", route_raw="5热处理", strict_mode="no")
    conn = get_connection(test_db)
    try:
        SupplierService(conn).update("SUP_DAYS", default_days=3.0)
    finally:
        conn.close()
    html = _confirm_routes(client, part_no="P_SUPPLIER_GUARD", preview=preview, strict_mode="no")
    _assert_need_repreview("供应商默认周期漂移", html)
    _assert_part_absent(test_db, "P_SUPPLIER_GUARD", "供应商默认周期漂移")

    print("OK")


if __name__ == "__main__":
    main()
