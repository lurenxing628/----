"""Resource and lifecycle constraints, rechecked under the outer command lock."""

from core.models.workbench_execution_input import reject
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.services.personnel.operator_qualification import OperatorQualificationError, OperatorQualificationService
from data.repositories.workbench_execution_repo import chunks
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository


class ReportResourceValidator:
    def __init__(self, conn):
        self.conn = conn
        self.identities = WorkbenchIdentityRepository(conn)
        self.entities = {}
        self.checked = set()
        self.machine_types = {}

    def preload(self, refs):
        for chunk in chunks(sorted(set(refs))):
            marks = ",".join("?" for _ in chunk)
            rows = self.conn.execute(f"""SELECT e.*, m.op_type_id AS machine_type FROM WorkbenchEntityRefs e
                LEFT JOIN Machines m ON e.kind='machine' AND e.active=1 AND m.machine_id=e.entity_key
                WHERE e.ref IN ({marks})""", chunk).fetchall()
            for row in rows:
                self.entities[row["ref"]] = WorkbenchEntityIdentity(row["ref"], row["kind"], row["entity_key"], row["revision"], bool(row["active"]))
                if row["kind"] == "machine":
                    self.machine_types[row["entity_key"]] = row["machine_type"]

    def resolve(self, ref, kind):
        if ref is None:
            return None
        if ref not in self.entities:
            self.entities[ref] = self.identities.get(ref)
        entity = self.entities[ref]
        if entity is None or not entity.active or entity.kind != kind:
            reject("填的设备或人员不存在，或者记录已失效；旧编号不会指到同号的新设备人员。请刷新后重新选择。", "constraint_conflict", 409)
        return entity.entity_key

    def validate(self, operation, values):
        key = (operation["source"], operation["op_type_id"], values.get("actual_machine_ref"), values.get("actual_operator_ref"))
        if key in self.checked:
            return
        machine = self.resolve(values.get("actual_machine_ref"), "machine")
        operator = self.resolve(values.get("actual_operator_ref"), "operator")
        if machine is not None:
            if not operation["op_type_id"] or self.machine_types.get(machine) != operation["op_type_id"]:
                reject("填的设备工种和这道工序对不上。请到资料总览核对设备工种。", "constraint_conflict", 409)
        if operator is not None:
            try:
                OperatorQualificationService(self.conn).require(operator_id=operator, op_type_id=operation["op_type_id"], machine_id=machine)
            except OperatorQualificationError as exc:
                reject(str(exc), "constraint_conflict", 409)
        self.checked.add(key)


def require_current(facts, operation_ref, task_ref=None):
    operation = facts["operations"][operation_ref]
    current = facts["current_tasks"].get(operation_ref)
    plan = facts["plan"]
    if not operation["identity_active"] or operation["id"] is None:
        reject("这道工序已经被删除，旧报工不会改到同号的新工序。请刷新后重新选择。", "entity_not_found", 404)
    if operation["source"] not in ("internal", "external"):
        reject("这道工序是自制还是外协读不出来，系统不猜要填哪些设备人员。请到基础资料确认归属。", "constraint_conflict", 409)
    if operation_ref in facts["unresolved"]:
        reject("历史报工记录的编号分不清是哪一条，系统不猜。请先复核后再登记。", "constraint_conflict", 409)
    if not current or not plan or not plan["capabilities"]["report_actual"]:
        reject("这道工序在正式计划里没有可登记的安排。请先排产。", "plan_not_writable", 409)
    if task_ref is not None and task_ref != current["task_ref"]:
        reject("只能按当前正式计划登记；原来的安排不会自动跟到新版本。请刷新后重新选择工序。", "plan_not_writable", 409)
    return current


def validate_legacy_link(legacy, legacy_fact_ref, values):
    if legacy_fact_ref is None:
        return
    row = next((row for row in legacy if row["legacy_fact_ref"] == legacy_fact_ref), None)
    if row is None or row["event_type"] != "finish" or not row["recorded_against_task_ref"]:
        reject("指定的历史记录不是这道工序能明确补齐的完工记录。请重新选择要补齐的记录。", "constraint_conflict", 409)
    known = {"actual_end": row["event_time"].replace(" ", "T"), "completed_quantity": row["quantity_done"]}
    for field, value in known.items():
        if value is not None and values.get(field) is not None and values[field] != value:
            reject("补齐的内容和原来的完工记录冲突，系统不会覆盖原记录。请核对后重新提交。", "constraint_conflict", 409)


