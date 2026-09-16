"""Bounded, SELECT-only execution facts; mutations live in the report repository."""

import json

from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_contract_issues
from core.infrastructure.workbench_execution_void_schema import execution_void_contract_issues
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution_input import MAX_FACT_ROWS, MAX_OPERATIONS, public_ref, reject
from data.repositories.base_repo import BaseRepository


def chunks(values, size=300):
    for start in range(0, len(values), size):
        yield values[start:start + size]


class WorkbenchExecutionRepository(BaseRepository):
    def require_schema(self):
        if execution_ledger_contract_issues(self.conn) or execution_void_contract_issues(self.conn):
            raise WorkbenchCommandRejected("execution_ledger_unavailable", "报工数据库结构不完整，请联系维护人员升级数据库。")

    def clock(self):
        row = self.fetchone("SELECT revision FROM WorkbenchExecutionLedgerClock WHERE singleton=1")
        plan = self.fetchone("SELECT revision FROM WorkbenchPlanIdentityClock WHERE singleton=1")
        if row is None or plan is None:
            reject("报工或计划状态资料缺失，请联系维护人员核对。", "execution_ledger_unavailable", 409)
        return {"ledger_revision": row["revision"], "plan_revision": plan["revision"]}

    def operation_rows(self, refs):
        values = list(dict.fromkeys(public_ref(ref) for ref in refs))
        if len(values) > MAX_OPERATIONS:
            reject("执行工序超过单次10000条读取上限。", "query_too_large", 413)
        rows = []
        for chunk in chunks(values):
            marks = ",".join("?" for _ in chunk)
            rows.extend(self.fetchall(f"""SELECT o.ref AS operation_ref, o.active AS identity_active,
                bo.*, b.quantity AS batch_quantity FROM WorkbenchPlanSourceRefs o
                LEFT JOIN BatchOperations bo ON o.active=1 AND bo.id=CAST(o.source_key AS INTEGER)
                    AND CAST(bo.id AS TEXT)=o.source_key
                LEFT JOIN Batches b ON b.batch_id=bo.batch_id
                WHERE o.kind='operation' AND o.ref IN ({marks})""", chunk))
        result = {row["operation_ref"]: row for row in rows}
        if set(result) != set(values):
            reject("工序关联资料缺失，请刷新重选；仍无法打开时请联系维护人员。", "entity_not_found", 404)
        return result

    def task(self, task_ref):
        public_ref(task_ref)
        row = self.task_headers([task_ref]).get(task_ref)
        if row is None or row["operation_ref"] is None:
            reject("任务不存在或报工关联资料缺失，请刷新重选。", "entity_not_found", 404)
        return row

    def task_headers(self, refs):
        result = {}
        for chunk in chunks(list(refs)):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall(f"""SELECT t.ref AS task_ref, t.plan_ref, r.operation_ref,
            r.operation_id AS op_id, r.active AS row_active, r.kind, r.version,
            r.source_key, p.active AS plan_active FROM WorkbenchTaskRefs t
            JOIN WorkbenchPlanSourceRefs r ON r.ref=t.row_ref
            JOIN WorkbenchPlanSourceRefs p ON p.ref=t.plan_ref WHERE t.ref IN ({marks})""", chunk)
            result.update((row["task_ref"], row) for row in rows)
        return result

    def task_map(self, operation_refs, plan_ref):
        result = {}
        if plan_ref is None:
            return result
        for chunk in chunks(list(operation_refs)):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall(f"""SELECT t.ref AS task_ref, t.plan_ref, r.operation_ref,
                r.operation_id AS op_id, r.version, s.start_time, s.end_time, s.machine_id,
                s.operator_id, s.lock_status FROM WorkbenchPlanSourceRefs r
                JOIN WorkbenchTaskRefs t ON t.row_ref=r.ref AND t.plan_ref=?
                LEFT JOIN Schedule s ON r.kind='schedule_row' AND s.id=CAST(r.source_key AS INTEGER)
                    AND s.op_id=r.operation_id AND s.version=r.version
                WHERE r.operation_ref IN ({marks}) AND r.active=1""", [plan_ref] + chunk)
            for row in rows:
                if row["operation_ref"] in result:
                    reject("同一计划中工序安排身份重复。", "constraint_conflict", 409)
                result[row["operation_ref"]] = row
        return result

    def page_tasks(self, plan_ref, size, after):
        public_ref(plan_ref)
        if type(size) is not int or not 1 <= size <= 500:
            reject("执行任务分页大小须为1至500。", status=400)
        if after is not None:
            public_ref(after)
        return self.fetchall("""SELECT t.ref AS task_ref, r.operation_ref FROM WorkbenchTaskRefs t
            JOIN WorkbenchPlanSourceRefs r ON r.ref=t.row_ref AND r.active=1
            WHERE t.plan_ref=? AND t.ref>? ORDER BY t.ref LIMIT ?""", (plan_ref, after or "", size + 1))

    def reports(self, refs):
        result, count = {}, 0
        for chunk in chunks(list(refs)):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall(f"""SELECT p.*, v.revision_ref, v.sequence, v.previous_revision_ref,
                v.action, v.values_json, v.reason, v.local_operator, v.declared_operator,
                v.recorded_at AS revision_at, v.request_key, c.receipt_ref
                FROM WorkbenchProductionReports p
                JOIN WorkbenchProductionReportRevisions v ON v.report_ref=p.report_ref
                LEFT JOIN WorkbenchCommandReceipts c ON c.request_key=v.request_key
                WHERE p.operation_ref IN ({marks}) ORDER BY p.report_ref, v.sequence LIMIT ?""",
                                 chunk + [MAX_FACT_ROWS + 1 - count])
            count += len(rows)
            if count > MAX_FACT_ROWS:
                reject("报工及更正历史超过读取上限，请缩小范围。", "query_too_large", 413)
            for row in rows:
                row["values"] = json.loads(row.pop("values_json"))
                result.setdefault(row["operation_ref"], {}).setdefault(row["report_ref"], []).append(row)
        return result

    def legacy(self, refs):
        result, count = {}, 0
        for chunk in chunks(list(refs)):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall(f"SELECT * FROM WorkbenchExecutionLegacyFacts WHERE operation_ref IN ({marks}) ORDER BY id LIMIT ?",
                                 chunk + [MAX_FACT_ROWS + 1 - count])
            count += len(rows)
            if count > MAX_FACT_ROWS:
                reject("历史现场记录超过读取上限，请缩小范围。", "query_too_large", 413)
            for row in rows:
                result.setdefault(row["operation_ref"], []).append(row)
        return result

    def report_voids(self, refs):
        result, count = {}, 0
        for chunk in chunks(list(refs)):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall(f"""SELECT v.*, c.receipt_ref FROM WorkbenchProductionReportVoids v
                JOIN WorkbenchProductionReports p ON p.report_ref=v.report_ref
                LEFT JOIN WorkbenchCommandReceipts c ON c.request_key=v.request_key
                WHERE p.operation_ref IN ({marks}) ORDER BY v.report_ref LIMIT ?""", chunk + [MAX_FACT_ROWS + 1 - count])
            count += len(rows)
            if count > MAX_FACT_ROWS:
                reject("报工撤销历史超过读取上限，请缩小范围。", "query_too_large", 413)
            result.update((row["report_ref"], row) for row in rows)
        return result

    def unresolved_operations(self, operations):
        ids = {row["id"]: ref for ref, row in operations.items() if row["id"] is not None}
        result = set()
        for chunk in chunks(list(ids)):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall(f"""SELECT DISTINCT op_id FROM WorkbenchExecutionLegacyFacts
                WHERE (operation_ref IS NULL OR recorded_against_task_ref IS NULL) AND op_id IN ({marks})""", chunk)
            result.update(ids[row["op_id"]] for row in rows)
        return result

    def report_header(self, *, report_ref=None, report_no=None):
        if report_ref is not None:
            public_ref(report_ref)
            return self.fetchone("SELECT * FROM WorkbenchProductionReports WHERE report_ref=?", (report_ref,))
        return self.fetchone("SELECT * FROM WorkbenchProductionReports WHERE report_no=?", (report_no,))

    def report_headers(self, values, *, by_number=False):
        field = "report_no" if by_number else "report_ref"
        result = {}
        for chunk in chunks(list(values)):
            marks = ",".join("?" for _ in chunk)
            rows = self.fetchall(f"SELECT * FROM WorkbenchProductionReports WHERE {field} IN ({marks})", chunk)
            result.update((row[field], row) for row in rows)
        return result

    def resources(self, refs):
        rows = []
        for chunk in chunks(sorted(set(refs))):
            marks = ",".join("?" for _ in chunk)
            rows.extend(self.fetchall(f"""SELECT e.ref, e.kind, e.entity_key AS business_code, e.active,
                CASE WHEN e.active=0 THEN NULL WHEN e.kind='machine' THEN m.name
                     WHEN e.kind='operator' THEN o.name END AS label
                FROM WorkbenchEntityRefs e
                LEFT JOIN Machines m ON e.kind='machine' AND e.active=1 AND m.machine_id=e.entity_key
                LEFT JOIN Operators o ON e.kind='operator' AND e.active=1 AND o.operator_id=e.entity_key
                WHERE e.ref IN ({marks})""", chunk))
        return [{"kind": row["kind"], "ref": row["ref"], "business_code": row["business_code"],
                 "label": row["label"] or row["business_code"], "available": bool(row["active"])} for row in rows]
