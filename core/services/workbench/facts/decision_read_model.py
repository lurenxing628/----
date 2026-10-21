"""Pure immutable decision projections from the caller's prepared archive rows."""

from copy import deepcopy
from math import isfinite
from typing import Any, Dict, List, Optional, overload

from core.models.workbench_command import canonical_json
from core.models.workbench_preflight import preflight_window

from .admission_scope import project_admitted_scope
from .candidate_delivery import project_legacy_delivery_detail
from .candidate_process import PROCESS_VERSION, candidate_process
from .candidate_projection import candidate_summary, dispositions
from .candidate_tasks import project_validated_tasks
from .candidate_values import text
from .completion_scope import project_completion_summary
from .decision_baseline import read_decision_baseline_members
from .decision_candidate import project_candidate_summary
from .decision_delivery import project_decision_delivery
from .decision_metrics import admission_operations, project_official_core_metrics
from .decision_preparation import (
    admission_operation_standards,
    preparation_work_items,
    project_decision_preparation,
)
from .decision_read_models import (
    _BATCH_MEMBERS,
    _OPERATION_MEMBERS,
    ARRANGEMENT_COLUMNS,
    PROJECTION_VERSION,
    Memberships,
)
from .decision_selection import selection_basis
from .operation_effort_evidence import saved_operation_efforts
from .preflight_dependencies import material_deferred_ids
from .preparation_projection import _ALLOCATIONS
from .resource_intervals import resource_cohort, task_interval
from .run_history_projection import _failure, scope_summary
from .schema_compat import archived_columns

CALENDAR_TABLES = (
    "SchemaVersion", "WorkbenchEntityRefs", "Machines", "Operators", "MachineDowntimes", "WorkCalendar",
    "OperatorCalendar", "WorkbenchOperatorProfiles", "WorkbenchShiftProfiles", "WorkbenchShiftPatternDays",
    "WorkbenchShiftDayPeriods", "WorkbenchCalendarDefaults",
)
_ARTIFACT_FIELDS = (
    "candidate_key", "sequence", "status", "label", "kind", "objective", "objective_name", "score", "health",
    "algo_mode", "used_strategy", "dispatch_mode", "dispatch_rule", "failure_reason", "reused_from_candidate_key",
    "generation_policy_version", "target_objectives", "representative_objectives", "evaluations", "origin", "first_found_elapsed_ms",
    "search_evidence_ref", "elapsed_seconds", "time_budget_seconds", "graph_critical_weight", "graph_impact_weight",
    "graph_downstream_weight", "sort_strategy",
)


class _Members:
    """Append ordered, known membership fields to this model's permanent directories."""

    def __init__(self, saved=None):
        self.value = deepcopy(saved) if saved is not None else {
            "operation_refs": [], "batch_refs": [], "operation_sets": [], "batch_sets": []}
        self.positions = {kind: {ref: index for index, ref in enumerate(self.value[kind + "_refs"])}
                          for kind in ("operation", "batch")}
        self.sets = {kind: {tuple(rows): index for index, rows in enumerate(self.value[kind + "_sets"])}
                     for kind in ("operation", "batch")}

    def position(self, ref, kind):
        positions = self.positions[kind]
        if ref not in positions:
            positions[ref] = len(self.value[kind + "_refs"])
            self.value[kind + "_refs"].append(ref)
        return positions[ref]

    def member(self, refs, kind):
        values = tuple(self.position(ref, kind) for ref in refs)
        sets = self.sets[kind]
        if values not in sets:
            sets[values] = len(self.value[kind + "_sets"])
            self.value[kind + "_sets"].append(list(values))
        return {"membership_kind": kind, "membership_index": sets[values]}

    @overload
    def encode(self, value: Dict[str, Any], parent: Optional[str] = None) -> Dict[str, Any]: ...

    @overload
    def encode(self, value: List[Any], parent: Optional[str] = None) -> List[Any]: ...

    @overload
    def encode(self, value: Any, parent: Optional[str] = None) -> Any: ...

    def encode(self, value: Any, parent: Optional[str] = None) -> Any:
        if type(value) is list:
            return [self.encode(item) for item in value]
        if type(value) is not dict:
            return value
        if set(value) == {"membership_kind", "membership_index"}:
            return dict(value)
        result = {}
        for field, item in value.items():
            if field == "input":
                result[field] = item
            elif type(item) is list and (field in _OPERATION_MEMBERS or parent == "coverage" and field in _ALLOCATIONS):
                result[field] = self.member(item, "operation")
            elif type(item) is list and field in _BATCH_MEMBERS:
                result[field] = self.member(item, "batch")
            else:
                result[field] = self.encode(item, field)
        return result


