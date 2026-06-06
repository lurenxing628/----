"""回归测试：/excel-demo/preview 上传守卫——超过 EXCEL_MAX_UPLOAD_BYTES(1MB) 的文件须返回 413 并展示统一中文提示「上传文件超过 1MB」且不泄露内部错误码(7005/错误码)；正常 xlsx 须 200 预览出上传内容并带 preview_baseline 隐藏字段。"""

import io
import re
from html import unescape


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



def test_excel_demo_upload_guard(app_client) -> None:
    app = app_client.application
    app.config["EXCEL_MAX_UPLOAD_BYTES"] = 1 * 1024 * 1024
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
    client = app_client

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
    if "上传文件超过 1MB" not in too_large_body:
        raise RuntimeError(f"超限上传未返回统一大小提示：{too_large_body[:500]}")
    if "7005" in too_large_body or "错误码" in too_large_body:
        raise RuntimeError(f"超限上传 HTML 页面不应显示内部错误码：{too_large_body[:500]}")

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
