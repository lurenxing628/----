"""Pure immutable decision projections from the caller's prepared archive rows."""

from copy import deepcopy
from typing import Any, Dict, List, Optional, overload

from core.models.enums import RUN_RESOURCE_VIEW_VALUES
from core.models.workbench_preflight import preflight_window
from core.models.workbench_run_receipt import FailedReceipt, PersistedReceipt

from .admission_scope import project_admitted_scope
from .archived_calendar import CALENDAR_TABLES, ArchivedCalendar, archived_calendar_tables
from .candidate_delivery import project_delivery_detail
from .candidate_facts import RESOURCE_TABLES
from .candidate_projection import candidate_summary, completed_dispositions
from .candidate_tasks import project_validated_tasks
from .candidate_values import text
from .changeovers import changeover_projection
from .completion_scope import project_completion_summary
from .decision_baseline import read_decision_baseline
from .decision_candidate import project_candidate_summary
from .decision_delivery import project_decision_delivery
from .decision_metrics import admission_deferred_refs, admission_operation_refs, project_official_core_metrics
from .decision_preparation import admission_operation_standards, preparation_work_items, project_decision_preparation
from .decision_read_models import (
    ARRANGEMENT_COLUMNS,
    BATCH_MEMBERS,
    OPERATION_MEMBERS,
    Memberships,
    build_changeover_metrics,
    build_operation_catalog_rows,
    build_resource_metrics_from_summaries,
    build_side_batch_rows,
    build_side_operation_rows,
    by_operation,
)
from .decision_selection import selection_basis
from .operation_effort_evidence import saved_operation_efforts
from .preflight_dependencies import material_deferred_ids
from .preparation_projection import ALLOCATIONS
from .resource_calendar import normalize_resource_calendar
from .resource_intervals import resource_cohort
from .resource_pressure import DEFAULT_PRESSURE_THRESHOLD
from .resource_projection import ResourceTaskIndex, resource_summary
from .run_history_projection import failure_reason, scope_summary


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
        result = {}
        for field, item in value.items():
            if field == "input":
                result[field] = item
            elif type(item) is list and (field in OPERATION_MEMBERS or parent == "coverage" and field in ALLOCATIONS):
                result[field] = self.member(item, "operation")
            elif type(item) is list and field in BATCH_MEMBERS:
                result[field] = self.member(item, "batch")
            else:
                result[field] = self.encode(item, field)
        return result


def build_admission_read_model(capture, *, facts):
    """Small history/status scope; the decision block lives in its separate column."""
    options = capture["run_options"]
    summary = dict(scope_summary(capture["input"]), run_options=options)
    workload = project_admitted_scope(capture["input"], facts, summary=summary)
    return {"scope_summary": summary, "input": capture["input"], "run_options": options,
            **{field: workload[field] for field in ("batches", "operation_count", "objective", "objective_label")},
            "workload_data_gaps": workload["data_gaps"]}


def _calendar(facts):
    """The admitted archive's calendar part, kept in the archive's own positional shape."""
    source = facts.archive
    return {"columns": {name: source["columns"][name] for name in CALENDAR_TABLES},
            "tables": {name: source["tables"][name] for name in CALENDAR_TABLES}}


def _resources(facts, tasks):
    resources = {}
    for (kind, key), ref in facts.entity_refs.items():
        if kind not in ("machine", "operator", "supplier"):
            continue
        resources[(kind, ref)] = {"kind": kind, "ref": ref, "saved_id": key,
                                  "label": text(facts.related(RESOURCE_TABLES[kind], key)["name"], kind + ".label", [])}
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
        rows.append([row.get(field) for field in ARRANGEMENT_COLUMNS])
    return {"columns": list(ARRANGEMENT_COLUMNS), "rows": rows, "resource_values": resources}