def _configuration(facts, receipt):
    saved = ((receipt or {}).get("summary") or {}).get("algo", {}).get("config_snapshot")
    if type(saved) is dict:
        return saved
    return {row["config_key"]: row.get("config_value") for row in facts.table("ScheduleConfig") or []}


def _stored_number(value):
    if type(value) is int:
        return value
    if type(value) is float:
        return value if isfinite(value) else None
    if type(value) is str:
        try:
            return int(value)
        except ValueError:
            try:
                number = float(value)
                return number if isfinite(number) else None
            except ValueError:
                pass
    return None


def _run_options(capture, facts, receipt):
    if type(capture.get("run_options")) is dict:
        return dict(capture["run_options"])
    config, selection = _configuration(facts, receipt), (receipt or {}).get("selection") or {}
    return {"generation_policy_version": selection.get("generation_policy_version"),
            "primary_objective": selection.get("primary_objective") or selection.get("objective_name") or config.get("objective"),
            "target_objectives": selection.get("target_objectives"),
            "time_budget_seconds": _stored_number(capture["input"].get("time_budget_seconds", config.get("time_budget_seconds"))),
            "algo_mode": config.get("algo_mode"), "graph_analysis_mode": config.get("graph_analysis_mode")}


def build_admission_read_model(capture, *, facts):
    """Small history/status scope; the decision block lives in its separate column."""
    options = _run_options(capture, facts, None)
    summary = scope_summary(canonical_json(capture["input"]))
    if options["generation_policy_version"] is not None:
        summary = dict(summary, run_options=options)
    workload = project_admitted_scope(capture["input"], facts.archive, tables=facts.tables,
                                      entity_refs=facts.entity_refs, summary=summary)
    return {"scope_summary": summary, "input": capture["input"], "run_options": options,
            **{field: workload[field] for field in ("batches", "operation_count", "objective", "objective_label")},
            "workload_data_gaps": workload["data_gaps"]}


def _calendar(facts):
    source = facts.archive
    names = {name for name in CALENDAR_TABLES if name in source["tables"]}
    return {"version": "production-facts-v2",
            "schema": [row for row in source["schema"] if row[2] in names],
            "columns": {name: archived_columns(source, name) for name in CALENDAR_TABLES if name in names},
            "tables": {name: source["tables"][name] for name in CALENDAR_TABLES if name in names}}


def _resources(facts, tasks=()):
    resources = {}
    for (kind, key), ref in facts.entity_refs.items():
        if kind not in ("machine", "operator", "supplier"):
            continue
        table = {"machine": "Machines", "operator": "Operators", "supplier": "Suppliers"}[kind]
        row = facts.tables[table].get(key)
        resources[(kind, ref)] = {"kind": kind, "ref": ref, "saved_id": key,
                                  "label": text(row.get("name"), kind + ".label", []) if row else None}
    for task in tasks:
        for kind in ("machine", "operator", "supplier"):
            value = task.get(kind)
            if value is not None and value.get("ref") is not None:
                resources.setdefault((kind, value["ref"]),
                    {"kind": kind, "ref": value["ref"], "saved_id": None, "label": value.get("label")})
    return [resources[key] for key in sorted(resources)]


def _arrangements(tasks):
    rows, resources, positions = [], [], {}
    for task in tasks:
        row = dict(task)
        for kind in ("machine", "operator", "supplier"):
            resource = task.get(kind)
            position = None
            if resource is not None:
                key = kind, resource.get("ref"), resource.get("label")
                if key not in positions:
                    positions[key] = len(resources)
                    resources.append({"kind": kind, "ref": key[1], "label": key[2]})
                position = positions[key]
            row[kind + "_resource_index"] = position
        row.setdefault("interval_comparable", True)
        rows.append([row.get(field) for field in ARRANGEMENT_COLUMNS])
    return {"columns": list(ARRANGEMENT_COLUMNS), "rows": rows, "resource_values": resources}


