"""Retired editor bindings, current explicit controls, and retained legacy POST confirmation values."""

from __future__ import annotations

import io
import json
from contextlib import closing
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode, urlsplit

from jinja2 import Environment, FileSystemLoader, select_autoescape

from tests._support.excel_templates import point_env_at_shared
from tests._support.gantt_retirement import _Boot
from tests._support.paths import REPO_ROOT


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _render_excel_import_component(strict_mode=True) -> str:
    env = Environment(loader=FileSystemLoader(str(REPO_ROOT / "templates")),
                      autoescape=select_autoescape(("html", "xml")))
    env.globals["get_flashed_messages"] = lambda **kwargs: []
    env.globals["request"] = SimpleNamespace(endpoint="scheduler.excel_batches_preview")
    env.filters["legacy_preview_fields"] = lambda row, endpoint: []
    row = SimpleNamespace(status=SimpleNamespace(value="new"), row_num=1, message="可确认")
    return env.get_template("workbench/legacy_result.html").render(
        title="原导入预检", filename="geometry.xlsx", mode="overwrite", confirm_url="/confirm",
        strict_mode_supported=True, strict_mode=strict_mode, auto_generate_ops=True,
        preview_rows=[row], raw_rows_json='[{"批次号":"B_RENDER"}]', preview_baseline="fixed-original-preview",
    )


def _build_app(tmp_path, monkeypatch):
    root = Path(tmp_path).resolve()
    test_db = root / "aps_test.db"
    for name in ("logs", "backups", "journal"):
        (root / name).mkdir(exist_ok=True)
    for key, value in {"APS_ENV": "development", "APS_DB_PATH": str(test_db), "APS_LOG_DIR": str(root / "logs"),
                       "APS_BACKUP_DIR": str(root / "backups"), "APS_SYSTEM_JOURNAL_DIR": str(root / "journal")}.items():
        monkeypatch.setenv(key, value)
    point_env_at_shared(monkeypatch)
    from core.infrastructure.database import ensure_schema
    from web.bootstrap.entrypoint import create_app_with_mode

    ensure_schema(str(test_db), logger=None, schema_path=str(REPO_ROOT / "schema.sql"), backup_dir=None)
    _seed_strict_mode_render_data(str(test_db))
    return create_app_with_mode("default"), str(test_db)


def _close_app(app):
    gate = app.extensions["workbench_request_lifecycle"]
    assert gate.shutdown(timeout=20), "Form contract fixture did not drain"


def _with_db(db_path: str):
    from core.infrastructure.database import get_connection

    return get_connection(db_path)


