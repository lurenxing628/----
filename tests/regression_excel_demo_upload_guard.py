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



def _make_xlsx_bytes(headers, rows) -> bytes:
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
    return buf.getvalue()



def _extract_hidden_input(html: str, name: str) -> str:
    for match in re.finditer(r"<input[^>]+>", html, re.I):
        tag = match.group(0)
        if re.search(rf'name="{re.escape(name)}"', tag):
            value_match = re.search(r'value="([^"]*)"', tag)
            return unescape(value_match.group(1)).strip() if value_match else ""
    raise RuntimeError(f"未能从页面提取隐藏字段：{name}")



def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_excel_demo_upload_guard_")
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

    from core.infrastructure.database import ensure_schema
    from core.infrastructure.errors import ErrorCode

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"), backup_dir=None)

    import importlib

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    app.config["EXCEL_MAX_UPLOAD_BYTES"] = 1 * 1024 * 1024
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
    client = app.test_client()

    too_large_resp = client.post(
        "/excel-demo/preview",
        data={
            "mode": "overwrite",
            "file": (io.BytesIO(b"x" * (app.config["EXCEL_MAX_UPLOAD_BYTES"] + 1)), "too-large.xlsx"),
        },
        content_type="multipart/form-data",
    )
    too_large_body = too_large_resp.get_data(as_text=True)
    if too_large_resp.status_code != 413:
        raise RuntimeError(f"超限上传返回码异常：{too_large_resp.status_code} body={too_large_body[:500]}")
    if ErrorCode.FILE_TOO_LARGE.value not in too_large_body:
        raise RuntimeError(f"超限上传未返回统一 FILE_TOO_LARGE 错误：{too_large_body[:500]}")
    if "上传文件超过 1MB" not in too_large_body:
        raise RuntimeError(f"超限上传未返回统一大小提示：{too_large_body[:500]}")

    normal_bytes = _make_xlsx_bytes(
        ["工号", "姓名", "状态", "班组", "备注"],
        [{"工号": "OP001", "姓名": "张三", "状态": "在岗", "班组": None, "备注": "demo"}],
    )
    preview_resp = client.post(
        "/excel-demo/preview",
        data={
            "mode": "overwrite",
            "file": (io.BytesIO(normal_bytes), "demo.xlsx"),
        },
        content_type="multipart/form-data",
    )
    preview_html = preview_resp.get_data(as_text=True)
    if preview_resp.status_code != 200:
        raise RuntimeError(f"正常预览失败：{preview_resp.status_code} body={preview_html[:500]}")
    if "OP001" not in preview_html:
        raise RuntimeError("正常文件预览未展示上传内容")
    if not _extract_hidden_input(preview_html, "preview_baseline"):
        raise RuntimeError("正常文件预览缺少 preview_baseline")

    print("OK")


if __name__ == "__main__":
    main()
