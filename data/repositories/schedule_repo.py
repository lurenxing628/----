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

    def list_version_rows_by_op_ids_start_range(
        self,
        *,
        version: int,
        op_ids: Sequence[int],
        start_time: str,
        end_time: str,
        chunk_size: int = 900,
    ) -> List[Dict[str, Any]]:
        """
        查询指定版本在 [start_time, end_time) 范围内的排程记录（按 start_time 过滤），并限定 op_id 集合。

        主要用于“冻结窗口”：
        - sqlite 默认变量上限 999，因此这里默认分块查询
        - 返回 dict 行（不转模型），便于上层做 seed 构建
        """
        ids: List[int] = []
        for x in (op_ids or []):
            try:
                v = int(x)
            except (TypeError, ValueError):
                continue
            if v > 0:
                ids.append(v)
        if not ids:
            return []

        out: List[Dict[str, Any]] = []
        for i in range(0, len(ids), int(chunk_size)):
            chunk = ids[i : i + int(chunk_size)]
            placeholders = ",".join(["?"] * len(chunk))
            sql = f"""
            SELECT op_id, machine_id, operator_id, start_time, end_time
            FROM Schedule
            WHERE version = ?
              AND op_id IN ({placeholders})
              AND start_time >= ?
              AND start_time < ?
            """
            params: List[Any] = [int(version)] + list(chunk) + [start_time, end_time]
            out.extend(self.fetchall(sql, tuple(params)))
        return out

    def list_overlapping_with_details(self, start_time: str, end_time: str, version: int) -> List[Dict[str, Any]]:
        """
        查询与给定时间区间“有重叠”的排程记录，并补齐甘特图/周计划所需的关联信息。

        说明：
        - 使用“区间重叠”条件，避免跨周任务被遗漏：
          start_time < end AND end_time > start
        - 返回 dict 行（带 join 字段），供服务层直接拼装输出。
        """
        sql = """
        SELECT
            s.id AS schedule_id,
            s.op_id AS op_id,
            s.start_time AS start_time,
            s.end_time AS end_time,
            s.version AS version,

            bo.op_code AS op_code,
            bo.batch_id AS batch_id,
            bo.piece_id AS piece_id,
            bo.seq AS seq,
            bo.op_type_name AS op_type_name,
            bo.source AS source,
            bo.status AS op_status,
            s.machine_id AS machine_id,
            s.operator_id AS operator_id,
            bo.supplier_id AS supplier_id,

            b.part_no AS part_no,
            b.part_name AS part_name,
            b.due_date AS due_date,
            b.priority AS priority,

            m.name AS machine_name,
            o.name AS operator_name,
            sup.name AS supplier_name
        FROM Schedule s
        LEFT JOIN BatchOperations bo ON bo.id = s.op_id
        LEFT JOIN Batches b ON b.batch_id = bo.batch_id
        LEFT JOIN Machines m ON m.machine_id = s.machine_id
        LEFT JOIN Operators o ON o.operator_id = s.operator_id
        LEFT JOIN Suppliers sup ON sup.supplier_id = bo.supplier_id
        WHERE s.version = ?
          AND s.start_time < ?
          AND s.end_time > ?
        ORDER BY s.start_time, s.id
        """
        return self.fetchall(sql, (int(version), end_time, start_time))

    def list_by_version_with_details(self, version: int) -> List[Dict[str, Any]]:
        """
        查询指定版本的全部排程记录，并补齐甘特图/关键链识别所需的关联信息。

        说明：
        - 返回 dict 行（带 join 字段），供服务层直接拼装输出。
        """
        sql = """
        SELECT
            s.id AS schedule_id,
            s.op_id AS op_id,
            s.start_time AS start_time,
            s.end_time AS end_time,
            s.version AS version,

            bo.op_code AS op_code,
            bo.batch_id AS batch_id,
            bo.piece_id AS piece_id,
            bo.seq AS seq,
            bo.op_type_name AS op_type_name,
            bo.source AS source,
            bo.status AS op_status,
            s.machine_id AS machine_id,
            s.operator_id AS operator_id,
            bo.supplier_id AS supplier_id,

            b.part_no AS part_no,
            b.part_name AS part_name,
            b.due_date AS due_date,
            b.priority AS priority,

            m.name AS machine_name,
            o.name AS operator_name,
            sup.name AS supplier_name
        FROM Schedule s
        LEFT JOIN BatchOperations bo ON bo.id = s.op_id
        LEFT JOIN Batches b ON b.batch_id = bo.batch_id
        LEFT JOIN Machines m ON m.machine_id = s.machine_id
        LEFT JOIN Operators o ON o.operator_id = s.operator_id
        LEFT JOIN Suppliers sup ON sup.supplier_id = bo.supplier_id
        WHERE s.version = ?
        ORDER BY s.start_time, s.id
        """
        return self.fetchall(sql, (int(version),))

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

