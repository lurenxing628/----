"""Copy the explicit complete base, including private legacy row fields."""

from typing import Any, Dict, cast

from core.models.schedule_plan_role import SOURCE_SCHEDULE
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_reference import WorkbenchPlanReferenceError
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.models.workbench_trial import MAX_TRIAL_TASKS, issue, reject
from core.services.scheduler.contracts.external_context import (
    context_group_key,
    context_problem,
    member_index,
    merged_supplier_problem,
)
from core.services.workbench.facts.candidate_archive import require_candidate_scope
from core.services.workbench.facts.candidate_facts import GenerationFacts, archived_table
from core.services.workbench.facts.candidate_projection import candidate_summary, dispositions, validate_manifest
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_tasks import validate_saved_tasks
from core.services.workbench.facts.decision_baseline import same_saved_arrangements
from core.services.workbench.facts.decision_baseline_source import decision_baseline_source_resolver
from core.services.workbench.facts.delivery_completeness import deferred_operation_evidence
from core.services.workbench.facts.preflight_checks import stored_date
from core.services.workbench.facts.zero_duration_evidence import point_basis
from core.services.workbench.plan.projection import project_plan
from core.services.workbench.plan.read_context import PlanReadContext
from core.services.workbench.run.piece_adoption_trial import trial_piece_predecessors
from data.repositories.workbench_trial_repo import new_ref

from .archived_external_context import archived_contexts
from .effort import operation_types
from .execution_anchors import attach_execution_anchors
from .facts import ProductionFactsCapture, entity_maps, live_context
from .materials import plan_material_policy


def _arrangement(payload, refs, interval):
    result = {}
    for field, source in (("start", "start_time"), ("end", "end_time")):
        raw = payload.get(source)
        try:
            parsed = interval[0 if field == "start" else 1]
            canonical = parsed.isoformat()
            accepted = {canonical}
            if parsed.second == 0 and parsed.microsecond == 0:
                accepted.add(parsed.isoformat(timespec="minutes"))
                if parsed.hour == parsed.minute == 0:
                    accepted.add(parsed.date().isoformat())
            if parsed.tzinfo is not None or raw.replace(" ", "T") not in accepted:
                raise ValueError("Not canonical factory-local time")
            result[field] = canonical
        except (ValueError, TypeError):
            reject("trial_base_time_invalid", "基础安排的时间格式不对，这里不猜时长。请刷新后重试。")
    for kind in ("machine", "operator"):
        key = payload.get(kind + "_id")
        result[kind + "_id"] = key
        result[kind + "_ref"] = refs.get((kind, key)) if key is not None else None
        if key is not None and result[kind + "_ref"] is None:
            reject("identity_missing", "原安排的设备或人员编号缺失。")
    return result


def _row(payload, op, batch, refs, *, source_task_ref, source_row_ref, operation_ref, interval, detail=None):
    current = _arrangement(payload, refs, interval)
    return {"row_ref": new_ref(), "task_ref": new_ref(), "operation_ref": operation_ref,
            "source_task_ref": source_task_ref, "source_row_ref": source_row_ref,
            "current": current,
            "original": {"arrangement": current, "source_row": payload, "operation": op, "batch": batch,
                         "detail": detail, "batch_ref": refs.get(("batch", op["batch_id"])), "predecessor_operation_refs": []}}


def _plan(conn, ref, capture):
    try:
        return _plan_capture(conn, ref, capture)
    except WorkbenchPlanReferenceError as exc:
        missing = exc.code == "reference_not_found"
        raise WorkbenchCommandRejected("entity_not_found" if missing else exc.code,
            "所选计划已不存在，请刷新列表后重新选择。" if missing else "计划或安排编号已失效，请刷新列表后重新选择。",
            404 if missing else 409) from exc