def _arranged_resources(rows):
    resources = {}
    for task in rows:
        for kind in ("machine", "operator", "supplier"):
            value = task[kind]
            if value is not None and value["ref"] is not None:
                resources[(kind, value["ref"])] = {"kind": kind, "ref": value["ref"], "label": value["label"]}
    return [resources[key] for key in sorted(resources)]


def _resource_views(tasks, operation_refs, intervals):
    selected = set(operation_refs)
    result = {}
    for name, rows in (("selected_batches", [row for row in tasks if row["operation_ref"] in selected]), ("full_candidate", tasks)):
        members = resource_cohort([rows], task_intervals=[intervals])
        by_resource = {(row["kind"], row["ref"]): [] for row in members}
        for row in rows:
            interval = intervals[row["row_ref"]]
            if row["source"] == "external" or interval[0] == interval[1]:
                continue
            for kind in ("machine", "operator"):
                value = row[kind]
                if value is not None and (kind, value["ref"]) in by_resource:
                    by_resource[(kind, value["ref"])].append(interval)
        result[name] = {
            "resources": [dict(row,
                span_start=min(value[0] for value in by_resource[(row["kind"], row["ref"])]).isoformat()
                    if by_resource[(row["kind"], row["ref"])] else None,
                span_end=max(value[1] for value in by_resource[(row["kind"], row["ref"])]).isoformat()
                    if by_resource[(row["kind"], row["ref"])] else None) for row in members],
            "arranged_resources": _arranged_resources(rows),
        }
    return result


def _precompute_changeover_side(tasks, intervals, scope_op_refs, range_start, range_end, *, available: bool):
    projected = changeover_projection(tasks, start=range_start, end=range_end, work_available=available,
                                      next_operation_refs=scope_op_refs, task_intervals=intervals)
    return {"projection": projected, "metrics": build_changeover_metrics(projected, tasks, scope_op_refs, intervals)}


def _eval_resource_side(tasks_by_view, intervals, available: bool, modes, range_start, range_end,
                        off_res, cand_res, norm_cals):
    cohorts, details_by_view = {}, {}
    for view in RUN_RESOURCE_VIEW_VALUES:
        idx = ResourceTaskIndex(tasks_by_view[view], range_start, range_end, work_available=available,
                                task_intervals=intervals, retain_statistics_values=True)
        union_res = off_res[view] if "admission_official" in modes else cand_res[view]
        w_rows, d_summaries, d_periods = {}, {}, {}
        for res in union_res:
            ref = res["ref"]
            w_row, periods = idx.window_with_days(res, norm_cals[ref])
            d_summary = idx.day_filter_summary(res, norm_cals[ref], threshold=DEFAULT_PRESSURE_THRESHOLD)
            idx.release(res)
            w_rows[ref] = w_row
            d_summaries[ref] = d_summary
            d_periods[ref] = periods
        details_by_view[view] = {
            "window_rows": w_rows,
            "day_filter_summaries": d_summaries,
            "day_periods": d_periods,
        }
        for mode in modes:
            cohort_res = off_res[view] if mode == "admission_official" else cand_res[view]
            summaries = {kind: resource_summary([w_rows[r["ref"]] for r in cohort_res if r["kind"] == kind], kind=kind,
                         identity_issues=[it for it in idx.identity_issues if it["kind"] == kind], work_available=available)
                         for kind in ("machine", "operator")}
            cohorts[f"{mode}:{view}"] = {"summaries": summaries,
                "metrics": build_resource_metrics_from_summaries(summaries, w_rows, cohort_res, available)}
    return {"cohorts": cohorts, "details_by_view": details_by_view}


