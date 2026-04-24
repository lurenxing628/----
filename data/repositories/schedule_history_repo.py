from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from core.infrastructure.errors import AppError, ErrorCode
from core.models import ScheduleHistory

from .base_repo import BaseRepository


class ScheduleHistoryRepository(BaseRepository):
    """排产历史仓库（ScheduleHistory）。"""

    def get(self, history_id: int) -> Optional[ScheduleHistory]:
        row = self.fetchone(
            "SELECT id, schedule_time, version, strategy, batch_count, op_count, result_status, result_summary, created_by FROM ScheduleHistory WHERE id = ?",
            (int(history_id),),
        )
        return ScheduleHistory.from_row(row) if row else None

    def list_recent(self, limit: int = 20) -> List[ScheduleHistory]:
        rows = self.fetchall(
            "SELECT id, schedule_time, version, strategy, batch_count, op_count, result_status, result_summary, created_by FROM ScheduleHistory ORDER BY id DESC LIMIT ?",
            (int(limit),),
        )
        return [ScheduleHistory.from_row(r) for r in rows]

    def get_by_version(self, version: int) -> Optional[ScheduleHistory]:
        row = self.fetchone(
            "SELECT id, schedule_time, version, strategy, batch_count, op_count, result_status, result_summary, created_by FROM ScheduleHistory WHERE version = ? ORDER BY id DESC LIMIT 1",
            (int(version),),
        )
        return ScheduleHistory.from_row(row) if row else None

    def get_latest_version(self) -> int:
        val = self.fetchvalue("SELECT COALESCE(MAX(version), 0) FROM ScheduleHistory", default=0)
        try:
            return int(val)
        except Exception:
            return 0

    def allocate_next_version(self) -> int:
        """
        原子分配排产版本号（避免并发下 MAX(version)+1 复用）。

        实现策略：
        - 使用 `ScheduleVersionSeq` 自增表分配唯一递增版本号（version=PRIMARY KEY AUTOINCREMENT）
        - 对齐：确保序列表不会落后于 `ScheduleHistory.max(version)`（兼容老库/从旧版本升级）
        - 允许版本号出现“跳号”（例如落库失败/回滚）；但保证不会复用
        """
        conn = self.conn
        try:
            # 兜底：即使 schema.sql 未执行到，也能按需创建（幂等）
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ScheduleVersionSeq (
                    version INTEGER PRIMARY KEY AUTOINCREMENT
                )
                """
            )

            # 计算对齐基线：取历史最大版本号 与 序列表最大值 的较大者
            row_h = conn.execute("SELECT COALESCE(MAX(version), 0) FROM ScheduleHistory").fetchone()
            max_history = int((row_h[0] if row_h else 0) or 0)
            row_s = conn.execute("SELECT COALESCE(MAX(version), 0) FROM ScheduleVersionSeq").fetchone()
            max_seq = int((row_s[0] if row_s else 0) or 0)

            baseline = int(max(max_history, max_seq))
            if baseline > 0 and baseline > max_seq:
                # 插入 baseline 作为“对齐锚点”，让下一次 DEFAULT VALUES 返回 baseline+1
                conn.execute(
                    "INSERT OR IGNORE INTO ScheduleVersionSeq(version) VALUES (?)",
                    (int(baseline),),
                )

            cur = conn.execute("INSERT INTO ScheduleVersionSeq DEFAULT VALUES")
            lastrowid = getattr(cur, "lastrowid", None)
            v = int(lastrowid) if lastrowid is not None else 0
            if v <= 0:
                # 兜底：极端情况下 lastrowid 不可用时再查一次
                row = conn.execute("SELECT COALESCE(MAX(version), 0) FROM ScheduleVersionSeq").fetchone()
                v = int((row[0] if row else 0) or 0)

            if int(v) <= 0:
                raise RuntimeError(f"allocate_next_version 返回非法版本号：{v!r}")
            return int(v)
        except Exception as e:
            if self.logger:
                try:
                    self.logger.error(f"分配排产版本号失败：{e}", exc_info=True)
                except Exception:
                    pass
            raise AppError(ErrorCode.DB_QUERY_ERROR, "分配排产版本号失败，请查看日志。", cause=e) from e

    def list_versions(self, limit: int = 30) -> List[Dict[str, Any]]:
        """
        返回最近版本列表（去重），用于页面下拉选择。
        """
        # 注意：strategy/result_status 不能用 MAX(text)（会变成字典序），需要取“最新一条记录”的值。
        rows = self.fetchall(
            """
            SELECT h.version, h.schedule_time, h.strategy, h.result_status, h.result_summary
            FROM ScheduleHistory h
            WHERE h.id = (
                SELECT h2.id
                FROM ScheduleHistory h2
                WHERE h2.version = h.version
                ORDER BY h2.schedule_time DESC, h2.id DESC
                LIMIT 1
            )
            ORDER BY h.version DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        return rows

    def create(self, payload: Dict[str, Any]) -> None:
        self.execute(
            """
            INSERT INTO ScheduleHistory
            (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(payload.get("version") or 1),
                payload.get("strategy"),
                payload.get("batch_count"),
                payload.get("op_count"),
                payload.get("result_status"),
                payload.get("result_summary"),
                payload.get("created_by"),
            ),
        )
