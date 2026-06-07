"""单元测试：check_quickref_vs_routes 工具——报告使用仓库相对路径与稳定快照元数据（无盘符、无生成时间），_extract_doc_endpoints/_diff_endpoints 能识别速查表与真实路由间的缺失/多余/方法不匹配，main 打印仓库相对报告路径。"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

from flask import Flask

from tests._support.paths import REPO_ROOT, REPO_ROOT_STR


def _repo_root() -> Path:
    return REPO_ROOT


def _import_check_quickref_vs_routes():
    repo_root = _repo_root()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    module_name = "tests.check_quickref_vs_routes"
    sys.modules.pop(module_name, None)
    module_path = repo_root / "tests" / "check_quickref_vs_routes.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块：{module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_render_report_uses_repo_relative_path_and_stable_metadata():
    module = _import_check_quickref_vs_routes()

    report = module._render_report(
        doc_display_path="开发文档/系统速查表.md",
        doc_count=3,
        rule_count=3,
        missing_in_code=[],
        undocumented_in_doc=[],
    )

    assert "开发文档/系统速查表.md" in report
    assert "D:\\" not in report
    assert "C:\\" not in report
    assert "生成时间" not in report


def test_extract_doc_endpoints_and_diff_missing_extra_method_mismatch():
    module = _import_check_quickref_vs_routes()

    doc_eps = module._extract_doc_endpoints(
        """
- `GET /system/logs`：操作日志
- `POST /system/logs/delete`：删除日志
- `GET /reports/overdue`：超期报表
        """
    )
    route_eps = {
        ("GET", "/system/logs"),
        ("GET", "/system/logs/delete"),
        ("GET", "/reports/overdue"),
        ("POST", "/reports/overdue/export"),
    }

    missing, extra = module._diff_endpoints(doc_eps, route_eps)

    assert ("POST", "/system/logs/delete") in missing
    assert ("GET", "/system/logs/delete") in extra
    assert ("POST", "/reports/overdue/export") in extra


def test_main_prints_repo_relative_report_path(monkeypatch, tmp_path, capsys):
    module = _import_check_quickref_vs_routes()
    repo_root = tmp_path
    doc_dir = repo_root / "开发文档"
    doc_dir.mkdir()
    (repo_root / "app.py").write_text("app = None\n", encoding="utf-8")
    (repo_root / "schema.sql").write_text("-- schema\n", encoding="utf-8")
    (doc_dir / "系统速查表.md").write_text("- `GET /health`：健康检查\n", encoding="utf-8")
    app = Flask("quickref-test")

    @app.route("/health")
    def health():
        return "ok"

    def load_app_with_noisy_startup(_repo_root):
        logging.warning("noisy startup path /tmp/aps_quickref_check_random/logs/aps_secret_key.txt")
        return app, "quickref_test_app"

    monkeypatch.setattr(module, "find_repo_root", lambda: str(repo_root))
    monkeypatch.setattr(module, "_load_app_for_scan", load_app_with_noisy_startup)

    assert module.main() == 0

    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["evidence/QualityGate/quickref_vs_routes.md", "OK"]
    assert captured.err == ""
