"""回归测试：批量复制批次时，批次号末尾无数字（如纯中文"急件A"）属于用户可自助修正的输入问题——
路由必须给出可读原因（批次号末尾必须包含数字），不得显示"系统错误"，也不得以 logger.exception
向运行日志写 ERROR 堆栈污染排障链路。"""

from __future__ import annotations

import importlib
import sqlite3

from core.infrastructure.database import ensure_schema
from tests._support.excel_templates import point_env_at_shared
from tests._support.paths import REPO_ROOT
from tests._support.workbench_web_contract import retired_response

SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _build_app(tmp_path, monkeypatch):
    test_db = tmp_path / "aps_test.db"
    test_logs = tmp_path / "logs"
    test_backups = tmp_path / "backups"
    test_logs.mkdir(exist_ok=True)
    test_backups.mkdir(exist_ok=True)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(test_db))
    monkeypatch.setenv("APS_LOG_DIR", str(test_logs))
    monkeypatch.setenv("APS_BACKUP_DIR", str(test_backups))
    point_env_at_shared(monkeypatch)

    ensure_schema(str(test_db), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    _seed_batch_without_trailing_digit(str(test_db))
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def _seed_batch_without_trailing_digit(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT INTO Parts(part_no, part_name) VALUES ('P001', '零件一')")
        conn.execute(
            """
            INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
            VALUES ('急件A', 'P001', '零件一', 5, '2026-08-01', 'normal', 'yes', 'pending')
            """
        )
        conn.commit()
    finally:
        conn.close()


def _capture_exception_logs(app, monkeypatch):
    logged = []

    def _fake_exception(message, *args, **kwargs):
        logged.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "exception", _fake_exception)
    return logged


def test_bulk_copy_batch_without_trailing_digit_gets_friendly_error_not_500(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    logged = _capture_exception_logs(app, monkeypatch)

    resp = client.post(
        "/scheduler/batches/bulk/copy",
        data={"batch_ids": ["急件A"]},
        follow_redirects=True,
    )
    body = resp.get_data(as_text=True)

    retired_response(resp, post_result=True)
    assert "批量复制完成：成功 0，失败 1。" in body
    assert "批次号末尾必须包含数字" in body, "用户必须看到可自助修正的具体原因"
    assert "系统错误" not in body, "输入问题不得被包装成'系统错误'"
    assert logged == [], f"输入问题不得写 logger.exception ERROR 堆栈，实际={logged!r}"
    with sqlite3.connect(app.config["DATABASE_PATH"]) as conn:
        assert conn.execute("SELECT batch_id,quantity FROM Batches ORDER BY batch_id").fetchall() == [("急件A", 5)]