def _resource_views(tasks, operation_refs, intervals=None):
    selected = set(operation_refs)
    result = {}
    for name, rows in (("selected_batches", [row for row in tasks if row["operation_ref"] in selected]), ("full_candidate", tasks)):
        saved = intervals if intervals is not None else {row["row_ref"]: task_interval(row) for row in rows}
        members = resource_cohort([rows], task_intervals=[saved])
        by_resource = {(row["kind"], row["ref"]): [] for row in members}
        for row in rows:
            interval = saved[row["row_ref"]]
            if row.get("source") == "external" or interval is not None and interval[0] == interval[1]:
                continue
            for kind in ("machine", "operator"):
                ref = (row.get(kind) or {}).get("ref")
                if (kind, ref) in by_resource and interval is not None:
                    by_resource[(kind, ref)].append(interval)
        result[name] = {"resources": [dict(row,
            span_start=min(value[0] for value in by_resource[(row["kind"], row["ref"])]).isoformat()
                if by_resource[(row["kind"], row["ref"])] else None,
            span_end=max(value[1] for value in by_resource[(row["kind"], row["ref"])]).isoformat()
                if by_resource[(row["kind"], row["ref"])] else None) for row in members]}
    return result


def _operation_batches(facts, members):
    positions = []
    for ref in members.value["operation_refs"]:
        operation = facts.tables["BatchOperations"].get(facts.operations.get(ref), {})
        batch_ref = facts.entity_refs.get(("batch", operation.get("batch_id")))
        positions.append(members.position(batch_ref, "batch") if batch_ref is not None else None)
    return positions


def _official_projection(run, facts, receipt, official, refs, deferred, batch_refs, dependencies):
    tasks = official["tasks"]
    scope_refs = set(refs)
    selected = [row for row in tasks if row["operation_ref"] in scope_refs]
    available = official["identity"]["state"] == "available"
    deferred_ids = set(official["deferred_operation_ids"])
    official_deferred = {ref for ref, key in facts.operations.items() if key in deferred_ids}
    intervals = {row["row_ref"]: task_interval(row) for row in tasks}
    delivery = project_decision_delivery(facts, selected, batch_refs, available=available,
        deferred_ids=official["deferred_operation_ids"], intervals=intervals)
    values, coverage = project_official_core_metrics(tasks, refs, official_deferred & scope_refs, available, delivery)
    prepared = project_decision_preparation(facts, refs, {}, selected, run_ref=run["run_ref"], available=available,
        deferred_refs=official_deferred, requirements_available=available, official=official)
    work = preparation_work_items(facts, prepared["rows"], dispositions(receipt), available=available)
    completion = project_completion_summary(delivery, work, available=available, schedulable_coverage=coverage["schedulable"])
    return {"identity": dict(official["identity"]), "source_states": official["source_states"],
        "dependencies": dependencies or {"candidates": [], "scenarios": []},
        "operation_refs": sorted({row["operation_ref"] for row in tasks}), "deferred_operation_refs": sorted(official_deferred),
        "core_metrics": values, "coverage": coverage, "preparation": prepared["summary"], "completion": completion,
        "delivery": delivery, "arrangements": _arrangements(tasks), "resources": _resources(facts, tasks),
        "resource_views": _resource_views(tasks, refs, intervals)}


def _missing_candidate_reference(run, facts, refs, deferred, batch_refs, receipt, standards=None):
    efforts = saved_operation_efforts((receipt or {}).get("operation_effort"), identities=facts.operations)
    preparation = project_decision_preparation(facts, refs, efforts, [], run_ref=run["run_ref"],
        available=False, deferred_refs=deferred, standards=standards,
        requirements_available=(receipt or {}).get("operation_effort") is not None)
    delivery = project_decision_delivery(facts, [], batch_refs, available=False,
        deferred_ids={facts.operations[ref] for ref in deferred}, candidate=None)
    return {"preparation": preparation["summary"], "delivery": delivery,
            "completion": project_completion_summary(delivery, [], available=False)}