def _precompute_default_resources(run_ref, calendar_archive, context_resources, range_start, range_end,
                                  official_pack, candidate_packs):
    saved_ids = {(item["kind"], item["ref"]): item["saved_id"]
                 for item in context_resources if item["kind"] in ("machine", "operator")}
    cand_res, off_res = {}, {}
    for view in RUN_RESOURCE_VIEW_VALUES:
        c_ord, o_ord = {}, {}
        for pack in candidate_packs:
            for row in pack["resource_views"][view]["resources"]:
                item = {"kind": row["kind"], "ref": row["ref"], "label": row["label"],
                        "saved_id": saved_ids.get((row["kind"], row["ref"]))}
                c_ord.setdefault((row["kind"], row["ref"]), item)
                o_ord.setdefault((row["kind"], row["ref"]), item)
        for row in official_pack["resource_views"][view]["resources"]:
            o_ord.setdefault((row["kind"], row["ref"]),
                             {"kind": row["kind"], "ref": row["ref"], "label": row["label"],
                              "saved_id": saved_ids.get((row["kind"], row["ref"]))})
        cand_res[view] = [c_ord[k] for k in sorted(c_ord)]
        off_res[view] = [o_ord[k] for k in sorted(o_ord)]
    all_res = {r["ref"]: r for v in RUN_RESOURCE_VIEW_VALUES for r in off_res[v]}
    archived_cal = ArchivedCalendar(archived_calendar_tables(calendar_archive), source_ref=run_ref)
    norm_cals = {ref: normalize_resource_calendar(cal, range_start, range_end)
                 for ref, cal in archived_cal.iter_resources(list(all_res.values()), range_start, range_end)}
    out_official = _eval_resource_side(official_pack["tasks_by_view"], official_pack["intervals"],
                                       official_pack["available"], ("admission_official",),
                                       range_start, range_end, off_res, cand_res, norm_cals)
    out_candidates = {
        pack["candidate_ref"]: _eval_resource_side(pack["tasks_by_view"], pack["intervals"], True,
            ("admission_official", "candidates"), range_start, range_end, off_res, cand_res, norm_cals)
        for pack in candidate_packs
    }
    return out_official, out_candidates


def _operation_batches(facts, members):
    return [members.position(facts.operation_batch_ref(ref), "batch") for ref in members.value["operation_refs"]]


def _official_projection(run, facts, disposition, official, refs, batch_refs):
    tasks, scope_refs = official["tasks"], set(refs)
    selected = [row for row in tasks if row["operation_ref"] in scope_refs]
    available = official["identity"]["state"] == "available"
    deferred_ids = set(official["deferred_operation_ids"])
    official_deferred = {ref for ref, key in facts.operations.items() if key in deferred_ids}
    intervals = official["task_intervals"]
    delivery = project_decision_delivery(facts, selected, batch_refs, available=available,
        deferred_ids=deferred_ids, intervals=intervals)
    values, coverage = project_official_core_metrics(
        tasks, refs, official_deferred & scope_refs, available, delivery, task_intervals=intervals)
    prepared = project_decision_preparation(facts, refs, {}, by_operation(selected), run_ref=run["run_ref"], available=available,
        deferred_refs=official_deferred, requirements_available=available, official=official)
    work = preparation_work_items(facts, prepared["rows"], disposition, available=available)
    completion = project_completion_summary(delivery, work, available=available, schedulable_coverage=coverage["schedulable"])
    return {"identity": official["identity"], "source_states": official["source_states"],
        "operation_refs": sorted({row["operation_ref"] for row in tasks}), "deferred_operation_refs": sorted(official_deferred),
        "core_metrics": values, "coverage": coverage, "preparation": prepared["summary"], "completion": completion,
        "delivery": delivery, "arrangements": _arrangements(tasks), "resources": _resources(facts, tasks),
        "resource_views": _resource_views(tasks, refs, intervals)}


def _missing_candidate_reference(run, facts, refs, deferred, batch_refs):
    """Admission placeholder while a run has no selected candidate to compare against."""
    preparation = project_decision_preparation(facts, refs, {}, {}, run_ref=run["run_ref"],
        available=False, deferred_refs=deferred, requirements_available=False)
    delivery = project_decision_delivery(facts, [], batch_refs, available=False,
        deferred_ids={facts.operations[ref] for ref in deferred}, candidate=None, intervals={})
    return {"preparation": preparation["summary"], "delivery": delivery,
            "completion": project_completion_summary(delivery, [], available=False)}


