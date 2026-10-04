"""Bind scheduling to the batch contexts used by preflight and batch detail."""

from collections import defaultdict
from types import SimpleNamespace

from core.errors import AppError
from core.models.operation_execution_event import (
    EXECUTION_STATUS_COMPLETED,
    EXECUTION_STATUS_PAUSED,
    EXECUTION_STATUS_PROCESSING,
)
from core.models.workbench_preflight import issue
from core.services.scheduler.contracts.external_context import (
    context_group_key,
    context_problem,
    member_index,
    merged_supplier_problem,
)
from core.services.scheduler.run.schedule_execution_guardrails import build_execution_guardrails_from_projections
from core.services.scheduler.run.schedule_execution_resource_facts import collect_resource_execution_facts
from core.services.scheduler.run.schedule_input_seed_metadata import (
    merged_actual_group_intervals,
    merged_external_group_identity,
)
from core.services.scheduler.schedule_service import ScheduleService
from core.services.workbench.execution.ledger import ExecutionLedgerService
from core.services.workbench.facts.run_input_codec import restore_execution_projections
from core.services.workbench.facts.run_input_rows import fail
from data.repositories.schedule_execution_facts_repo import ScheduleExecutionFactsRepository


def prime_template_cache(svc, tables, batches, operations):
    contexts = {row["operation_id"]: row for row in tables.get("BatchExternalContexts", [])}
    members = member_index(contexts, tables.get("BatchOperations", []))
    for op in operations:
        if op.source != "external":
            continue
        problem = context_problem(contexts.get(op.id), operation_id=op.id,
                                  part_no=batches[op.batch_id].part_no, sequence=op.seq)
        if problem:
            fail("external_context_invalid", problem, op_id=op.id)
        row = contexts[op.id]
        problem = merged_supplier_problem(row, op.supplier_id,
            members.get((op.batch_id, context_group_key(row), getattr(op, "piece_id", None))))
        if problem:
            fail("external_context_invalid", problem, op_id=op.id)
    svc._aps_schedule_input_cache = {"batch": dict(batches), "external_contexts": contexts,
                                     "external_members": members, "external_contexts_bound": True}


def _merged_groups(tables, batches, operations):
    contexts = {row["operation_id"]: row for row in tables.get("BatchExternalContexts", [])}
    groups = {}
    for op in operations:
        if op.source != "external":
            continue
        context = contexts.get(op.id)
        if context is None or context_problem(context, operation_id=op.id, part_no=batches[op.batch_id].part_no, sequence=op.seq):
            continue
        group = SimpleNamespace(merge_mode=context["merge_mode"], group_id=context_group_key(context))
        groups[op.id] = merged_external_group_identity(op, group=group)
    return groups


def _cycle_members(groups, periods, actual_ids):
    return {op_id: {"start": periods[group][0].isoformat(), "end": periods[group][1].isoformat()}
            for op_id, group in groups.items() if op_id not in actual_ids and group in periods}


def external_execution_cycles(tables, batches, operations, seeds, actual_ids):
    """Use proven actual periods with valid immutable batch/group/piece bindings."""
    groups = _merged_groups(tables, batches, operations)
    return _cycle_members(groups, merged_actual_group_intervals(groups, seeds, actual_ids), actual_ids)


def _time(value):
    return value.isoformat(sep=" ")


def _actual_periods(facts, groups, seeds, actual_ids, rows):
    """与排产同口径收集已报工成员的实际周期；同组对不上的不抛异常，改为指出是哪几道。"""
    members = defaultdict(dict)
    for seed in seeds:
        if seed["op_id"] in actual_ids and groups.get(seed["op_id"]) is not None:
            members[groups[seed["op_id"]]][seed["op_id"]] = (seed["start_time"], seed["end_time"])
    periods, problems = {}, []
    for identity, values in members.items():
        if len(set(values.values())) == 1:
            periods[identity] = next(iter(values.values()))
            continue
        ordered = sorted(values, key=lambda op_id: rows[op_id]["seq"])
        detail = "；".join(f"第 {rows[op_id]['seq']} 道 {_time(values[op_id][0])} 至 {_time(values[op_id][1])}" for op_id in ordered)
        problems.append(facts.public_issue(issue("external_cycle_actuals_differ",
            "合并外协组各道工序报工的实际起止不一致（" + detail + "），排产会被拦下。同组工序是一起送出、一起回厂的，"
            "请到现场记录把同组报工更正成同一实际开工、完工时间。"), rows[ordered[0]]))
    return periods, problems


def preflight_external_cycles(facts, batches, operations, projections):
    """Return frozen cycles plus explicit blockers for split actuals.

    同组未报工成员的锁定或不重排时段保留安排是否与实际周期一致，由 preflight_held 按排产同一保留范围核对。
    """
    contexts = {row["operation_id"]: row for row in facts.tables.get("BatchExternalContexts", [])}
    if not any(op["source"] == "external" and (contexts.get(op["id"]) or {}).get("merge_mode") == "merged"
               and projections[facts.operation_ref(op)]["first_actual_start"] for op in operations):
        return {}, []
    svc = ScheduleService(facts.conn)
    version = svc.history_repo.get_latest_version()
    prior = prior_execution_projections(facts, version, projections)
    models = [SimpleNamespace(**op) for op in operations]
    _, fixed, completed, seeds, _, _ = build_execution_guardrails_from_projections(
        svc, models, prev_version=version, execution_projections=prior)
    batch_models = {batch["batch_id"]: SimpleNamespace(**batch) for batch in batches}
    rows = {op["id"]: op for op in operations}
    groups = _merged_groups(facts.tables, batch_models, models)
    periods, problems = _actual_periods(facts, groups, seeds, fixed | completed, rows)
    cycles = _cycle_members(groups, periods, fixed | completed)
    return cycles, problems


