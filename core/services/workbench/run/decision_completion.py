"""Request-local completed cohorts and remaining demand from archived facts."""

from core.services.workbench.facts.completion_scope import (
    attach_remaining_operations,
    completion_groups,
    project_completion_summary,
)
from core.services.workbench.facts.decision_delivery import common_delivery
from core.services.workbench.facts.decision_preparation import preparation_work_items
from core.services.workbench.facts.preparation_projection import public_preparation_metrics


class DecisionCompletion:
    def __init__(self, source):
        self.source, self._delivery, self._scopes, self._remaining = source, {}, {}, {}
        self._work = {}

    def delivery(self, key):
        if key == "reference" and self.source.comparison_mode == "candidates" and self.source.reference_ref:
            return self.delivery(self.source.reference_ref)
        if key not in self._delivery:
            self._delivery[key] = self.source.delivery(key)
        return self._delivery[key]

    def scope(self, key, coverage=None, *, details=False):
        key = self.source.computation_key(key)
        cache_key = key, details
        if cache_key not in self._scopes:
            source = self.source
            if not details and (key != "reference" or not source.official_changed):
                self._scopes[cache_key] = source.saved_projection(key, "completion")
                return self._scopes[cache_key]
            if details:
                self._scopes[cache_key] = attach_remaining_operations(self.scope(key, coverage), self.work_items(key))
            else:
                self._scopes[cache_key] = project_completion_summary(self.delivery(key), self.work_items(key),
                    available=source.preparation.available(key), schedulable_coverage=coverage)
        return self._scopes[cache_key]

    def work_items(self, key):
        if key not in self._work:
            source = self.source
            available = source.preparation.available(key)
            self._work[key] = preparation_work_items(source.facts, source.preparation.rows(key), source.disposition,
                available=available, labels=source.preparation.labels if available else None)
        return self._work[key]

    def groups(self, candidates):
        rows = [{"candidate_ref": row["candidate_ref"], "persisted_status": row["persisted_status"],
                 "completion_scope": self.scope(row["candidate_ref"], row["coverage"]["schedulable"])} for row in candidates]
        return completion_groups(rows)

    def remaining_batches(self, key):
        if key not in self._remaining:
            self._remaining[key] = {row["batch_ref"]: row for row in self.scope(key)["remaining_batches"]}
        return self._remaining[key]

    def remaining_operation_refs(self, key):
        scope = self.scope(key)
        return set(scope["unplanned_operation_refs"]) | set(scope["deferred_operation_refs"])

    def common(self, key):
        return common_delivery(self.delivery("reference"), self.delivery(key))


def compact_completion(value, drill):
    names = (("complete", "complete_batch_refs"), ("incomplete", "incomplete_batch_refs"),
             ("ordinary_incomplete", "ordinary_incomplete_batch_refs"), ("deferred", "deferred_batch_refs"),
             ("unknown", "unknown_batch_refs"))
    available = value["source_available"]
    return {"scope": "full_admission", "state": value["state"], "source_available": available,
            **{name + "_batch_count": len(value[key]) for name, key in names},
            "unplanned_operation_count": len(value["unplanned_operation_refs"]) if available else None,
            "deferred_operation_count": len(value["deferred_operation_refs"]) if available else None,
            "sample_batch_refs": {name: value[key][:3] for name, key in names if name != "ordinary_incomplete"},
            "remaining_work": {"metrics": public_preparation_metrics(value["remaining_work"]["metrics"]),
                "operation_count": len(value["unplanned_operation_refs"]) + len(value["deferred_operation_refs"]) if available else None,
                "unplanned_operation_count": len(value["unplanned_operation_refs"]) if available else None,
                "deferred_operation_count": len(value["deferred_operation_refs"]) if available else None}, "drill": drill}


def compact_common(value):
    refs, pair = value["common_completed_batch_refs"], value["common_delivery"]
    state = "unavailable" if not refs else pair["after"]["state"] if pair["before"]["state"] == pair["after"]["state"] else "partial"
    return {"scope": "common_completed_batches", "state": state, "batch_count": len(refs), "sample_batch_refs": refs[:3],
            **{side: {key: number for key, number in pair[side].items() if not key.endswith("_refs")} for side in ("before", "after")},
            "delay_delta_hours": pair["delay_delta_hours"], "overdue_delta_count": pair["overdue_delta_count"]}