def build_admission_decision_read_model(run, capture, official, *, facts, dispositions, dates):
    """Project the actual admission baseline once; callers own source resolution. ``dates`` is the admitted
    input's date range (``run_dates``), converted once by the caller."""
    refs = admission_operation_refs(facts, capture["input"])
    disposition = completed_dispositions(dispositions, expected_refs=refs)
    deferred = admission_deferred_refs(facts, capture["input"], refs, disposition)
    refs, batch_refs = sorted(refs), sorted(capture["input"]["batch_refs"])
    scope_op_refs = set(refs)
    members = _Members()
    for ref in refs:
        members.position(ref, "operation")
    for ref in batch_refs:
        members.position(ref, "batch")
    saved_official = _official_projection(run, facts, disposition, official, refs, batch_refs)
    range_start, range_end = preflight_window(dates)
    calendar_archive = _calendar(facts)
    missing_ref = _missing_candidate_reference(run, facts, refs, deferred, batch_refs)
    off_tasks, off_intervals = official["tasks"], official["task_intervals"]
    off_avail = official["identity"]["state"] == "available"
    saved_official["default_changeovers"] = _precompute_changeover_side(
        off_tasks, off_intervals, scope_op_refs, range_start, range_end, available=off_avail)
    missing_ref["default_changeovers"] = _precompute_changeover_side([], {}, scope_op_refs, range_start, range_end, available=False)
    context = {"input": capture["input"], "run_options": capture["run_options"],
        "range_start": range_start, "range_end": range_end,
        "admission_operation_refs": refs, "expected_operation_refs": sorted(scope_op_refs - deferred),
        "deferred_operation_refs": sorted(deferred), "official_members": {
            "identity": saved_official["identity"], "operation_refs": saved_official["operation_refs"]},
        "resources": saved_official["resources"], "missing_candidate_reference": missing_ref}
    encoded_official, encoded_context = members.encode(saved_official), members.encode(context)
    encoded_context["operation_batch_indices"] = _operation_batches(facts, members)
    return {"context": encoded_context, "memberships": members.value, "calendar": calendar_archive, "official": encoded_official,
            "dispositions": list(disposition.values())}


def prepare_admission_read_models(run, capture, official, *, facts, dispositions, dates):
    return {"scope": build_admission_read_model(capture, facts=facts),
            "decision": build_admission_decision_read_model(run, capture, official, facts=facts, dispositions=dispositions,
                                                            dates=dates)}


def _persisted_header(receipt: PersistedReceipt, candidates):
    saved_manifest = {row["candidate_ref"]: row for row in receipt.candidates}
    manifest = [dict(candidate_ref=row["candidate_ref"], sequence=row["sequence"],
        **{field: saved_manifest[row["candidate_ref"]][field] for field in ("label", "task_count", "selected")})
        for row in candidates]
    return {"state": receipt.state, "result_persisted": True, "error": None, "candidates": manifest,
        "selection": receipt.selection,
        "summary": {key: value for key, value in receipt.summary.items()
                    if type(value) in (int, float, str, bool) or value is None}}


def _failure_header(receipt: FailedReceipt):
    return {"state": receipt.state, "result_persisted": False,
            "error": failure_reason({"state": receipt.state}, {"error": receipt.error}), "candidates": [],
            "selection": None, "summary": {}}


def build_failure_read_models(admission_decision, result: FailedReceipt):
    """Failed/interrupted terminal heads reuse their actual saved admission block."""
    return {
        "run_model": {"header": _failure_header(result),
                      **{key: admission_decision[key] for key in ("context", "memberships", "calendar", "official")}, "process": None},
        "candidate_models": [], "side_batches": [], "operation_catalog": [], "side_operations": [], "side_resources": [],
    }


