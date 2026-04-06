from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _reset_aps_logger_handlers() -> None:
    for logger_name in ("APS", "web.bootstrap.factory"):
        logger = logging.getLogger(logger_name)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass


def _apply_env(monkeypatch, root: Path, *, suffix: str) -> dict[str, str]:
    db_path = root / f"aps_{suffix}.db"
    log_dir = root / f"logs_{suffix}"
    backup_dir = root / f"backups_{suffix}"
    template_dir = root / f"templates_excel_{suffix}"
    log_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    template_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(db_path))
    monkeypatch.setenv("APS_LOG_DIR", str(log_dir))
    monkeypatch.setenv("APS_BACKUP_DIR", str(backup_dir))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(template_dir))
    monkeypatch.setenv("SECRET_KEY", "aps-runtime-env-refresh-key")
    return {
        "DATABASE_PATH": str(db_path),
        "LOG_DIR": str(log_dir),
        "BACKUP_DIR": str(backup_dir),
        "EXCEL_TEMPLATE_DIR": str(template_dir),
    }


def _import_entry_module(module_name: str):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def _assert_runtime_paths(app, expected: dict[str, str]) -> None:
    for key, value in expected.items():
        assert app.config.get(key) == value


def test_app_create_app_uses_current_environment_each_time(tmp_path, monkeypatch) -> None:
    try:
        expected_first = _apply_env(monkeypatch, tmp_path, suffix="first")
        mod_first = _import_entry_module("app")
        _assert_runtime_paths(mod_first.app, expected_first)
        _assert_runtime_paths(mod_first.create_app(), expected_first)

        expected_second = _apply_env(monkeypatch, tmp_path, suffix="second")
        mod_second = _import_entry_module("app")
        _assert_runtime_paths(mod_second.app, expected_second)
        app_second = mod_second.create_app()
        _assert_runtime_paths(app_second, expected_second)
        assert app_second.config["DATABASE_PATH"] != expected_first["DATABASE_PATH"]
    finally:
        _reset_aps_logger_handlers()
        logging.shutdown()


def test_app_new_ui_create_app_uses_current_environment_each_time(tmp_path, monkeypatch) -> None:
    try:
        expected_first = _apply_env(monkeypatch, tmp_path, suffix="first_new_ui")
        mod_first = _import_entry_module("app_new_ui")
        _assert_runtime_paths(mod_first.app, expected_first)
        _assert_runtime_paths(mod_first.create_app(), expected_first)

        expected_second = _apply_env(monkeypatch, tmp_path, suffix="second_new_ui")
        mod_second = _import_entry_module("app_new_ui")
        _assert_runtime_paths(mod_second.app, expected_second)
        app_second = mod_second.create_app()
        _assert_runtime_paths(app_second, expected_second)
        assert app_second.config["DATABASE_PATH"] != expected_first["DATABASE_PATH"]
    finally:
        _reset_aps_logger_handlers()
        logging.shutdown()
