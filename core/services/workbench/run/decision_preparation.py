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

from .decision_impact import drill_target

if TYPE_CHECKING:
    from .decision_source import DecisionSource

_HOURS = ("setup_standard_hours", "processing_standard_hours", "required_standard_hours")


class DecisionPreparation:
    def __init__(self, source: DecisionSource):
        self.source = source
        self._rows, self._rows_by_ref, self._summaries, self._labels_by_ref = {}, {}, {}, {}

    def available(self, key):
        key = self.source.computation_key(key)
        if key == "reference":
            return self.source.baseline["state"] == "available"
        return next(row["status"] for row in self.source.rows if row["candidate_ref"] == key) == "completed"

    def label_for(self, ref):
        if ref not in self._labels_by_ref:
            self._labels_by_ref[ref] = operation_labels(self.source.facts, ref)[0]
        return self._labels_by_ref[ref]

    @cached_property
    def labels(self):
        return {ref: self.label_for(ref) for ref in self.source.scope["operation_refs"]}

    @cached_property
    def current_standards(self):
        return admission_operation_standards(self.source.facts, self.source.scope["operation_refs"], self.source.run["run_ref"])

    @cached_property
    def reference_deferred(self):
        if self.source.comparison_mode == "candidates":
            return self.source.deferred_refs
        return {ref for ref in self.source.scope["operation_refs"] if self.source.facts.operations[ref] in self.source.reference_deferred_ids}

    def rows(self, key):
        key = self.source.computation_key(key)
        if key not in self._rows:
            source = self.source
            formal = key == "reference" and source.comparison_mode == "admission_official"
            available = self.available(key)
            requirements_available = available if formal else source.receipt["operation_effort"] is not None or available
            projection = project_decision_preparation(source.facts, source.scope["operation_refs"],
                {} if formal else source.operation_efforts, self.source.analysis_tasks(key), run_ref=source.run["run_ref"], available=available,
                deferred_refs=self.reference_deferred if key == "reference" else source.deferred_refs,
                requirements_available=requirements_available, official=source.official_details if formal else None,
                standards=None if formal else self.current_standards, task_groups=self.source.analysis_groups(key))
            rows = projection["rows"]
            self._rows[key] = rows
            self._rows_by_ref[key] = {row["operation_ref"]: row for row in rows}
            self._summaries[key] = projection["summary"]
        return self._rows[key]

    def _row(self, key, ref, tasks):
        source = self.source
        formal = key == "reference" and source.comparison_mode == "admission_official"
        return project_decision_preparation_row(source.facts, ref, tasks, {} if formal else source.operation_efforts,
            run_ref=source.run["run_ref"], available=self.available(key),
            deferred_refs=self.reference_deferred if key == "reference" else source.deferred_refs,
            official=source.official_details if formal else None, standards=None if formal else self.current_standards)

    def summary(self, key):
        key = self.source.computation_key(key)
        if key not in self._summaries:
            if key != "reference" or not self.source.official_changed:
                self._summaries[key] = self.source.saved_projection(key, "preparation")
            else:
                self.rows(key)
        return self._summaries[key]

    def metrics(self, key):
        return self.summary(key)["metrics"]

    def demand_hours(self, key):
        return self.summary(key)["demand"]["value"]

    def compact(self, key, ref):
        key = self.source.computation_key(key)
        self.rows(key)
        if ref not in self._rows_by_ref[key] and key == "reference" and self.source.comparison_mode == "admission_official":
            self._rows_by_ref[key][ref] = self._row(key, ref, self.source.analysis_groups("reference")[ref])
        return {field: value for field, value in self._rows_by_ref[key][ref].items()
                if field not in ("operation_ref", "arranged")}

    def rows_by_ref(self, key):
        key = self.source.computation_key(key)
        self.rows(key)
        return self._rows_by_ref[key]

    def matches_machine(self, ref, machine_ref):
        source = self.source
        for key in ("reference", source.selected_ref):
            tasks = source.analysis_groups(key)[ref]
            if any(task["machine"] and task["machine"]["ref"] == machine_ref for task in tasks):
                return True
            formal = key == "reference" and source.comparison_mode == "admission_official"
            if not tasks and not formal:
                operation = source.facts.tables["BatchOperations"].get(source.facts.operations[ref], {})
                saved_id = operation.get("machine_id")
                saved_ref = source.facts.entity_refs.get(("machine", saved_id)) if type(saved_id) is str else None
                if saved_ref == machine_ref:
                    return True
        return False

    def _side(self, key, row):
        source, ref = self.source, row["operation_ref"]
        tasks = self.source.analysis_groups(key)[ref]
        machines = {task["machine"]["ref"]: task["machine"] for task in tasks if task["machine"] and task["machine"]["ref"] is not None}
        formal = key == "reference" and source.comparison_mode == "admission_official"
        if not tasks and not formal:
            operation = source.facts.tables["BatchOperations"].get(source.facts.operations[ref], {})
            saved_id = operation.get("machine_id")
            saved_ref = source.facts.entity_refs.get(("machine", saved_id)) if type(saved_id) is str else None
            if saved_ref is not None:
                machines[saved_ref] = {"ref": saved_ref, "label": source.facts.tables["Machines"].get(saved_id, {}).get("name")}
        values = [machines[ref] for ref in sorted(machines)]
        return {**{field: value for field, value in row.items() if field not in ("operation_ref", "arranged")},
                "machine": values[0] if len(values) == 1 else None, "machines": values,
                "machine_basis": "saved_arrangement" if tasks else "admission_requirement" if values else None,
                "arrangements": [{field: task[field] for field in ("row_ref", "start", "end", "machine", "operator", "source", "interval_comparable")} for task in tasks]}

    def _impact_row(self, ref, before_row, after_row):
        labels = self.label_for(ref)
        previous, selected = self._side("reference", before_row), self._side(self.source.selected_ref, after_row)
        deltas = {field: preparation_delta({"value": selected[field], "total_count": 1, "covered_operation_refs": [ref]},
                                            {"value": previous[field], "total_count": 1, "covered_operation_refs": [ref]}) for field in _HOURS}
        row = {**{field: labels[field] for field in ("operation_ref", "batch_ref", "batch_label", "part_label", "sequence", "process_label", "piece_id")},
                     "batch_id": labels["batch_label"], "before": previous, "after": selected, "deltas": deltas,
                     "data_gaps": labels["data_gaps"],
                     "drill": {"selected": drill_target(self.source, tasks=self.source.analysis_groups(self.source.selected_ref)[ref], batch_ref=labels["batch_ref"], operation_ref=ref),
                               "reference": drill_target(self.source, tasks=self.source.analysis_groups("reference")[ref], batch_ref=labels["batch_ref"], operation_ref=ref, before=True)}}
        for drill in row["drill"].values():
            if drill is not None:
                drill.update(resource_view=self.source.resource_view, comparison_tab="preparation")
        return row

    def impacts(self, operation_refs):
        before, after = self.rows_by_ref("reference"), self.rows_by_ref(self.source.selected_ref)
        return [self._impact_row(ref, before[ref], after[ref]) for ref in operation_refs]

    def public_summary(self):
        before, after = (self.summary(key) for key in ("reference", self.source.selected_ref))
        return {"scope": "full_admission", "before": public_preparation_metrics(before["metrics"]),
                "after": public_preparation_metrics(after["metrics"]),
                "deltas": {key: preparation_delta(value, before["metrics"][key]) for key, value in after["metrics"].items()},
                "role_totals": {"before": public_preparation_roles(before["role_totals"]), "after": public_preparation_roles(after["role_totals"])},
                "coverage": {"before": before["coverage"], "after": after["coverage"]}}

    def public_coverage(self, key):
        summary = self.summary(key)
        return {"scope": "full_admission", "allocation_groups": summary["coverage"], "role_totals": public_preparation_roles(summary["role_totals"])}
