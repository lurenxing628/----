"""现场分析的计划完工范围明细与设备/人员名称映射。"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable

from .base_repo import BaseRepository
from .schedule_detail_query import build_schedule_detail_sql
from .schedule_time_sql import register_schedule_time_sql_functions, time_dt

_NAME_SQL_PREFIX = {
    "machine": "SELECT machine_id, name FROM Machines WHERE machine_id IN (",
    "operator": "SELECT operator_id, name FROM Operators WHERE operator_id IN (",
}
RESOURCE_NAME_KINDS = tuple(_NAME_SQL_PREFIX)
_NAME_CHUNK = 400


class WorkbenchReportFactsRepository(BaseRepository):
    def __init__(self, conn, logger=None):
        super().__init__(conn, logger=logger)
        register_schedule_time_sql_functions(conn)

    def plan_rows(self, version, *, date_from=None, date_to=None, batch_id=None, limit):
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
        return self.fetchall("""SELECT DISTINCT bo.batch_id, s.machine_id, s.operator_id
            FROM Schedule s LEFT JOIN BatchOperations bo ON bo.id=s.op_id WHERE s.version=?""", (version,))

    def actual_resource_refs(self, plan_ref):
        """Only resource identities used by the plan's operations; no ledger projections."""
        operations = """WITH operations AS (
            SELECT r.operation_ref FROM WorkbenchTaskRefs t
            JOIN WorkbenchPlanSourceRefs r ON r.ref=t.row_ref AND r.active=1
            WHERE t.plan_ref=?
        ) """
        legacy = self.iter_rows(operations + """SELECT DISTINCT f.actual_machine_ref, f.actual_operator_ref
            FROM operations o JOIN WorkbenchExecutionLegacyFacts f ON f.operation_ref=o.operation_ref""", (plan_ref,))
        refs = {ref for row in legacy for ref in row.values() if ref}
        reports = self.iter_rows(operations + """SELECT v.values_json FROM operations o
            JOIN WorkbenchProductionReports p ON p.operation_ref=o.operation_ref
            JOIN WorkbenchProductionReportRevisions v ON v.report_ref=p.report_ref
            WHERE NOT EXISTS (SELECT 1 FROM WorkbenchProductionReportRevisions later
                WHERE later.report_ref=v.report_ref AND later.sequence>v.sequence)
            AND NOT EXISTS (SELECT 1 FROM WorkbenchProductionReportVoids void
                WHERE void.report_ref=p.report_ref)""", (plan_ref,))
        for row in reports:
            values = json.loads(row["values_json"])
            refs.update(values[field] for field in ("actual_machine_ref", "actual_operator_ref") if values.get(field))
        return refs

    def resource_names(self, kind: str, keys: Iterable[str]) -> Dict[str, Any]:
        """{str(业务键): name}，按 400 个一批查询；kind 只能是 machine / operator。"""
        if kind not in _NAME_SQL_PREFIX:
            raise ValueError("unsupported resource kind: " + repr(kind))
        prefix = _NAME_SQL_PREFIX[kind]
        values = list(keys)
        labels: Dict[str, Any] = {}
        for start in range(0, len(values), _NAME_CHUNK):
            chunk = values[start:start + _NAME_CHUNK]
            sql = prefix + ",".join("?" for _ in chunk) + ")"
            labels.update((str(row[0]), row[1]) for row in self.execute(sql, chunk))
        return labels
