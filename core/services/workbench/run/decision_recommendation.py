"""Fixed saved recommendation with current-reference business tradeoffs."""

from typing import Any, Dict, cast

from core.services.workbench.facts.decision_metrics import delivery_metric_values, metric_delta
from core.services.workbench.facts.delivery_projection import delivery_batch_delta

from .decision_completion import compact_common, compact_completion
from .decision_impact import _arrangement, _drill, _operation_delta
from .decision_tradeoffs import aggregate_tradeoffs, tradeoff_entry

RECOMMENDATION_VERSION = "decision-recommendation-v1"


def detail_drill(source, candidate_ref, tab, query=None):
    """Target the saved recommendation while retaining the original view context."""
    return {"run_ref": source.run["run_ref"], "candidate_ref": candidate_ref,
            "selected_candidate_ref": candidate_ref, "comparison_mode": source.comparison_mode,
            "reference_candidate_ref": source.reference_ref, "range_start": source.scope["range_start"],
            "range_end": source.scope["range_end"], "resource_view": source.resource_view,
            "comparison_tab": tab, "detail_query": query or {}}


def _support(source, candidate_ref, kind, ref, tab, query, *, tasks=None, operation_ref=None, batch_ref=None, before=False):
    if tasks is None:
        drill = detail_drill(source, candidate_ref, tab, query)
    else:
        # operations excludes unavailable baselines before calling with before=True;
        # all other callers use before=False.
        drill = cast(Dict[str, Any], _drill(source, tasks=tasks, batch_ref=batch_ref, operation_ref=operation_ref, before=before))
        if not before or source.comparison_mode == "admission_official":
            drill["candidate_ref"] = candidate_ref
        drill.update(selected_candidate_ref=candidate_ref, resource_view=source.resource_view)
        if len(tasks) == 1:
            drill["selected_row_ref"] = tasks[0]["row_ref"]
        drill.update(query)
    return {"kind": kind, "ref": ref, "candidate_ref": candidate_ref, "side": "reference" if before else "selected", "drill": drill}


