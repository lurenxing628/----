from __future__ import annotations

from typing import Any, Dict, List


def fetch_overdue_base_rows(conn, version: int) -> List[Dict[str, Any]]:
    """
    取数：超期清单基础行（含 due_date 与 finish_time）。
    """
    v = int(version or 0)
    rows = conn.execute(
        """
        SELECT
          b.batch_id AS batch_id,
          b.part_no AS part_no,
          b.part_name AS part_name,
          b.quantity AS quantity,
          b.due_date AS due_date,
          MAX(s.end_time) AS finish_time
        FROM Batches b
        LEFT JOIN BatchOperations bo ON bo.batch_id = b.batch_id
        LEFT JOIN Schedule s ON s.op_id = bo.id AND s.version = ?
        WHERE b.due_date IS NOT NULL AND TRIM(CAST(b.due_date AS TEXT)) <> ''
        GROUP BY b.batch_id
        ORDER BY b.due_date ASC, b.batch_id ASC
        """,
        (v,),
    ).fetchall()
    return [dict(r) for r in (rows or [])]


def fetch_downtime_rows(conn, start_time: str, end_time: str) -> List[Dict[str, Any]]:
    """
    取数：停机区间（active）与设备名称。

    参数：
    - start_time/end_time 为字符串（%Y-%m-%d %H:%M:%S）
    - 查询条件为区间重叠：start < end_time AND end > start_time
    """
    rows = conn.execute(
        """
        SELECT md.machine_id, m.name AS machine_name, md.start_time, md.end_time, md.reason_code, md.reason_detail
        FROM MachineDowntimes md
        LEFT JOIN Machines m ON m.machine_id = md.machine_id
        WHERE md.status = 'active'
          AND md.start_time < ?
          AND md.end_time > ?
        ORDER BY md.machine_id, md.start_time, md.id
        """,
        (end_time, start_time),
    ).fetchall()
    return [dict(r) for r in (rows or [])]

