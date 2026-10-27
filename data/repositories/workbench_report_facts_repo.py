"""现场分析的计划完工范围明细与设备/人员名称映射。"""

from __future__ import annotations

from .base_repo import BaseRepository
from .schedule_detail_query import build_schedule_detail_sql
from .schedule_time_sql import register_schedule_time_sql_functions, time_dt
from .workbench_execution_repo import stored_report_values


class WorkbenchReportFactsRepository(BaseRepository):
    def __init__(self, conn, logger=None):
        super().__init__(conn, logger=logger)
        register_schedule_time_sql_functions(conn)

    def plan_rows(self, version, *, date_from, date_to, batch_id, limit):
        where, params = ["s.version = ?"], [version]
        if date_from is not None:
            # 和报表投影一致：按工厂当地的计划完工日（含起止日期），不是工序时间重叠。
            where.append("SUBSTR(" + time_dt("s", "end_time") + ", 1, 10) BETWEEN ? AND ?")
            params.extend([date_from, date_to])
        if batch_id is not None:
            where.append("bo.batch_id = ?")
            params.append(batch_id)
        return self.fetchall(build_schedule_detail_sql(where_clauses=where) + " LIMIT ?", params + [limit])

    def plan_resource_keys(self, version):
        return self.fetchall(
            """SELECT DISTINCT bo.batch_id, s.machine_id, m.name AS machine_name, s.operator_id, o.name AS operator_name
            FROM Schedule s
            LEFT JOIN BatchOperations bo ON bo.id = s.op_id
            LEFT JOIN Machines AS m ON m.machine_id = s.machine_id
            LEFT JOIN Operators AS o ON o.operator_id = s.operator_id
            WHERE s.version = ?""",
            (version,),
        )

    def actual_resource_refs(self, plan_ref):
        """Only resource identities used by the plan's operations; no ledger projections."""
        operations = """WITH operations AS (
            SELECT r.operation_ref FROM WorkbenchTaskRefs t
            JOIN WorkbenchPlanSourceRefs r ON r.ref=t.row_ref AND r.active=1
            WHERE t.plan_ref=?
        ) """
        refs = set()
        reports = self.iter_rows(operations + """SELECT v.values_json FROM operations o
            JOIN WorkbenchProductionReports p ON p.operation_ref=o.operation_ref
            JOIN WorkbenchProductionReportRevisions v ON v.report_ref=p.report_ref
            WHERE NOT EXISTS (SELECT 1 FROM WorkbenchProductionReportRevisions later
                WHERE later.report_ref=v.report_ref AND later.sequence>v.sequence)
            AND NOT EXISTS (SELECT 1 FROM WorkbenchProductionReportVoids void
                WHERE void.report_ref=p.report_ref)""", (plan_ref,))
        for row in reports:
            values = stored_report_values(row["values_json"])
            refs.update(values[field] for field in ("actual_machine_ref", "actual_operator_ref") if values.get(field))
        return refs