class RecommendationSupport:
    def __init__(self, source, candidate_ref):
        self.source, self.key = source, candidate_ref
        self._batches, self._operations = None, None

    def batches(self, direction, metric):
        source, key = self.source, self.key
        if self._batches is None:
            old, new = ({row["batch_ref"]: row for row in source.completion.delivery(name)} for name in ("reference", key))
            self._batches = [(ref, old[ref], new[ref], delivery_batch_delta(old[ref], new[ref])) for ref in sorted(new)]
        result = []
        for ref, before, after, delta in self._batches:
            number = delta["delay_delta_hours"] if metric == "total_tardiness_hours" else (
                int(after["risk"] == "overdue") - int(before["risk"] == "overdue") if before["schedule_complete"] and after["schedule_complete"] else None)
            if number is not None and number != 0 and (number < 0) == (direction == "better"):
                result.append(_support(source, key, "batch", ref, "batches", {"batch_ref": ref}))
                if len(result) == 3:
                    break
        return result

    def operations(self, metric):
        source, key = self.source, self.key
        if source.baseline["state"] != "available":
            return []
        if source.computation_key(key) == source.computation_key("reference"):
            return []
        if self._operations is None:
            old, new = source.analysis_groups("reference"), source.analysis_groups(key)
            self._operations = []
            for ref in source.scope["operation_refs"]:
                previous, current = old[ref], new[ref]
                delta = _operation_delta(_arrangement(previous), _arrangement(current),
                    task_intervals=source.task_intervals(key), reference_task_intervals=source.task_intervals("reference"))
                known_change = any(kind not in ("unknown", "unchanged") for kind in delta["change_kinds"])
                # The common operation-change metrics keep multiple segments in
                # unknown coverage; they are not samples of a known adjustment.
                if known_change and len(previous) <= 1 and len(current) <= 1:
                    self._operations.append((ref, delta, current or previous, not current))
        rows = [(ref, tasks, before) for ref, delta, tasks, before in self._operations
                if metric != "machine_change_count" or delta["machine_changed"] is True]
        return [_support(source, key, "operation", ref, "operations", {}, tasks=tasks,
                batch_ref=source.operation_batch_ref(ref), operation_ref=ref, before=before) for ref, tasks, before in rows[:3]]

    def resources(self, definition, direction):
        source, key = self.source, self.key
        kind, field = definition["key"].split("_", 1)
        flags = {"high_pressure_count": "high_pressure", "zero_capacity_task_count": "zero_capacity_task",
                 "conflict_resource_count": "conflict"}
        result = []
        for resource in source.resources.resources:
            if resource["kind"] != kind:
                continue
            old, new = (source.resources._window_rows[source.computation_key(name), resource["ref"]] for name in ("reference", key))
            name = flags.get(field, field)
            previous, selected = old.get(name), new.get(name)
            if type(previous) not in (int, float, bool) or type(selected) not in (int, float, bool):
                continue
            value = selected - previous
            if value and (value < 0) == (direction == "better"):
                ref = resource["ref"]
                result.append(_support(source, key, "resource", ref, "resources", {"resource_kind": kind, "resource_ref": ref}))
                if len(result) == 3:
                    break
        return result

    def entries(self, definition, delta):
        source, key = self.source, self.key
        name, group = definition["key"], definition["group"]
        if name in ("unplanned_operation_count", "deferred_operation_count"):
            remaining = source.completion.scope(key)
            allocation = "unplanned" if name == "unplanned_operation_count" else "deferred"
            refs = remaining[allocation + "_operation_refs"]
            values = [_support(source, key, "preparation", ref, "preparation", {"work_scope": "remaining", "allocation_state": allocation, "batch_ref": source.operation_batch_ref(ref)}) for ref in refs[:3]]
        elif group == "delivery":
            values = self.batches(delta["direction"], name)
        elif group == "stability":
            values = self.operations(name)
        elif definition["source"] == "runtime_operation_effort":
            remaining = source.completion.scope(key)
            refs = remaining["unplanned_operation_refs"] + remaining["deferred_operation_refs"]
            values = [_support(source, key, "preparation", ref, "preparation", {"work_scope": "remaining", "batch_ref": source.operation_batch_ref(ref)}) for ref in refs[:3]]
        elif definition["source"] == "archived_changeover_events":
            events = source.changeovers.projection(key)["events"][:3]
            lookup = {task["row_ref"]: task for task in source.changeovers.tasks(key)}
            values = [_support(source, key, "changeover", row["next_row_ref"], "changeovers", {"resource_ref": row["machine_ref"], "resource_kind": "machine"},
                tasks=[lookup[row["next_row_ref"]]], batch_ref=lookup[row["next_row_ref"]]["batch_ref"], operation_ref=row["next_operation_ref"]) for row in events]
        elif definition["source"] == "archived_resource_calendar":
            values = self.resources(definition, delta["direction"])
        else:
            values = []
        tab = ("changeovers" if definition["source"] == "archived_changeover_events" else
               "batches" if group in ("delivery", "completeness") else "resources" if group == "resources" else
               "preparation" if group == "preparation" else "operations")
        return values or [_support(source, key, "collection", None, tab, {})]