def validate_projection_change(before, after):
    for item in after.data_gaps:
        if item["code"] in ("quantity_exceeded", "invalid_legacy_sequence", "legacy_identity_unresolved", "operation_retired"):
            reject(item["message"], "constraint_conflict", 409)
    if after.target_quantity is None and after.known_completed_quantity > before.known_completed_quantity:
        reject("这道工序的目标数量读不出来，判断不了有没有超报。请到批次管理核对数量。", "constraint_conflict", 409)


def _constraint_signature(projection):
    return (projection.execution_state, projection.first_actual_start, projection.confirmed_finish,
            projection.known_completed_quantity, projection.unknown_record_count,
            [(r.report_ref, r.actual_start, r.actual_end, r.completed_quantity, r.actual_machine_ref,
              r.actual_operator_ref) for r in projection.reports])


def _successor_refs(conn, op):
    rows = conn.execute("""SELECT bo.id, bo.status, o.ref AS operation_ref FROM BatchOperations bo
        JOIN WorkbenchPlanSourceRefs o ON o.kind='operation' AND o.active=1 AND o.source_key=CAST(bo.id AS TEXT)
        WHERE bo.batch_id=? AND bo.piece_id IS ? AND bo.seq>? ORDER BY bo.seq LIMIT 10001""",
        (op["batch_id"], op["piece_id"], op["seq"])).fetchall()
    if len(rows) > 10000:
        reject("要检查的后道工序太多，超过上限，系统不会跳过检查。请缩小这次报工的范围后重试。", "query_too_large", 413)
    return [row["operation_ref"] for row in rows]


def _downstream_conflicts(before, after, downstream, plans):
    conflicts = []
    reopened = before.execution_state == "complete" and after.execution_state != "complete"
    for projection in downstream:
        planned = plans.get(projection.operation_ref)
        if reopened and (projection.execution_state != "unreported" or planned is not None):
            conflicts.append({"code": "downstream_requires_completion", "operation_ref": projection.operation_ref})
        finish = after.confirmed_finish
        starts = [projection.first_actual_start]
        if planned:
            starts.append(planned["start_time"].replace(" ", "T"))
        if finish and any(start and finish > start for start in starts):
            conflicts.append({"code": "downstream_time_conflict", "operation_ref": projection.operation_ref})
    return conflicts


def _adopted_conflicts(before, after, current, revisions):
    if not current or not any(row["recorded_against_plan_ref"] != current["plan_ref"] for row in revisions):
        return []
    conflicts = []
    if before.known_completed_quantity != after.known_completed_quantity or before.first_actual_start != after.first_actual_start:
        conflicts.append({"code": "adopted_execution_basis_changed", "operation_ref": before.operation_ref})
    if before.execution_state == "complete" and after.execution_state != "complete":
        conflicts.append({"code": "adopted_completion_required", "operation_ref": before.operation_ref})
    before_resources = [(r.report_ref, r.actual_machine_ref, r.actual_operator_ref) for r in before.reports]
    after_resources = [(r.report_ref, r.actual_machine_ref, r.actual_operator_ref) for r in after.reports]
    if before_resources != after_resources:
        conflicts.append({"code": "adopted_actual_resource_changed", "operation_ref": before.operation_ref})
    return conflicts


def correction_conflicts(conn, ledger, facts, before, after, revisions):
    """Protect factual downstream production and adopted schedules, not inferred IDs."""
    if _constraint_signature(before) == _constraint_signature(after):
        return []
    refs = _successor_refs(conn, facts["operations"][before.operation_ref])
    downstream = ledger.project_operations(refs) if refs else []
    current = facts["current_tasks"].get(before.operation_ref)
    plans = ledger.repo.task_map(refs, facts["plan"]["plan_ref"])
    return _downstream_conflicts(before, after, downstream, plans) + _adopted_conflicts(before, after, current, revisions)
