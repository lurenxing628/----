"""One request's archived run, candidate arrangements and fixed comparison scope."""

from functools import cached_property
from typing import Any, Dict, Optional, overload

from core.models.workbench_preflight import preflight_window
from core.models.workbench_run_candidate import local_time, reference, reject
from core.services.workbench.facts.candidate_baseline import invalid_baseline
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.candidate_projection import dispositions, validate_manifest
from core.services.workbench.facts.candidate_tasks import project_validated_tasks, validate_saved_tasks
from core.services.workbench.facts.candidate_values import corrupt
from core.services.workbench.facts.decision_baseline import read_decision_baseline
from core.services.workbench.facts.decision_baseline_source import decision_baseline_source_resolver
from core.services.workbench.facts.decision_delivery import project_decision_delivery
from core.services.workbench.facts.decision_metrics import METRIC_VERSION
from core.services.workbench.facts.decision_read_models import Memberships, analysis_arrangements, decode_model
from core.services.workbench.facts.decision_selection import selection_basis
from core.services.workbench.facts.operation_effort_evidence import saved_operation_efforts
from core.services.workbench.facts.resource_intervals import task_interval
from core.services.workbench.facts.resource_projection import resource_cohort
from data.repositories.workbench_run_repo import WorkbenchRunRepository


