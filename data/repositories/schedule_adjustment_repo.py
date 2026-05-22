from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

from core.models.schedule_adjustment import ScheduleAdjustmentChange, ScheduleAdjustmentDraft

from .base_repo import BaseRepository

_DRAFT_COLUMNS = (
    "draft_id",
    "base_version",
    "base_plan_role",
    "status",
    "created_by",
    "reason",
    "change_count",
    "audit_summary",
    "expires_at",
    "created_at",
    "updated_at",
)

_CHANGE_COLUMNS = (
    "id",
    "draft_id",
    "schedule_id",
    "op_id",
    "change_type",
    "from_start",
    "from_end",
    "to_start",
    "to_end",
    "from_machine_id",
    "to_machine_id",
    "from_operator_id",
    "to_operator_id",
    "validation_status",
    "validation_message",
    "created_at",
)


def _columns_sql(columns: Sequence[str]) -> str:
    return ", ".join(columns)


def _draft(item: Union[ScheduleAdjustmentDraft, Dict[str, Any]]) -> ScheduleAdjustmentDraft:
    return item if isinstance(item, ScheduleAdjustmentDraft) else ScheduleAdjustmentDraft.from_row(item)


def _change(item: Union[ScheduleAdjustmentChange, Dict[str, Any]]) -> ScheduleAdjustmentChange:
    return item if isinstance(item, ScheduleAdjustmentChange) else ScheduleAdjustmentChange.from_row(item)


class ScheduleAdjustmentRepository(BaseRepository):
    """甘特图模拟调整 Draft 草稿仓库。"""

    def get_draft(self, draft_id: str) -> Optional[ScheduleAdjustmentDraft]:
        row = self.fetchone(
            f"SELECT {_columns_sql(_DRAFT_COLUMNS)} FROM ScheduleAdjustmentDraft WHERE draft_id = ?",
            (str(draft_id),),
        )
        return ScheduleAdjustmentDraft.from_row(row) if row else None

    def create_draft(
        self, draft: Union[ScheduleAdjustmentDraft, Dict[str, Any]]
    ) -> ScheduleAdjustmentDraft:
        item = _draft(draft)
        self.execute(
            """
            INSERT INTO ScheduleAdjustmentDraft (
                draft_id, base_version, base_plan_role, status, created_by, reason, audit_summary, expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.draft_id,
                int(item.base_version),
                item.base_plan_role,
                item.status,
                item.created_by,
                item.reason,
                item.audit_summary,
                item.expires_at,
            ),
        )
        created = self.get_draft(item.draft_id)
        if created is None:
            raise RuntimeError("调整草稿写入后没有返回记录")
        return created

    def list_drafts_by_base(self, *, base_version: int, base_plan_role: str) -> List[ScheduleAdjustmentDraft]:
        rows = self.fetchall(
            f"""
            SELECT {_columns_sql(_DRAFT_COLUMNS)}
            FROM ScheduleAdjustmentDraft
            WHERE base_version = ? AND base_plan_role = ?
            ORDER BY updated_at DESC, created_at DESC
            """,
            (int(base_version), str(base_plan_role)),
        )
        return [ScheduleAdjustmentDraft.from_row(row) for row in rows]

    def update_draft_status(
        self, *, draft_id: str, status: str, reason: Optional[str] = None
    ) -> ScheduleAdjustmentDraft:
        self.execute(
            """
            UPDATE ScheduleAdjustmentDraft
            SET status = ?,
                reason = COALESCE(?, reason),
                updated_at = CURRENT_TIMESTAMP
            WHERE draft_id = ?
            """,
            (str(status), reason, str(draft_id)),
        )
        draft = self.get_draft(draft_id)
        if draft is None:
            raise RuntimeError(f"调整草稿不存在：{draft_id}")
        return draft

    def delete_draft(self, draft_id: str) -> int:
        cur = self.execute("DELETE FROM ScheduleAdjustmentDraft WHERE draft_id = ?", (str(draft_id),))
        return int(cur.rowcount or 0)

    def create_change(
        self, change: Union[ScheduleAdjustmentChange, Dict[str, Any]]
    ) -> ScheduleAdjustmentChange:
        item = _change(change)
        cur = self.execute(
            """
            INSERT INTO ScheduleAdjustmentChange (
                draft_id, schedule_id, op_id, change_type,
                from_start, from_end, to_start, to_end,
                from_machine_id, to_machine_id, from_operator_id, to_operator_id,
                validation_status, validation_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.draft_id,
                item.schedule_id,
                int(item.op_id),
                item.change_type,
                item.from_start,
                item.from_end,
                item.to_start,
                item.to_end,
                item.from_machine_id,
                item.to_machine_id,
                item.from_operator_id,
                item.to_operator_id,
                item.validation_status,
                item.validation_message,
            ),
        )
        item.id = int(cur.lastrowid) if cur.lastrowid is not None else item.id
        self._refresh_draft_count(item.draft_id)
        return item

    def list_changes(self, draft_id: str) -> List[ScheduleAdjustmentChange]:
        rows = self.fetchall(
            f"""
            SELECT {_columns_sql(_CHANGE_COLUMNS)}
            FROM ScheduleAdjustmentChange
            WHERE draft_id = ?
            ORDER BY id
            """,
            (str(draft_id),),
        )
        return [ScheduleAdjustmentChange.from_row(row) for row in rows]

    def _refresh_draft_count(self, draft_id: str) -> None:
        self.execute(
            """
            UPDATE ScheduleAdjustmentDraft
            SET change_count = (
                    SELECT COUNT(1)
                    FROM ScheduleAdjustmentChange
                    WHERE draft_id = ?
                ),
                updated_at = CURRENT_TIMESTAMP
            WHERE draft_id = ?
            """,
            (str(draft_id), str(draft_id)),
        )
