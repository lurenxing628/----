#!/usr/bin/env python3
"""验证 config_manual 页面相关模块说明区的结构与样式契约。"""
from __future__ import annotations

import importlib
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

from flask import url_for

REPO_ROOT = Path(__file__).resolve().parent


def _prepare_env(tmpdir: Path) -> None:
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = str(tmpdir / "aps_test.db")
    os.environ["APS_LOG_DIR"] = str(tmpdir / "logs")
    os.environ["APS_BACKUP_DIR"] = str(tmpdir / "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = str(tmpdir / "templates_excel")
    os.environ["SECRET_KEY"] = "aps-verify-manual-styles"


def _load_app(repo_root: Path):
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def _mode_headers(ui_mode: str) -> dict:
    return {"Cookie": f"aps_ui_mode={ui_mode}"}


def _build_url(app, endpoint: str, **values: Any) -> str:
    with app.test_request_context():
        return url_for(endpoint, **values)


def _check(condition: bool, message: str, failures: list) -> None:
    if condition:
        print(f"[OK] {message}")
    else:
        print(f"[FAIL] {message}")
        failures.append(message)


def _has_css_rule(css_content: str, pattern: str) -> bool:
    return re.search(pattern, css_content, re.DOTALL) is not None


def main() -> None:
    print("=== APS manual styles verification ===\n")
    failures = []

    css_file = REPO_ROOT / "static" / "css" / "ui_contract.css"
    _check(css_file.exists(), f"CSS 文件存在：{css_file}", failures)
    if not css_file.exists():
        sys.exit(1)

    css_content = css_file.read_text(encoding="utf-8")
    css_checks = [
        (
            "manual-related-body/code 基础样式存在",
            r"\.manual-related-body\s+code\s*\{(?=[^}]*background\s*:)(?=[^}]*color\s*:)[^}]*\}",
        ),
        (
            "manual-related-body/pre 基础样式存在",
            r"\.manual-related-body\s+pre\s*\{(?=[^}]*background\s*:)(?=[^}]*border-left\s*:)[^}]*\}",
        ),
        (
            "manual-related-body/code 暗色样式存在",
            r'html\[data-theme="dark"\]\s+\.manual-related-body\s+code\s*\{(?=[^}]*background\s*:)(?=[^}]*color\s*:)[^}]*\}',
        ),
        (
            "manual-related-body/pre 暗色样式存在",
            r'html\[data-theme="dark"\]\s+\.manual-related-body\s+pre\s*\{(?=[^}]*background\s*:)(?=[^}]*color\s*:)[^}]*\}',
        ),
        (
            "manual-related-body 最小宽度规则存在",
            r"\.manual-related-panel\s*,\s*\.manual-related-body\s*\{[^}]*min-width\s*:\s*0\s*;",
        ),
    ]
    for message, pattern in css_checks:
        _check(_has_css_rule(css_content, pattern), message, failures)

    tmpdir = Path(tempfile.mkdtemp(prefix="aps_verify_manual_styles_"))
    _prepare_env(tmpdir)
    app = _load_app(REPO_ROOT)
    client = app.test_client()

    page_cases = [
        ("material.materials_page", "物料页"),
        ("scheduler.config_page", "高级设置页"),
    ]
    for ui_mode in ("v1", "v2"):
        print(f"\n=== HTML 结构检查（{ui_mode}）===\n")
        for endpoint, label in page_cases:
            page_url = _build_url(app, "scheduler.config_manual_page", page=endpoint)
            resp = client.get(page_url, headers=_mode_headers(ui_mode))
            text = resp.get_data(as_text=True)
            _check(resp.status_code == 200, f"{label} 说明书页可访问（{ui_mode}）", failures)
            if resp.status_code != 200:
                continue

            _check("manual-main-column" in text, f"{label} 存在 manual-main-column（{ui_mode}）", failures)
            _check("manual-related-panel" in text, f"{label} 存在 manual-related-panel（{ui_mode}）", failures)
            _check("manual-related-body" in text, f"{label} 存在 manual-related-body（{ui_mode}）", failures)
            _check('data-manual-markdown="' in text, f"{label} 存在 data-manual-markdown 占位（{ui_mode}）", failures)
            _check("js/config_manual.js" in text, f"{label} 加载 config_manual.js（{ui_mode}）", failures)
            _check("aps-config-manual-data" in text, f"{label} 存在 JSON 配置块（{ui_mode}）", failures)

    if failures:
        print("\n=== Verification failed ===")
        for item in failures:
            print(f"- {item}")
        sys.exit(1)

    print("\n=== Verification complete ===")
    print("OK")


if __name__ == "__main__":
    main()
