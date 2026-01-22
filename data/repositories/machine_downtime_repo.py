from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.models import MachineDowntime

from .base_repo import BaseRepository


class MachineDowntimeRepository(BaseRepository):
    """设备停机时间段仓库（MachineDowntimes）。"""

    def get(self, downtime_id: int) -> Optional[MachineDowntime]:
        row = self.fetchone(
            """
            SELECT id, machine_id, start_time, end_time, reason_code, reason_detail,
                   status, created_at, updated_at
            FROM MachineDowntimes
            WHERE id = ?
            """,
            (int(downtime_id),),
        )
        return MachineDowntime.from_row(row) if row else None

    def list_by_machine(self, machine_id: str, include_cancelled: bool = False) -> List[MachineDowntime]:
        sql = """
            SELECT id, machine_id, start_time, end_time, reason_code, reason_detail,
                   status, created_at, updated_at
            FROM MachineDowntimes
            WHERE machine_id = ?
        """
        params: List[Any] = [machine_id]
        if not include_cancelled:
            sql += " AND status = 'active'"
        sql += " ORDER BY start_time DESC, id DESC"
        rows = self.fetchall(sql, tuple(params))
        return [MachineDowntime.from_row(r) for r in rows]

    def has_overlap(
        self,
        machine_id: str,
        start_time: str,
        end_time: str,
        exclude_id: Optional[int] = None,
    ) -> bool:
        """
        判断是否与已有“有效(active)”停机区间重叠。
        重叠条件：NOT(end<=existing_start OR start>=existing_end)
        """
        sql = """
            SELECT 1
            FROM MachineDowntimes
            WHERE machine_id = ?
              AND status = 'active'
              AND NOT (end_time <= ? OR start_time >= ?)
        """
        params: List[Any] = [machine_id, start_time, end_time]
        if exclude_id is not None:
            sql += " AND id <> ?"
            params.append(int(exclude_id))
        sql += " LIMIT 1"
        return bool(self.fetchvalue(sql, tuple(params)))

    def create(self, payload: Dict[str, Any]) -> MachineDowntime:
        d = payload if isinstance(payload, MachineDowntime) else MachineDowntime.from_row(payload)
        self.execute(
            """
            INSERT INTO MachineDowntimes
            (machine_id, start_time, end_time, reason_code, reason_detail, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                d.machine_id,
                d.start_time,
                d.end_time,
                d.reason_code,
                d.reason_detail,
                d.status or "active",
            ),
        )
        # 返回时把 id 补上（sqlite lastrowid）
        try:
            new_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        except Exception:
            new_id = None
        d.id = new_id
        return d

    def update(self, downtime_id: int, updates: Dict[str, Any]) -> None:
        if not updates:
            return
        allowed = {"start_time", "end_time", "reason_code", "reason_detail", "status"}
        set_parts: List[str] = []
        params: List[Any] = []
        for key in ("start_time", "end_time", "reason_code", "reason_detail", "status"):
            if key in updates and key in allowed:
                set_parts.append(f"{key} = ?")
                params.append(updates.get(key))
        if not set_parts:
            return
        set_parts.append("updated_at = CURRENT_TIMESTAMP")
        params.append(int(downtime_id))
        sql = f"UPDATE MachineDowntimes SET {', '.join(set_parts)} WHERE id = ?"
        self.execute(sql, tuple(params))

    def cancel(self, downtime_id: int) -> None:
        self.execute(
            "UPDATE MachineDowntimes SET status='cancelled', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (int(downtime_id),),
        )

