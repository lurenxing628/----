from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _prepare_env(tmpdir: Path) -> None:
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = str(tmpdir / "aps_test.db")
    os.environ["APS_LOG_DIR"] = str(tmpdir / "logs")
    os.environ["APS_BACKUP_DIR"] = str(tmpdir / "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = str(tmpdir / "templates_excel")
    os.environ["SECRET_KEY"] = "aps-ui-copy-plain-language"


def _load_app():
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    for name in list(sys.modules):
        if name == "app" or name.startswith("web.bootstrap.entrypoint") or name.startswith("web.bootstrap.factory"):
            sys.modules.pop(name, None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def _get_text(client, path: str) -> str:
    resp = client.get(path)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:1000]
    return resp.get_data(as_text=True)


def _assert_not_in_any(phrases: list[str], sources: dict[str, str]) -> None:
    for phrase in phrases:
        for name, text in sources.items():
            assert phrase not in text, f"{name} 不应再出现旧文案：{phrase}"


def main() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="aps_ui_copy_plain_language_"))
    _prepare_env(tmpdir)
    app = _load_app()

    template_sources = {
        "process/detail.html": _read("templates/process/detail.html"),
        "scheduler/batch_detail.html": _read("templates/scheduler/batch_detail.html"),
        "components/excel_import.html": _read("templates/components/excel_import.html"),
        "components/ui_macros.html": _read("templates/components/ui_macros.html"),
        "routes/process_excel_routes.py": _read("web/routes/process_excel_routes.py"),
        "docs/manual": _read("static/docs/scheduler_manual.md"),
        "new-docs/manual": _read("web_new_test/static/docs/scheduler_manual.md"),
    }

    _assert_not_in_any(
        [
            "重新解析（覆盖工序模板）",
            "从零件模板重建工序（会覆盖补充信息）",
            "自动生成/重建工序",
            "上传并预览",
            "确认导入（保存到系统）",
            "请重新上传 Excel 并检查后再确认导入",
            "批次信息（Excel导入/导出）",
            "人员专属工作日历（Excel）",
            "现代界面可从左侧\"Excel 演示\"进入",
        ],
        template_sources,
    )

    assert "按路线重新生成工序清单" in template_sources["process/detail.html"]
    assert "按最新工艺模板刷新本批次工序" in template_sources["scheduler/batch_detail.html"]
    assert "请重新上传 Excel 并检查后再确认写入" in template_sources["routes/process_excel_routes.py"]
    assert "确认写入系统" in template_sources["components/excel_import.html"]

    with app.test_client() as client:
        part_hours_html = _get_text(client, "/process/excel/part-operation-hours")
        assert "更新已有工时" in part_hours_html
        assert "只补空工时" in part_hours_html
        assert "只导入新编号" not in part_hours_html

        routes_html = _get_text(client, "/process/excel/routes")
        assert "更新已有，新增缺少" in routes_html
        assert "只导入新编号" in routes_html
        assert "清空本类数据后重导" in routes_html

    print("OK")


if __name__ == "__main__":
    main()
