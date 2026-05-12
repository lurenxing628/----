from __future__ import annotations

import importlib
import io
import json
import os
import re
import sys
import tempfile
from base64 import urlsafe_b64decode, urlsafe_b64encode
from html import unescape as html_unescape
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _prepare_env(tmpdir: Path) -> None:
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = str(tmpdir / "aps_test.db")
    os.environ["APS_LOG_DIR"] = str(tmpdir / "logs")
    os.environ["APS_BACKUP_DIR"] = str(tmpdir / "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = str(tmpdir / "templates_excel")
    os.environ["SECRET_KEY"] = "aps-excel-hidden-payload-contract"


def _load_app():
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    for name in list(sys.modules):
        if name == "app" or name.startswith("web.bootstrap.entrypoint") or name.startswith("web.bootstrap.factory"):
            sys.modules.pop(name, None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def _make_xlsx_bytes() -> io.BytesIO:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "工种配置"
    ws.append(["工种ID", "工种名称", "归属"])
    ws.append(["OT_PAYLOAD", "隐藏数据检查工种", "自制"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _extract_raw_rows_payload(html: str) -> str:
    match = re.search(r'<textarea[^>]+name="raw_rows_json"[^>]*>(.*?)</textarea>', html, re.S)
    assert match, "预览页必须把确认写入所需数据放在 raw_rows_json textarea 中"
    return html_unescape(match.group(1)).strip()


def _extract_hidden_input(html: str, name: str) -> str:
    for match in re.finditer(r"<input[^>]+>", html, re.I):
        tag = match.group(0)
        if re.search(rf'name="{re.escape(name)}"', tag, re.I):
            value_match = re.search(r'value="([^"]*)"', tag, re.I)
            return html_unescape(value_match.group(1)).strip() if value_match else ""
    raise AssertionError(f"预览页必须提供隐藏字段：{name}")


def _decode_preview_payload(payload: str):
    prefix = "aps-preview-json-b64:"
    assert payload.startswith(prefix), "raw_rows_json 必须使用 aps-preview-json-b64 编码，避免页面源码直接出现内部值"
    decoded = urlsafe_b64decode(payload[len(prefix) :].encode("ascii")).decode("utf-8")
    rows = json.loads(decoded)
    assert isinstance(rows, list), f"raw_rows_json 解码后必须是真实列表：{type(rows)!r}"
    return rows


def _encode_preview_payload(rows) -> str:
    raw = json.dumps(rows, ensure_ascii=False)
    encoded = urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")
    return f"aps-preview-json-b64:{encoded}"


def main() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="aps_excel_hidden_payload_"))
    _prepare_env(tmpdir)
    app = _load_app()

    with app.test_client() as client:
        resp = client.post(
            "/process/excel/op-types/preview",
            data={"mode": "overwrite", "file": (_make_xlsx_bytes(), "op_types.xlsx")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)[:1000]
        html = resp.get_data(as_text=True)

    assert "检查数据解析失败，请重新上传 Excel 并检查。" not in html
    assert 'name="raw_rows_json"' in html
    assert 'name="preview_baseline"' in html
    assert 'action="/process/excel/op-types/confirm"' in html
    assert re.search(r'<input[^>]+name="preview_baseline"[^>]+value="[^"]+"', html)
    assert '<details class="aps-row-detail">' in html
    assert "<summary>查看数据</summary>" in html
    assert "本行数据" in html
    assert "raw_rows_json" in html
    assert "preview_baseline" in html
    assert "internal" not in html
    assert "external" not in html

    raw_payload = _extract_raw_rows_payload(html)
    preview_baseline = _extract_hidden_input(html, "preview_baseline")
    decoded_rows = _decode_preview_payload(raw_payload)
    assert len(decoded_rows) == 1
    assert decoded_rows[0]["工种ID"] == "OT_PAYLOAD"
    assert decoded_rows[0]["工种名称"] == "隐藏数据检查工种"
    assert decoded_rows[0]["归属"] == "internal"

    tampered_rows = [dict(decoded_rows[0])]
    tampered_rows[0]["工种ID"] = "OT_TAMPERED"
    tampered_rows[0]["工种名称"] = "篡改后的工种"

    with app.test_client() as client:
        confirm_resp = client.post(
            "/process/excel/op-types/confirm",
            data={
                "mode": "overwrite",
                "filename": "op_types.xlsx",
                "raw_rows_json": _encode_preview_payload(tampered_rows),
                "preview_baseline": preview_baseline,
            },
            follow_redirects=True,
        )
        assert confirm_resp.status_code == 200, confirm_resp.get_data(as_text=True)[:1000]
        confirm_html = confirm_resp.get_data(as_text=True)

    assert "导入被拒绝：数据已变化，请重新上传 Excel 并检查后再确认写入。" in confirm_html

    from core.infrastructure.database import get_connection

    conn = get_connection(str(tmpdir / "aps_test.db"))
    try:
        count = conn.execute("SELECT COUNT(1) FROM OpTypes WHERE op_type_id=?", ("OT_TAMPERED",)).fetchone()[0]
        assert int(count) == 0, "篡改 raw_rows_json 后不能写入未预览过的工种"
    finally:
        conn.close()

    print("OK")


def test_excel_hidden_payload_contract() -> None:
    main()


if __name__ == "__main__":
    main()
