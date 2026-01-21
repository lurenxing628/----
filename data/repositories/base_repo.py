from __future__ import annotations

import sqlite3
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from core.infrastructure.errors import AppError, ErrorCode


Params = Union[Sequence[Any], Dict[str, Any]]


def _row_to_dict(row: Union[sqlite3.Row, Dict[str, Any]]) -> Dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    # sqlite3.Row 支持 keys()
    return {k: row[k] for k in row.keys()}


class BaseRepository:
    """
    基础仓库类（数据访问层）。

    目标：
    - 统一 SQL 执行与 Row 映射（sqlite3.Row -> dict）
    - 统一把 DB 异常翻译为 AppError（用户可见 message 尽量中文）
    - 默认不 commit：事务由服务层的 TransactionManager 控制
    """

    def __init__(self, conn: sqlite3.Connection, logger=None):
        self.conn = conn
        self.logger = logger

    # -------------------------
    # 基础执行与查询
    # -------------------------
    def execute(self, sql: str, params: Optional[Params] = None) -> sqlite3.Cursor:
        try:
            if params is None:
                return self.conn.execute(sql)
            return self.conn.execute(sql, params)
        except sqlite3.IntegrityError as e:
            raise self._translate_integrity_error(e) from e
        except sqlite3.Error as e:
            self._log_db_error(sql, params, e)
            raise AppError(ErrorCode.DB_QUERY_ERROR, "数据库执行失败，请查看日志。", cause=e) from e

    def executemany(self, sql: str, seq_of_params: Iterable[Params]) -> sqlite3.Cursor:
        try:
            return self.conn.executemany(sql, seq_of_params)
        except sqlite3.IntegrityError as e:
            raise self._translate_integrity_error(e) from e
        except sqlite3.Error as e:
            self._log_db_error(sql, None, e)
            raise AppError(ErrorCode.DB_QUERY_ERROR, "数据库批量执行失败，请查看日志。", cause=e) from e

    def fetchone(self, sql: str, params: Optional[Params] = None) -> Optional[Dict[str, Any]]:
        cur = self.execute(sql, params)
        row = cur.fetchone()
        return _row_to_dict(row) if row else None

    def fetchall(self, sql: str, params: Optional[Params] = None) -> List[Dict[str, Any]]:
        cur = self.execute(sql, params)
        rows = cur.fetchall() or []
        return [_row_to_dict(r) for r in rows]

    def fetchvalue(self, sql: str, params: Optional[Params] = None, default: Any = None) -> Any:
        cur = self.execute(sql, params)
        row = cur.fetchone()
        if not row:
            return default
        # sqlite3.Row 既可索引也可 key 访问；这里取第 0 列
        return row[0]

    # -------------------------
    # 统一异常翻译
    # -------------------------
    def _translate_integrity_error(self, e: sqlite3.IntegrityError) -> AppError:
        msg = str(e) or ""

        # UNIQUE 约束冲突
        if "UNIQUE constraint failed" in msg:
            return AppError(
                ErrorCode.DUPLICATE_ENTRY,
                "数据已存在，不能重复添加（唯一性约束冲突）。",
                details={"db_message": msg},
                cause=e,
            )

        # 外键约束冲突
        if "FOREIGN KEY constraint failed" in msg:
            return AppError(
                ErrorCode.DB_INTEGRITY_ERROR,
                "数据关联校验失败：引用的记录不存在或已被删除。",
                details={"db_message": msg},
                cause=e,
            )

        # 非空约束冲突
        if "NOT NULL constraint failed" in msg:
            return AppError(
                ErrorCode.VALIDATION_ERROR,
                "缺少必填字段（不能为空）。",
                details={"db_message": msg},
                cause=e,
            )

        return AppError(
            ErrorCode.DB_INTEGRITY_ERROR,
            "数据库完整性约束失败，请检查输入数据。",
            details={"db_message": msg},
            cause=e,
        )

    def _log_db_error(self, sql: str, params: Optional[Params], e: Exception) -> None:
        if not self.logger:
            return
        try:
            self.logger.error(
                "数据库错误：%s；SQL=%s；params=%s",
                e,
                sql,
                params,
            )
        except Exception:
            # 记录日志失败不应影响主流程
            pass