def _plan_capture(conn, ref, capture):
    context = PlanReadContext(conn)
    with context.read_scope():
        locator, binding = context.references._resolved_record(ref)
        source = binding["source_table"]
        table, kind = {"schedule": ("Schedule", "schedule_row"),
                       "candidate_rows": ("ScheduleCandidateRows", "candidate_row"),
                       "adjustment_scenario_rows": ("ScheduleAdjustmentScenarioRow", "scenario_row")}[source]
        query = {"version": locator.version, "source_table": source,
                 "candidate_id": int(binding["owner_key"]) if source == "candidate_rows" else None,
                 "scenario_id": locator.scenario_id}
        if table in capture.table_names:
            selected = [row for row in capture.table(table) if (
                row["scenario_id"] == locator.scenario_id if source == "adjustment_scenario_rows" else
                row["version"] == locator.version and (source != "candidate_rows" or row["candidate_id"] == query["candidate_id"]))]
            context.seed_source_rows(selected, **query)
        _, entry, _ = context.selected(ref)
        identity = entry.plan_identity
        if identity is None:
            reject("plan_unavailable", "所选计划的编号已失效，请刷新计划列表后重新选择。")
        tables = {"BatchOperations": capture.index("BatchOperations", "id"),
                  "Batches": capture.index("Batches", "batch_id")}
        detail = context.detail_rows(entry)
        tasks = context.task_refs(ref, detail)
        operations = context.operation_refs(row["op_id"] for row in detail)
        refs = entity_maps({"WorkbenchEntityRefs": capture.table("WorkbenchEntityRefs")})
        raw = capture.rows_for_ids(table, {row["schedule_id"] for row in detail})
        source_refs = {int(row["source_key"]): row["ref"] for row in capture.table("WorkbenchPlanSourceRefs")
                       if row["kind"] == kind and row["active"] == 1}
        result, point_work = [], None
        intervals = context.datetime_intervals(entry)
        parts = capture.index("Parts", "part_no")
        for item in detail:
            op = tables["BatchOperations"].get(item["op_id"])
            batch = tables["Batches"].get(item["batch_id"])
            if op is None or batch is None or item["schedule_id"] not in source_refs:
                reject("trial_base_incomplete", "原计划工序、批次或来源行缺失。")
            item = dict(item, due_date=batch["due_date"])
            result.append(_row(raw[item["schedule_id"]], op, batch, refs, source_task_ref=tasks[item["schedule_id"]],
                               source_row_ref=source_refs[item["schedule_id"]], operation_ref=operations[item["op_id"]],
                               detail=item, interval=intervals[item["schedule_id"]]))
            result[-1]["original"]["part"] = parts.get(batch["part_no"])
            if result[-1]["current"]["start"] == result[-1]["current"]["end"]:
                if source != "schedule":
                    reject("point_evidence_unproven", "这道零工时工序来自旧候选方案或模拟结果，没有可核对的依据。")
                if point_work is None:
                    point_work = context.point_work(locator.version)
                _attach_point_work(result[-1], point_work[item["op_id"]])
        operations = {int(row["source_key"]): row["ref"] for row in capture.table("WorkbenchPlanSourceRefs")
                      if row["kind"] == "operation" and row["active"] == 1}
        issues = [] if entry.completeness == "complete" else [issue("trial_base_incomplete", "基础方案不完整，暂无法评估交期。")]
        history = context.history(locator.version) if source == SOURCE_SCHEDULE else None
        delivery_record = ({"source": source, "summary": history["result_summary"], "result_status": history["result_status"]}
                           if history is not None else {"source": source})
        deferred, deferred_issues = deferred_operation_evidence(conn, delivery_record)
        runtime = _formal_effort_source(conn, ref, locator.version, delivery_record, list(raw.values()))
        slot_types = operation_types(result, refs, capture.index("OpTypes", "op_type_id"))
        types = runtime.get("operation_types")
        if types is None:
            types = {row["operation_ref"]: {"ref": None, "label": None} for row in result}
        return result, {"identity": project_plan(entry, ref), "source_table": table, **runtime,
                        "operation_types": types, "trial_operation_types": slot_types,
                        "material_policy": plan_material_policy(conn, locator.version, history=history),
                        "deferred_operation_ids": sorted(deferred), "deferred_operation_issues": deferred_issues}, tables["BatchOperations"], operations, issues


