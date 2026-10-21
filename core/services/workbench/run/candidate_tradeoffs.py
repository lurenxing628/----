"""Dashboard's existing viewing scope consumes the same tradeoff projection."""

from core.services.workbench.facts.changeovers import subject_arrangements
from core.services.workbench.facts.common_completed_delivery import common_completed_delivery
from core.services.workbench.facts.decision_metrics import (
    delivery_metric_values,
    metric_definitions,
    metric_delta,
    metric_value,
)

from .decision_recommendation import RECOMMENDATION_VERSION
from .decision_tradeoffs import aggregate_tradeoffs, tradeoff_entry


def candidate_tradeoffs(data, before_delivery, after_delivery, before_tasks, after_tasks, *, subject_operation_refs,
                        before_intervals=None, after_intervals=None):
    candidate_ref, run_ref = data["candidate"]["candidate_ref"], data["generation"]["run_ref"]
    common = common_completed_delivery(before_delivery, after_delivery)
    refs, pair = common["common_completed_batch_refs"], common["common_delivery"]
    delivery_values = {side: delivery_metric_values(pair[side]) for side in ("before", "after")}
    definitions = [item for item in metric_definitions() if item["group"] == "delivery" or item["source"] == "archived_resource_calendar"
                   or item["key"] in ("type_changeover_count", "machine_change_count")]
    entries = []
    resource_support = {
        kind: [{"kind": "resource", "ref": row["resource_ref"],
                "query": {"resource_kind": kind, "resource_ref": row["resource_ref"]}, "tab": "resources"}
               for row in data["resources"] if row["kind"] == kind and row["delta"] is not None and row["delta"] != 0][:3]
        for kind in ("machine", "operator")
    }
    for definition in definitions:
        name, scope, support = definition["key"], definition["scope"], []
        if definition["group"] == "delivery":
            scope = "common_completed_batches"
            previous, selected = delivery_values["before"][name], delivery_values["after"][name]
            support = [{"kind": "batch", "ref": ref, "query": {"batch_ref": ref}, "tab": "batches"} for ref in refs[:3]]
        elif definition["source"] == "archived_resource_calendar":
            kind, field = name.split("_", 1)
            values = [data["resource_common"][side][kind] for side in ("before", "after")]
            previous, selected = [metric_value(row[field], total=row["resource_count"], unknown=int(row[field] is None),
                                                scope=scope, metric_version=definition["metric_version"]) for row in values]
            support = resource_support[kind]
        elif name == "type_changeover_count":
            previous, selected = [metric_value(data["summary"][side]["changeovers"]["value"], scope=scope,
                                               unknown=int(data["summary"][side]["changeovers"]["value"] is None)) for side in ("before", "after")]
            for value, tasks, intervals in ((previous, before_tasks, before_intervals), (selected, after_tasks, after_intervals)):
                value["covered_operation_refs"] = sorted({row["operation_ref"] for row in subject_arrangements(
                    tasks, subject_operation_refs, task_intervals=intervals)})
        else:
            changes = data["machine_changes"]
            previous, selected = metric_value(0, scope=scope), metric_value(changes["count"], scope=scope, unknown=changes["unknown_count"])
            support = [{"kind": "operation", "ref": ref, "query": {"operation_ref": ref}, "tab": "operations"} for ref in changes["operation_refs"][:3]]
        delta = metric_delta(definition, selected, previous)
        if definition["group"] == "delivery" and not refs:
            delta.update(state="unavailable", value=None, direction="neutral", reason={"code": "common_completed_set_empty", "message": "当前两侧没有共同完整完成的批次。"})
        elif definition["group"] == "delivery" and pair["before"]["state"] == pair["after"]["state"] == "not_applicable":
            delta.update(state="not_applicable", direction="neutral", reason={"code": "common_due_unspecified", "message": "共同完整批次全部未指定交期。"})
        elif definition["group"] == "delivery" and (pair["before"]["invalid_due_count"] or pair["after"]["invalid_due_count"]):
            delta["reason"] = {"code": "common_due_invalid", "message": "共同完整批次包含无效交期，整项交付评价保持未知。"}
        tab = "batches" if definition["group"] == "delivery" else "resources" if definition["group"] == "resources" else "changeovers" if name == "type_changeover_count" else "operations"
        support = support or [{"kind": "collection", "ref": None, "query": {}, "tab": tab}]
        supporting_refs = [{"kind": row["kind"], "ref": row["ref"], "candidate_ref": candidate_ref,
            "drill": {"run_ref": run_ref, "candidate_ref": candidate_ref, "selected_candidate_ref": candidate_ref,
                "comparison_mode": "admission_official", "reference_candidate_ref": None,
                "range_start": data["time_scope"]["range_start"], "range_end": data["time_scope"]["range_end"],
                "resource_view": "selected_batches", "comparison_tab": row["tab"], "detail_query": row["query"]}}
            for row in support]
        entries.append(tradeoff_entry(definition, delta, scope=scope, source=definition["source"], metric_version=definition["metric_version"],
                                      supporting_refs=supporting_refs, compared_batch_refs=refs if definition["group"] == "delivery" else ()))
    return {"recommendation_version": RECOMMENDATION_VERSION, "scope": "admission_selected_batches", **aggregate_tradeoffs(entries, definitions)}
