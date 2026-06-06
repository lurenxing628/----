"""回归测试：人员-设备关联 Excel 导入（/personnel/excel/links 的 preview→confirm 全链路），别名表头「操作工号/机器编号」与标准表头「工号/设备编号」都被归一化、preview 用 aps-preview-json-b64 编码不退回明文 JSON，confirm 后正确写入 OperatorMachine 的 skill_level 与 is_primary。"""

from __future__ import annotations

import io
import json
import re
from base64 import urlsafe_b64decode

from core.infrastructure.database import get_connection


def _make_xlsx_bytes(headers, rows):
    import openpyxl

    wb = openpyxl.Workbook()
    try:
        ws = wb.active
        assert ws is not None

        ws.title = "Sheet1"
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h) for h in headers])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf
    finally:
        try:
            wb.close()
        except Exception:
            pass


def _extract_raw_rows_json(html: str) -> str:
    m = re.search(r'<textarea name="raw_rows_json"[^>]*>(.*?)</textarea>', html, re.S)
    if not m:
        raise RuntimeError("未能从页面提取 raw_rows_json")
    return m.group(1).replace("&quot;", '"').replace("&#34;", '"').replace("&amp;", "&").strip()


def _extract_hidden_input(html: str, name: str) -> str:
    for m in re.finditer(r"<input[^>]+>", html, re.I):
        tag = m.group(0)
        if re.search(rf'name="{re.escape(name)}"', tag):
            vm = re.search(r'value="([^"]*)"', tag)
            value = vm.group(1) if vm else ""
            return value.replace("&quot;", '"').replace("&#34;", '"').replace("&amp;", "&").strip()
    return ""


def _decode_preview_rows_payload(raw_rows_json: str) -> str:
    prefix = "aps-preview-json-b64:"
    if not raw_rows_json.startswith(prefix):
        raise RuntimeError("raw_rows_json 必须使用 aps-preview-json-b64 编码，不能退回明文 JSON")
    return urlsafe_b64decode(raw_rows_json[len(prefix) :].encode("ascii")).decode("utf-8")


def _assert_status(name: str, resp, expect_code: int = 200):
    if resp.status_code != expect_code:
        body = ""
        try:
            body = resp.data.decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect_code}；body={body[:500]}")


def _preview_and_confirm(client, *, headers, rows, filename: str):
    preview_resp = client.post(
        "/personnel/excel/links/preview",
        data={"mode": "overwrite", "file": (_make_xlsx_bytes(headers, rows), filename)},
        content_type="multipart/form-data",
    )
    _assert_status("personnel links preview", preview_resp, 200)
    preview_html = preview_resp.data.decode("utf-8", errors="ignore")
    raw_rows_json = _extract_raw_rows_json(preview_html)
    preview_baseline = _extract_hidden_input(preview_html, "preview_baseline")
    if not preview_baseline:
        raise RuntimeError("人员设备关联预览缺少 preview_baseline")
    confirm_resp = client.post(
        "/personnel/excel/links/confirm",
        data={
            "mode": "overwrite",
            "filename": filename,
            "raw_rows_json": raw_rows_json,
            "preview_baseline": preview_baseline,
        },
        follow_redirects=True,
    )
    _assert_status("personnel links confirm", confirm_resp, 200)
    return raw_rows_json


def test_personnel_excel_links_header_aliases(app_client, db_path) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "测试员", "active"))
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC001", "设备1", "active"))
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC002", "设备2", "active"))
        conn.commit()
    finally:
        conn.close()

    raw_rows_json = _preview_and_confirm(
        app_client,
        headers=["操作工号", "机器编号", "技能等级", "主操设备"],
        rows=[{"操作工号": "OP001", "机器编号": "MC001", "技能等级": "expert", "主操设备": "yes"}],
        filename="links_alias.xlsx",
    )
    normalized_rows = json.loads(_decode_preview_rows_payload(raw_rows_json))
    if normalized_rows[0].get("工号") != "OP001" or normalized_rows[0].get("设备编号") != "MC001":
        raise RuntimeError(f"alias 表头未被归一化为工号/设备编号：{normalized_rows[0]}")

    _preview_and_confirm(
        app_client,
        headers=["工号", "设备编号", "技能等级", "主操设备"],
        rows=[{"工号": "OP001", "设备编号": "MC002", "技能等级": "normal", "主操设备": "no"}],
        filename="links_standard.xlsx",
    )

    conn = get_connection(db_path)
    try:
        row1 = conn.execute(
            "SELECT operator_id, machine_id, skill_level, is_primary FROM OperatorMachine WHERE operator_id=? AND machine_id=?",
            ("OP001", "MC001"),
        ).fetchone()
        if not row1:
            raise RuntimeError("alias 表头导入后未写入 OP001-MC001 关联")
        if row1["skill_level"] != "expert" or row1["is_primary"] != "yes":
            raise RuntimeError(f"alias 表头导入字段值异常：{dict(row1)}")

        row2 = conn.execute(
            "SELECT operator_id, machine_id, skill_level, is_primary FROM OperatorMachine WHERE operator_id=? AND machine_id=?",
            ("OP001", "MC002"),
        ).fetchone()
        if not row2:
            raise RuntimeError("标准表头导入后未写入 OP001-MC002 关联")
        if row2["skill_level"] != "normal" or row2["is_primary"] != "no":
            raise RuntimeError(f"标准表头导入字段值异常：{dict(row2)}")
    finally:
        conn.close()
