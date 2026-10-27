"""Resource and lifecycle constraints, rechecked under the outer command lock."""

from datetime import datetime

from core.algorithm_contracts.value_domains import OPERATION_SOURCES
from core.models.resource_capabilities import machine_types
from core.models.workbench_execution_input import reject
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.services.personnel.operator_qualification import OperatorQualificationError, OperatorQualificationService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_report_validation_repo import WorkbenchReportValidationRepository


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

    def validate(self, operation, values, *, previous_values):
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
    if operation["source"] not in OPERATION_SOURCES:
        reject("工序归属无法读取，请到基础资料确认自制或外协。", "constraint_conflict", 409)
    if not current or not plan or not plan["capabilities"]["report_actual"]:
        reject("这道工序在正式计划里没有可登记的安排。请先排产。", "plan_not_writable", 409)
    if task_ref is not None and task_ref != current["task_ref"]:
        reject("请刷新后选择当前正式计划的工序报工。", "plan_not_writable", 409)
    return current


def validate_projection_change(before, after):
    for item in after.data_gaps:
        if item["code"] in ("quantity_exceeded", "operation_retired"):
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


def _cycle_peer_periods(dependencies, operation):
    refs = dependencies.cycle_peers(operation)
    return [(ref, _actual_period(row)) for ref, row in zip(refs, dependencies.projections(refs))]


def merged_cycle_parted(dependencies, operation, before, after):
    """改动后同组里原本对得上、现在对不上的成员 (工序, 实际周期)，按工序顺序；与登记、更正同一口径。

    撤销不按这个拦：同组两道各有一条偏早的报工时，单独撤销哪条都会先对不上，只能先撤一条再逐道改齐。
    """
    mine, previous = _actual_period(after), _actual_period(before)
    if operation["source"] != "external" or mine == previous:
        return []
    return [peer for peer in _cycle_peer_periods(dependencies, operation)
            if _periods_conflict(mine, peer[1]) and not _periods_conflict(previous, peer[1])]


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
    blocker = _cycle_blocker(_cycle_peer_periods(dependencies, operation), mine, previous, correcting)
    if blocker is not None:
        ref, theirs = blocker
        reject("合并外协组的工序是一起送出、一起回厂的，同组各道的实际开工和实际完工要相同。同组第 "
               + str(dependencies.sequences[ref]) + " 道已登记" + _period_text(theirs)
               + "。请按相同时间填写；如果那道的时间不对，请先更正那条报工。", "constraint_conflict", 409)


def _retained_resource_refs(projection):
    machines, operators = set(), set()
    for report in projection.reports:
        if report.actual_machine_ref is not None:
            machines.add(report.actual_machine_ref)
        if report.actual_operator_ref is not None:
            operators.add(report.actual_operator_ref)
    return machines, operators


def _actual_period_basis(projection):
    """Deduplicate and join adjacent periods; keep overlaps and unknowns visible."""
    periods = {tuple(None if value is None else datetime.fromisoformat(value)
                     for value in (report.actual_start, report.actual_end)) for report in projection.reports}
    unresolved = frozenset((start, end) for start, end in periods if start is None or end is None or end <= start)
    coverage = []
    for start, end in sorted((start, end) for start, end in periods
                             if start is not None and end is not None and end > start):
        if coverage and start == coverage[-1][1]:
            coverage[-1] = (coverage[-1][0], end)
        else:
            coverage.append((start, end))
    return tuple(coverage), unresolved


def _report_resource_segments(projection):
    return tuple((report.actual_start, report.actual_end, report.actual_machine_ref, report.actual_operator_ref)
                 for report in sorted(projection.reports,
                                      key=lambda report: (report.actual_start or "", report.actual_end or "")))


def _constraint_signature(projection):
    return (projection.execution_state, projection.first_actual_start, projection.confirmed_finish,
            projection.known_completed_quantity, projection.unknown_record_count, _actual_period_basis(projection),
            *_retained_resource_refs(projection))


def execution_facts_changed(before, after):
    return (_constraint_signature(before) != _constraint_signature(after)
            or (bool(before.reports and after.reports and (len(before.reports) > 1 or len(after.reports) > 1))
                and _report_resource_segments(before) != _report_resource_segments(after)))


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


def _upstream_conflicts(after, upstream):
    if after.first_actual_start is None:
        return []
    return [{"code": "upstream_time_conflict", "operation_ref": row.operation_ref} for row in upstream
            if row.confirmed_finish and row.confirmed_finish > after.first_actual_start]