def _seed_strict_mode_render_data(db_path: str) -> None:
    conn = _with_db(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO Parts (part_no, part_name, route_raw, route_parsed) VALUES (?, ?, ?, ?)",
            ("P_RENDER", "渲染测试零件", "10表处理20总检", "no"),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO ExternalGroups
                (group_id, part_no, start_seq, end_seq, merge_mode, total_days)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("G_RENDER", "P_RENDER", 10, 20, "separate", 2),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO Batches
                (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_RENDER", "P_RENDER", "渲染测试零件", 1, "2026-05-01", "normal", "yes", "pending"),
        )
        conn.commit()
    finally:
        conn.close()


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
    wb.close()
    buf.seek(0)
    return buf



def _html(response) -> str:
    try:
        assert response.status_code == 200
        return response.get_data(as_text=True)
    finally:
        response.close()


def _business_rows(db_path):
    with closing(_with_db(db_path)) as conn:
        return {table: [tuple(row) for row in conn.execute("SELECT * FROM " + table + " ORDER BY rowid")]
                for table in ("Parts", "ExternalGroups", "Batches", "BatchOperations", "ScheduleConfig", "ScheduleHistory")}


def _canonical_boot(client, original_path, view):
    response = client.get(original_path, follow_redirects=False)
    try:
        assert response.status_code == 302, response.get_data(as_text=True)
        location = response.headers["Location"]
        target = urlsplit(location)
        assert target.path == "/workbench" and not target.scheme and not target.netloc
    finally:
        response.close()
    html = _html(client.get(location, follow_redirects=False))
    parser = _Boot()
    parser.feed(html)
    boot = json.loads("".join(parser.parts))
    assert boot["schema_version"] == 1 and boot["view"] == view
    assert boot["navigation"]["version"] == 1 and boot["navigation"]["view"] == view
    assert 'data-workbench-boot="loading"' in html
    return boot["navigation"]["context"]


def _retired_list_and_current_boot(client, original_path, view):
    response = client.get(original_path, follow_redirects=False)
    try:
        assert response.status_code == 410
        html = response.get_data(as_text=True)
        assert "新入口不能等价表达这组旧条件" in html
        assert "原业务数据、保存的配置和历史记录仍保留" in html
    finally:
        response.close()
    # This is an explicit new workspace visit, not an equivalent old-filter redirect.
    context = {"source": "production"} if view == "process" else {}
    navigation = {"version": 1, "view": view, "context": context}
    query = urlencode({"view": view, "nav": json.dumps(navigation)})
    html = _html(client.get("/workbench?" + query, follow_redirects=False))
    parser = _Boot()
    parser.feed(html)
    boot = json.loads("".join(parser.parts))
    assert boot["view"] == view and boot["navigation"] == navigation
    assert 'data-workbench-boot="loading"' in html


class _FormSignals(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.inputs, self.forms, self.definition_pairs = [], [], []
        self._definition, self._parts, self._label = None, [], None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "input":
            self.inputs.append(values)
        if tag == "form":
            self.forms.append(values)
        if tag in ("dt", "dd"):
            self._definition, self._parts = tag, []

    def handle_data(self, data):
        if self._definition:
            self._parts.append(data)

    def handle_endtag(self, tag):
        if tag != self._definition:
            return
        text = "".join(self._parts).strip()
        if tag == "dt":
            self._label = text
        else:
            self.definition_pairs.append((self._label, text))
        self._definition = None


def _assert_readonly_strict_parameter(html, value):
    parsed = _FormSignals()
    parsed.feed(html)
    strict = [field for field in parsed.inputs if field.get("name") == "strict_mode"]
    assert strict == [{"type": "hidden", "name": "strict_mode", "value": value}]
    assert ("发现问题就停止", "是" if value == "yes" else "否") in parsed.definition_pairs
    confirmations = [field for field in parsed.inputs if field.get("type") == "checkbox"]
    assert confirmations and all("required" in field and "name" not in field for field in confirmations)
    assert len(parsed.forms) == 1 and parsed.forms[0]["method"] == "post"
    assert parsed.forms[0]["data-legacy-confirmation"] == "true"
    assert all(field.get("type") == "hidden" for field in strict)


def test_excel_import_component_renders_strict_mode_toggle_fields() -> None:
    for value, flag in (("yes", True), ("no", False)):
        html = _render_excel_import_component(flag)
        _assert_readonly_strict_parameter(html, value)
        assert 'name="preview_baseline" value="fixed-original-preview"' in html
        assert 'name="raw_rows_json" hidden' in html
    current = _read("frontend/workbench/app/BatchFiles.jsx")
    assert "新建批次不自动生成工序" in current
    assert "adapter.importPreview(file, mode, scope, snapshot)" in current
    assert "strict_mode" not in current


def test_process_pages_render_strict_mode_toggle_fields(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _seed_strict_mode_render_data(db_path)
    try:
        before = _business_rows(db_path)
        client = app.test_client()
        _retired_list_and_current_boot(client, "/process/", "process")
        context = _canonical_boot(client, "/process/parts/P_RENDER", "process")
        assert context["source"] == "production" and context["kind"] == "part"
        detail = client.get("/api/workbench/v1/entities/part/" + context["entity_ref"])
        try:
            assert detail.status_code == 200 and detail.get_json()["data"]["business_code"] == "P_RENDER"
        finally:
            detail.close()
        current = _read("frontend/workbench/app/ProcessCollectionActions.jsx")
        assert "这里只登记零件和路线原文，不会自动确认工艺。" in current
        assert "processCreateStrictMode" not in current
        assert _business_rows(db_path) == before
    finally:
        _close_app(app)


def test_scheduler_batch_pages_render_strict_mode_toggle_fields(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _seed_strict_mode_render_data(db_path)
    try:
        before = _business_rows(db_path)
        client = app.test_client()
        _retired_list_and_current_boot(client, "/scheduler/batches", "batches")
        context = _canonical_boot(client, "/scheduler/batches/B_RENDER", "batches")
        response = client.get("/api/workbench/v1/entities/batch/" + context["entity_ref"])
        try:
            assert response.status_code == 200 and response.get_json()["data"]["business_code"] == "B_RENDER"
        finally:
            response.close()
        detail = _read("frontend/workbench/app/BatchDetail.jsx")
        workspace = _read("frontend/workbench/app/BatchWorkspace.jsx")
        assert 'type="checkbox" checked={strict}' in detail
        assert "onChange={event => setStrict(event.target.checked)}" in detail
        assert "资料不完整时停止刷新" in detail
        assert "preview('sync', { strict_mode: strict }, entity, snapshot)" in workspace
        assert _business_rows(db_path) == before
    finally:
        _close_app(app)


def test_process_excel_page_renders_strict_mode_toggle_fields(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    try:
        before = _business_rows(_db_path)
        _retired_list_and_current_boot(app.test_client(), "/process/excel/routes", "process")
        current = _read("frontend/workbench/app/ProcessFileActions.jsx")
        assert "checked={ack}" in current and "onChange={event => setAck(event.target.checked)}" in current
        assert "已核对全部修改前后内容，确认这些更新。" in current
        assert "本批整体确认；任何一行不能提交，本批全部不修改。" in current
        assert "body.append('mode', 'upsert')" in current and "strict_mode" not in current
        assert _business_rows(_db_path) == before
    finally:
        _close_app(app)


def test_batch_excel_confirm_page_uses_hidden_strict_mode_and_readonly_display(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    _seed_strict_mode_render_data(db_path)
    try:
        before = _business_rows(db_path)
        preview_response = app.test_client().post(
            "/scheduler/excel/batches/preview",
            data={
                "mode": "overwrite", "auto_generate_ops": "1", "strict_mode": "yes",
                "file": (_make_xlsx_bytes(
                    ["批次号", "图号", "数量", "交期", "优先级", "齐套", "齐套日期", "备注"],
                    [{"批次号": "B_RENDER_EXCEL", "图号": "P_RENDER", "数量": 2, "交期": "2026-05-10",
                      "优先级": "normal", "齐套": "yes", "齐套日期": None, "备注": "strict-mode-render"}],
                ), "batches.xlsx"),
            },
            content_type="multipart/form-data",
        )
        html = _html(preview_response)
        _assert_readonly_strict_parameter(html, "yes")
        assert 'name="auto_generate_ops" value="1"' in html
        assert 'name="preview_baseline"' in html and 'name="raw_rows_json" hidden' in html
        assert "确认后会按模板重新生成批次工序" in html
        assert _business_rows(db_path) == before
    finally:
        _close_app(app)


def main() -> None:
    test_excel_import_component_renders_strict_mode_toggle_fields()
    print("OK")


if __name__ == "__main__":
    main()
