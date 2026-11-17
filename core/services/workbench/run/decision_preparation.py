"""One saved requirement ledger, allocated by each candidate's actual task rows."""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from core.services.workbench.facts.candidate_tasks import operation_labels
from core.services.workbench.facts.decision_preparation import (
    admission_operation_standards,
    project_decision_preparation,
    project_decision_preparation_row,
)
from core.services.workbench.facts.preparation_projection import (
    preparation_delta,
    public_preparation_metrics,
    public_preparation_roles,
)

if TYPE_CHECKING:
    from .decision_source import DecisionSource


class DecisionPreparation:
    def __init__(self, source: DecisionSource):
        self.source = source
        self._rows, self._rows_by_ref, self._summaries, self._labels_by_ref = {}, {}, {}, {}

    def label_for(self, ref):
        if ref not in self._labels_by_ref:
            self._labels_by_ref[ref] = operation_labels(self.source.facts, ref)[0]
        return self._labels_by_ref[ref]

    @cached_property
    def labels(self):
        return {ref: self.label_for(ref) for ref in self.source.admitted_operation_refs}

    @cached_property
    def current_standards(self):
        return admission_operation_standards(self.source.facts, self.source.admitted_operation_refs, self.source.run["run_ref"])

    @cached_property
    def reference_deferred(self):
        if self.source.comparison_mode == "candidates":
            return self.source.deferred_refs
        return {ref for ref in self.source.admitted_operation_refs if self.source.facts.operations[ref] in self.source.reference_deferred_ids}

    def rows(self, key):
        key = self.source.computation_key(key)
        if key not in self._rows:
            source = self.source
            formal = key == "reference" and source.comparison_mode == "admission_official"
            available = source.arrangement_available(key)
            requirements_available = available if formal else source.receipt.operation_effort is not None or available
            projection = project_decision_preparation(source.facts, source.admitted_operation_refs,
                {} if formal else source.operation_efforts, source.operation_arrangements(key), run_ref=source.run["run_ref"], available=available,
                deferred_refs=self.reference_deferred if key == "reference" else source.deferred_refs,
                requirements_available=requirements_available, official=source.official_details if formal else None,
                standards=None if formal else self.current_standards)
            rows = projection["rows"]
            self._rows[key] = rows
            self._rows_by_ref[key] = {row["operation_ref"]: row for row in rows}
        return self._rows[key]

    def _row(self, key, ref, task):
        source = self.source
        formal = key == "reference" and source.comparison_mode == "admission_official"
        return project_decision_preparation_row(source.facts, ref, task, {} if formal else source.operation_efforts,
            run_ref=source.run["run_ref"], available=source.arrangement_available(key),
            deferred_refs=self.reference_deferred if key == "reference" else source.deferred_refs,
            official=source.official_details if formal else None, standards=None if formal else self.current_standards)

    def summary(self, key):
        key = self.source.computation_key(key)
        if key not in self._summaries:
            self._summaries[key] = self.source.saved_projection(key, "preparation")
        return self._summaries[key]

    def metrics(self, key):
        return self.summary(key)["metrics"]

    def demand_hours(self, key):
        return self.summary(key)["demand"]["value"]

    def compact(self, key, ref):
        key = self.source.computation_key(key)
        self.rows(key)
        if ref not in self._rows_by_ref[key] and key == "reference" and self.source.comparison_mode == "admission_official":
            self._rows_by_ref[key][ref] = self._row(key, ref, self.source.operation_arrangements("reference").get(ref))
        return {field: value for field, value in self._rows_by_ref[key][ref].items()
                if field not in ("operation_ref", "arranged")}

    def public_summary(self):
        before, after = (self.summary(key) for key in ("reference", self.source.selected_ref))
        return {"scope": "full_admission", "before": public_preparation_metrics(before["metrics"]),
                "after": public_preparation_metrics(after["metrics"]),
                "deltas": {key: preparation_delta(value, before["metrics"][key]) for key, value in after["metrics"].items()},
                "role_totals": {"before": public_preparation_roles(before["role_totals"]), "after": public_preparation_roles(after["role_totals"])}}

    def public_coverage(self, key):
        summary = self.summary(key)
        return {"scope": "full_admission", "role_totals": public_preparation_roles(summary["role_totals"])}