def _actual_resources_changed(before, after, source):
    before_resources = _retained_resource_refs(before)
    after_resources = _retained_resource_refs(after)
    if source == "external" and not any(after_resources):
        # 外协不占本厂设备人员，排产也从不按外协报工的设备人员安排（守卫见外协带资源即拒绝）；
        # 只把旧记录里的设备人员清空不算改了采用依据，否则这类旧数据既改不掉、也挡住所有排产。
        return False
    return before_resources != after_resources or (
        source != "external" and bool(before.reports and after.reports)
        and (len(before.reports) > 1 or len(after.reports) > 1)
        and _report_resource_segments(before) != _report_resource_segments(after)
    )


def _adopted_conflicts(before, after, current, revisions, source):
    if not current or not any(row["recorded_against_plan_ref"] != current["plan_ref"] for row in revisions):
        return []
    conflicts = []
    if before.known_completed_quantity != after.known_completed_quantity or before.first_actual_start != after.first_actual_start:
        conflicts.append({"code": "adopted_execution_basis_changed", "operation_ref": before.operation_ref})
    if before.execution_state == "complete" and after.execution_state != "complete":
        conflicts.append({"code": "adopted_completion_required", "operation_ref": before.operation_ref})
    if _actual_period_basis(before) != _actual_period_basis(after):
        conflicts.append({"code": "adopted_actual_period_changed", "operation_ref": before.operation_ref})
    if _actual_resources_changed(before, after, source):
        conflicts.append({"code": "adopted_actual_resource_changed", "operation_ref": before.operation_ref})
    return conflicts


def execution_conflicts(ledger, facts, before, after, revisions, *, dependencies, protect_plan=True,
                        include_downstream_active=False, task_map=None):
    """Check final actual neighbours; corrections also retain adopted-plan protection."""
    operation = facts["operations"][before.operation_ref]
    refs = dependencies.relatives(operation)
    upstream = dependencies.projections(dependencies.relatives(operation, predecessors=True))
    downstream = dependencies.projections(refs)
    current = facts["current_tasks"].get(before.operation_ref)
    plans = {} if not protect_plan else task_map if task_map is not None else ledger.task_map(refs, facts["plan"]["plan_ref"])
    conflicts = (_upstream_conflicts(after, upstream)
                 + _downstream_conflicts(before, after, downstream, plans)
                 + _adopted_conflicts(before, after, current, revisions, operation["source"]))
    if include_downstream_active:
        for row in downstream:
            if row.execution_state != "unreported" and not any(item["operation_ref"] == row.operation_ref for item in conflicts):
                conflicts.append({"code": "downstream_execution_exists", "operation_ref": row.operation_ref})
    return conflicts


def execution_conflict_details(ledger, facts, conflicts):
    """Public identities, reasons and exact official arrangements for report rejection/preview."""
    refs = list(dict.fromkeys(item["operation_ref"] for item in conflicts))
    operations = ledger.operation_rows(refs)
    plans = ledger.task_map(refs, facts["plan"]["plan_ref"])
    messages = {"upstream_time_conflict": "前道工序的实际完工时间与变更后保留的开工记录冲突",
                "downstream_execution_exists": "后道工序已有开工或报工记录",
                "downstream_requires_completion": "后道工序的执行或正式安排依赖本工序完工",
                "downstream_time_conflict": "后道工序时间与变更后的完工记录冲突",
                "adopted_execution_basis_changed": "当前正式计划使用了这次报工的数量或开工记录",
                "adopted_completion_required": "当前正式计划依赖这次完工记录",
                "adopted_actual_period_changed": "当前正式计划使用了这次报工的实际执行时段，变更会改变已确认的时段依据",
                "adopted_actual_resource_changed": "当前正式计划使用了这次报工的实际资源"}
    result = []
    for item in conflicts:
        operation = operations[item["operation_ref"]]
        task = plans.get(item["operation_ref"])
        plan = None if task is None else {"plan_ref": task["plan_ref"], "task_ref": task["task_ref"],
            "version": task["version"], "start": task["start_time"].replace(" ", "T"),
            "end": task["end_time"].replace(" ", "T")}
        result.append(dict(item, batch_id=operation["batch_id"], operation_code=operation["op_code"],
            piece_id=operation["piece_id"], operation_label=str(operation["seq"]) + " " + operation["op_type_name"],
            message=messages[item["code"]], plan=plan))
    return result
