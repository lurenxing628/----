from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, cast

from core.shared.local_datetime import datetime_to_us, format_local_datetime, us_to_datetime

from .base_repo import BaseRepository


def _display(us: int) -> str:
    """start_time/end_time 只作展示，由写入的微秒在这里一处生成。"""
    return format_local_datetime(us_to_datetime(us))


class MachineDowntimeRepository(BaseRepository):
    """设备停机时间段仓库（MachineDowntimes）。"""

    def list_active_overlaps_with_machine_names(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        return self.fetchall(
            """
            SELECT md.machine_id, m.name AS machine_name, md.start_us, md.end_us
            FROM MachineDowntimes md
            LEFT JOIN Machines m ON m.machine_id = md.machine_id
            WHERE md.status = 'active' AND md.start_us < ? AND md.end_us > ?
            """,
            (datetime_to_us(end), datetime_to_us(start)),
        )

    def create(self, payload: Dict[str, Any]) -> int:
        cur = self.execute(
            """
            INSERT INTO MachineDowntimes
            (machine_id, scope_type, scope_value, start_time, end_time, start_us, end_us, reason_code, reason_detail, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["machine_id"],
                payload["scope_type"],
                payload["scope_value"],
                _display(payload["start_us"]),
                _display(payload["end_us"]),
                payload["start_us"],
                payload["end_us"],
                payload["reason_code"],
                payload["reason_detail"],
                payload["status"],
            ),
        )
        return cast(int, cur.lastrowid)

    def update(self, downtime_id: int, updates: Dict[str, Any]) -> None:
        self.execute(
            """
            UPDATE MachineDowntimes
            SET start_time = ?, end_time = ?, start_us = ?, end_us = ?, reason_code = ?, reason_detail = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                _display(updates["start_us"]),
                _display(updates["end_us"]),
                updates["start_us"],
                updates["end_us"],
                updates["reason_code"],
                updates["reason_detail"],
                downtime_id,
            ),
        )

    def cancel(self, downtime_id: int) -> None:
        self.execute(
            "UPDATE MachineDowntimes SET status='cancelled', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (downtime_id,),
        )
