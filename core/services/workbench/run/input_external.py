"""Bind scheduling to the batch contexts used by preflight and batch detail."""

from collections import defaultdict

from core.models.workbench_preflight import issue
from core.services.scheduler.contracts.external_context import (
    context_group_key,
    context_problem,
    member_index,
    merged_supplier_problem,
)
from core.services.scheduler.run.schedule_execution_guardrails import build_execution_guardrails_from_projections
from core.services.scheduler.run.schedule_input_seed_metadata import (
    merged_actual_group_intervals,
    merged_group_identity,
)
from core.services.scheduler.run.schedule_template_lookup import FrozenExternalContext
from core.services.workbench.execution.ledger import ExecutionLedgerService
from core.services.workbench.facts.run_input_rows import fail
from core.services.workbench.facts.stored_algo_inputs import stored_batch, stored_batch_operation
from data.repositories.sqlite_rows import sql_order


def verified_external_contexts(tables, batches, operations):
    """本次排产的外协工序在同一份快照里只核对一次冻结周期记录，按工序编号交给排产输入构建。"""
    contexts = {row["operation_id"]: row for row in tables["BatchExternalContexts"]}
    members = member_index(contexts, tables["BatchOperations"])
    verified = {}
    for op in operations:
        if op.source != "external":
            continue
        problem = context_problem(contexts.get(op.id), operation_id=op.id, part_no=batches[op.batch_id].part_no, sequence=op.seq)
        if problem:
            fail("external_context_invalid", problem, op_id=op.id)
        row = contexts[op.id]
        group_key = context_group_key(row)
        problem = merged_supplier_problem(row, op.supplier_id, members.get((op.batch_id, group_key, op.piece_id)))
        if problem:
            fail("external_context_invalid", problem, op_id=op.id)
        verified[op.id] = FrozenExternalContext(row, group_key)
    return verified


def _merged_groups(tables, batches, operations):
    contexts = {row["operation_id"]: row for row in tables["BatchExternalContexts"]}
    groups = {}
    for op in operations:
        if op.source != "external":
            continue
        context = contexts.get(op.id)
        if context is None or context_problem(context, operation_id=op.id, part_no=batches[op.batch_id].part_no, sequence=op.seq):
            continue
        groups[op.id] = merged_group_identity(op.batch_id, op.piece_id, merge_mode=context["merge_mode"],
                                              group_id=context_group_key(context))
    return groups


def execution_groups(facts, batches, operations):
    key = tuple(sorted(op.id for op in operations))
    if key not in facts.external_groups:
        facts.external_groups[key] = _merged_groups(facts.tables, batches, operations)
    return facts.external_groups[key]


def _cycle_members(groups, periods, actual_ids):
    return {op_id: {"start": periods[group][0].isoformat(), "end": periods[group][1].isoformat()}
            for op_id, group in groups.items() if op_id not in actual_ids and group in periods}


def external_execution_cycles(facts, batches, operations, seeds, actual_ids):
    """Use proven actual periods with valid immutable batch/group/piece bindings."""
    groups = execution_groups(facts, batches, operations)
    return _cycle_members(groups, merged_actual_group_intervals(groups, seeds, actual_ids), actual_ids)


def _time(value):
    return value.isoformat(sep=" ")


def _actual_periods(facts, groups, seeds, rows):
    """与排产同口径收集已报工成员的实际周期；同组对不上的不抛异常，改为指出是哪几道。"""
    members = defaultdict(dict)
    for seed in seeds:
        if groups.get(seed["op_id"]) is not None:
            members[groups[seed["op_id"]]][seed["op_id"]] = (seed["start_time"], seed["end_time"])
    periods, problems = {}, []
    for identity, values in members.items():
        if len(set(values.values())) == 1:
            periods[identity] = next(iter(values.values()))
            continue
        ordered = sorted(values, key=lambda op_id: rows[op_id]["seq"])
        detail = "；".join(
            f"第 {rows[op_id]['seq']} 道 {_time(values[op_id][0])} 至 {_time(values[op_id][1])}"
            for op_id in ordered
        )
        problems.append(facts.public_issue(issue("external_cycle_actuals_differ",
            "合并外协组各道工序已登记的实际时间不一致（" + detail + "），排产会被拦下。同组工序是一起送出、一起回厂的，"
            "请到现场记录把同组报工更正成同一实际开工、完工时间。"), rows[ordered[0]]))
    return periods, problems


