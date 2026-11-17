"""现场分析的计划完工范围明细与设备/人员名称映射。"""

from __future__ import annotations

from datetime import date, datetime

from core.shared.local_datetime import datetime_to_us

from .base_repo import BaseRepository
from .schedule_detail_query import build_schedule_detail_sql


class WorkbenchReportFactsRepository(BaseRepository):
    def plan_rows(self, version, *, date_from, date_to, batch_id, limit):
        where, params = ["s.version = ?"], [version]
        if date_from is not None:
            # 和报表投影一致：按工厂当地的计划完工日（含起止日期），不是工序时间重叠。
            start_d = date.fromisoformat(date_from)
            end_d = date.fromisoformat(date_to)
            start_us = datetime_to_us(datetime(start_d.year, start_d.month, start_d.day))
            end_incl_us = datetime_to_us(datetime(end_d.year, end_d.month, end_d.day, 23, 59, 59, 999999))
            where.append("s.end_us >= ? AND s.end_us <= ?")
            params.extend([start_us, end_incl_us])
        if batch_id is not None:
            where.append("s.batch_id = ?")
            params.append(batch_id)
        return self.fetchall(build_schedule_detail_sql(where_clauses=where) + " LIMIT ?", params + [limit])

    def plan_resource_keys(self, version):
        return self.fetchall(
            """SELECT DISTINCT s.batch_id, s.machine_id, m.name AS machine_name, s.operator_id, o.name AS operator_name
            FROM Schedule s
            LEFT JOIN Machines AS m ON m.machine_id = s.machine_id
            LEFT JOIN Operators AS o ON o.operator_id = s.operator_id
            WHERE s.version = ?""",
            (version,),
        )

    def actual_resource_refs(self, plan_ref):
        """Only resource identities used by the plan's operations; no ledger projections."""
        rows = self.fetchall(
            """SELECT DISTINCT p.actual_machine_ref, p.actual_operator_ref
            FROM ScheduleHistory h
            JOIN Schedule s ON s.version = h.version
            JOIN WorkbenchProductionReports p ON p.operation_ref = s.operation_ref
            WHERE h.plan_ref = ?
              AND p.voided = 0
              AND (p.actual_machine_ref IS NOT NULL OR p.actual_operator_ref IS NOT NULL)""",
            (plan_ref,),
        )
        refs = set()
        for row in rows:
            if row["actual_machine_ref"] is not None:
                refs.add(row["actual_machine_ref"])
            if row["actual_operator_ref"] is not None:
                refs.add(row["actual_operator_ref"])
        return refs
