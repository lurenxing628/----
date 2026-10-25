from __future__ import annotations

from typing import Any, Mapping, Sequence

from .base_repo import BaseRepository


class ScheduleRepository(BaseRepository):
    """排程结果仓库（Schedule）。"""

    def bulk_create(self, schedules: Sequence[Mapping[str, Any]]) -> int:
        return self.executemany(
            "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                (
                    item["op_id"],
                    item["machine_id"],
                    item["operator_id"],
                    item["start_time"],
                    item["end_time"],
                    item["lock_status"],
                    item["version"],
                )
                for item in schedules
            ),
        ).rowcount

