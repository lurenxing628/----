from __future__ import annotations

import importlib
import io
import json
import os
import re
import sys
import tempfile
from base64 import urlsafe_b64decode
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


def _decode_preview_payload(payload: str):
    prefix = "aps-preview-json-b64:"
    assert payload.startswith(prefix), "raw_rows_json 必须使用 aps-preview-json-b64 编码，避免页面源码泄漏内部值"
    decoded = urlsafe_b64decode(payload[len(prefix) :].encode("ascii")).decode("utf-8")
    rows = json.loads(decoded)
    assert isinstance(rows, list), f"raw_rows_json 解码后必须是真实列表：{type(rows)!r}"
    return rows


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
    decoded_rows = _decode_preview_payload(raw_payload)
    assert len(decoded_rows) == 1
    assert decoded_rows[0]["工种ID"] == "OT_PAYLOAD"
    assert decoded_rows[0]["工种名称"] == "隐藏数据检查工种"
    assert decoded_rows[0]["归属"] == "internal"

    print("OK")


if __name__ == "__main__":
    main()