def build_admission_decision_read_model(run, capture, official, *, facts, receipt=None, dependencies=None):
    """Project the actual admission baseline once; callers own source resolution."""
    disposition = dispositions(receipt)
    refs, deferred, _ = admission_operations(facts, capture["input"], disposition)
    refs, batch_refs = sorted(refs), sorted(capture["input"]["batch_refs"])
    members = _Members()
    for ref in refs:
        members.position(ref, "operation")
    for ref in batch_refs:
        members.position(ref, "batch")
    saved_official = ({**read_decision_baseline_members(capture, facts), "projection_state": "disposition_not_recorded"}
                      if official is None else
                      _official_projection(run, facts, receipt, official, refs, deferred, batch_refs, dependencies))
    range_start, range_end = preflight_window(capture["input"])
    context = {"input": capture["input"], "run_options": _run_options(capture, facts, receipt),
        "range_start": range_start, "range_end": range_end,
        "admission_operation_refs": refs, "expected_operation_refs": sorted(set(refs) - deferred),
        "deferred_operation_refs": sorted(deferred), "official_members": {
            "identity": dict(saved_official["identity"]), "operation_refs": saved_official["operation_refs"]},
        "resources": _resources(facts, official["tasks"] if official is not None else ()),
        # Guard facts own actual deferrals; the public pending run has no result receipt.
        "missing_candidate_reference": _missing_candidate_reference(
            run, facts, refs, deferred, batch_refs, None)}
    encoded_official, encoded_context = members.encode(saved_official), members.encode(context)
    encoded_context["operation_batch_indices"] = _operation_batches(facts, members)
    return {"context": encoded_context, "memberships": members.value, "calendar": _calendar(facts), "official": encoded_official}


def prepare_admission_read_models(run, capture, official, *, facts, receipt=None, dependencies=None):
    return {"scope": build_admission_read_model(capture, facts=facts),
            "decision": build_admission_decision_read_model(run, capture, official, facts=facts, receipt=receipt, dependencies=dependencies)}


def _header_artifact(artifact):
    result = {key: artifact[key] for key in _ARTIFACT_FIELDS if key in artifact}
    metrics = artifact.get("metrics") or {}
    result["metrics"] = {key: value for key, value in metrics.items() if type(value) in (int, float, str, bool) or value is None}
    completion = metrics.get("completion")
    if type(completion) is dict:
        scope = completion.get("objective_scope")
        if scope is None and completion.get("incomplete_batch_ids") and completion.get("explained") is True:
            scope = "completed_batches_only"
        result["metrics"]["completion"] = {"objective_scope": scope, "explained": completion.get("explained")}
    return result


def _header(run, receipt, candidates):
    receipt = receipt or {}
    saved_manifest = {row["candidate_ref"]: row for row in receipt.get("candidates", [])}
    manifest = [dict(candidate_ref=row["candidate_ref"], run_ref=row["run_ref"],
        sequence=row["sequence"], candidate_key=row["artifact"].get("candidate_key"),
        **{field: saved_manifest[row["candidate_ref"]][field] for field in ("label", "status", "task_count", "selected")},
        artifact=_header_artifact(row["artifact"])) for row in candidates]
    summary = receipt.get("summary") or {}
    return {"state": receipt.get("state", run["state"]), "result_persisted": receipt.get("result_persisted", False),
        "error": _failure(dict(run, state=receipt.get("state", run["state"])), receipt), "candidates": manifest,
        "selection": receipt.get("selection"),
        "summary": {key: value for key, value in summary.items() if type(value) in (int, float, str, bool) or value is None}}


def build_failure_read_models(run, admission_decision, result):
    """Failed/interrupted terminal heads reuse their actual saved admission block."""
    return {"run_model": {"projection_version": PROJECTION_VERSION, "header": _header(run, result, []),
        **{key: admission_decision[key] for key in ("context", "memberships", "calendar", "official")}, "process": None},
        "candidate_models": []}