def preflight_external_cycles(facts, batches, operations, projections):
    """Return frozen cycles plus explicit blockers for split actuals.

    同组未报工成员按不重排时段保留的安排是否与实际周期一致，由 preflight_held 按排产同一保留范围核对。
    """
    contexts = {row["operation_id"]: row for row in facts.tables["BatchExternalContexts"]}
    if not any(op["source"] == "external" and (contexts.get(op["id"]) or {}).get("merge_mode") == "merged"
               and projections[facts.operation_ref(op)]["first_actual_start"] for op in operations):
        return {}, []
    version = max((row["version"] for row in facts.capture.table("ScheduleHistory")), default=0)
    prior = prior_execution_projections(facts, version)
    models = [stored_batch_operation(op) for op in operations]
    batch_models = {batch["batch_id"]: stored_batch(batch) for batch in batches}
    groups = execution_groups(facts, batch_models, models)
    _, completed, seeds, _ = build_execution_guardrails_from_projections(
        facts.conn, models, prev_version=version, execution_projections=prior, facts=facts)
    rows = {op["id"]: op for op in operations}
    periods, problems = _actual_periods(facts, groups, seeds, rows)
    cycles = _cycle_members(groups, periods, completed)
    return cycles, problems


def prior_execution_projections(facts, version):
    refs = {facts.operation_refs[op_id] for op_id in facts.latest_plan_rows(version)}
    supplied = facts.execution_projections
    missing = sorted(refs - set(supplied))
    ledger = facts.execution_service or ExecutionLedgerService(facts.conn)
    for offset in range(0, len(missing), 10000):
        supplied.update((item.operation_ref, item) for item in ledger.project_operations(missing[offset:offset + 10000]))
    return [supplied[ref] for ref in sorted(refs)]


def _holds_resource(row):
    return row.get("actual_machine_ref") is not None or row.get("actual_operator_ref") is not None


def _projection_holds_resource(projection):
    return any(_holds_resource(row) for row in projection["reports"])


def _planned_external(facts, version):
    planned = set(facts.latest_plan_rows(version))
    return {facts.operation_refs[op["id"]]: op for op in facts.tables["BatchOperations"]
            if op["source"] == "external" and op["id"] in planned and op["id"] in facts.operation_refs}


def _resource_bearing_external(facts, version):
    external = _planned_external(facts, version)
    supplied = {ref: facts.execution_projections[ref].to_dict() for ref in external if ref in facts.execution_projections}
    missing = sorted(set(external) - set(supplied))
    ledger = facts.execution_service or ExecutionLedgerService(facts.conn)
    for offset in range(0, len(missing), 10000):
        for row in ledger.project_operations(missing[offset:offset + 10000]):
            facts.execution_projections[row.operation_ref] = row
            supplied[row.operation_ref] = row.to_dict()
    return {op["id"]: (op, supplied[ref]) for ref, op in external.items()
            if _projection_holds_resource(supplied[ref])}


def _external_resource_issue(facts, op, projection):
    label = f"外协工序（第 {op['seq']} 道 {op['op_type_name']}）"
    numbers = [row["report_no"] for row in projection["reports"] if _holds_resource(row)]
    message = (label + "的报工 " + "、".join(numbers) + " 填了本厂设备或人员，排产会被拦下（只排其他批次也一样）。"
               "请到现场记录更正这条报工，清除实际设备和实际人员；跟进人请填在经办人里。")
    return facts.public_issue(issue("external_actual_resource_conflict", message), op)


def external_resource_issues(facts, version):
    """与排产守卫同一份执行事实核对外协记录里的本厂设备人员，先指出要更正的报工。

    只先投影正式计划里的外协工序；外协报工一旦带有本厂设备或人员，排产守卫一律阻断。
    """
    candidates = _resource_bearing_external(facts, version)
    if not candidates:
        return []
    return [
        _external_resource_issue(facts, op, projection)
        for _op_id, (op, projection) in sorted(
            candidates.items(),
            key=lambda pair: (
                sql_order(pair[1][0]["batch_id"]),
                sql_order(pair[1][0]["seq"]),
                sql_order(pair[0]),
            ),
        )
    ]
