"""One request's archived run, candidate arrangements and fixed comparison scope."""

from functools import cached_property

from core.models.workbench_preflight import preflight_window
from core.models.workbench_run_candidate import local_time, reference, reject
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.candidate_projection import dispositions, validate_manifest
from core.services.workbench.facts.candidate_tasks import project_validated_tasks, validate_saved_tasks
from core.services.workbench.facts.candidate_values import corrupt
from core.services.workbench.facts.decision_baseline import read_decision_baseline, read_decision_baseline_members
from core.services.workbench.facts.decision_baseline_source import decision_baseline_source_resolver
from core.services.workbench.facts.operation_effort_evidence import saved_operation_efforts
from core.services.workbench.facts.resource_intervals import task_interval
from core.services.workbench.facts.resource_projection import resource_cohort, saved_resource_tasks

from .decision_delivery import project_decision_delivery, project_saved_decision_delivery
from .decision_metrics import METRIC_VERSION, admission_operations
from .decision_selection import selection_basis


class DecisionSource:
    def __init__(self, store, run_ref, *, comparison_mode="candidates", reference_candidate_ref=None,
                 selected_candidate_ref=None, range_start=None, range_end=None, resource_view="selected_batches"):
        reference(run_ref)
        if comparison_mode not in ("candidates", "admission_official"):
            reject("invalid_input", "请选择同次候选方案或排产时的正式计划作为比较模式。", 422)
        if comparison_mode == "admission_official" and reference_candidate_ref is not None:
            reject("invalid_input", "比较排产时的正式计划时，请清除候选方案基准。", 422)
        if resource_view not in ("selected_batches", "full_candidate"):
            reject("invalid_input", "请选择本次所选批次或方案全部安排。", 422)
        self.store = store
        self.run = store.run(run_ref)
        self.receipt = store.receipt(self.run)
        self.rows = store.candidates(run_ref)
        validate_manifest(self.run, self.rows, self.receipt)
        self.capture = store.capture(run_ref)
        self.facts = GenerationFacts(self.capture)
        self.disposition = dispositions(self.receipt)
        self.basis = selection_basis(self.receipt, self.rows)
        self.comparison_mode = comparison_mode
        self.resource_view = resource_view
        original = next((row for row in self.rows if row["status"] == "completed" and row["artifact"].get("kind") == "baseline"), None)
        self.reference_ref = (reference_candidate_ref or (original["candidate_ref"] if original else None)) if comparison_mode == "candidates" else None
        self.selected_ref = selected_candidate_ref or self.basis["selected_candidate_ref"]
        self._candidate_reference(self.reference_ref)
        self._candidate_reference(self.selected_ref, require_result=False)
        self._projected = {}
        self._verified = {}
        self._task_intervals = {}
        self.scope = self._scope(range_start, range_end)
        self.scope["resource_refs"] = {kind: self.resource_cohort[kind + "_refs"] for kind in ("machine", "operator")}

    def _candidate_reference(self, candidate_ref, *, require_result=True):
        if candidate_ref is None:
            return
        reference(candidate_ref)
        candidate = next((row for row in self.rows if row["candidate_ref"] == candidate_ref), None)
        if candidate is None:
            if self.store.candidate_run(candidate_ref) != self.run["run_ref"]:
                reject("invalid_input", "比较候选属于另一轮排产，请选择本次排产中的方案。", 422)
            corrupt()
        if require_result and candidate["status"] != "completed":
            reject("invalid_input", "该候选尚未产出任务安排，请选择已产出的方案。", 422)
        return candidate

    def _scope(self, range_start, range_end):
        if (range_start is None) != (range_end is None):
            reject("invalid_input", "比较时间范围要同时填写开始和结束时间。", 422)
        if range_start is None:
            range_start, range_end = preflight_window(self.capture["input"])
        try:
            start, end = local_time(range_start), local_time(range_end)
        except (TypeError, ValueError):
            reject("invalid_input", "比较时间范围需要有效的本地时间。", 422)
        if start >= end:
            reject("invalid_input", "比较时间范围结束时间须晚于开始时间。", 422)
        refs, _, _ = admission_operations(self.facts, self.capture["input"], self.disposition)
        baseline = self.baseline
        identity = {"kind": "candidate", "candidate_ref": self.reference_ref} if self.comparison_mode == "candidates" else {
            "kind": "admission_official", "baseline_ref": baseline["baseline_ref"]}
        return {"run_ref": self.run["run_ref"], "comparison_mode": self.comparison_mode, "selected_candidate_ref": self.selected_ref,
                "reference": identity, "reference_state": baseline["state"], "range_start": start.isoformat(), "range_end": end.isoformat(),
                "batch_refs": sorted(self.capture["input"]["batch_refs"]), "operation_refs": sorted(refs),
                "resource_view": self.resource_view,
                "metric_scope": "full_admission", "time_basis": "factory_local", "delta_basis": "candidate_minus_reference"}

    def tasks(self, candidate_ref):
        if candidate_ref not in self._projected:
            row = next(item for item in self.rows if item["candidate_ref"] == candidate_ref)
            self._projected[candidate_ref] = project_validated_tasks(
                self.core_tasks(candidate_ref), row, self.facts, self._task_intervals[candidate_ref])
            del self._verified[candidate_ref]
        return self._projected[candidate_ref]

    def core_tasks(self, candidate_ref):
        if candidate_ref in self._projected:
            return self._projected[candidate_ref]
        if candidate_ref not in self._verified:
            row = next(item for item in self.rows if item["candidate_ref"] == candidate_ref)
            self._verified[candidate_ref], self._task_intervals[candidate_ref] = validate_saved_tasks(
                self.store.tasks(candidate_ref), row, self.facts)
        return self._verified[candidate_ref]

    def delivery(self, key):
        key = self.computation_key(key)
        if key == "reference":
            return project_decision_delivery(self.facts, self.before_tasks, self.scope["batch_refs"],
                deferred_ids=self.reference_deferred_ids, available=self.baseline["state"] == "available",
                intervals=self.task_intervals(key))
        candidate = next(row for row in self.rows if row["candidate_ref"] == key)
        tasks = self.core_tasks(key)
        deferred = {self.facts.operations[ref] for ref in self.deferred_refs}
        project = project_decision_delivery if key in self._projected else project_saved_decision_delivery
        return project(self.facts, tasks, self.scope["batch_refs"], deferred_ids=deferred, candidate=candidate,
                       available=self.result_available(key), intervals=self.task_intervals(key))

    def result_available(self, candidate_ref):
        return any(row["candidate_ref"] == candidate_ref and row["status"] == "completed" for row in self.rows)

    def computation_key(self, key):
        if key == "reference" and self.comparison_mode == "candidates" and self.reference_ref is not None:
            return self.reference_ref
        return key

    def task_intervals(self, key):
        key = self.computation_key(key)
        if key not in self._task_intervals:
            if key == "reference":
                tasks = self.official["tasks"] if self.comparison_mode == "admission_official" else []
                self._task_intervals[key] = {row["row_ref"]: task_interval(row) for row in tasks}
            else:
                self.core_tasks(key)
        return self._task_intervals[key]

    @cached_property
    def reference_operation_groups(self):
        from .decision_impact import _by_operation
        return _by_operation(self.before_tasks)

    @cached_property
    def operation_comparisons(self):
        from .decision_impact import operation_comparisons
        deferred = {ref for ref in self.scope["operation_refs"] if self.facts.operations[ref] in self.reference_deferred_ids}
        return operation_comparisons(self.tasks(self.selected_ref), self.before_tasks, self.scope["operation_refs"],
            self.baseline["state"] == "available", selected_available=self.result_available(self.selected_ref),
            deferred_refs=self.deferred_refs, reference_deferred_refs=deferred, reference_groups=self.reference_operation_groups,
            task_intervals=self.task_intervals(self.selected_ref), reference_task_intervals=self.task_intervals("reference"))

    @cached_property
    def operation_impacts(self):
        from .decision_impact import operation_impacts
        return operation_impacts(self)

    @cached_property
    def official(self):
        resolver = decision_baseline_source_resolver(self.store.conn)
        return read_decision_baseline(self.capture, self.facts, self.disposition, self.run["accepted_at"], source_resolver=resolver)

    @cached_property
    def official_members(self):
        if "official" in self.__dict__:
            return {"identity": dict(self.official["identity"]),
                    "operation_refs": sorted({row["operation_ref"] for row in self.official["tasks"]})}
        return read_decision_baseline_members(self.capture, self.facts)

    @cached_property
    def baseline(self):
        if self.comparison_mode == "admission_official":
            return {**self.official["identity"], "candidate_ref": None}
        row = next((item for item in self.rows if item["candidate_ref"] == self.reference_ref), None)
        return {"kind": "candidate", "candidate_ref": self.reference_ref, "baseline_ref": None, "version": None,
                "source_candidate_ref": None, "label": row["artifact"].get("label") if row else None,
                "state": "available" if row else "selection_required"}

    @cached_property
    def before_tasks(self):
        if self.comparison_mode == "admission_official":
            refs = set(self.scope["operation_refs"])
            return [row for row in self.official["tasks"] if row["operation_ref"] in refs]
        return self.tasks(self.reference_ref) if self.reference_ref else []

    def resource_tasks(self, candidate_ref):
        rows = self.tasks(candidate_ref)
        if self.resource_view == "full_candidate":
            return rows
        return [row for row in rows if row["operation_ref"] in self.operation_refs]

    @cached_property
    def operation_refs(self):
        return set(self.scope["operation_refs"])

    @cached_property
    def resource_before_tasks(self):
        if self.comparison_mode == "admission_official":
            return self.official["tasks"] if self.resource_view == "full_candidate" else self.before_tasks
        return self.resource_tasks(self.reference_ref) if self.reference_ref else []

    @cached_property
    def resource_cohort(self):
        keys = dict.fromkeys(self.computation_key(key) for key in
                             ["reference"] + [candidate["candidate_ref"] for candidate in self.rows])
        pools, intervals, resources = [], [], {}
        for key in keys:
            if key == "reference":
                tasks = self.resource_before_tasks
            elif key in self._projected:
                tasks = self.resource_tasks(key)
            else:
                tasks = saved_resource_tasks(self.core_tasks(key), self.facts, resources,
                    operation_refs=self.operation_refs if self.resource_view == "selected_batches" else None)
            pools.append(tasks)
            intervals.append(self.task_intervals(key))
        ordered = resource_cohort(pools, task_intervals=intervals)
        return {"source": "all_run_candidates_and_reference", "resource_view": self.resource_view, "resources": ordered,
                **{kind + "_refs": [row["ref"] for row in ordered if row["kind"] == kind] for kind in ("machine", "operator")}}

    @cached_property
    def resources(self):
        from .decision_resources import DecisionResources
        return DecisionResources(self)

    @cached_property
    def operation_efforts(self):
        return saved_operation_efforts((self.receipt or {}).get("operation_effort"), identities=self.facts.operations)

    @cached_property
    def preparation(self):
        from .decision_preparation import DecisionPreparation
        return DecisionPreparation(self)

    @cached_property
    def changeovers(self):
        from .decision_changeovers import DecisionChangeovers
        return DecisionChangeovers(self)

    @cached_property
    def completion(self):
        from .decision_completion import DecisionCompletion
        return DecisionCompletion(self)

    @cached_property
    def deferred_refs(self):
        return admission_operations(self.facts, self.capture["input"], self.disposition)[1]

    @cached_property
    def reference_deferred_ids(self):
        if self.comparison_mode == "candidates":
            return {self.facts.operations[ref] for ref in self.deferred_refs}
        return set(self.official["deferred_operation_ids"])

    @property
    def selected(self):
        return next((row for row in self.rows if row["candidate_ref"] == self.selected_ref), None)

    def state(self):
        return {"run": self.run, "capture_ref": self.run["run_ref"], "metric_version": METRIC_VERSION,
                "recommendation_version": "decision-recommendation-v1",
                "official_sources": self.official["source_states"] if self.comparison_mode == "admission_official" else [],
                "candidates": [{"candidate_ref": row["candidate_ref"], "status": row["status"], "task_count": row["task_count"]} for row in self.rows]}
