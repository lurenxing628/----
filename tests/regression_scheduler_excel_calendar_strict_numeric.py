"""回归测试：工作日历 Excel preview 路由严格拒绝 bool / NaN / Inf 数值。

验证 scheduler_excel_calendar.py 的 validate_row 闭包通过 parse_finite_float
正确拒绝布尔值（True/False）和非有限浮点数（NaN/Inf）作为"可用工时"/"效率"。
"""

import importlib
import io
import os
import re
import sys
import tempfile


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
    assert ws is not None
    ws.title = "日历导入"
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h) for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    buf.seek(0)
    return buf


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_calendar_strict_numeric_")
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

    from core.services.scheduler.config_service import ConfigService

    conn = get_connection(test_db)
    try:
        ConfigService(conn).set_holiday_default_efficiency(0.6)
    finally:
        conn.close()

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    headers = ["日期", "类型", "可用工时", "效率", "允许普通件", "允许急件", "说明"]
    base = {"类型": "workday", "允许普通件": "yes", "允许急件": "yes", "说明": ""}

    rows = [
        {**base, "日期": "2026-05-01", "可用工时": True, "效率": 1.0},        # bool -> 拒绝
        {**base, "日期": "2026-05-02", "可用工时": 8, "效率": "NaN"},           # 字符串 NaN -> float("nan") -> isfinite 拒绝
        {**base, "日期": "2026-05-03", "可用工时": "Infinity", "效率": 1.0},    # 字符串 Inf -> float("inf") -> isfinite 拒绝
        {**base, "日期": "2026-05-04", "可用工时": 8, "效率": 1.0},             # 正常行
    ]

    preview_resp = client.post(
        "/scheduler/excel/calendar/preview",
        data={
            "mode": "overwrite",
            "file": (_make_xlsx_bytes(headers, rows), "calendar.xlsx"),
        },
        content_type="multipart/form-data",
    )
    assert preview_resp.status_code == 200, (
        f"preview 返回 {preview_resp.status_code}，期望 200"
    )

    html = preview_resp.data.decode("utf-8", errors="ignore")

    # 统计错误行数：badge-error 出现次数
    error_badges = re.findall(r'badge-error', html)
    assert len(error_badges) == 3, (
        f"应有 3 个错误行（bool/NaN/Inf），实际 badge-error 出现 {len(error_badges)} 次"
    )

    # 验证错误信息包含 "必须是数字" 或 "必须是有限数字"
    assert "必须是数字" in html, "布尔值应触发 '必须是数字' 错误"
    assert "必须是有限数字" in html, "NaN/Inf 应触发 '必须是有限数字' 错误"

    # 验证正常行存在（第 4 行应为 new 或 update，不是 error）
    assert "badge-new" in html or "badge-update" in html, (
        "第 4 行（正常数据）应为新增或更新状态"
    )

    print("OK")


if __name__ == "__main__":
    main()
