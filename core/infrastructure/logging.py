"""日志底座：只依赖标准库，启动期还没有应用、数据库或 Flask 时也能导入。

数据库操作日志在 `core/infrastructure/operation_logging.py`；启动期文件落盘在
`web/bootstrap/launcher_observability.py`。两者都复用这里的格式化与 stderr 写入。
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from typing import Any, Optional, Tuple


def format_log_message(message: str, *args: Any) -> str:
    """按 logging 的 % 规则展开参数；参数与格式不符时保留原文和参数，不丢这条日志。"""
    if not args:
        return message
    try:
        return message % args
    except (TypeError, ValueError, OverflowError):
        return f"{message} | args={args!r}"


def write_stderr(text: str) -> None:
    """没有日志器可写时的最后通道；管道断开或流已关闭时放弃这一行。"""
    try:
        print(text, file=sys.stderr)
    except (OSError, ValueError):
        return


def safe_log(logger: Optional[logging.Logger], level: str, message: str, *args: Any) -> None:
    """有日志器就按级别写进日志器，没有时写 stderr。"""
    if logger is None:
        write_stderr(format_log_message(message, *args))
        return
    getattr(logger, level)(message, *args)


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

    def _expected_log_files(self) -> Tuple[str, str]:
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
            try:
                handler.close()
            except OSError as exc:
                write_stderr(f"关闭旧日志处理器失败，已继续重新配置：{exc}")

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
