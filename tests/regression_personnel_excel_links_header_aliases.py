from __future__ import annotations

import io
import json
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


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_personnel_link_alias_")
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

    conn = get_connection(test_db)
    try:
        conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "测试员", "active"))
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC001", "设备1", "active"))
        conn.execute("INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)", ("MC002", "设备2", "active"))
        conn.commit()
    finally:
        conn.close()

    import importlib

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    client = app.test_client()

    raw_rows_json = _preview_and_confirm(
        client,
        headers=["操作工号", "机器编号", "技能等级", "主操设备"],
        rows=[{"操作工号": "OP001", "机器编号": "MC001", "技能等级": "expert", "主操设备": "yes"}],
        filename="links_alias.xlsx",
    )
    normalized_rows = json.loads(raw_rows_json)
    if normalized_rows[0].get("工号") != "OP001" or normalized_rows[0].get("设备编号") != "MC001":
        raise RuntimeError(f"alias 表头未被归一化为工号/设备编号：{normalized_rows[0]}")

    _preview_and_confirm(
        client,
        headers=["工号", "设备编号", "技能等级", "主操设备"],
        rows=[{"工号": "OP001", "设备编号": "MC002", "技能等级": "normal", "主操设备": "no"}],
        filename="links_standard.xlsx",
    )

    conn = get_connection(test_db)
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

    print("OK")


if __name__ == "__main__":
    main()
