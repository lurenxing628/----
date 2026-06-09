"""回归测试：POST /personnel/excel/links/preview 路由内部异常时不泄露实现细节——当 normalize_skill_level_optional 抛 RuntimeError，响应应为 500 且页面只显示「服务器内部错误」，绝不把原始异常文案（normalize exploded）透出给用户。"""

from __future__ import annotations

import importlib
import io
import logging
import os
import sqlite3
import tempfile
from unittest.mock import patch

import openpyxl

from core.infrastructure.database import ensure_schema
from tests._support.excel_templates import point_env_at_shared
from tests._support.paths import REPO_ROOT_STR as REPO_ROOT

SCHEMA_PATH = os.path.join(REPO_ROOT, "schema.sql")


def _reset_aps_logger_handlers() -> None:
    for logger_name in ("APS", "web.bootstrap.factory"):
        logger = logging.getLogger(logger_name)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass


def _build_excel_bytes() -> io.BytesIO:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None

    ws.append(["工号", "设备编号", "技能等级"])
    ws.append(["OP100", "MC100", "expert"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_personnel_excel_preview_hides_internal_runtime_error(monkeypatch) -> None:
    with tempfile.TemporaryDirectory(prefix="aps_test_personnel_excel_preview_") as root:
        test_db = os.path.join(root, "aps_test.db")
        test_logs = os.path.join(root, "logs")
        test_backups = os.path.join(root, "backups")
        test_templates = os.path.join(root, "templates_excel")
        os.makedirs(test_logs, exist_ok=True)
        os.makedirs(test_backups, exist_ok=True)
        os.makedirs(test_templates, exist_ok=True)

        monkeypatch.setenv("APS_ENV", "development")
        monkeypatch.setenv("APS_DB_PATH", test_db)
        monkeypatch.setenv("APS_LOG_DIR", test_logs)
        monkeypatch.setenv("APS_BACKUP_DIR", test_backups)
        point_env_at_shared(monkeypatch)

        ensure_schema(test_db, logger=None, schema_path=SCHEMA_PATH, backup_dir=None)

        conn = sqlite3.connect(test_db)
        try:
            conn.execute("INSERT INTO Operators (operator_id, name) VALUES (?, ?)", ("OP100", "测试员甲"))
            conn.execute("INSERT INTO Machines (machine_id, name) VALUES (?, ?)", ("MC100", "设备甲"))
            conn.commit()
        finally:
            conn.close()

        _reset_aps_logger_handlers()
        config_mod = importlib.import_module("config")
        importlib.reload(config_mod)
        factory_mod = importlib.import_module("web.bootstrap.factory")
        importlib.reload(factory_mod)
        app = factory_mod.create_app_core(
            ui_mode="default",
            enable_secret_key=True,
            enable_security_headers=True,
            enable_session_cookie_hardening=True,
        )
        app.config["TESTING"] = False
        app.config["PROPAGATE_EXCEPTIONS"] = False
        client = app.test_client()
        try:
            with patch(
                "core.services.personnel.operator_machine_normalizers.normalize_skill_level_optional",
                side_effect=RuntimeError("normalize exploded"),
            ):
                resp = client.post(
                    "/personnel/excel/links/preview",
                    data={"mode": "overwrite", "file": (_build_excel_bytes(), "t.xlsx")},
                    content_type="multipart/form-data",
                )

            body = resp.data.decode("utf-8", errors="ignore")
            assert resp.status_code == 500
            assert "normalize exploded" not in body
            assert "服务器内部错误" in body
        finally:
            _reset_aps_logger_handlers()
            logging.shutdown()
