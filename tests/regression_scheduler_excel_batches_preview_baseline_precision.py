from __future__ import annotations

import importlib
import io
import os
import sys
from html.parser import HTMLParser
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCHEMA_PATH = REPO_ROOT / "schema.sql"
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from excel_preview_confirm_helpers import build_confirm_payload, extract_raw_rows_json

_STALE_PREVIEW_MESSAGE = "导入被拒绝：数据已变化，请重新上传 Excel 并检查后再确认写入。"


class _FlashMessageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[tuple[str, str]] = []
        self._category: str | None = None
        self._depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if self._category is None and tag == "div" and attrs_dict.get("data-flash"):
            self._category = str(attrs_dict["data-flash"])
            self._depth = 1
            self._parts = []
            return
        if self._category is not None:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._category is None:
            return
        self._depth -= 1
        if self._depth == 0:
            message = " ".join(" ".join(self._parts).split())
            self.messages.append((self._category, message))
            self._category = None
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._category is not None:
            self._parts.append(data)


def _flash_messages(html: str, category: str) -> list[str]:
    parser = _FlashMessageParser()
    parser.feed(html)
    return [message for flash_category, message in parser.messages if flash_category == category]


def _assert_stale_preview_error(html: str, *, expected: bool) -> None:
    error_messages = _flash_messages(html, "error")
    matched = any(_STALE_PREVIEW_MESSAGE in message for message in error_messages)
    assert matched is expected, error_messages


def _build_app(tmp_path, monkeypatch):
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

    from core.infrastructure.database import ensure_schema

    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app(), str(test_db)


def _make_xlsx_bytes(headers, rows):
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Sheet1"
    ws.append(headers)
    for row in rows:
        ws.append([row.get(header) for header in headers])
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    buf.seek(0)
    return buf


def _preview_batches(client, *, rows, auto_generate_ops: str, strict_mode: str = "no") -> str:
    response = client.post(
        "/scheduler/excel/batches/preview",
        data={
            "mode": "overwrite",
            "auto_generate_ops": auto_generate_ops,
            "strict_mode": strict_mode,
            "file": (
                _make_xlsx_bytes(
                    ["批次号", "图号", "数量", "交期", "优先级", "齐套", "齐套日期", "备注"],
                    rows,
                ),
                "batches.xlsx",
            ),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200, response.get_data(as_text=True)[:500]
    return response.get_data(as_text=True)


def _confirm_batches(client, preview_html: str, *, auto_generate_ops: str, strict_mode: str = "no") -> str:
    payload = build_confirm_payload(
        preview_html,
        mode="overwrite",
        filename="batches.xlsx",
        context="/scheduler/excel/batches/preview",
        confirm_extra={"auto_generate_ops": auto_generate_ops, "strict_mode": strict_mode},
        confirm_hidden_fields=["auto_generate_ops", "strict_mode"],
    )
    response = client.post("/scheduler/excel/batches/confirm", data=payload, follow_redirects=True)
    assert response.status_code == 200, response.get_data(as_text=True)[:500]
    return response.get_data(as_text=True)


def _assert_batch_present(db_path: str, batch_id: str) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT COUNT(1) AS cnt FROM Batches WHERE batch_id=?", (batch_id,)).fetchone()
        assert row is not None and int(row["cnt"] or 0) == 1, dict(row) if row else None
    finally:
        conn.close()


def _assert_batch_absent(db_path: str, batch_id: str) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT COUNT(1) AS cnt FROM Batches WHERE batch_id=?", (batch_id,)).fetchone()
        assert row is not None and int(row["cnt"] or 0) == 0, dict(row) if row else None
    finally:
        conn.close()


def test_scheduler_excel_batches_unrelated_part_change_does_not_force_repreview(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)

    from core.infrastructure.database import get_connection
    from core.services.process.op_type_service import OpTypeService
    from core.services.process.part_service import PartService

    conn = get_connection(db_path)
    try:
        op_type_svc = OpTypeService(conn)
        part_svc = PartService(conn)
        op_type_svc.create("OT_IN", "数车", "internal")
        part_svc.upsert_and_parse_no_tx("P_TARGET", "目标件", "5数车")
        part_svc.upsert_and_parse_no_tx("P_OTHER", "无关件", "5数车")
        conn.commit()
    finally:
        conn.close()

    client = app.test_client()
    preview_html = _preview_batches(
        client,
        rows=[
            {
                "批次号": "B_SCOPE_OK",
                "图号": "P_TARGET",
                "数量": 2,
                "交期": "2026-05-01",
                "优先级": "normal",
                "齐套": "yes",
                "齐套日期": None,
                "备注": "scope-check",
            }
        ],
        auto_generate_ops="0",
    )
    raw_payload = extract_raw_rows_json(preview_html)
    assert raw_payload.startswith("aps-preview-json-b64:")
    assert '"normal"' not in raw_payload
    assert '"yes"' not in raw_payload

    conn = get_connection(db_path)
    try:
        conn.execute("UPDATE Parts SET part_name=? WHERE part_no=?", ("无关件-已改名", "P_OTHER"))
        conn.commit()
    finally:
        conn.close()

    confirm_html = _confirm_batches(client, preview_html, auto_generate_ops="0")

    _assert_stale_preview_error(confirm_html, expected=False)
    _assert_batch_present(db_path, "B_SCOPE_OK")


def test_scheduler_excel_batches_autobuild_supplier_default_days_drift_requires_repreview(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)

    from core.infrastructure.database import get_connection
    from core.services.process.op_type_service import OpTypeService
    from core.services.process.supplier_service import SupplierService

    conn = get_connection(db_path)
    try:
        op_type_svc = OpTypeService(conn)
        supplier_svc = SupplierService(conn)
        op_type_svc.create("OT_EXT", "表处理", "external")
        supplier_svc.create("SUP_EXT", "外协供应商", op_type_value="OT_EXT", default_days=2.0, status="active")
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?, ?, ?, ?, ?)",
            ("P_AUTOBUILD", "待补建件", "10表处理", "no", None),
        )
        conn.commit()
    finally:
        conn.close()

    client = app.test_client()
    preview_html = _preview_batches(
        client,
        rows=[
            {
                "批次号": "B_PARSE_REVIEW",
                "图号": "P_AUTOBUILD",
                "数量": 1,
                "交期": "2026-05-02",
                "优先级": "normal",
                "齐套": "yes",
                "齐套日期": None,
                "备注": "autobuild-review",
            }
        ],
        auto_generate_ops="1",
    )

    conn = get_connection(db_path)
    try:
        SupplierService(conn).update("SUP_EXT", default_days=3.0)
    finally:
        conn.close()

    confirm_html = _confirm_batches(client, preview_html, auto_generate_ops="1")

    _assert_stale_preview_error(confirm_html, expected=True)
    _assert_batch_absent(db_path, "B_PARSE_REVIEW")


