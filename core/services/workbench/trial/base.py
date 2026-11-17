"""Copy the explicit complete base."""

from typing import cast

from core.algorithm_contracts.operation_effort import RUNTIME_REQUIREMENT_BASIS
from core.algorithm_contracts.schedule_point_evidence import SchedulePointEvidence, is_point_work
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_load_limits import MAX_WINDOW_OPERATIONS
from core.models.workbench_plan_reference import WorkbenchPlanReferenceError
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.models.workbench_trial import issue, reject
from core.services.scheduler.contracts.external_context import (
    context_group_key,
    context_problem,
    member_index,
    merged_supplier_problem,
)
from core.services.workbench.facts.candidate_archive import require_candidate_scope
from core.services.workbench.facts.candidate_projection import candidate_completeness
from core.services.workbench.facts.candidate_read_source import read_candidate_source
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_values import corrupt
from core.services.workbench.facts.trial_origin import (
    CandidateTrialSource,
    OfficialTrialSource,
    TrialOrigin,
    TrialSource,
)
from core.services.workbench.facts.zero_duration import (
    PointEventError,
    point_work_quantity,
    schedule_row_point_evidence,
)
from core.services.workbench.plan.projection import project_plan
from core.services.workbench.plan.read_context import PlanReadContext
from core.shared.local_datetime import row_interval
from core.shared.refs import new_ref
from core.shared.stored_dates import stored_date

from .effort import slot_operation_types
from .execution_anchors import attach_execution_anchors, resolve_execution_anchors
from .facts import LiveTables, ProductionFactsCapture, entity_maps, live_context
from .piece_scope import trial_piece_scope


def _arrangement(arrangement, refs, interval):
    result = {
        "start": interval[0].isoformat(),
        "end": interval[1].isoformat(),
    }
    for kind in ("machine", "operator"):
        key = arrangement[kind + "_id"]
        result[kind + "_id"] = key
        result[kind + "_ref"] = refs.get((kind, key)) if key is not None else None
        if key is not None and result[kind + "_ref"] is None:
            reject("identity_missing", "原安排的设备或人员编号缺失。")
    return result


def _row(arrangement, op, batch, refs, *, source_task_ref, source_row_ref, operation_ref, interval):
    current = _arrangement(arrangement, refs, interval)
    return {
        "row_ref": new_ref(),
        "task_ref": new_ref(),
        "operation_ref": operation_ref,
        "source_task_ref": source_task_ref,
        "source_row_ref": source_row_ref,
        "current": current,
        "original": {
            "arrangement": current,
            "operation": op,
            "batch": batch,
            "batch_ref": refs[("batch", op["batch_id"])],
            "predecessor_operation_refs": [],
        },
    }


def _plan(conn, ref, capture):
    try:
        return _plan_capture(conn, ref, capture)
    except WorkbenchPlanReferenceError as exc:
        missing = exc.code == "reference_not_found"
        raise WorkbenchCommandRejected(
            "entity_not_found" if missing else exc.code,
            "所选计划已不存在，请刷新列表后重新选择。" if missing else "计划或安排编号已失效，请刷新列表后重新选择。",
            404 if missing else 409,
        ) from exc


def _point_basis(work):
    value = work["witness"]
    basis = {
        "op_id": value.op_id,
        "setup_hours": value.setup_hours,
        "unit_hours": value.unit_hours,
        "quantity": value.quantity,
    }
    op = work["operation"]
    if op.get("piece_id") is not None:
        basis.update(
            piece_id=op["piece_id"],
            batch_id=op["batch_id"],
            operation_ref=work["execution"]["operation_ref"],
        )
    return basis


