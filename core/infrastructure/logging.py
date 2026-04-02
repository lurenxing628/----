from __future__ import annotations

import json
import logging
import logging.handlers
import os
from typing import Any, Callable, Dict, Optional

from core.infrastructure.transaction import in_transaction_context


def _invoke_safely(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> bool:
    try:
        fn(*args, **kwargs)
        return True
    except Exception:
        return False


class AppLogger:
    """应用日志管理器（滚动文件 + 错误文件）。"""

    def __init__(
        self,
        app_name: str = "APS",
        log_dir: str = "logs",
        log_level: str = "INFO",
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ):
        self.app_name = app_name
        self.log_dir = log_dir
        self.log_level = getattr(logging, (log_level or "INFO").upper(), logging.INFO)
        self.max_bytes = max_bytes
        self.backup_count = backup_count

        os.makedirs(log_dir, exist_ok=True)

        self.logger = logging.getLogger(app_name)
        self.logger.setLevel(self.log_level)

        # 避免重复添加 handler（例如热重载/多次 create_app）
        if self._needs_reconfigure():
            self._reset_handlers()
            self._add_console_handler()
            self._add_file_handler()
            self._add_error_file_handler()

    def _expected_log_files(self) -> tuple[str, str]:
        return (
            os.path.abspath(os.path.join(self.log_dir, f"{self.app_name.lower()}.log")),
            os.path.abspath(os.path.join(self.log_dir, f"{self.app_name.lower()}_error.log")),
        )

    def _needs_reconfigure(self) -> bool:
        handlers = list(self.logger.handlers)
        if not handlers:
            return True
        expected_log, expected_error_log = self._expected_log_files()
        existing_files = set()
        for handler in handlers:
            if not isinstance(handler, logging.FileHandler):
                continue
            base_filename = handler.baseFilename
            if base_filename:
                existing_files.add(os.path.abspath(str(base_filename)))
        has_console = any(isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler) for handler in handlers)
        return (not has_console) or expected_log not in existing_files or expected_error_log not in existing_files

    def _reset_handlers(self) -> None:
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)
            _invoke_safely(handler.close)

    def _add_console_handler(self):
        handler = logging.StreamHandler()
        handler.setLevel(self.log_level)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def _add_file_handler(self):
        log_file = os.path.join(self.log_dir, f"{self.app_name.lower()}.log")
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding="utf-8",
        )
        handler.setLevel(self.log_level)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s [%(filename)s:%(lineno)d]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def _add_error_file_handler(self):
        log_file = os.path.join(self.log_dir, f"{self.app_name.lower()}_error.log")
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding="utf-8",
        )
        handler.setLevel(logging.ERROR)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s [%(filename)s:%(lineno)d]:\n"
            "  %(message)s\n",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        if name:
            return logging.getLogger(f"{self.app_name}.{name}")
        return self.logger


class OperationLogger:
    """操作日志记录器（写入数据库 OperationLogs 表）。"""

    def __init__(self, db_connection: Any, logger: Optional[logging.Logger] = None):
        self.conn = db_connection
        self.logger = logger or logging.getLogger(__name__)

    def log(
        self,
        level: str,
        module: str,
        action: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        operator: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        raise_on_fail: bool = False,
    ) -> bool:
        auto_commit = False
        try:
            # 注意：不要在外层事务（TransactionManager）中隐式 commit()，否则会破坏原子性。
            # 这里通过 transaction 上下文标记来判断是否应自动提交。
            # 另外：若调用方已处于 sqlite 事务中（conn.in_transaction=True），也不能“顺手 commit”，避免误提交调用方未提交写入。
            pre_in_tx = False
            try:
                pre_in_tx = bool(getattr(self.conn, "in_transaction", False))
            except Exception:
                pre_in_tx = False
            auto_commit = (not pre_in_tx) and (not in_transaction_context(self.conn))
            self.conn.execute(
                """
                INSERT INTO OperationLogs
                (log_level, module, action, target_type, target_id,
                 operator, detail, error_code, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    level,
                    module,
                    action,
                    target_type,
                    target_id,
                    operator,
                    json.dumps(detail, ensure_ascii=False) if detail else None,
                    error_code,
                    error_message,
                ),
            )
            if auto_commit:
                post_in_tx = True
                try:
                    post_in_tx = bool(getattr(self.conn, "in_transaction", False))
                except Exception:
                    post_in_tx = True
                if post_in_tx:
                    self.conn.commit()
            return True
        except Exception as e:
            # 若我们决定自动提交，则异常路径也要尽量结束事务，避免悬挂
            if auto_commit:
                _invoke_safely(self.conn.rollback)
            # 记录失败时写文件日志，避免影响主流程
            _invoke_safely(self.logger.error, f"写入操作日志失败：{e}")
            if raise_on_fail:
                raise
            return False

    def info(self, module: str, action: str, **kwargs) -> bool:
        ok = self.log("INFO", module, action, **kwargs)
        if ok:
            _invoke_safely(self.logger.info, f"[{module}] 操作：{action}（{kwargs.get('target_type') or ''} {kwargs.get('target_id') or ''}）")
        return bool(ok)

    def warn(self, module: str, action: str, **kwargs) -> bool:
        ok = self.log("WARN", module, action, **kwargs)
        if ok:
            _invoke_safely(self.logger.warning, f"[{module}] 警告：{action}（{kwargs}）")
        return bool(ok)

    def error(self, module: str, action: str, error_code: str, error_message: str, **kwargs) -> bool:
        ok = self.log(
            "ERROR",
            module,
            action,
            error_code=error_code,
            error_message=error_message,
            **kwargs,
        )
        if ok:
            _invoke_safely(self.logger.error, f"[{module}] 失败：{action}（[{error_code}] {error_message}）")
        return bool(ok)