def recommendation(source, candidates, definitions):
    basis = source.basis
    selected = next((row for row in candidates if row["candidate_ref"] == basis["selected_candidate_ref"]), None)
    axes = {"algorithm": {"state": "selected" if selected else "unavailable", "reason_code": basis["reason_code"],
                          "evidence_state": basis["evidence_state"]},
            "completion": {"search": selected["coverage"]["search"] if selected else None,
                           "schedulable": selected["coverage"]["schedulable"] if selected else None, "delivery": None},
            "preflight": {"state": "not_checked", "source": "existing_adoption_preview"}}
    result = {"recommendation_version": RECOMMENDATION_VERSION, "state": "available" if selected else "unavailable",
              "candidate_ref": basis["selected_candidate_ref"], "viewed_candidate_ref": source.selected_ref,
              "recommendation_type": None, "headline": "本次排产尚未保存推荐方案。", "axes": axes,
              "completion_scope": None, "reason_code": basis["reason_code"], "selection_basis": basis,
              "benefits": [], "costs": [], "current_comparison": {"state": "unavailable", "candidate_ref": basis["selected_candidate_ref"],
                "viewed_candidate_ref": source.selected_ref, "reference": source.baseline,
                "benefits": [], "costs": [], "all_differences": [], "common_completed_delivery": None}}
    if selected is None:
        return result
    key, schedulable = selected["candidate_ref"], selected["coverage"]["schedulable"]
    scope = source.completion.scope(key, schedulable)
    compact = compact_completion(scope, detail_drill(source, key, "preparation", {"work_scope": "remaining"}))
    complete = scope["state"] == "complete" and schedulable["state"] == "complete"
    deferred = schedulable["state"] == "complete" and bool(scope["deferred_batch_refs"]) and not (
        scope["ordinary_incomplete_batch_refs"] or scope["unknown_batch_refs"] or scope["unplanned_operation_refs"])
    kind = "complete" if complete else "schedulable_scope" if deferred else "partial"
    label = selected["label"] or key
    facts = []
    if scope["complete_batch_refs"]:
        facts.append(str(len(scope["complete_batch_refs"])) + " 批工序已排齐")
    if scope["unplanned_operation_refs"]:
        facts.append(str(len(scope["unplanned_operation_refs"])) + " 道工序未安排")
    if scope["deferred_operation_refs"]:
        facts.append(str(len(scope["deferred_operation_refs"])) + " 道工序因缺料暂未安排")
    if scope["unknown_batch_refs"]:
        facts.append(str(len(scope["unknown_batch_refs"])) + " 批缺少安排资料，请查看原因")
    headline = "推荐方案：" + label + ("；" + "；".join(facts) if facts else "；工序安排资料未保存") + "。"
    common = source.completion.common(key)
    pair, batch_refs = common["common_delivery"], common["common_completed_batch_refs"]
    common_values = {side: delivery_metric_values(pair[side]) for side in ("before", "after")}
    support, entries = RecommendationSupport(source, key), []
    for definition in definitions:
        name, delta = definition["key"], selected["deltas"][definition["key"]]
        entry_scope = definition["scope"]
        refs = ()
        if definition["group"] == "delivery":
            entry_scope, refs = "common_completed_batches", batch_refs
            delta = metric_delta(definition, common_values["after"][name], common_values["before"][name])
            if not refs:
                delta.update(value=None, state="unavailable", direction="neutral",
                             reason={"code": "common_completed_set_empty", "message": "推荐与当前基准没有双方工序都已排齐的批次。"})
            elif pair["before"]["state"] == pair["after"]["state"] == "not_applicable":
                delta.update(state="not_applicable", direction="neutral",
                             reason={"code": "common_due_unspecified", "message": "双方工序都已排齐的批次均未填写交期。"})
            elif pair["before"]["invalid_due_count"] or pair["after"]["invalid_due_count"]:
                delta["reason"] = {"code": "common_due_invalid", "message": "部分双方工序都已排齐的批次交期格式有误，无法比较交期。"}
        elif delta["state"] == "unavailable":
            delta = {**delta, "reason": selected["metrics"][name].get("reason") or (
                {"code": "reference_unavailable", "message": "当前查看基准缺少可用的归档值。"} if source.baseline["state"] != "available" else None)}
        entries.append(tradeoff_entry(definition, delta, scope=entry_scope, source=definition["source"],
            metric_version=definition["metric_version"], supporting_refs=support.entries(definition, delta), compared_batch_refs=refs))
    comparison = {"state": source.baseline["state"],
                  "candidate_ref": key, "viewed_candidate_ref": source.selected_ref, "reference": source.baseline,
                  **aggregate_tradeoffs(entries, definitions), "common_completed_delivery": compact_common(common)}
    axes["completion"]["delivery"] = compact
    result.update(recommendation_type=kind, headline=headline, completion_scope=compact, current_comparison=comparison,
                  benefits=[row for row in entries if row["direction"] == "better"], costs=[row for row in entries if row["direction"] == "worse"])
    return result
