"""回归测试：基础设施层不静默吞错的契约——OperationLogger 在 in_transaction 不可读时不自动 commit 且留警告（logger 自身报错则回退 stderr），AppError 保留 args 并拒绝非 Exception 的 cause，迁移工具 table_exists/column_exists 对非法标识符抛 ValueError 而非静默放过。"""

from __future__ import annotations

import sqlite3

import pytest


class _BoomInTransactionConn:
    def __init__(self) -> None:
        self.rollback_count = 0
        self.commit_count = 0
        self.executed = []

    @property
    def in_transaction(self):
        raise RuntimeError("in_transaction unreadable")

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        return None

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


class _CollectingLogger:
    def __init__(self) -> None:
        self.warnings = []
        self.errors = []

    def warning(self, message: str) -> None:
        self.warnings.append(str(message))

    def error(self, message: str) -> None:
        self.errors.append(str(message))


class _BrokenWarningLogger:
    def warning(self, message: str) -> None:
        raise RuntimeError("logger warning unavailable")

    def error(self, message: str) -> None:
        return None


def test_operation_logger_does_not_autocommit_when_transaction_state_unreadable() -> None:
    from core.infrastructure.logging import OperationLogger

    conn = _BoomInTransactionConn()
    logger = _CollectingLogger()

    assert OperationLogger(conn, logger=logger).log("INFO", "test", "write") is True
    assert conn.executed, "操作日志仍应尝试写入"
    assert conn.commit_count == 0, "事务状态查不清时不能自动 commit"
    assert any("事务状态失败" in item or "不会自动提交" in item for item in logger.warnings)


def test_operation_logger_transaction_state_warning_falls_back_to_stderr(capsys) -> None:
    from core.infrastructure.logging import OperationLogger

    conn = _BoomInTransactionConn()

    assert OperationLogger(conn, logger=_BrokenWarningLogger()).log("INFO", "test", "write") is True
    stderr = capsys.readouterr().err
    assert "读取数据库事务状态失败" in stderr
    assert "不会自动提交" in stderr
    assert conn.commit_count == 0


def test_app_error_preserves_args_and_rejects_non_exception_cause() -> None:
    from core.infrastructure.errors import AppError, ErrorCode

    cause = RuntimeError("root cause")
    err = AppError(ErrorCode.UNKNOWN_ERROR, "用户能看到的错误", cause=cause)
    assert err.args == ("用户能看到的错误",)
    assert err.__cause__ is cause

    with pytest.raises(TypeError):
        AppError(ErrorCode.UNKNOWN_ERROR, "错误", cause="bad")  # type: ignore[arg-type]


def test_migration_identifier_validation_is_not_silent() -> None:
    from core.infrastructure.migrations.common import column_exists, table_exists

    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE GoodTable (id INTEGER PRIMARY KEY, name TEXT)")
        assert table_exists(conn, "GoodTable") is True
        assert column_exists(conn, "GoodTable", "name") is True
        with pytest.raises(ValueError):
            table_exists(conn, "bad-table")
        with pytest.raises(ValueError):
            column_exists(conn, "GoodTable", "bad-column")
    finally:
        conn.close()