def _build_candidate_bundle(candidate, packet, *, run_ref, capture_input, facts, refs, scope_op_refs, batch_refs,
                            deferred, deferred_ids, receipt_deferred_ids, operation_scope, disposition,
                            efforts, standards, basis, range_start, range_end):
    ref, intervals = candidate["candidate_ref"], packet["intervals"]
    tasks = project_validated_tasks(packet["raw_tasks"], facts, intervals)
    delivery = project_decision_delivery(facts, tasks, batch_refs, candidate=candidate, available=True,
                                         deferred_ids=deferred_ids, intervals=intervals)
    summary = project_candidate_summary(candidate, tasks, facts, batch_refs, basis, delivery,
                                        operation_scope=operation_scope)
    res_views = _resource_views(tasks, refs, intervals)
    summary.update(run_ref=run_ref, catalog=candidate_summary(candidate, disposition, scheduled_op_ids=packet["scheduled_op_ids"]),
                   scheduled_operation_refs=sorted({row["operation_ref"] for row in tasks}), resource_views=res_views,
                   default_changeovers=_precompute_changeover_side(tasks, intervals, scope_op_refs, range_start, range_end, available=True))
    arranged = by_operation(tasks)
    prepared = project_decision_preparation(facts, refs, efforts, arranged, run_ref=run_ref, available=True,
                                            deferred_refs=deferred, standards=standards, requirements_available=True)
    work = preparation_work_items(facts, prepared["rows"], disposition, available=True)
    completion = project_completion_summary(delivery, work, available=True, schedulable_coverage=summary["coverage"]["schedulable"])
    detail = project_delivery_detail(candidate, facts, tasks, capture_input, intervals=intervals, deferred_ids=receipt_deferred_ids,
                                     precomputed_delivery=delivery if deferred_ids == receipt_deferred_ids else None)
    rem_refs = set(completion["unplanned_operation_refs"]) | set(completion["deferred_operation_refs"])
    cand_side_batches = build_side_batch_rows(ref, batch_refs, scope_op_refs, delivery, tasks, intervals)
    cand_side_ops = build_side_operation_rows(ref, refs, arranged, intervals, prepared["rows"], deferred, rem_refs)
    pack = {"candidate_ref": ref, "resource_views": res_views, "intervals": intervals,
            "tasks_by_view": {"selected_batches": [r for r in tasks if r["operation_ref"] in scope_op_refs], "full_candidate": tasks}}
    raw_model = {"candidate_ref": ref, "summary": summary, "preparation": prepared["summary"],
                 "completion": completion, "delivery": delivery, "delivery_detail": detail, "arrangements": _arrangements(tasks)}
    return pack, raw_model, cand_side_batches, cand_side_ops