class DecisionSource:
    def __init__(self, store, run_ref, *, comparison_mode="candidates", reference_candidate_ref=None,
                 selected_candidate_ref=None, range_start=None, range_end=None, resource_view="selected_batches", prepared=None):
        reference(run_ref)
        if comparison_mode not in ("candidates", "admission_official"):
            reject("invalid_input", "请选择同次候选方案或排产时的正式计划作为比较模式。", 422)
        if comparison_mode == "admission_official" and reference_candidate_ref is not None:
            reject("invalid_input", "比较排产时的正式计划时，请清除候选方案基准。", 422)
        if resource_view not in ("selected_batches", "full_candidate"):
            reject("invalid_input", "请选择本次所选批次或方案全部安排。", 422)
        self.store, self.repo = store, WorkbenchRunRepository(store.conn)
        prepared = prepared or {}
        head = prepared.get("head")
        self.run = prepared.get("run") or ({key: head[key] for key in ("run_ref", "state", "accepted_at", "finished_at")} if head else store.run(run_ref))
        if self.run["run_ref"] != run_ref:
            corrupt()
        active = self.run["state"] in ("queued", "running")
        if active:
            self.header = None
            self._active_decision = (prepared["admission_decision"] if "admission_decision" in prepared else
                decode_model(self.repo.admission_read_model(run_ref, ("decision",)), ("decision",))["decision"])
            self.context = self._active_decision["context"]
            self.memberships = Memberships(self._active_decision["memberships"])
            self.rows = []
        else:
            needed = tuple(name for name in ("header", "context", "memberships") if name not in prepared)
            model = decode_model(self.repo.decision_read_model(run_ref, needed), needed) if needed else {}
            self.header = prepared["header"] if "header" in prepared else model["header"]
            self.context = prepared["context"] if "context" in prepared else model["context"]
            self.memberships = Memberships(prepared["memberships"] if "memberships" in prepared else model["memberships"])
            self.rows = self.header["candidates"]
            if self.header["state"] != self.run["state"]:
                corrupt()
        self._candidate_models = {}
        for row in self.repo.candidate_read_models(run_ref) if self.rows else ():
            model = decode_model(row, ("summary",))
            summary = model["summary"]
            if row["run_ref"] != run_ref or summary.get("run_ref") != run_ref or summary.get("candidate_ref") != row["candidate_ref"]:
                corrupt()
            self._candidate_models[row["candidate_ref"]] = model
        if set(self._candidate_models) != {row["candidate_ref"] for row in self.rows}:
            corrupt()
        for row in self.rows:
            summary = self._candidate_models[row["candidate_ref"]]["summary"]
            if summary.get("persisted_status") != row["status"] or summary.get("task_count") != row["task_count"]:
                corrupt()
        basis_header = {**self.header, "selection": self.memberships.expand(self.header.get("selection"))} if self.header else None
        self.basis = selection_basis(basis_header, self.rows)
        self.comparison_mode, self.resource_view = comparison_mode, resource_view
        original = next((row for row in self.rows if row["status"] == "completed" and row["artifact"].get("kind") == "baseline"), None)
        default = self.basis["selected_candidate_ref"] if ((self.header or {}).get("selection") or {}).get("generation_policy_version") == "unified_search_v1" else (original["candidate_ref"] if original else None)
        self.reference_ref = (reference_candidate_ref or default) if comparison_mode == "candidates" else None
        self.selected_ref = selected_candidate_ref or self.basis["selected_candidate_ref"]
        self._candidate_reference(self.reference_ref)
        self._candidate_reference(self.selected_ref, require_result=False)
        self._projected, self._verified, self._task_intervals, self._analysis, self._candidate_records = {}, {}, {}, {}, {}
        self._raw_tasks, self._candidate_sources, self._prepared_task_rows, self._scheduled_op_ids = {}, {}, {}, {}
        self._candidate_records.update({row["candidate_ref"]: row for row in prepared.get("rows", ())})
        for name in ("receipt", "capture", "facts", "disposition"):
            if name in prepared:
                self.__dict__[name] = prepared[name]
        for candidate_ref, source in prepared.get("candidate_sources", {}).items():
            self._candidate_records[candidate_ref] = source.candidate
            self._projected[candidate_ref] = source.tasks
            self._raw_tasks[candidate_ref] = source.raw_tasks
            self._scheduled_op_ids[candidate_ref] = source.scheduled_op_ids
            self._candidate_sources[candidate_ref] = source
        self.scope = self._scope(range_start, range_end)
        self.scope["resource_refs"] = {kind: self.resource_cohort[kind + "_refs"] for kind in ("machine", "operator")}

    @cached_property
    def receipt(self):
        receipt = self.store.receipt(self.run)
        validate_manifest(self.run, self.rows, receipt)
        return receipt

    @cached_property
    def capture(self):
        return self.store.capture(self.run["run_ref"])

    @cached_property
    def facts(self):
        return GenerationFacts(self.capture)

    @cached_property
    def disposition(self):
        return dispositions(self.receipt)

    @cached_property
    def input(self):
        return self.memberships.expand(self.context["input"])

    def _members(self, field, kind="operation"):
        return self.memberships.refs(self.context.get(field, []), kind)

    def saved_candidate(self, candidate_ref):
        internal = {"catalog", "scheduled_operation_refs", "resource_views", "run_ref"}
        value = self._candidate_models[candidate_ref]["summary"]
        return self.memberships.expand({key: item for key, item in value.items() if key not in internal})

    def saved_candidate_catalog(self, candidate_ref, *, fields=None):
        value = self._candidate_models[candidate_ref]["summary"]["catalog"]
        return self.memberships.expand(value if fields is None else {field: value[field] for field in fields})

    def _saved_projection(self, key, field):
        """Load and validate a request's cached raw field before membership expansion."""
        key = self.computation_key(key)
        if key == "reference":
            projection = self.context["missing_candidate_reference"] if self.comparison_mode == "candidates" else self.official
            return projection[field]
        model = self._candidate_models[key]
        if field not in model:
            saved = self.repo.candidate_read_model(key, (field,))
            if saved is None or saved["run_ref"] != self.run["run_ref"]:
                corrupt()
            model.update(decode_model(saved, (field,)))
        return model[field]

    def saved_projection(self, key, field):
        return self.memberships.expand(self._saved_projection(key, field))

    def candidate_record(self, candidate_ref: str):
        if candidate_ref not in self._candidate_records:
            candidate = self.store.candidate(candidate_ref)
            saved = self._candidate_reference(candidate_ref, require_result=False)
            if candidate["run_ref"] != self.run["run_ref"] or any(candidate[name] != saved[name] for name in ("status", "task_count", "sequence")):
                corrupt()
            self._candidate_records[candidate_ref] = candidate
        return self._candidate_records[candidate_ref]

    def analysis_tasks(self, key):
        key = self.computation_key(key)
        if key not in self._analysis:
            if key == "reference":
                self._analysis[key] = self.official["tasks"] if self.comparison_mode == "admission_official" else []
            else:
                self._analysis[key] = analysis_arrangements(self._saved_projection(key, "arrangements"))
        return self._analysis[key]

    def analysis_groups(self, key):
        from .decision_impact import _by_operation
        name = self.computation_key(key)
        cache = self.__dict__.setdefault("_analysis_groups", {})
        if name not in cache:
            cache[name] = _by_operation(self.analysis_tasks(name))
        return cache[name]

    def operation_batch_ref(self, operation_ref):
        index = self.__dict__.get("_operation_batch_refs")
        if index is None:
            operations, batches = self.memberships.value["operation_refs"], self.memberships.value["batch_refs"]
            positions = self.context["operation_batch_indices"]
            if len(positions) != len(operations):
                corrupt()
            index = {ref: batches[pos] if pos is not None else None for ref, pos in zip(operations, positions)}
            self.__dict__["_operation_batch_refs"] = index
        return index.get(operation_ref)

    def scheduled_refs(self, key):
        key = self.computation_key(key)
        value = self.official["operation_refs"] if key == "reference" else self._candidate_models[key]["summary"]["scheduled_operation_refs"]
        refs = set(self.memberships.refs(value, "operation"))
        return refs & self.operation_refs if key == "reference" else refs

    @cached_property
    def calendar_archive(self):
        if self.run["state"] in ("queued", "running"):
            return self._active_decision["calendar"]
        return decode_model(self.repo.decision_read_model(self.run["run_ref"], ("calendar",)), ("calendar",))["calendar"]

    @cached_property
    def saved_process(self):
        if self.run["state"] in ("queued", "running"):
            return None
        return decode_model(self.repo.decision_read_model(self.run["run_ref"], ("process",)), ("process",))["process"]

    @overload
    def _candidate_reference(self, candidate_ref: None, *, require_result: bool = True) -> None: ...

    @overload
    def _candidate_reference(self, candidate_ref: str, *, require_result: bool = True) -> Dict[str, Any]: ...

    def _candidate_reference(self, candidate_ref: Optional[str], *, require_result: bool = True) -> Optional[Dict[str, Any]]:
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
            range_start, range_end = preflight_window(self.input)
        try:
            start, end = local_time(range_start), local_time(range_end)
        except (TypeError, ValueError):
            reject("invalid_input", "比较时间范围需要有效的本地时间。", 422)
        if start >= end:
            reject("invalid_input", "比较时间范围结束时间须晚于开始时间。", 422)
        refs = self._members("admission_operation_refs")
        baseline = self.baseline
        identity = {"kind": "candidate", "candidate_ref": self.reference_ref} if self.comparison_mode == "candidates" else {
            "kind": "admission_official", "baseline_ref": baseline["baseline_ref"]}
        result = {"run_ref": self.run["run_ref"], "comparison_mode": self.comparison_mode, "selected_candidate_ref": self.selected_ref,
                "reference": identity, "reference_state": baseline["state"], "range_start": start.isoformat(), "range_end": end.isoformat(),
                "batch_refs": sorted(self.input["batch_refs"]), "operation_refs": sorted(refs),
                "resource_view": self.resource_view,
                "metric_scope": "full_admission", "time_basis": "factory_local", "delta_basis": "candidate_minus_reference"}
        options = self.context.get("run_options")
        if options is not None and options.get("generation_policy_version") == "unified_search_v1":
            result["run_options"] = dict(options)
        return result

    def tasks(self, candidate_ref):
        if candidate_ref not in self._projected:
            row = self.candidate_record(candidate_ref)
            self._projected[candidate_ref] = project_validated_tasks(
                self.core_tasks(candidate_ref), row, self.facts, self._task_intervals[candidate_ref],
                prepared_tasks=self._prepared_task_rows[candidate_ref])
            del self._verified[candidate_ref]
            del self._prepared_task_rows[candidate_ref]
        return self._projected[candidate_ref]

    def core_tasks(self, candidate_ref):
        if candidate_ref in self._projected:
            return self._projected[candidate_ref]
        if candidate_ref not in self._verified:
            row = self.candidate_record(candidate_ref)
            self._raw_tasks[candidate_ref] = self.store.tasks(candidate_ref)
            self._prepared_task_rows[candidate_ref] = {}
            (self._verified[candidate_ref], self._task_intervals[candidate_ref],
             self._scheduled_op_ids[candidate_ref]) = validate_saved_tasks(
                self._raw_tasks[candidate_ref], row, self.facts, prepared_tasks=self._prepared_task_rows[candidate_ref])
        return self._verified[candidate_ref]

    def candidate_source(self, candidate_ref):
        from core.services.workbench.facts.candidate_read_source import read_candidate_source
        if candidate_ref not in self._candidate_sources:
            tasks = self.tasks(candidate_ref)
            packet = {"run": self.run, "rows": self.rows, "receipt": self.receipt,
                "capture": self.capture, "facts": self.facts, "disposition": self.disposition,
                "candidate": self.candidate_record(candidate_ref), "raw_tasks": self._raw_tasks[candidate_ref], "tasks": tasks,
                "scheduled_op_ids": self._scheduled_op_ids[candidate_ref]}
            self._candidate_sources[candidate_ref] = read_candidate_source(self.store, candidate_ref, prepared=packet)
        return self._candidate_sources[candidate_ref]

    def delivery(self, key):
        if self.computation_key(key) == "reference" and self.official_changed:
            return project_decision_delivery(self.facts, self.official["tasks"], self.scope["batch_refs"],
                deferred_ids=self.reference_deferred_ids, available=self.baseline["state"] == "available",
                intervals=self.task_intervals("reference"))
        return self.saved_projection(key, "delivery")

    def legacy_delivery(self, candidate_ref):
        self._candidate_reference(candidate_ref, require_result=False)
        return self.saved_projection(candidate_ref, "delivery_detail")

    def result_available(self, candidate_ref):
        return any(row["candidate_ref"] == candidate_ref and row["status"] == "completed" for row in self.rows)

    def computation_key(self, key):
        if key == "reference" and self.comparison_mode == "candidates" and self.reference_ref is not None:
            return self.reference_ref
        return key

    def task_intervals(self, key):
        key = self.computation_key(key)
        if key not in self._task_intervals:
            self._task_intervals[key] = {row["row_ref"]: task_interval(row) for row in self.analysis_tasks(key)}
        return self._task_intervals[key]

    @cached_property
    def reference_operation_groups(self):
        return self.analysis_groups("reference")

    @cached_property
    def operation_comparisons(self):
        from .decision_impact import operation_comparisons
        return operation_comparisons(self.analysis_tasks(self.selected_ref), self.analysis_tasks("reference"), self.scope["operation_refs"],
            self.baseline["state"] == "available", selected_available=self.result_available(self.selected_ref),
            deferred_refs=self.deferred_refs, reference_deferred_refs=self.reference_deferred_refs,
            reference_groups=self.reference_operation_groups, task_intervals=self.task_intervals(self.selected_ref),
            reference_task_intervals=self.task_intervals("reference"))

    @cached_property
    def batch_impacts(self):
        from .decision_impact import batch_impacts
        return batch_impacts(self)

    @cached_property
    def batch_impact_summary(self):
        if "batch_impacts" in self.__dict__:
            return self.batch_impacts[1]
        from .decision_impact import batch_impact_summary
        return batch_impact_summary(self)

    @cached_property
    def operation_impacts(self):
        from .decision_impact import operation_impacts
        return operation_impacts(self)

    @cached_property
    def official_details(self):
        resolver = decision_baseline_source_resolver(self.store.conn)
        return read_decision_baseline(self.capture, self.facts, self.disposition, self.run["accepted_at"], source_resolver=resolver)

    @cached_property
    def official(self):
        model: Dict[str, Any] = self._active_decision["official"] if self.run["state"] in ("queued", "running") else decode_model(
            self.repo.decision_read_model(self.run["run_ref"], ("official",)), ("official",))["official"]
        if model.get("projection_state") == "disposition_not_recorded":
            invalid_baseline()
        if not self.repo.dependencies_match(model["dependencies"]):
            self.__dict__["_official_changed"] = True
            value: Dict[str, Any] = dict(self.official_details)
            value["operation_refs"] = sorted({row["operation_ref"] for row in value["tasks"]})
            value["deferred_operation_refs"] = sorted(ref for ref, op in self.facts.operations.items()
                                                      if op in value["deferred_operation_ids"])
            return value
        value = dict(model)
        value["tasks"] = analysis_arrangements(model["arrangements"])
        return value

    @property
    def official_changed(self):
        if self.comparison_mode != "admission_official":
            return False
        _ = self.official
        return self.__dict__.get("_official_changed", False)

    @cached_property
    def official_members(self):
        if "official" in self.__dict__:
            return {"identity": dict(self.official["identity"]),
                    "operation_refs": self.memberships.refs(self.official["operation_refs"], "operation")}
        return self.memberships.expand(self.context["official_members"])

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
            refs = self.operation_refs
            return [row for row in self.official_details["tasks"] if row["operation_ref"] in refs]
        return self.tasks(self.reference_ref) if self.reference_ref else []

    def resource_tasks(self, candidate_ref):
        rows = self.analysis_tasks(candidate_ref)
        return rows if self.resource_view == "full_candidate" else [row for row in rows if row["operation_ref"] in self.operation_refs]

    @cached_property
    def operation_refs(self):
        return set(self.scope["operation_refs"])

    @cached_property
    def resource_before_tasks(self):
        rows = self.analysis_tasks("reference")
        return rows if self.resource_view == "full_candidate" else [row for row in rows if row["operation_ref"] in self.operation_refs]

    @cached_property
    def resource_cohort(self):
        ordered = {}
        keys = dict.fromkeys(self.computation_key(key) for key in ["reference"] + [candidate["candidate_ref"] for candidate in self.rows])
        for key in keys:
            if key == "reference":
                if self.comparison_mode == "admission_official" and self.official_changed:
                    pools = resource_cohort([self.resource_before_tasks])
                else:
                    pools = self.official["resource_views"][self.resource_view]["resources"] if self.comparison_mode == "admission_official" else []
            else:
                pools = self._candidate_models[key]["summary"]["resource_views"][self.resource_view]["resources"]
            for row in pools:
                ordered.setdefault((row["kind"], row["ref"]), {name: row[name] for name in ("kind", "ref", "label")})
        resources = [ordered[key] for key in sorted(ordered)]
        return {"source": "all_run_candidates_and_reference", "resource_view": self.resource_view, "resources": resources,
                **{kind + "_refs": [row["ref"] for row in resources if row["kind"] == kind] for kind in ("machine", "operator")}}

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
        return set(self._members("deferred_operation_refs"))

    @cached_property
    def reference_deferred_ids(self):
        if self.comparison_mode == "candidates":
            return {self.facts.operations[ref] for ref in self.deferred_refs}
        return {self.facts.operations[ref] for ref in self.reference_deferred_refs}

    @cached_property
    def reference_deferred_refs(self):
        return self.deferred_refs if self.comparison_mode == "candidates" else set(self.memberships.refs(self.official["deferred_operation_refs"], "operation"))

    @property
    def selected(self):
        return next((row for row in self.rows if row["candidate_ref"] == self.selected_ref), None)

    def state(self):
        return {"run": self.run, "capture_ref": self.run["run_ref"], "metric_version": METRIC_VERSION,
                "recommendation_version": "decision-recommendation-v1",
                "official_sources": self.official["source_states"] if self.comparison_mode == "admission_official" else [],
                "candidates": [{"candidate_ref": row["candidate_ref"], "status": row["status"], "task_count": row["task_count"]} for row in self.rows]}