def _official_point_work_from_row(raw_row, op, batch, operation_ref):
    witness = cast(SchedulePointEvidence, schedule_row_point_evidence(raw_row))
    point_op = {
        **op,
        "id": raw_row["op_id"],
        "batch_id": raw_row["batch_id"],
        "piece_id": raw_row["piece_id"],
        "seq": raw_row["seq"],
        "op_type_name": raw_row["op_type_name"],
        "source": raw_row["source"],
        "setup_hours": raw_row["setup_hours"],
        "unit_hours": raw_row["unit_hours"],
    }
    point_batch = {
        **batch,
        "batch_id": raw_row["batch_id"],
        "quantity": raw_row["batch_quantity"],
        "priority": raw_row["batch_priority"],
    }
    target_basis = "piece" if raw_row["piece_id"] is not None else "batch"
    point_execution = {
        "operation_ref": operation_ref,
        "target_quantity": raw_row["quantity"],
        "remaining_quantity": raw_row["remaining_quantity"],
        "target_basis": target_basis,
    }
    return {"witness": witness, "operation": point_op, "batch": point_batch, "execution": point_execution}


def _candidate_point_work_from_row(item, op, batch, execution, at):
    if op.get("source") != "internal" or item["source"] != "internal" or execution is None:
        raise PointEventError("point_identity_unproven", "零工时工序必须对应原来的整批或分件工序。")
    quantity = point_work_quantity(op, batch, execution, item["operation_ref"])
    setup, unit = op.get("setup_hours"), op.get("unit_hours")
    if not is_point_work(op["source"], setup, unit, quantity):
        raise PointEventError("point_duration_nonzero", "这道工序有实际工时，不是零工时工序。")
    witness = SchedulePointEvidence(
        op_id=op["id"],
        machine_id=item["machine_id"],
        operator_id=item["operator_id"],
        at=at,
        setup_hours=setup,
        unit_hours=unit,
        quantity=quantity,
    )
    return {"witness": witness, "operation": op, "batch": batch, "execution": execution}


def _formal_effort_source(efforts, schedule_rows):
    """The official version's admitted requirement ledger, kept in the trial source as it was saved."""
    types = {
        row["operation_ref"]: {"ref": row["op_type_ref"], "label": row["op_type_label"]}
        for row in schedule_rows
    }
    return {
        "operation_effort": (
            None if efforts is None else {"effort_basis": RUNTIME_REQUIREMENT_BASIS, "items": list(efforts.values())}
        ),
        "operation_types": types,
    }


def _plan_capture(conn, ref, capture):
    context = PlanReadContext(conn)
    with context.read_scope():
        locator = context.resolve(ref)
        entry, _ = context.selected(ref)
        tables = {
            "BatchOperations": capture.index("BatchOperations", "id"),
            "Batches": capture.index("Batches", "batch_id"),
        }
        refs = entity_maps({"WorkbenchEntityRefs": capture.table("WorkbenchEntityRefs")})
        schedule_rows = sorted(
            (row for row in capture.table("Schedule") if row["version"] == locator.version),
            key=lambda row: (row["start_us"], row["id"]),
        )
        result = []
        parts = capture.index("Parts", "part_no")
        for raw_row in schedule_rows:
            op = tables["BatchOperations"][raw_row["op_id"]]
            batch = tables["Batches"][raw_row["batch_id"]]
            task_ref = raw_row["task_ref"]
            op_ref = raw_row["operation_ref"]
            interval = row_interval(raw_row)
            result.append(
                _row(
                    raw_row,
                    op,
                    batch,
                    refs,
                    source_task_ref=task_ref,
                    source_row_ref=task_ref,
                    operation_ref=op_ref,
                    interval=interval,
                )
            )
            result[-1]["original"]["part"] = parts[batch["part_no"]]
            if raw_row["is_point_event"] == 1:
                work = _official_point_work_from_row(raw_row, op, batch, op_ref)
                _attach_point_work(result[-1], work)
        issues = [] if entry.completeness == "complete" else [issue("trial_base_incomplete", "基础方案不完整，暂无法评估交期。")]
        documents = context.history_documents(locator.version)
        runtime = _formal_effort_source(documents.operation_effort, schedule_rows)
        slot_types = slot_operation_types(result, refs, capture.index("OpTypes", "op_type_id"))
        suppliers = {
            raw_row["operation_ref"]: {
                "supplier_id": raw_row["supplier_id"],
                "ref": raw_row["supplier_ref"],
                "label": raw_row["supplier_label"],
            }
            for raw_row in schedule_rows
        }
        return (
            result,
            OfficialTrialSource({
                "identity": project_plan(entry, ref),
                **runtime,
                "trial_operation_types": slot_types,
                "suppliers": suppliers,
                "material_policy": documents.material_policy,
                "deferred_operation_ids": sorted(documents.deferred_operation_ids),
                "deferred_operation_issues": [],
            }),
            tables["BatchOperations"],
            issues,
        )


