"""回归测试：守护批次创建/刷新工序/Excel 批次确认路由把 BatchService 的用户可见告警如实闪现——外协供应商缺失时给出按 1 天安排的 warning；告警超过 3 条时只显示前 3 条并追加「另有 N 条提醒未在当前页显示」当前页文案，不引导去系统历史。"""

from __future__ import annotations

import importlib
import io
import os
import re
import sys
from html import unescape
from pathlib import Path

from tests._support.excel_templates import point_env_at_shared
from tests._support.paths import REPO_ROOT

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
    point_env_at_shared(monkeypatch)

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
            cat == "warning" and "工种“表处理”没有找到可用的外协供应商，本次会先按 1 天安排。建议补好供应商和周期。" in msg
            for cat, msg in flashes
        ), flashes

        batch_row = conn.execute("SELECT COUNT(1) AS cnt FROM Batches WHERE batch_id=?", ("B_WARN",)).fetchone()
        assert batch_row is not None and int(batch_row["cnt"] or 0) == 1
        op_row = conn.execute("SELECT COUNT(1) AS cnt FROM BatchOperations WHERE batch_id=?", ("B_WARN",)).fetchone()
        assert op_row is not None and int(op_row["cnt"] or 0) == 1
    finally:
        conn.close()


def test_scheduler_batch_create_warning_remainder_uses_current_page_copy(tmp_path, monkeypatch) -> None:
    app, conn = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    request_services_mod = importlib.import_module("web.bootstrap.request_services")

    monkeypatch.setattr(
        request_services_mod.BatchService,
        "consume_user_visible_warnings",
        lambda _self: [f"创建提醒 {idx}" for idx in range(1, 6)],
    )

    try:
        resp = client.post(
            "/scheduler/batches/create",
            data={
                "batch_id": "B_WARN_LIMIT",
                "part_no": "P_ROUTE",
                "quantity": "1",
                "priority": "normal",
                "ready_status": "yes",
            },
        )

        assert resp.status_code in (301, 302)
        with client.session_transaction() as sess:
            flashes = list(sess.get("_flashes") or [])

        warning_messages = [msg for cat, msg in flashes if cat == "warning"]
        assert warning_messages[:3] == ["创建提醒 1", "创建提醒 2", "创建提醒 3"]
        assert "另有 2 条提醒未在当前页显示，请处理已展示提醒后重新检查。" in warning_messages
        assert not any("请到系统历史查看" in msg for msg in warning_messages)
    finally:
        conn.close()


def test_scheduler_batch_generate_ops_warning_remainder_uses_current_page_copy(tmp_path, monkeypatch) -> None:
    app, conn = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    request_services_mod = importlib.import_module("web.bootstrap.request_services")

    try:
        create_resp = client.post(
            "/scheduler/batches/create",
            data={
                "batch_id": "B_WARN_REFRESH_LIMIT",
                "part_no": "P_ROUTE",
                "quantity": "1",
                "priority": "normal",
                "ready_status": "yes",
            },
        )
        assert create_resp.status_code in (301, 302)
        with client.session_transaction() as sess:
            sess.pop("_flashes", None)

        monkeypatch.setattr(
            request_services_mod.BatchService,
            "consume_user_visible_warnings",
            lambda _self: [f"刷新提醒 {idx}" for idx in range(1, 6)],
        )

        refresh_resp = client.post("/scheduler/batches/B_WARN_REFRESH_LIMIT/generate-ops")

        assert refresh_resp.status_code in (301, 302)
        with client.session_transaction() as sess:
            flashes = list(sess.get("_flashes") or [])

        assert any("已刷新本批次工序：共" in msg for _cat, msg in flashes), flashes
        warning_messages = [msg for cat, msg in flashes if cat == "warning"]
        assert warning_messages[:3] == ["刷新提醒 1", "刷新提醒 2", "刷新提醒 3"]
        assert "另有 2 条提醒未在当前页显示，请处理已展示提醒后重新检查。" in warning_messages
        assert "刷新提醒 4" not in warning_messages
        assert "刷新提醒 5" not in warning_messages
        assert not any("系统历史" in msg for msg in warning_messages)
    finally:
        conn.close()


def test_scheduler_excel_batch_confirm_surfaces_warnings_with_limit(tmp_path, monkeypatch) -> None:
    app, conn = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    request_services_mod = importlib.import_module("web.bootstrap.request_services")

    monkeypatch.setattr(
        request_services_mod.BatchService,
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
        )

        assert confirm_resp.status_code in (301, 302)
        with client.session_transaction() as sess:
            flashes = list(sess.get("_flashes") or [])

        assert any("已按模板自动生成批次工序" in msg for _cat, msg in flashes), flashes
        warning_messages = [msg for cat, msg in flashes if cat == "warning"]
        assert "第 1 条告警" in warning_messages
        assert "第 2 条告警" in warning_messages
        assert "第 3 条告警" in warning_messages
        assert "另有 2 条提醒未在当前页显示，请处理已展示提醒后重新检查。" in warning_messages
        assert "第 4 条告警" not in warning_messages
        assert "第 5 条告警" not in warning_messages
        assert not any("请到系统历史查看" in msg for msg in warning_messages)
    finally:
        conn.close()