def test_scheduler_excel_batches_autobuild_non_effective_supplier_change_does_not_force_repreview(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)

    from core.infrastructure.database import get_connection
    from core.services.process.op_type_service import OpTypeService
    from core.services.process.supplier_service import SupplierService

    conn = get_connection(db_path)
    try:
        op_type_svc = OpTypeService(conn)
        supplier_svc = SupplierService(conn)
        op_type_svc.create("OT_EXT", "表处理", "external")
        supplier_svc.create("SUP_A", "候补供应商", op_type_value="OT_EXT", default_days=2.0, status="active")
        supplier_svc.create("SUP_Z", "最终供应商", op_type_value="OT_EXT", default_days=5.0, status="active")
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?, ?, ?, ?, ?)",
            ("P_AUTOBUILD", "待补建件", "10表处理", "no", None),
        )
        conn.commit()
    finally:
        conn.close()

    client = app.test_client()
    preview_html = _preview_batches(
        client,
        rows=[
            {
                "批次号": "B_PARSE_SECONDARY_OK",
                "图号": "P_AUTOBUILD",
                "数量": 1,
                "交期": "2026-05-02",
                "优先级": "normal",
                "齐套": "yes",
                "齐套日期": None,
                "备注": "autobuild-secondary-supplier",
            }
        ],
        auto_generate_ops="1",
    )

    conn = get_connection(db_path)
    try:
        SupplierService(conn).update("SUP_A", default_days=9.0)
    finally:
        conn.close()

    confirm_html = _confirm_batches(client, preview_html, auto_generate_ops="1")

    _assert_stale_preview_error(confirm_html, expected=False)
    _assert_batch_present(db_path, "B_PARSE_SECONDARY_OK")


def test_scheduler_excel_batches_autobuild_supplier_status_change_requires_repreview(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)

    from core.infrastructure.database import get_connection
    from core.services.process.op_type_service import OpTypeService
    from core.services.process.supplier_service import SupplierService

    conn = get_connection(db_path)
    try:
        op_type_svc = OpTypeService(conn)
        supplier_svc = SupplierService(conn)
        op_type_svc.create("OT_EXT", "表处理", "external")
        supplier_svc.create("SUP_EXT", "外协供应商", op_type_value="OT_EXT", default_days=2.0, status="active")
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?, ?, ?, ?, ?)",
            ("P_AUTOBUILD", "待补建件", "10表处理", "no", None),
        )
        conn.commit()
    finally:
        conn.close()

    client = app.test_client()
    preview_html = _preview_batches(
        client,
        rows=[
            {
                "批次号": "B_PARSE_STATUS_OK",
                "图号": "P_AUTOBUILD",
                "数量": 1,
                "交期": "2026-05-03",
                "优先级": "normal",
                "齐套": "yes",
                "齐套日期": None,
                "备注": "autobuild-status",
            }
        ],
        auto_generate_ops="1",
    )

    conn = get_connection(db_path)
    try:
        SupplierService(conn).update("SUP_EXT", status="inactive")
    finally:
        conn.close()

    confirm_html = _confirm_batches(client, preview_html, auto_generate_ops="1")

    _assert_stale_preview_error(confirm_html, expected=True)
    _assert_batch_absent(db_path, "B_PARSE_STATUS_OK")