def _date_issues(rows):
    issues = []
    for row in rows:
        for field in ("due_date", "ready_date"):
            value = row["original"]["batch"][field]
            if value is not None and (type(value) is not str or stored_date(value) is None):
                issues.append(
                    dict(
                        issue("trial_base_date_invalid", "原批次交期或可开工日期无效；保留原值，不能正式采用。", row["task_ref"]),
                        field=field,
                    )
                )
    return issues


def _candidate(conn, ref):
    store = CandidateStore(conn)
    with store.snapshot():
        source = read_candidate_source(store, ref)
        run, candidate, capture, facts = source.run, source.candidate, source.capture, source.facts
        scheduled_op_ids = source.scheduled_op_ids
        result = []
        for item in source.raw_tasks:
            op = source.prepared_tasks[item["row_ref"]]
            batch = facts.related("Batches", op["batch_id"])
            interval = source.task_intervals[item["row_ref"]]
            result.append(
                _row(
                    item,
                    op,
                    batch,
                    facts.entity_refs,
                    source_task_ref=None,
                    source_row_ref=item["row_ref"],
                    operation_ref=item["operation_ref"],
                    interval=interval,
                )
            )
            if interval[0] == interval[1]:
                try:
                    work = _candidate_point_work_from_row(
                        item, op, batch, facts.execution.get(item["operation_ref"]), interval[0]
                    )
                except (PointEventError, ValueError, TypeError):
                    corrupt()
                _attach_point_work(result[-1], work)
            result[-1]["original"]["part"] = facts.related("Parts", batch["part_no"])
        scope = source.disposition
        completeness = candidate_completeness(candidate, scope, scheduled_op_ids=scheduled_op_ids)
        display_name = candidate["artifact"]["label"]
        issues = []
        try:
            expected = require_candidate_scope(
                run, candidate, scope, capture, scheduled_op_ids=scheduled_op_ids, completeness=completeness
            )
            if {row["original"]["operation"]["id"] for row in result} != expected:
                raise CandidateAdoptionBlocked("candidate_scope_incomplete", "候选任务范围不完整。")
        except CandidateAdoptionBlocked:
            issues.append(issue("trial_base_incomplete", "候选方案没有覆盖排产时的全部工序，没排上的工序也照样列出。"))
        # A candidate's tasks carry their operations' own types: what the run recorded is what each slot holds.
        types = slot_operation_types(result, facts.entity_refs, facts.tables["OpTypes"])
        document = {
            "run_ref": run["run_ref"],
            "candidate_ref": ref,
            "identity": {
                "candidate_ref": ref,
                "kind": "candidate",
                "display_name": display_name,
                "completeness": completeness,
            },
            "dispositions": scope,
            "operation_effort": source.receipt.operation_effort,
            "trial_operation_types": types,
            "operation_types": types,
        }
        return result, CandidateTrialSource(document, capture, facts), facts.tables["BatchOperations"], issues


def prepare_base(conn, intent, *, ledger, data_context):
    key, ref = next(iter(intent["base"].items()))
    capture = ProductionFactsCapture(conn)
    rows, source, all_ops, issues = _plan(conn, ref, capture) if key == "plan_ref" else _candidate(conn, ref)
    if not rows:
        reject("trial_base_empty", "基础方案没有真实任务行，未从摘要重造任务。")
    if len(rows) > MAX_WINDOW_OPERATIONS:
        reject("query_too_large", f"完整基础范围超过{MAX_WINDOW_OPERATIONS}条，未按可见范围截断。", 413)
    origin = TrialOrigin({"source": source.document}, rows, tables=LiveTables(capture), source=source)
    issues.extend(_date_issues(rows))
    _predecessors(rows, all_ops, origin.refs_by_op_id, issues)
    live = live_context(conn, origin, capture, ledger=ledger, data_context=data_context)
    admission = origin.admission = {
        "input": intent,
        "source": source.document,
        "base_issues": issues,
        "baseline": live["baseline"],
        "execution": live["execution"],
    }
    _attach_original_context(rows, origin, live)
    resolved_anchors = resolve_execution_anchors(rows, live)
    issues.extend(attach_execution_anchors(rows, *resolved_anchors))
    return admission, rows, live, resolved_anchors


