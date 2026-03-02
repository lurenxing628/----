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
        def _truncate(s: str, max_len: int = 200) -> str:
            s = "" if s is None else str(s)
            s = s.replace("\r", "\\r").replace("\n", "\\n")
            return s if len(s) <= max_len else (s[: max_len - 3] + "...")

        def _is_sensitive_key(k: str) -> bool:
            kk = (k or "").lower()
            return any(x in kk for x in ("password", "passwd", "token", "secret", "apikey", "api_key", "cookie", "session"))

        def _safe_value(v: Any) -> Any:
            if v is None:
                return None
            if isinstance(v, (bytes, bytearray, memoryview)):
                try:
                    return f"<{type(v).__name__} len={len(v)}>"
                except Exception:
                    return f"<{type(v).__name__}>"
            try:
                return _truncate(repr(v), max_len=200)
            except Exception:
                return f"<unreprable {type(v).__name__}>"

        def _safe_params(p: Optional[Params]) -> Any:
            if p is None:
                return None
            try:
                if isinstance(p, dict):
                    out: Dict[str, Any] = {}
                    items = list(p.items())
                    for k, v in items[:30]:
                        ks = _truncate(str(k), max_len=80)
                        out[ks] = "<redacted>" if _is_sensitive_key(ks) else _safe_value(v)
                    if len(items) > 30:
                        out["..."] = f"+{len(items) - 30} more"
                    return out
                if isinstance(p, (list, tuple)):
                    seq = list(p)
                    out2 = [_safe_value(v) for v in seq[:30]]
                    if len(seq) > 30:
                        out2.append(f"...+{len(seq) - 30} more")
                    return out2
                return _safe_value(p)
            except Exception:
                return "<unloggable params>"

        try:
            self.logger.error("数据库错误：%s；SQL=%s；params=%s", e, sql, _safe_params(params))
        except Exception:
            # 记录日志失败不应影响主流程
            pass

