"""One saved requirement ledger, allocated by each candidate's actual task rows."""

from collections import defaultdict
from functools import cached_property

from core.models.enums import OperationRequirementRole, SourceType
from core.services.workbench.facts.candidate_tasks import operation_labels
from core.services.workbench.facts.operation_effort_evidence import archived_standard_effort
from core.services.workbench.facts.preparation_projection import (
    preparation_delta,
    preparation_summary,
    project_operation_effort,
    public_preparation_metrics,
    public_preparation_roles,
)

from .decision_impact import _drill

_HOURS = ("setup_standard_hours", "processing_standard_hours", "required_standard_hours")


class DecisionPreparation:
    def __init__(self, source):
        self.source = source
        self._rows, self._rows_by_ref, self._summaries, self._groups = {}, {}, {}, {}

    def available(self, key):
        key = self.source.computation_key(key)
        if key == "reference":
            return self.source.baseline["state"] == "available"
        return next(row["status"] for row in self.source.rows if row["candidate_ref"] == key) == "completed"

    def tasks(self, key):
        key = self.source.computation_key(key)
        return self.source.before_tasks if key == "reference" else self.source.tasks(key)

    def groups(self, key):
        key = self.source.computation_key(key)
        if key not in self._groups:
            groups = defaultdict(list)
            for task in self.tasks(key):
                groups[task["operation_ref"]].append(task)
            self._groups[key] = groups
        return self._groups[key]

    @cached_property
    def labels(self):
        return {ref: operation_labels(self.source.facts, ref)[0] for ref in self.source.scope["operation_refs"]}

    @cached_property
    def current_standards(self):
        source = self.source
        result = {}
        for ref in source.scope["operation_refs"]:
            operation = source.facts.tables["BatchOperations"].get(source.facts.operations[ref], {})
            execution = source.facts.execution.get(ref, {})
            result[ref] = {**archived_standard_effort(operation, execution),
                           "evidence_source": {"kind": "admission", "run_ref": source.run["run_ref"]}}
        return result

    def _facts(self, key, ref):
        source = self.source
        formal = key == "reference" and source.comparison_mode == "admission_official"
        if formal:
            original = source.official["operation_efforts"].get(ref) or {}
            saved_standard = source.official["operation_standards"].get(ref)
            if saved_standard is not None:
                standard = {**archived_standard_effort(saved_standard["operation"], saved_standard["execution"]),
                            "evidence_source": saved_standard["evidence_source"]}
            else:
                standard = None
            return original.get("effort"), standard, original.get("evidence_source")
        return source.operation_efforts.get(ref), self.current_standards[ref], {"kind": "run", "run_ref": source.run["run_ref"]}

    def _allocation(self, key, ref, runtime, tasks):
        if not self.available(key):
            return "unknown"
        deferred = self.reference_deferred if key == "reference" else self.source.deferred_refs
        if not tasks:
            return "deferred" if ref in deferred else "unplanned"
        source = runtime.get("source") if runtime is not None else tasks[0]["source"]
        if source == SourceType.EXTERNAL.value:
            return "external"
        role = (runtime or {}).get("requirement_role")
        if role in (OperationRequirementRole.NEW_SCHEDULE.value, OperationRequirementRole.RETAINED.value,
                    OperationRequirementRole.EXECUTION.value, OperationRequirementRole.COMPLETED.value):
            return role
        return "unknown"

    @cached_property
    def reference_deferred(self):
        if self.source.comparison_mode == "candidates":
            return self.source.deferred_refs
        return {ref for ref in self.source.scope["operation_refs"] if self.source.facts.operations[ref] in self.source.reference_deferred_ids}

    def rows(self, key):
        key = self.source.computation_key(key)
        if key not in self._rows:
            rows = [self._row(key, ref, self.groups(key)[ref]) for ref in self.source.scope["operation_refs"]]
            self._rows[key] = rows
            self._rows_by_ref[key] = {row["operation_ref"]: row for row in rows}
        return self._rows[key]

    def _row(self, key, ref, tasks):
        source = self.source
        formal = key == "reference" and source.comparison_mode == "admission_official"
        runtime, standard, evidence_source = self._facts(key, ref)
        operation = source.facts.tables["BatchOperations"].get(source.facts.operations.get(ref), {})
        original_source = runtime.get("source") if runtime is not None else (
            tasks[0]["source"] if formal and tasks else operation.get("source") if not formal else None)
        row = project_operation_effort(runtime, standard, allocation_state=self._allocation(key, ref, runtime, tasks),
                                       source_available=self.available(key), source=original_source,
                                       execution=source.facts.execution.get(ref, {}), evidence_source=evidence_source)
        row.update(operation_ref=ref, arranged=bool(tasks))
        return row

    @cached_property
    def formal_task_groups(self):
        result = defaultdict(list)
        for task in self.source.official["tasks"]:
            result[task["operation_ref"]].append(task)
        return result

    def summary(self, key):
        key = self.source.computation_key(key)
        if key not in self._summaries:
            formal = key == "reference" and self.source.comparison_mode == "admission_official"
            requirements_available = self.available(key) if formal else (self.source.receipt or {}).get("operation_effort") is not None or self.available(key)
            self._summaries[key] = preparation_summary(self.rows(key), available=self.available(key), requirements_available=requirements_available)
        return self._summaries[key]

    def metrics(self, key):
        return self.summary(key)["metrics"]

    def compact(self, key, ref):
        key = self.source.computation_key(key)
        self.rows(key)
        if ref not in self._rows_by_ref[key] and key == "reference" and self.source.comparison_mode == "admission_official":
            self._rows_by_ref[key][ref] = self._row(key, ref, self.formal_task_groups[ref])
        return {field: value for field, value in self._rows_by_ref[key][ref].items()
                if field not in ("operation_ref", "arranged")}

    def _side(self, key, row):
        source, ref = self.source, row["operation_ref"]
        tasks = self.groups(key)[ref]
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
                "arrangements": [{field: task.get(field) for field in ("row_ref", "start", "end", "machine", "operator", "source", "interval_comparable")} for task in tasks]}

    def impacts(self):
        before, after = ({row["operation_ref"]: row for row in self.rows(key)} for key in ("reference", self.source.selected_ref))
        rows = []
        for ref in self.source.scope["operation_refs"]:
            labels = self.labels[ref]
            previous, selected = self._side("reference", before[ref]), self._side(self.source.selected_ref, after[ref])
            deltas = {field: preparation_delta({"value": selected[field], "total_count": 1, "covered_operation_refs": [ref]},
                                                {"value": previous[field], "total_count": 1, "covered_operation_refs": [ref]}) for field in _HOURS}
            row = {**{field: labels[field] for field in ("operation_ref", "batch_ref", "batch_label", "part_label", "sequence", "process_label", "piece_id")},
                         "batch_id": labels["batch_label"], "before": previous, "after": selected, "deltas": deltas,
                         "data_gaps": labels["data_gaps"],
                         "drill": {"selected": _drill(self.source, tasks=self.groups(self.source.selected_ref)[ref], batch_ref=labels["batch_ref"], operation_ref=ref),
                                   "reference": _drill(self.source, tasks=self.groups("reference")[ref], batch_ref=labels["batch_ref"], operation_ref=ref, before=True)}}
            for drill in row["drill"].values():
                if drill is not None:
                    drill.update(resource_view=self.source.resource_view, comparison_tab="preparation")
            rows.append(row)
        return rows

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