def prior_execution_projections(facts, version, projections):
    rows = ScheduleExecutionFactsRepository(facts.conn).latest_plan_rows(version)
    refs = {facts.operation_refs[row["op_id"]] for row in rows}
    supplied = dict(projections)
    missing = sorted(refs - set(supplied))
    ledger = ExecutionLedgerService(facts.conn)
    for offset in range(0, len(missing), 10000):
        supplied.update({item.operation_ref: item.to_dict() for item in ledger.project_operations(missing[offset:offset + 10000])})
    return restore_execution_projections([supplied[ref] for ref in sorted(refs)])


_SEEDED = (EXECUTION_STATUS_PROCESSING, EXECUTION_STATUS_PAUSED, EXECUTION_STATUS_COMPLETED)


def _holds_resource(row):
    # 旧现场记录的设备人员可能没有对上编号，按原始设备人员号也算。
    return any(row.get(key) is not None for key in ("actual_machine_ref", "actual_operator_ref", "actual_machine_id", "actual_operator_id"))


def _planned_external(facts, version):
    planned = {row["op_id"] for row in facts.schedule_through(version)}
    return {facts.operation_refs[op["id"]]: op for op in facts.tables["BatchOperations"]
            if op["source"] == "external" and op["id"] in planned and op["id"] in facts.operation_refs}


def _resource_bearing_external(facts, version, projections):
    external = _planned_external(facts, version)
    supplied = {ref: projections[ref] for ref in external if ref in projections}
    missing = sorted(set(external) - set(supplied))
    ledger = ExecutionLedgerService(facts.conn)
    for offset in range(0, len(missing), 10000):
        supplied.update((row.operation_ref, row.to_dict()) for row in ledger.project_operations(missing[offset:offset + 10000]))
    return {op["id"]: (op, supplied[ref]) for ref, op in external.items()
            if any(_holds_resource(row) for row in supplied[ref]["reports"] + supplied[ref]["legacy_facts"])}


def _external_resource_issue(facts, op, projection, *, this_run_only):
    label = f"外协工序（第 {op['seq']} 道 {op['op_type_name']}）"
    numbers = [row["report_no"] for row in projection["reports"] if _holds_resource(row)]
    if numbers:
        message = (label + "的报工 " + "、".join(numbers) + " 填了本厂设备或人员，排产会被拦下（只排其他批次也一样）。"
                   "请到现场记录更正这条报工，清除实际设备和实际人员；跟进人请填在经办人里。")
    elif this_run_only:
        message = label + "的历史现场记录带了本厂设备或人员，选这批排产会被拦下。可以先不选这批，并联系维护人员核对这条历史记录。"
    else:
        message = label + "的历史现场记录带了本厂设备或人员，排产会被拦下（只排其他批次也一样）。请联系维护人员核对这条历史记录。"
    return facts.public_issue(issue("external_actual_resource_conflict", message), op)


def _guard_verdict(guard_facts, op_id, selected):
    """守卫两处拒绝外协带资源：要按报工核对的工序（整次排产都拦），选中且保留执行记录的工序（选这批才拦）。"""
    fact = guard_facts.get(op_id)
    if fact is None:
        return None
    if fact.ledger_operation_ref is not None and "execution_ledger_external_resource_conflict" in fact.execution_protection_reasons:
        return "all_runs"
    if op_id in selected and fact.actual_status in _SEEDED and (fact.actual_machine_id is not None or fact.actual_operator_id is not None):
        return "this_run"
    return None


def external_resource_issues(facts, svc, operations, projections, version):
    """与排产守卫同一份执行事实核对外协记录里的本厂设备人员，先指出要更正的报工或要核对的旧记录。

    只先投影正式计划里的外协工序；有带资源的记录时才按守卫口径整体核对，平时不多读。
    """
    candidates = _resource_bearing_external(facts, version, projections) if version is not None else {}
    if not candidates:
        return []
    try:
        guard_facts, _, _ = collect_resource_execution_facts(
            svc, prev_version=version, execution_projections=prior_execution_projections(facts, version, projections))
    except (AppError, ValueError, TypeError, KeyError, OverflowError):
        # 执行记录本身核对不了时排产也会失败；仍逐条指出带资源的外协记录，按会拦下整次排产提示。
        guard_facts = None
    selected = {op["id"] for op in operations}
    issues = []
    for op_id, (op, projection) in sorted(candidates.items(), key=lambda pair: (pair[1][0]["batch_id"], pair[1][0]["seq"])):
        verdict = "all_runs" if guard_facts is None else _guard_verdict(guard_facts, op_id, selected)
        if verdict is not None:
            issues.append(_external_resource_issue(facts, op, projection, this_run_only=verdict == "this_run"))
    return issues