def _formal_effort_source(conn, ref, version, record, rows):
    if record["source"] != SOURCE_SCHEDULE:
        return {"operation_effort": None}
    history = {"version": version, "result_summary": record["summary"], "result_status": record["result_status"]}
    source = decision_baseline_source_resolver(conn)(plan_ref=ref, version=version, history=history)
    evidence = source.get("evidence")
    if evidence is not None and not same_saved_arrangements(rows, evidence["arranged"]):
        return {"operation_effort": None, "operation_effort_issues": [
            {"code": "adoption_plan_drift", "message": "正式安排与原采用来源不同，准备需求分解未知。"}]}
    return {"operation_effort": source.get("operation_effort"), "operation_types": source.get("operation_types"),
            "operation_effort_issues": [source["issue"]] if source.get("issue") else []}

def _date_issues(rows):
    issues = []
    for row in rows:
        for field in ("due_date", "ready_date"):
            value = row["original"]["batch"][field]
            if value is not None and (type(value) is not str or stored_date(value) is None):
                issues.append(dict(issue("trial_base_date_invalid", "原批次交期或可开工日期无效；保留原值，不能正式采用。", row["task_ref"]), field=field))
    return issues


def _candidate(conn, ref):
    store = CandidateStore(conn)
    with store.snapshot():
        run_ref = store.candidate_run(ref)
        run, candidates = store.run(run_ref), store.candidates(run_ref)
        receipt = store.receipt(run)
        validate_manifest(run, candidates, receipt)
        candidate = next(row for row in candidates if row["candidate_ref"] == ref)
        # A candidate that passes manifest validation has a saved receipt.
        receipt = cast(Dict[str, Any], receipt)
        capture = store.capture(run_ref)
        facts = GenerationFacts(capture)
        rows = store.tasks(ref)
        prepared_tasks = {}
        rows, _, scheduled_op_ids = validate_saved_tasks(rows, candidate, facts, prepared_tasks=prepared_tasks)
        result = []
        for item in rows:
            prepared = prepared_tasks[item["row_ref"]]
            op, gaps = prepared["operation"], prepared["operation_gaps"]
            batch = facts.tables["Batches"].get(op.get("batch_id"))
            if gaps or not op or batch is None:
                reject("trial_base_incomplete", "生成候选时的工序或批次资料缺失。")
            result.append(_row(item["payload"], op, batch, facts.entity_refs, source_task_ref=None,
                               source_row_ref=item["row_ref"], operation_ref=item["operation_ref"],
                               interval=prepared["interval"]))
            if result[-1]["current"]["start"] == result[-1]["current"]["end"]:
                _attach_point_work(result[-1], prepared["point_work"])
            result[-1]["original"]["part"] = facts.tables["Parts"].get(batch["part_no"])
        scope = dispositions(receipt)
        summary = candidate_summary(candidate, scope, scheduled_op_ids=scheduled_op_ids)
        issues = []
        try:
            expected = require_candidate_scope(run, candidate, scope, capture, scheduled_op_ids=scheduled_op_ids)
            if {row["original"]["operation"]["id"] for row in result} != expected:
                raise CandidateAdoptionBlocked("candidate_scope_incomplete", "候选任务范围不完整。")
        except CandidateAdoptionBlocked:
            issues.append(issue("trial_base_incomplete", "候选方案没有覆盖排产时的全部工序，没排上的工序也照样列出。"))
        work_types = facts.tables["OpTypes"]
        extra = {"identity": {"candidate_ref": ref, "run_ref": run_ref, "kind": "candidate",
                               "display_name": summary["label"], "completeness": summary["completeness"]},
                 "capture": capture, "dispositions": scope, "operation_effort": receipt.get("operation_effort"),
                 "trial_operation_types": operation_types(result, facts.entity_refs, work_types),
                 "operation_types": operation_types(result, facts.entity_refs, work_types,
                      candidate["artifact"].get("results", []))}
        return result, extra, facts.tables["BatchOperations"], facts.operation_refs, issues, facts


