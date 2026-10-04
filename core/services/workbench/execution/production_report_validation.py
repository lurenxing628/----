"""Resource and lifecycle constraints, rechecked under the outer command lock."""

from datetime import datetime

from core.models.resource_capabilities import machine_types
from core.models.workbench_execution_input import reject
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.services.personnel.operator_qualification import OperatorQualificationError, OperatorQualificationService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_report_validation_repo import WorkbenchReportValidationRepository

from .production_report_dependencies import ReportDependencies


def _reject_external_resources(operation, values):
    # 外协不占本厂设备和人员，排产守卫也按这条拒绝；保留原资源的更正同样不放行，
    # 否则写进去的报工会让之后每次排产都被拦下。
    if operation["source"] == "external" and (values.get("actual_machine_ref") or values.get("actual_operator_ref")):
        reject("外协工序不占用本厂设备和人员，实际设备、实际人员请留空；原报工已填的，请用「更正」清除。跟进人请填在经办人里。",
               "constraint_conflict", 409)


class ReportResourceValidator:
    def __init__(self, conn):
        self.conn = conn
        self.identities = WorkbenchIdentityRepository(conn)
        self.repo = WorkbenchReportValidationRepository(conn)
        self.entities = {}
        self.checked = set()
        self.machine_types = {}

    def preload(self, refs):
        for row in self.repo.entity_rows_with_machine_type(refs):
            self.entities[row["ref"]] = WorkbenchEntityIdentity(row["ref"], row["kind"], row["entity_key"], row["revision"], bool(row["active"]))
            if row["kind"] == "machine":
                self.machine_types[row["entity_key"]] = set(machine_types({"op_type_id": row["machine_type"], "op_type_ids": row["op_type_ids"]}))

    def resolve(self, ref, kind):
        if ref is None:
            return None
        if ref not in self.entities:
            self.entities[ref] = self.identities.get(ref)
        entity = self.entities[ref]
        if entity is None or not entity.active or entity.kind != kind:
            reject("设备或人员已失效，请刷新重选。", "constraint_conflict", 409)
        return entity.entity_key

    def validate(self, operation, values, *, previous_values=None):
        if values != previous_values:
            # 原样未改的旧行（如 Excel 导出后原样导回）不在这里拒绝，交给排产检查指出要更正的报工。
            _reject_external_resources(operation, values)
        # An existing report is evidence for its original actual resources and
        # interval. Maintaining quantity/hours/remark must retain their permanent
        # identities, but must not reapply today's capabilities or permissions.
        preserved_actual = previous_values is not None and all(
            values.get(field) == previous_values.get(field) for field in
            ("actual_machine_ref", "actual_operator_ref", "actual_start", "actual_end"))
        if preserved_actual:
            self.resolve(values.get("actual_machine_ref"), "machine")
            self.resolve(values.get("actual_operator_ref"), "operator")
            return  # Historical validation never fills the current-qualification cache.
        key = (operation["source"], operation["op_type_id"], values.get("actual_machine_ref"), values.get("actual_operator_ref"))
        if key in self.checked:
            return
        machine = self.resolve(values.get("actual_machine_ref"), "machine")
        operator = self.resolve(values.get("actual_operator_ref"), "operator")
        if machine is not None:
            if not operation["op_type_id"] or operation["op_type_id"] not in self.machine_types.get(machine, set()):
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
        reject("工序已删除，请刷新重选。", "entity_not_found", 404)
    if operation["source"] not in ("internal", "external"):
        reject("工序归属无法读取，请到基础资料确认自制或外协。", "constraint_conflict", 409)
    if operation_ref in facts["unresolved"]:
        reject("历史报工关联记录不明确，请核对后再登记。", "constraint_conflict", 409)
    if not current or not plan or not plan["capabilities"]["report_actual"]:
        reject("这道工序在正式计划里没有可登记的安排。请先排产。", "plan_not_writable", 409)
    if task_ref is not None and task_ref != current["task_ref"]:
        reject("请刷新后选择当前正式计划的工序报工。", "plan_not_writable", 409)
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
            reject("补填内容与原完工记录冲突，请核对后重试。", "constraint_conflict", 409)


def validate_projection_change(before, after):
    for item in after.data_gaps:
        if item["code"] in ("quantity_exceeded", "invalid_legacy_sequence", "legacy_identity_unresolved", "operation_retired"):
            reject(item["message"], "constraint_conflict", 409)
    if after.target_quantity is None and after.known_completed_quantity > before.known_completed_quantity:
        reject("这道工序的目标数量读不出来，判断不了有没有超报。请到批次管理核对数量。", "constraint_conflict", 409)


def _actual_period(projection):
    return tuple(None if value is None else datetime.fromisoformat(value)
                 for value in (projection.first_actual_start, projection.confirmed_finish))


def _periods_conflict(mine, theirs):
    return any(left is not None and right is not None and left != right for left, right in zip(mine, theirs))


def _periods_agree(mine, theirs):
    """两边都填了的时间都相同，且至少有一项两边都填了；只报了开工的那道也算和整组一致。"""
    shared = [(left, right) for left, right in zip(mine, theirs) if left is not None and right is not None]
    return bool(shared) and all(left == right for left, right in shared)


def _period_text(period):
    start, end = (value.isoformat(sep=" ") if value is not None else "未填" for value in period)
    return "实际开工 " + start + "、实际完工 " + end


def _joins_split_group(mine, periods):
    """其余各道之间本来就对不上，而这道改成了和其中一道一致。"""
    split = any(_periods_conflict(first, second) for index, first in enumerate(periods) for second in periods[index + 1:])
    return split and any(_periods_agree(mine, theirs) for theirs in periods)


