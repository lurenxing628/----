from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

from core.models import Schedule

from .base_repo import BaseRepository


class ScheduleRepository(BaseRepository):
    """排程结果仓库（Schedule）。"""

    def get(self, schedule_id: int) -> Optional[Schedule]:
        row = self.fetchone(
            "SELECT id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version, created_at FROM Schedule WHERE id = ?",
            (int(schedule_id),),
        )
        return Schedule.from_row(row) if row else None

    def list_by_version(self, version: int) -> List[Schedule]:
        rows = self.fetchall(
            "SELECT id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version, created_at FROM Schedule WHERE version = ? ORDER BY start_time, id",
            (int(version),),
        )
        return [Schedule.from_row(r) for r in rows]

    def list_between(self, start_time: str, end_time: str, version: Optional[int] = None) -> List[Schedule]:
        sql = "SELECT id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version, created_at FROM Schedule WHERE start_time >= ? AND end_time <= ?"
        params: List[Any] = [start_time, end_time]
        if version is not None:
            sql += " AND version = ?"
            params.append(int(version))
        sql += " ORDER BY start_time, id"
        rows = self.fetchall(sql, tuple(params))
        return [Schedule.from_row(r) for r in rows]

    def list_by_machine(self, machine_id: str, version: Optional[int] = None) -> List[Schedule]:
        if version is None:
            rows = self.fetchall(
                "SELECT id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version, created_at FROM Schedule WHERE machine_id = ? ORDER BY start_time, id",
                (machine_id,),
            )
        else:
            rows = self.fetchall(
                "SELECT id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version, created_at FROM Schedule WHERE machine_id = ? AND version = ? ORDER BY start_time, id",
                (machine_id, int(version)),
            )
        return [Schedule.from_row(r) for r in rows]

    def create(self, schedule: Union[Schedule, Dict[str, Any]]) -> Schedule:
        s = schedule if isinstance(schedule, Schedule) else Schedule.from_row(schedule)
        cur = self.execute(
            """
            INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (int(s.op_id), s.machine_id, s.operator_id, s.start_time, s.end_time, s.lock_status, int(s.version)),
        )
        s.id = int(cur.lastrowid) if cur.lastrowid is not None else s.id
        return s

    def bulk_create(self, schedules: Sequence[Union[Schedule, Dict[str, Any]]]) -> int:
        params = []
        for item in schedules:
            s = item if isinstance(item, Schedule) else Schedule.from_row(item)
            params.append((int(s.op_id), s.machine_id, s.operator_id, s.start_time, s.end_time, s.lock_status, int(s.version)))
        cur = self.executemany(
            "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            params,
        )
        return cur.rowcount

    def delete(self, schedule_id: int) -> None:
        self.execute("DELETE FROM Schedule WHERE id = ?", (int(schedule_id),))

    def delete_by_version(self, version: int) -> None:
        self.execute("DELETE FROM Schedule WHERE version = ?", (int(version),))

    def delete_by_op(self, op_id: int) -> None:
        self.execute("DELETE FROM Schedule WHERE op_id = ?", (int(op_id),))

