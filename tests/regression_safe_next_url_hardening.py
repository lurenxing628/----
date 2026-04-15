from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

from flask import url_for


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("repo root not found")


def _prepare_env(tmpdir: str) -> None:
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = str(Path(tmpdir) / "aps_test.db")
    os.environ["APS_LOG_DIR"] = str(Path(tmpdir) / "logs")
    os.environ["APS_BACKUP_DIR"] = str(Path(tmpdir) / "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = str(Path(tmpdir) / "templates_excel")
    os.environ["SECRET_KEY"] = "aps-safe-next-hardening"


def _load_app(repo_root: str):
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def _assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise RuntimeError(f"{message}: expected={expected!r}, actual={actual!r}")


def _assert_is_none(actual, message: str) -> None:
    if actual is not None:
        raise RuntimeError(f"{message}: expected None, actual={actual!r}")


def main() -> None:
    repo_root = find_repo_root()
    tmpdir = tempfile.mkdtemp(prefix="aps_safe_next_hardening_")
    _prepare_env(tmpdir)
    app = _load_app(repo_root)

    system_utils = importlib.import_module("web.routes.system_utils")
    ui_mode = importlib.import_module("web.ui_mode")
    scheduler_config = importlib.import_module("web.routes.scheduler_config")

    with app.test_request_context("/scheduler/config"):
        dashboard_url = url_for("dashboard.index")

        valid_next_cases = [
            ("/scheduler/config", "/scheduler/config", "keep absolute internal path"),
            ("/scheduler/config?", "/scheduler/config", "trim trailing question mark"),
            ("scheduler/config?", "/scheduler/config", "trim trailing question mark before leading slash"),
            ("/scheduler/config?page=2", "/scheduler/config?page=2", "keep internal query string"),
            ("scheduler/config?page=2", "/scheduler/config?page=2", "add leading slash for bare internal path"),
        ]
        for raw, expected, message in valid_next_cases:
            _assert_equal(system_utils._safe_next_url(raw), expected, message)

        invalid_next_cases = [
            (None, "reject None"),
            ("", "reject empty string"),
            ("   ", "reject whitespace"),
            ("http://evil.example/x", "reject absolute url"),
            ("//evil.example/x", "reject protocol-relative url"),
            ("///evil.example/x", "reject triple-slash url"),
            ("////evil.example/x", "reject quad-slash url"),
            ("\\\\evil.example", "reject leading backslash"),
            ("/\\\\evil.example", "reject embedded backslash"),
            ("/line\nbreak", "reject newline"),
            ("/line\rbreak", "reject carriage return"),
            ("/line\x00break", "reject null byte"),
        ]
        for raw, message in invalid_next_cases:
            _assert_equal(system_utils._safe_next_url(raw), dashboard_url, message)

        valid_src_cases = [
            ("/scheduler/config", "/scheduler/config", "keep manual src path"),
            ("/scheduler/config?", "/scheduler/config?", "preserve trailing question mark in manual src"),
            ("/scheduler/config?page=2", "/scheduler/config?page=2", "keep manual src query string"),
        ]
        for raw, expected, message in valid_src_cases:
            _assert_equal(ui_mode.normalize_manual_src(raw), expected, message)

        invalid_src_cases = [
            ("", "reject manual src empty string"),
            ("   ", "reject manual src whitespace"),
            ("scheduler/config", "reject manual src without leading slash"),
            ("http://evil.example/x", "reject manual src absolute url"),
            ("//evil.example/x", "reject manual src protocol-relative url"),
            ("///evil.example/x", "reject manual src triple-slash url"),
            ("////evil.example/x", "reject manual src quad-slash url"),
            ("\\\\evil.example", "reject manual src leading backslash"),
            ("/\\\\evil.example", "reject manual src embedded backslash"),
            ("/line\nbreak", "reject manual src newline"),
            ("/line\rbreak", "reject manual src carriage return"),
            ("/line\x00break", "reject manual src null byte"),
        ]
        for raw, message in invalid_src_cases:
            _assert_is_none(ui_mode.normalize_manual_src(raw), message)

        safe_src = ui_mode.normalize_manual_src("/scheduler/config?")
        _assert_equal(
            scheduler_config._resolve_manual_back_url(safe_src),
            "/scheduler/config?",
            "manual back url should consume filtered safe_src only",
        )
        _assert_is_none(
            scheduler_config._resolve_manual_back_url(ui_mode.normalize_manual_src("http://evil.example/x")),
            "manual back url should stay None for rejected src",
        )
        _assert_is_none(
            scheduler_config._resolve_manual_back_url(None),
            "manual back url should fold empty input to None",
        )

    print("OK")


if __name__ == "__main__":
    main()