def _cycle_blocker(peers, mine, previous, correcting):
    """返回挡住这次登记的同组成员 (工序, 实际周期)；可以放行时返回 None。"""
    conflicting = [peer for peer in peers if _periods_conflict(mine, peer[1])]
    if not correcting:
        return next(iter(conflicting), None)
    # 原本和这道一致的成员先不管（整组逐道挪到新时间）；原本对不上的，更正后要对上。
    parted = [peer for peer in conflicting if _periods_agree(previous, peer[1])]
    unresolved = [peer for peer in conflicting if not _periods_agree(previous, peer[1])]
    if not unresolved or not _joins_split_group(mine, [theirs for _, theirs in peers]):
        return next(iter(unresolved), None)
    # 其余各道之间本来就对不上（如三道时间各不相同的旧数据），一次更正不可能和每道都对上：
    # 改成和其中一道一致、又没和原本一致的成员分开，就放行，再逐道改齐。
    return next(iter(parted), None)


def validate_merged_cycle(dependencies, operation, before, after, changed):
    """合并外协组一起送出、一起回厂，排产只按同一个实际周期保留整组。

    补登的时间必须和同组已登记的一致。更正允许先把原本一致的整组中的一道改到新时间，
    再逐道改齐（排产检查会提示未改齐的组）；原本就对不上的，更正后必须对上；
    其余各道之间也对不上时，更正后至少和其中一道对上。
    """
    mine, previous = _actual_period(after), _actual_period(before)
    if operation["source"] != "external" or mine == previous:
        return
    correcting = bool(changed) and all(row["action"] == "correct" for row in changed)
    refs = dependencies.cycle_peers(operation)
    peers = [(ref, _actual_period(row)) for ref, row in zip(refs, dependencies.projections(refs))]
    blocker = _cycle_blocker(peers, mine, previous, correcting)
    if blocker is not None:
        ref, theirs = blocker
        reject("合并外协组的工序是一起送出、一起回厂的，同组各道的实际开工和实际完工要相同。同组第 "
               + str(dependencies.sequences[ref]) + " 道已登记" + _period_text(theirs)
               + "。请按相同时间填写；如果那道的时间不对，请先更正那条报工。", "constraint_conflict", 409)


def _constraint_signature(projection):
    return (projection.execution_state, projection.first_actual_start, projection.confirmed_finish,
            projection.known_completed_quantity, projection.unknown_record_count,
            [(r.report_ref, r.actual_start, r.actual_end, r.completed_quantity, r.actual_machine_ref,
              r.actual_operator_ref) for r in projection.reports])


def _downstream_conflicts(before, after, downstream, plans, dependencies):
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
        if (finish and not dependencies.same_merged_cycle(after.operation_ref, projection.operation_ref)
                and any(start and finish > start for start in starts)):
            conflicts.append({"code": "downstream_time_conflict", "operation_ref": projection.operation_ref})
    return conflicts


def _upstream_conflicts(after, upstream, dependencies):
    if after.first_actual_start is None:
        return []
    return [{"code": "upstream_time_conflict", "operation_ref": row.operation_ref} for row in upstream
            if row.confirmed_finish and row.confirmed_finish > after.first_actual_start
            and not dependencies.same_merged_cycle(after.operation_ref, row.operation_ref)]


def _actual_resources_changed(before, after, source):
    before_resources = [(r.report_ref, r.actual_machine_ref, r.actual_operator_ref) for r in before.reports]
    after_resources = [(r.report_ref, r.actual_machine_ref, r.actual_operator_ref) for r in after.reports]
    if source == "external" and [row[0] for row in before_resources] == [row[0] for row in after_resources]:
        # 外协不占本厂设备人员，排产也从不按外协报工的设备人员安排（守卫见外协带资源即拒绝）；
        # 只把旧记录里的设备人员清空不算改了采用依据，否则这类旧数据既改不掉、也挡住所有排产。
        after_resources = [previous if row[1:] == (None, None) else row for previous, row in zip(before_resources, after_resources)]
    return before_resources != after_resources


def _adopted_conflicts(before, after, current, revisions, source):
    if not current or not any(row["recorded_against_plan_ref"] != current["plan_ref"] for row in revisions):
        return []
    conflicts = []
    if before.known_completed_quantity != after.known_completed_quantity or before.first_actual_start != after.first_actual_start:
        conflicts.append({"code": "adopted_execution_basis_changed", "operation_ref": before.operation_ref})
    if before.execution_state == "complete" and after.execution_state != "complete":
        conflicts.append({"code": "adopted_completion_required", "operation_ref": before.operation_ref})
    if _actual_resources_changed(before, after, source):
        conflicts.append({"code": "adopted_actual_resource_changed", "operation_ref": before.operation_ref})
    return conflicts


def execution_conflicts(ledger, facts, before, after, revisions, *, dependencies=None, protect_plan=True):
    """Check final actual neighbours; corrections also retain adopted-plan protection."""
    if _constraint_signature(before) == _constraint_signature(after):
        return []
    dependencies = dependencies or ReportDependencies(ledger, [after])
    operation = facts["operations"][before.operation_ref]
    refs = dependencies.relatives(operation)
    upstream = dependencies.projections(dependencies.relatives(operation, predecessors=True))
    downstream = dependencies.projections(refs)
    current = facts["current_tasks"].get(before.operation_ref)
    plans = ledger.task_map(refs, facts["plan"]["plan_ref"]) if protect_plan else {}
    return (_upstream_conflicts(after, upstream, dependencies)
            + _downstream_conflicts(before, after, downstream, plans, dependencies)
            + _adopted_conflicts(before, after, current, revisions, operation["source"]))
