from __future__ import annotations

from typing import Any, Dict, List, cast

from .base_repo import BaseRepository
from .schedule_time_sql import (
    overlap_or_bad_time_sql,
    register_schedule_time_sql_functions,
    require_dt_for_sql,
)


class MachineDowntimeRepository(BaseRepository):
    """设备停机时间段仓库（MachineDowntimes）。"""

    def __init__(self, conn, logger=None):
        super().__init__(conn, logger=logger)
        register_schedule_time_sql_functions(conn)

    def list_active_overlaps_with_machine_names(self, start_time: str, end_time: str) -> List[Dict[str, Any]]:
        parsed_start_time = require_dt_for_sql(start_time, "停机重叠查询时间写法不对，无法读取停机线索")
        parsed_end_time = require_dt_for_sql(end_time, "停机重叠查询时间写法不对，无法读取停机线索")
        return self.fetchall(
            f"""
            SELECT md.machine_id, m.name AS machine_name, md.start_time, md.end_time, md.reason_code, md.reason_detail
            FROM MachineDowntimes md
            LEFT JOIN Machines m ON m.machine_id = md.machine_id
            WHERE md.status = 'active'
              AND {overlap_or_bad_time_sql("md")}
            ORDER BY md.machine_id, md.start_time, md.id
            """,
            (parsed_end_time, parsed_start_time),
        )

    def create(self, payload: Dict[str, Any]) -> int:
        cur = self.execute(
            """
            INSERT INTO MachineDowntimes
            (machine_id, scope_type, scope_value, start_time, end_time, reason_code, reason_detail, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["machine_id"],
                payload["scope_type"],
                payload["scope_value"],
                payload["start_time"],
                payload["end_time"],
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
            SET start_time = ?, end_time = ?, reason_code = ?, reason_detail = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                updates["start_time"],
                updates["end_time"],
                updates["reason_code"],
                updates["reason_detail"],
                int(downtime_id),
            ),
        )

    def cancel(self, downtime_id: int) -> None:
        self.execute(
            "UPDATE MachineDowntimes SET status='cancelled', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (int(downtime_id),),
        )