def _original_external_facts(source: TrialSource, live):
    """A candidate base keeps its saved work relations; an official base reads this transaction's."""
    if isinstance(source, CandidateTrialSource):
        contexts, operations = source.facts.table("BatchExternalContexts"), source.facts.table("BatchOperations")
    else:
        tables = live["facts"]["tables"]
        contexts, operations = tables["BatchExternalContexts"], tables["BatchOperations"]
    by_operation = {item["operation_id"]: item for item in contexts}
    return by_operation, member_index(by_operation, operations)


def _attach_original_context(rows, origin, live):
    original_execution = origin.source_execution
    by_operation, members = _original_external_facts(origin.source, live)
    official = isinstance(origin.source, OfficialTrialSource)
    for row in rows:
        original = row["original"]
        live_exec = original_execution[row["operation_ref"]]
        if official and "execution" in original:
            original["execution"] = {**live_exec, **original["execution"]}
        else:
            original.setdefault("execution", live_exec)
        original["external_group"] = None
        op = original["operation"]
        if op["source"] == "external":
            context = by_operation.get(op["id"])
            problem = context_problem(
                context, operation_id=op["id"], part_no=original["batch"]["part_no"], sequence=op["seq"]
            )
            if context is None or problem:
                reject("trial_base_incomplete", problem)
            original["external_context_origin"] = context["origin"]
            problem = merged_supplier_problem(
                context, op["supplier_id"], members.get((op["batch_id"], context_group_key(context), op["piece_id"]))
            )
            if problem:
                reject("trial_base_incomplete", problem)
            if context["group_id"] is not None:
                original["external_group"] = dict(context, group_id=context_group_key(context))


def _attach_point_work(row, work):
    original = row["original"]
    original.update({key: work[key] for key in ("operation", "batch", "execution")})
    original["point_basis"] = _point_basis(work)


def _predecessors(rows, all_ops, operation_refs, issues):
    from core.models.workbench_piece_adoption import PieceAdoptionBlocked

    if any(row["original"]["operation"]["piece_id"] is not None for row in rows):
        try:
            _, predecessors = trial_piece_scope(rows, all_ops, operation_refs)
        except PieceAdoptionBlocked as exc:
            issues.append(issue(exc.code, str(exc)))
            return
        for row in rows:
            row["original"]["predecessor_operation_refs"] = predecessors[row["original"]["operation"]["id"]]
        return

    previous = _batch_predecessors(rows, all_ops, operation_refs, issues)
    for row in rows:
        key = row["original"]["operation"]["id"]
        if key in previous:
            if previous[key] is None:
                issues.append(issue("dependency_identity_missing", "前序工序编号缺失，无法核对工序顺序。", row["task_ref"]))
            else:
                row["original"]["predecessor_operation_refs"] = [previous[key]]


def _batch_predecessors(rows, all_ops, operation_refs, issues):
    from collections import defaultdict

    batches = {row["original"]["operation"]["batch_id"] for row in rows}
    chains = defaultdict(list)
    for op in all_ops.values():
        if op["batch_id"] in batches:
            chains[op["batch_id"], op["piece_id"]].append(op)
    previous = {}
    for chain in chains.values():
        if any(type(op["seq"]) is not int for op in chain) or len({op["seq"] for op in chain}) != len(chain):
            issues.append(issue("dependency_ambiguous", "同一批次分件的工序顺序不明确，不能确认前后序。"))
            continue
        ordered = sorted(chain, key=lambda op: op["seq"])
        for left, right in zip(ordered, ordered[1:]):
            previous[right["id"]] = operation_refs.get(left["id"])
    return previous