def prepare_base(conn, intent, *, execution_service):
    key, ref = next(iter(intent["base"].items()))
    capture = ProductionFactsCapture(conn)
    if key == "plan_ref":
        rows, source, all_ops, operation_refs, issues = _plan(conn, ref, capture)
        source_facts = None
    else:
        rows, source, all_ops, operation_refs, issues, source_facts = _candidate(conn, ref)
    if not rows:
        reject("trial_base_empty", "基础方案没有真实任务行，未从摘要重造任务。")
    if len(rows) > MAX_TRIAL_TASKS:
        reject("query_too_large", "完整基础范围超过10000条，未按可见范围截断。", 413)
    issues.extend(_date_issues(rows))
    _predecessors(rows, all_ops, operation_refs, issues)
    live = live_context(conn, [row["operation_ref"] for row in rows], capture, execution_service=execution_service)
    live["source_facts"] = source_facts
    admission = {"input": intent, "source": source, "facts": live["facts"],
                 "baseline": live["baseline"], "execution": live["execution"], "base_issues": issues}
    _attach_original_context(rows, source, key, live, source_facts)
    issues.extend(attach_execution_anchors(conn, rows, live))
    return admission, rows, live


def _original_external_facts(rows, original_tables, live):
    contexts = (archived_table(original_tables, "BatchExternalContexts") if original_tables is not None
                else live["facts"]["tables"].get("BatchExternalContexts"))
    if contexts is None and original_tables is not None:
        selected = {row["original"]["operation"]["id"] for row in rows
                    if row["original"]["operation"]["source"] == "external"}
        contexts = archived_contexts(original_tables, selected)
    by_operation = {item["operation_id"]: item for item in contexts or []}
    operations = (archived_table(original_tables, "BatchOperations") if original_tables is not None
                  else live["facts"]["tables"]["BatchOperations"])
    return by_operation, member_index(by_operation, operations or [])


def _attach_original_context(rows, source, key, live, facts):
    original_execution = ({row["operation_ref"]: row for row in source["capture"]["execution"]}
                          if key == "candidate_ref" else live["execution"])
    original_tables = facts.archive if facts is not None else None
    by_operation, members = _original_external_facts(rows, original_tables, live)
    for row in rows:
        original = row["original"]
        original.setdefault("execution", original_execution.get(row["operation_ref"]))
        original["external_group"] = None
        op = original["operation"]
        if op["source"] == "external":
            context = by_operation.get(op["id"])
            problem = context_problem(context, operation_id=op["id"],
                                      part_no=original["batch"]["part_no"], sequence=op["seq"])
            if context is None or problem:
                reject("trial_base_incomplete", problem)
            original["external_context_origin"] = context["origin"]
            problem = merged_supplier_problem(context, op["supplier_id"],
                members.get((op["batch_id"], context_group_key(context), op["piece_id"])))
            if problem:
                reject("trial_base_incomplete", problem)
            if context["group_id"] is not None:
                original["external_group"] = dict(context, group_id=context_group_key(context))


def _attach_point_work(row, work):
    original = row["original"]
    original.update({key: work[key] for key in ("operation", "batch", "execution")})
    original["point_basis"] = point_basis(work)


def _predecessors(rows, all_ops, operation_refs, issues):
    from core.models.workbench_piece_adoption import PieceAdoptionBlocked

    if any(row["original"]["operation"]["piece_id"] is not None for row in rows):
        try:
            predecessors = trial_piece_predecessors(rows, all_ops, operation_refs)
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