def build_decision_read_models(run, capture, receipt: PersistedReceipt, candidates, prepared_candidates, *, facts,
                               admission, process):
    """Consume verified rows once; precompute default 4-cohort resources and 3 pagination tables."""
    members, context, expanded = _Members(admission["memberships"]), dict(admission["context"]), Memberships(admission["memberships"])
    # A finished run always compares against its selected candidate; the placeholder serves queued, running and failed runs.
    del context["missing_candidate_reference"]
    refs = expanded.refs(context["admission_operation_refs"], "operation")
    scope_op_refs, deferred = set(refs), set(expanded.refs(context["deferred_operation_refs"], "operation"))
    batch_refs, disposition = sorted(capture["input"]["batch_refs"]), completed_dispositions(receipt.dispositions, expected_refs=refs)
    skipped = {ref for ref in refs if disposition[ref]["status"] == "skipped"} - deferred
    deferred_ids = {facts.operations[ref] for ref in deferred}
    receipt_deferred_ids = material_deferred_ids(disposition.values(), capture["input"])
    efforts = saved_operation_efforts(receipt.operation_effort, identities=facts.operations)
    standards = admission_operation_standards(facts, refs, run["run_ref"])
    basis = selection_basis(receipt.selection, candidates)
    range_start, range_end = context["range_start"], context["range_end"]

    official_details = read_decision_baseline(capture, facts, disposition)
    off_tasks, off_intervals = official_details["tasks"], official_details["task_intervals"]
    off_avail = official_details["identity"]["state"] == "available"
    off_deferred = {ref for ref, op_id in facts.operations.items() if op_id in set(official_details["deferred_operation_ids"])}
    off_selected = [row for row in off_tasks if row["operation_ref"] in scope_op_refs]
    off_arranged = by_operation(off_selected)
    off_prep = project_decision_preparation(facts, refs, {}, off_arranged, run_ref=run["run_ref"], available=off_avail,
                                            deferred_refs=off_deferred, requirements_available=off_avail, official=official_details)
    expanded_official = expanded.expand(admission["official"])
    off_rem = set(expanded_official["completion"]["unplanned_operation_refs"]) | set(expanded_official["completion"]["deferred_operation_refs"])
    operation_catalog = build_operation_catalog_rows(facts, refs, disposition)
    side_batches = build_side_batch_rows("official", batch_refs, scope_op_refs, expanded_official["delivery"], off_selected, off_intervals)
    side_operations = build_side_operation_rows("official", refs, off_arranged, off_intervals,
                                                off_prep["rows"], off_deferred & scope_op_refs, off_rem)

    candidate_packs, raw_candidate_models = [], []
    for candidate in candidates:
        pack, raw_model, c_batches, c_ops = _build_candidate_bundle(
            candidate, prepared_candidates[candidate["candidate_ref"]], run_ref=run["run_ref"], capture_input=capture["input"],
            facts=facts, refs=refs, scope_op_refs=scope_op_refs, batch_refs=batch_refs, deferred=deferred, deferred_ids=deferred_ids,
            receipt_deferred_ids=receipt_deferred_ids, operation_scope=(scope_op_refs, deferred, skipped), disposition=disposition,
            efforts=efforts, standards=standards, basis=basis, range_start=range_start, range_end=range_end)
        candidate_packs.append(pack)
        raw_candidate_models.append(raw_model)
        side_batches.extend(c_batches)
        side_operations.extend(c_ops)

    off_pack = {"resource_views": expanded_official["resource_views"], "intervals": off_intervals, "available": off_avail,
                "tasks_by_view": {"selected_batches": off_selected, "full_candidate": off_tasks}}
    off_res, cand_res_by_ref = _precompute_default_resources(
        run["run_ref"], admission["calendar"], expanded.expand(context["resources"]), range_start, range_end,
        off_pack, candidate_packs)
    side_resources = [
        {"side_key": "official", "resource_view": view, "payload": members.encode(off_res["details_by_view"][view])}
        for view in RUN_RESOURCE_VIEW_VALUES
    ]

    updated_official = {**admission["official"], "default_resource_cohorts": members.encode(off_res["cohorts"])}
    candidate_models = []
    for item in raw_candidate_models:
        ref = item["candidate_ref"]
        cand_res = cand_res_by_ref[ref]
        candidate_models.append({
            "candidate_ref": ref, "run_ref": run["run_ref"],
            "summary": members.encode({**item["summary"], "default_resource_cohorts": cand_res["cohorts"]}),
            "preparation": members.encode(item["preparation"]), "completion": members.encode(item["completion"]),
            "delivery": item["delivery"], "delivery_detail": item["delivery_detail"], "arrangements": item["arrangements"],
        })
        side_resources.extend(
            {"side_key": ref, "resource_view": view, "payload": members.encode(cand_res["details_by_view"][view])}
            for view in RUN_RESOURCE_VIEW_VALUES
        )
    context["operation_batch_indices"] = _operation_batches(facts, members)
    return {"run_model": {"header": _persisted_header(receipt, candidates),
                          "context": context, "memberships": members.value, "calendar": admission["calendar"],
                          "official": updated_official, "process": process},
            "candidate_models": candidate_models, "side_batches": side_batches,
            "operation_catalog": operation_catalog, "side_operations": side_operations, "side_resources": side_resources}
