from __future__ import annotations

import importlib
import io
import os
import re
import sys
from html import unescape
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _make_xlsx_bytes(headers, rows):
    import openpyxl

    wb = openpyxl.Workbook()
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


def _build_app(tmp_path, monkeypatch):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_templates = tmp_path / "templates_excel"
    test_logs.mkdir(parents=True, exist_ok=True)
    test_backups.mkdir(parents=True, exist_ok=True)
    test_templates.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(test_templates))

    from core.infrastructure.database import ensure_schema, get_connection

    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    conn = get_connection(str(test_db))
    conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_EXT", "表处理", "external"))
    conn.execute(
        "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?, ?, ?, ?, ?)",
        ("P_ROUTE", "路线件", "10表处理", "no", None),
    )
    conn.commit()

    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app(), conn


def test_scheduler_batch_template_warning_surface(tmp_path, monkeypatch) -> None:
    app, conn = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    try:
        resp = client.post(
            "/scheduler/batches/create",
            data={
                "batch_id": "B_WARN",
                "part_no": "P_ROUTE",
                "quantity": "1",
                "priority": "normal",
                "ready_status": "yes",
            },
        )

        assert resp.status_code in (301, 302)
        with client.session_transaction() as sess:
            flashes = list(sess.get("_flashes") or [])

        assert any(cat == "success" and "已创建批次并生成工序：B_WARN" in msg for cat, msg in flashes), flashes
        assert any(
            cat == "warning" and "工种“表处理”未找到供应商配置，已按默认 1.0 天初始化外协周期" in msg
            for cat, msg in flashes
        ), flashes

        batch_row = conn.execute("SELECT COUNT(1) AS cnt FROM Batches WHERE batch_id=?", ("B_WARN",)).fetchone()
        assert batch_row is not None and int(batch_row["cnt"] or 0) == 1
        op_row = conn.execute("SELECT COUNT(1) AS cnt FROM BatchOperations WHERE batch_id=?", ("B_WARN",)).fetchone()
        assert op_row is not None and int(op_row["cnt"] or 0) == 1
    finally:
        conn.close()


def test_scheduler_excel_batch_confirm_surfaces_warnings_with_limit(tmp_path, monkeypatch) -> None:
    app, conn = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    route_mod = importlib.import_module("web.routes.scheduler_excel_batches")

    monkeypatch.setattr(
        route_mod.BatchService,
        "consume_user_visible_warnings",
        lambda _self: [
            "第 1 条告警",
            "第 2 条告警",
            "",
            "第 2 条告警",
            "第 3 条告警",
            "第 4 条告警",
            "第 5 条告警",
        ],
    )

    try:
        preview_resp = client.post(
            "/scheduler/excel/batches/preview",
            data={
                "mode": "overwrite",
                "auto_generate_ops": "1",
                "file": (
                    _make_xlsx_bytes(
                        ["批次号", "图号", "数量", "交期", "优先级", "齐套", "齐套日期", "备注"],
                        [{"批次号": "B_WARN_XLSX", "图号": "P_ROUTE", "数量": 1, "交期": "2026-05-01", "优先级": "normal", "齐套": "yes", "齐套日期": None, "备注": "xlsx-warning"}],
                    ),
                    "batches.xlsx",
                ),
            },
            content_type="multipart/form-data",
        )
        assert preview_resp.status_code == 200
        preview_html = preview_resp.get_data(as_text=True)
        raw_rows_json = _extract_raw_rows_json(preview_html)
        preview_baseline = _extract_hidden_input(preview_html, "preview_baseline")
        assert preview_baseline

        confirm_resp = client.post(
            "/scheduler/excel/batches/confirm",
            data={
                "mode": "overwrite",
                "filename": "batches.xlsx",
                "raw_rows_json": raw_rows_json,
                "preview_baseline": preview_baseline,
                "auto_generate_ops": "1",
            },
            follow_redirects=True,
        )

        body = confirm_resp.get_data(as_text=True)
        assert confirm_resp.status_code == 200
        assert "已自动从模板生成/重建工序" in body
        assert "第 1 条告警" in body
        assert "第 2 条告警" in body
        assert "第 3 条告警" in body
        assert "另有 2 条告警，请到系统历史查看。" in body
        assert "第 4 条告警" not in body
        assert "第 5 条告警" not in body
    finally:
        conn.close()
