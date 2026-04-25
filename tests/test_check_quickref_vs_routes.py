from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


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
    assert "稳定快照" in report


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
