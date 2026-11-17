"""数据库操作日志：写 OperationLogs 表，并在应用日志里留一行摘要。

外层事务归调用方：处在 `TransactionManager` 上下文或连接已开事务时，这里只插入不提交、不回滚；
只有本次自己开始的隐式事务才在这里提交，写失败时回滚。`raise_on_fail=True` 把原异常交还调用方。
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any, Dict, Optional

from core.infrastructure.transaction import in_transaction_context
from core.shared.strict_json import canonical_json


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
            pre_in_tx = bool(self.conn.in_transaction)
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
                    canonical_json(detail) if detail else None,
                    error_code,
                    error_message,
                ),
            )
            if auto_commit:
                self.conn.commit()
            return True
        except Exception as e:
            # 若我们决定自动提交，则异常路径也要结束本次自己开始的事务，避免悬挂
            if auto_commit:
                try:
                    self.conn.rollback()
                except sqlite3.Error as rollback_exc:
                    self.logger.error(f"写入操作日志失败后的回滚也失败：{rollback_exc}")
            # 记录失败时写文件日志，避免影响主流程
            self.logger.error(f"写入操作日志失败：{e}")
            if raise_on_fail:
                raise
            return False

    def info(self, module: str, action: str, **kwargs) -> bool:
        ok = self.log("INFO", module, action, **kwargs)
        if ok:
            self.logger.info(f"[{module}] 操作：{action}（{kwargs.get('target_type') or ''} {kwargs.get('target_id') or ''}）")
        return ok

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
            self.logger.error(f"[{module}] 失败：{action}（[{error_code}] {error_message}）")
        return ok
