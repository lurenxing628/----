from __future__ import annotations

from typing import Any, Dict

from core.errors import BusinessError, ErrorCode

from .base_repo import BaseRepository


class ExternalGroupRepository(BaseRepository):
    """外部工序组仓库（ExternalGroups）。"""

    def create(self, group: Dict[str, Any]) -> None:
        self.execute(
            """
            INSERT INTO ExternalGroups
            (group_id, part_no, start_seq, end_seq, merge_mode, total_days, supplier_id, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                group["group_id"],
                group["part_no"],
                int(group["start_seq"]),
                int(group["end_seq"]),
                group["merge_mode"],
                group["total_days"],
                group["supplier_id"],
                group.get("remark"),
            ),
        )

    def update(self, group_id: str, updates: Dict[str, Any]) -> None:
        """
        更新外部工序组。

        说明：
        - 只更新 updates 中出现的字段
        - 允许显式清空 total_days/supplier_id/remark 为 NULL（用于 separate/merged 切换）
        """
        set_parts = [f"{key} = ?" for key in updates]
        sql = f"UPDATE ExternalGroups SET {', '.join(set_parts)} WHERE group_id = ?"
        cur = self.execute(sql, (*updates.values(), group_id))
        if cur.rowcount == 0:
            raise BusinessError(ErrorCode.EXTERNAL_GROUP_ERROR, f"外协工序组“{group_id}”不存在或已被删除")

    def delete_for_part(self, part_no: str, group_id: str) -> None:
        """删除某零件下的指定外协组（part_no 作为额外防护条件）。"""
        self.execute("DELETE FROM ExternalGroups WHERE part_no=? AND group_id=?", (part_no, group_id))

    def set_total_days(self, group_id: str, total_days: Any) -> None:
        """只改合并组总周期，不做存在性裁决（工时确认场景原语义）。"""
        self.execute("UPDATE ExternalGroups SET total_days=? WHERE group_id=?", (total_days, group_id))