def build_decision_read_models(run, capture, receipt, candidates, prepared_candidates, *, facts, admission, process=None):
    """Consume verified rows once; receipt/capture/tasks are never read here."""
    members = _Members(admission["memberships"])
    context = dict(admission["context"])
    expanded = Memberships(admission["memberships"])
    refs = expanded.refs(context["admission_operation_refs"], "operation")
    deferred = set(expanded.refs(context["deferred_operation_refs"], "operation"))
    batch_refs, disposition = sorted(capture["input"]["batch_refs"]), dispositions(receipt)
    skipped = {ref for ref in refs if (disposition or {}).get(ref, {}).get("status") == "skipped"} - deferred
    operation_scope = set(refs), deferred, skipped
    deferred_ids = {facts.operations[ref] for ref in deferred}
    legacy_deferred_ids = material_deferred_ids((disposition or {}).values(), capture["input"])
    efforts = saved_operation_efforts((receipt or {}).get("operation_effort"), identities=facts.operations)
    standards = admission_operation_standards(facts, refs, run["run_ref"])
    basis, candidate_models = selection_basis(receipt, candidates), []
    unified = ((receipt or {}).get("selection") or {}).get("generation_policy_version") == "unified_search_v1"
    default_reference = (next((row for row in candidates if row["candidate_ref"] == basis["selected_candidate_ref"]
                              and row["status"] == "completed"), None) if unified else
                         next((row for row in candidates if row["status"] == "completed" and row["artifact"].get("kind") == "baseline"), None))
    if default_reference is None:
        context["missing_candidate_reference"] = members.encode(_missing_candidate_reference(
            run, facts, refs, deferred, batch_refs, receipt, standards))
    else:
        context.pop("missing_candidate_reference", None)
    for candidate in candidates:
        ref = candidate["candidate_ref"]
        packet = prepared_candidates[ref]
        intervals = packet["intervals"]
        tasks = packet.get("tasks")
        if tasks is None:
            tasks = project_validated_tasks(packet["raw_tasks"], candidate, facts, intervals,
                                            prepared_tasks=packet.get("prepared_tasks"))
        available = candidate["status"] == "completed"
        delivery = project_decision_delivery(facts, tasks, batch_refs, candidate=candidate, available=available,
            deferred_ids=deferred_ids, intervals=intervals)
        summary = project_candidate_summary(candidate, tasks, facts, disposition, batch_refs, basis, candidates, delivery,
                                            operation_scope=operation_scope)
        summary.update(run_ref=run["run_ref"],
                       catalog=candidate_summary(candidate, disposition, scheduled_op_ids=packet["scheduled_op_ids"]),
                       scheduled_operation_refs=sorted({row["operation_ref"] for row in tasks}),
                       resource_views=_resource_views(tasks, refs, intervals))
        prepared = project_decision_preparation(facts, refs, efforts, tasks, run_ref=run["run_ref"], available=available,
            deferred_refs=deferred, standards=standards,
            requirements_available=(receipt or {}).get("operation_effort") is not None or available)
        work = preparation_work_items(facts, prepared["rows"], disposition, available=available)
        completion = project_completion_summary(delivery, work, available=available, schedulable_coverage=summary["coverage"]["schedulable"])
        detail = project_legacy_delivery_detail(candidate, facts, tasks, disposition, capture["input"], intervals=intervals,
                                                deferred_ids=legacy_deferred_ids)
        candidate_models.append({"candidate_ref": ref, "run_ref": run["run_ref"], "projection_version": PROJECTION_VERSION,
            "summary": members.encode(summary), "preparation": members.encode(prepared["summary"]),
            "completion": members.encode(completion), "delivery": delivery, "delivery_detail": detail,
            "arrangements": _arrangements(tasks)})
    header = members.encode(_header(run, receipt, candidates))
    context["operation_batch_indices"] = _operation_batches(facts, members)
    return {"run_model": {"projection_version": PROJECTION_VERSION, "header": header,
        "context": context, "memberships": members.value, "calendar": admission["calendar"], "official": admission["official"],
        "process": process if process is not None else {"version": PROCESS_VERSION,
            "candidates": [candidate_process(candidate, candidates) for candidate in candidates]}}, "candidate_models": candidate_models}
