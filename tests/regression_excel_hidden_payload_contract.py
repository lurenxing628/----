from __future__ import annotations

import importlib
import io
import os
import re
import sys
import tempfile
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
    ws.append(["工种编号", "工种名称", "归属"])
    ws.append(["OT_PAYLOAD", "隐藏数据检查工种", "自制"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


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

    assert 'name="raw_rows_json"' in html
    assert 'name="preview_baseline"' in html
    assert 'action="/process/excel/op-types/confirm"' in html
    assert re.search(r'<textarea[^>]+name="raw_rows_json"[^>]*>.+?</textarea>', html, re.S)
    assert re.search(r'<input[^>]+name="preview_baseline"[^>]+value="[^"]+"', html)
    assert '<details class="aps-row-detail">' in html
    assert "<summary>查看数据</summary>" in html
    assert "本行数据" in html
    assert "raw_rows_json" in html
    assert "preview_baseline" in html

    print("OK")


if __name__ == "__main__":
    main()
