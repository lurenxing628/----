from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from core.models import ExternalGroup

from .base_repo import BaseRepository


class ExternalGroupRepository(BaseRepository):
    """外部工序组仓库（ExternalGroups）。"""

    def get(self, group_id: str) -> Optional[ExternalGroup]:
        row = self.fetchone(
            "SELECT group_id, part_no, start_seq, end_seq, merge_mode, total_days, supplier_id, remark, created_at FROM ExternalGroups WHERE group_id = ?",
            (group_id,),
        )
        return ExternalGroup.from_row(row) if row else None

    def list_by_part(self, part_no: str) -> List[ExternalGroup]:
        rows = self.fetchall(
            "SELECT group_id, part_no, start_seq, end_seq, merge_mode, total_days, supplier_id, remark, created_at FROM ExternalGroups WHERE part_no = ? ORDER BY start_seq",
            (part_no,),
        )
        return [ExternalGroup.from_row(r) for r in rows]

    def create(self, group: Union[ExternalGroup, Dict[str, Any]]) -> ExternalGroup:
        g = group if isinstance(group, ExternalGroup) else ExternalGroup.from_row(group)
        self.execute(
            """
            INSERT INTO ExternalGroups
            (group_id, part_no, start_seq, end_seq, merge_mode, total_days, supplier_id, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                g.group_id,
                g.part_no,
                int(g.start_seq),
                int(g.end_seq),
                g.merge_mode,
                g.total_days,
                g.supplier_id,
                g.remark,
            ),
        )
        return g

    def update(self, group_id: str, updates: Dict[str, Any]) -> None:
        self.execute(
            """
            UPDATE ExternalGroups
            SET
              start_seq = COALESCE(?, start_seq),
              end_seq = COALESCE(?, end_seq),
              merge_mode = COALESCE(?, merge_mode),
              total_days = COALESCE(?, total_days),
              supplier_id = COALESCE(?, supplier_id),
              remark = COALESCE(?, remark)
            WHERE group_id = ?
            """,
            (
                updates.get("start_seq"),
                updates.get("end_seq"),
                updates.get("merge_mode"),
                updates.get("total_days"),
                updates.get("supplier_id"),
                updates.get("remark"),
                group_id,
            ),
        )

    def delete(self, group_id: str) -> None:
        self.execute("DELETE FROM ExternalGroups WHERE group_id = ?", (group_id,))

    def delete_by_part(self, part_no: str) -> None:
        self.execute("DELETE FROM ExternalGroups WHERE part_no = ?", (part_no,))

