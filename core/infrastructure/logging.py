import json
import logging
import logging.handlers
import os
from typing import Optional, Dict, Any


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
        if not self.logger.handlers:
            self._add_console_handler()
            self._add_file_handler()
            self._add_error_file_handler()

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

    def __init__(self, db_connection, logger: logging.Logger = None):
        self.conn = db_connection
        self.logger = logger or logging.getLogger(__name__)

    def log(
        self,
        level: str,
        module: str,
        action: str,
        target_type: str = None,
        target_id: str = None,
        operator: str = None,
        detail: Dict[str, Any] = None,
        error_code: str = None,
        error_message: str = None,
    ):
        try:
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
            self.conn.commit()
        except Exception as e:
            # 记录失败时写文件日志，避免影响主流程
            self.logger.error(f"写入操作日志失败：{e}")

    def info(self, module: str, action: str, **kwargs):
        self.log("INFO", module, action, **kwargs)
        # 控制台/文件日志也记录一条简要信息（中文）
        self.logger.info(f"[{module}] 操作：{action}（{kwargs.get('target_type') or ''} {kwargs.get('target_id') or ''}）")

    def warn(self, module: str, action: str, **kwargs):
        self.log("WARN", module, action, **kwargs)
        self.logger.warning(f"[{module}] 警告：{action}（{kwargs}）")

    def error(self, module: str, action: str, error_code: str, error_message: str, **kwargs):
        self.log(
            "ERROR",
            module,
            action,
            error_code=error_code,
            error_message=error_message,
            **kwargs,
        )
        self.logger.error(f"[{module}] 失败：{action}（[{error_code}] {error_message}）")

