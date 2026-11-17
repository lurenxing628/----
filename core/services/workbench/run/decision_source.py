"""One request's archived run, candidate arrangements and fixed comparison scope."""

from functools import cached_property
from typing import Any, Dict, List, Optional, Set, Tuple, overload

from core.models.content import read_stored_json
from core.models.enums import RUN_RESOURCE_VIEW_VALUES
from core.models.workbench_run_candidate import local_time, reference, reject
from core.models.workbench_run_receipt import PersistedReceipt
from core.services.scheduler.run.optimizer.shared_process import UNIFIED_PROCESS_VERSION
from core.services.workbench.facts.candidate_baseline import invalid_baseline
from core.services.workbench.facts.candidate_read_source import CandidateReadSource, SavedRun, load_saved_run
from core.services.workbench.facts.candidate_tasks import (
    ValidatedCandidateTasks,
    project_validated_tasks,
    validate_candidate_tasks,
)
from core.services.workbench.facts.candidate_values import corrupt
from core.services.workbench.facts.decision_baseline import read_decision_baseline
from core.services.workbench.facts.decision_metrics import METRIC_VERSION
from core.services.workbench.facts.decision_read_models import (
    Memberships,
    analysis_arrangements,
    by_operation,
    decode_model,
)
from core.services.workbench.facts.decision_selection import selection_basis
from core.services.workbench.facts.operation_effort_evidence import saved_operation_efforts
from data.repositories.workbench_run_repo import WorkbenchRunRepository


class DecisionSource:
    def __init__(self, store, run_ref, *, comparison_mode="candidates", reference_candidate_ref=None,
                 selected_candidate_ref=None, range_start=None, range_end=None, resource_view="selected_batches",
                 run: Optional[SavedRun] = None, candidate_sources: Tuple[CandidateReadSource, ...] = ()):
        """``run`` and ``candidate_sources`` are what the caller already read of this run in the same snapshot."""
        reference(run_ref)
        if comparison_mode not in ("candidates", "admission_official"):
            reject("invalid_input", "请选择同次候选方案或排产时的正式计划作为比较模式。", 422)
        if comparison_mode == "admission_official" and reference_candidate_ref is not None:
            reject("invalid_input", "比较排产时的正式计划时，请清除候选方案基准。", 422)
        if resource_view not in RUN_RESOURCE_VIEW_VALUES:
            reject("invalid_input", "请选择本次所选批次或方案全部安排。", 422)
        self.store, self.repo = store, WorkbenchRunRepository(store.conn)
        self._saved_run = run
        self.run = run.run if run is not None else store.run(run_ref)
        if self.run["state"] in ("queued", "running"):
            self.header = None
            self._active_decision = decode_model(self.repo.admission_read_model(run_ref, ("decision",)), ("decision",))["decision"]
            self.context = self._active_decision["context"]
            self.memberships = Memberships(self._active_decision["memberships"])
            self.rows = []
        else:
            fields = ("header", "context", "memberships")
            model = decode_model(self.repo.decision_read_model(run_ref, fields), fields)
            self.header, self.context = model["header"], model["context"]
            self.memberships = Memberships(model["memberships"])
            self.rows = self.header["candidates"]
            if self.header["state"] != self.run["state"]:
                corrupt()
        self._candidate_models = self._load_candidate_models(run_ref)
        self.basis = selection_basis(None if self.header is None else self.header["selection"], self.rows)
        self.comparison_mode, self.resource_view = comparison_mode, resource_view
        self.reference_ref = ((reference_candidate_ref if reference_candidate_ref is not None else self.basis["selected_candidate_ref"])
                              if comparison_mode == "candidates" else None)
        self.selected_ref = selected_candidate_ref if selected_candidate_ref is not None else self.basis["selected_candidate_ref"]
        self._reference_row = self._candidate_reference(self.reference_ref)
        self.selected = self._candidate_reference(self.selected_ref)
        self._candidate_sources: Dict[str, CandidateReadSource] = {
            source.candidate["candidate_ref"]: source for source in candidate_sources}
        self._candidate_records = {ref: source.candidate for ref, source in self._candidate_sources.items()}
        self._task_intervals = {ref: source.task_intervals for ref, source in self._candidate_sources.items()}
        self._validated: Dict[str, ValidatedCandidateTasks] = {}
        self._projected, self._analysis, self._operation_arrangements, self._side_resource_details = {}, {}, {}, {}
        self.batch_refs: List[str] = sorted(self.input["batch_refs"])
        self.admitted_operation_refs: List[str] = sorted(self._members("admission_operation_refs"))
        self.scope = self._scope(range_start, range_end)
        self.scope["resource_refs"] = {kind: self.resource_cohort[kind + "_refs"] for kind in ("machine", "operator")}

    def _load_candidate_models(self, run_ref: str) -> Dict[str, Any]:
        models = {}
        for row in self.repo.candidate_read_models(run_ref) if self.rows else ():
            model = decode_model(row, ("summary",))
            summary = model["summary"]
            if row["run_ref"] != run_ref or summary.get("run_ref") != run_ref or summary.get("candidate_ref") != row["candidate_ref"]:
                corrupt()
            models[row["candidate_ref"]] = model
        if set(models) != {row["candidate_ref"] for row in self.rows}:
            corrupt()
        for row in self.rows:
            summary = models[row["candidate_ref"]]["summary"]
            if summary.get("task_count") != row["task_count"]:
                corrupt()
        return models

    @property
    def saved_run(self) -> SavedRun:
        """This run's saved archive: the one the caller handed over, or loaded on first use and bound to the
        candidates of the saved decision header."""
        if self._saved_run is None:
            self._saved_run = load_saved_run(self.store, self.run, self.rows)
        return self._saved_run

    @property
    def receipt(self) -> PersistedReceipt:
        # Only the views of a run with candidates read its receipt.
        return self.saved_run.persisted

    @property
    def capture(self): return self.saved_run.capture

    @property
    def facts(self): return self.saved_run.facts

    @property
    def disposition(self) -> Dict[str, Dict[str, Any]]: return self.saved_run.disposition

    @cached_property
    def input(self): return self.memberships.expand(self.context["input"])

    def _members(self, field): return self.memberships.refs(self.context[field], "operation")

    def saved_candidate(self, candidate_ref, *, include_evaluations: bool = True, metric_keys=None):
        internal = {"catalog", "scheduled_operation_refs", "resource_views", "run_ref",
                    "default_resource_cohorts", "default_changeovers", *(() if include_evaluations else ("evaluations",))}
        raw = {key: item for key, item in self._candidate_models[candidate_ref]["summary"].items() if key not in internal}
        if metric_keys is not None:
            wanted = set(metric_keys)
            raw["metrics"] = {key: item for key, item in raw["metrics"].items() if key in wanted}
        return self.memberships.expand(raw)

    def saved_candidate_catalog(self, candidate_ref, *, fields=None):
        value = self._candidate_models[candidate_ref]["summary"]["catalog"]
        return self.memberships.expand(value if fields is None else {field: value[field] for field in fields})

    @property
    def is_default_window(self) -> bool:
        return self.scope["range_start"] == self.context["range_start"] and self.scope["range_end"] == self.context["range_end"]

    def side_key(self, key: str) -> str:
        comp = self.computation_key(key)
        if comp == "reference":
            return "official" if self.comparison_mode == "admission_official" else "missing_reference"
        return comp

    def precomputed_resource_cohort(self, key: str) -> Optional[Dict[str, Any]]:
        if not self.is_default_window:
            return None
        comp = self.computation_key(key)
        container = (self.official if self.comparison_mode == "admission_official" else self.context["missing_candidate_reference"]
                     ) if comp == "reference" else self._candidate_models[comp]["summary"]
        cohorts = container.get("default_resource_cohorts")
        return None if cohorts is None else self.memberships.expand(cohorts[f"{self.comparison_mode}:{self.resource_view}"])

    def precomputed_resource_details(self, key: str) -> Optional[Dict[str, Any]]:
        if not self.is_default_window:
            return None
        cache_key = (self.side_key(key), self.resource_view)
        if cache_key not in self._side_resource_details:
            raw = self.repo.side_resource_detail(self.run["run_ref"], cache_key[0], cache_key[1])
            self._side_resource_details[cache_key] = None if raw is None else read_stored_json(raw, dict)
        parsed = self._side_resource_details[cache_key]
        return None if parsed is None else self.memberships.expand(parsed)

    def precomputed_changeovers(self, key: str) -> Optional[Dict[str, Any]]:
        if not self.is_default_window:
            return None
        comp = self.computation_key(key)
        if comp == "reference":
            container = self.official if self.comparison_mode == "admission_official" else self.context["missing_candidate_reference"]
            return self.memberships.expand(container["default_changeovers"])
        return self.memberships.expand(self._candidate_models[comp]["summary"]["default_changeovers"])

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
            saved = self._candidate_reference(candidate_ref)
            if candidate["run_ref"] != self.run["run_ref"] or any(candidate[name] != saved[name] for name in ("task_count", "sequence")):
                corrupt()
            self._candidate_records[candidate_ref] = candidate
        return self._candidate_records[candidate_ref]

    def analysis_tasks(self, key):
        key = self.computation_key(key)
        if key not in self._analysis:
            if key == "reference":
                rows, intervals = self.official_arrangements if self.comparison_mode == "admission_official" else ([], {})
            elif key in self._projected:
                rows, intervals = self._projected[key], self._task_intervals[key]
            else:
                rows, intervals = analysis_arrangements(self._saved_projection(key, "arrangements"))
            self._analysis[key] = rows
            # A candidate's intervals already taken from its validated store rows stay the ones in use.
            self._task_intervals.setdefault(key, intervals)
        return self._analysis[key]

    def operation_arrangements(self, key):
        """Each operation's one arranged task on this side, keyed by permanent operation reference."""
        name = self.computation_key(key)
        if name not in self._operation_arrangements:
            self._operation_arrangements[name] = by_operation(self.analysis_tasks(name))
        return self._operation_arrangements[name]

    def arrangement_available(self, key):
        """Every saved candidate has its arrangement; only the reference side can lack one."""
        return self.computation_key(key) != "reference" or self.baseline["state"] == "available"

    @cached_property
    def _operation_batch_refs(self) -> Dict[str, Optional[str]]:
        operations, batches = self.memberships.value["operation_refs"], self.memberships.value["batch_refs"]
        positions = self.context["operation_batch_indices"]
        if len(positions) != len(operations):
            corrupt()
        return {ref: batches[pos] if pos is not None else None for ref, pos in zip(operations, positions)}

    def operation_batch_ref(self, operation_ref):
        return self._operation_batch_refs.get(operation_ref)

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
        """完成运行的共同过程存档，在存储边界一次性核验版本，以及它与本次 run_options 的目标目录一致。"""
        process = decode_model(self.repo.decision_read_model(self.run["run_ref"], ("process",)), ("process",))["process"]
        options = self.context["run_options"]
        if (process["version"] != UNIFIED_PROCESS_VERSION or process["primary_objective"] != options["primary_objective"]
                or process["target_objectives"] != options["target_objectives"]):
            corrupt()
        return process

    @overload
    def _candidate_reference(self, candidate_ref: None) -> None: ...
    @overload
    def _candidate_reference(self, candidate_ref: str) -> Dict[str, Any]: ...

    def _candidate_reference(self, candidate_ref: Optional[str]) -> Optional[Dict[str, Any]]:
        if candidate_ref is None:
            return
        candidate = next((row for row in self.rows if row["candidate_ref"] == candidate_ref), None)
        if candidate is None:
            if self.store.candidate_run(candidate_ref) != self.run["run_ref"]:
                reject("invalid_input", "比较候选属于另一轮排产，请选择本次排产中的方案。", 422)
            corrupt()
        return candidate

    def _scope(self, range_start, range_end):
        if (range_start is None) != (range_end is None):
            reject("invalid_input", "比较时间范围要同时填写开始和结束时间。", 422)
        if range_start is None:
            range_start, range_end = self.context["range_start"], self.context["range_end"]
        try:
            start, end = local_time(range_start), local_time(range_end)
        except (TypeError, ValueError):
            reject("invalid_input", "比较时间范围需要有效的本地时间。", 422)
        if start >= end:
            reject("invalid_input", "比较时间范围结束时间须晚于开始时间。", 422)
        baseline = self.baseline
        identity = {"kind": "candidate", "candidate_ref": self.reference_ref} if self.comparison_mode == "candidates" else {
            "kind": "admission_official", "baseline_ref": baseline["baseline_ref"]}
        return {"run_ref": self.run["run_ref"], "comparison_mode": self.comparison_mode, "selected_candidate_ref": self.selected_ref,
                "reference": identity, "reference_state": baseline["state"], "range_start": start.isoformat(), "range_end": end.isoformat(),
                "batch_count": len(self.batch_refs), "operation_count": len(self.admitted_operation_refs),
                "resource_view": self.resource_view, "metric_scope": "full_admission",
                "time_basis": "factory_local", "delta_basis": "candidate_minus_reference",
                "run_options": self.context["run_options"]}

    def _validated_tasks(self, candidate_ref) -> ValidatedCandidateTasks:
        if candidate_ref not in self._validated:
            validated = validate_candidate_tasks(self.store, self.candidate_record(candidate_ref), self.facts)
            self._validated[candidate_ref] = validated
            self._task_intervals[candidate_ref] = validated.task_intervals
        return self._validated[candidate_ref]

    def tasks(self, candidate_ref):
        if candidate_ref not in self._projected:
            if candidate_ref in self._candidate_sources:
                self._projected[candidate_ref] = self._candidate_sources[candidate_ref].tasks
            else:
                validated = self._validated_tasks(candidate_ref)
                self._projected[candidate_ref] = project_validated_tasks(
                    validated.raw_tasks, self.facts, validated.task_intervals, prepared_tasks=validated.prepared_tasks)
        return self._projected[candidate_ref]

    def candidate_source(self, candidate_ref) -> CandidateReadSource:
        if candidate_ref not in self._candidate_sources:
            self._candidate_sources[candidate_ref] = CandidateReadSource.of(
                self.saved_run, self.candidate_record(candidate_ref), self._validated_tasks(candidate_ref),
                projected=self._projected.get(candidate_ref, ()))
        return self._candidate_sources[candidate_ref]

    def delivery(self, key): return self.saved_projection(key, "delivery")

    def delivery_detail(self, candidate_ref): return self.saved_projection(candidate_ref, "delivery_detail")

    def computation_key(self, key):
        return self.reference_ref if key == "reference" and self.comparison_mode == "candidates" and self.reference_ref is not None else key

    def task_intervals(self, key):
        key = self.computation_key(key)
        if key not in self._task_intervals:
            self.analysis_tasks(key)
        return self._task_intervals[key]

    @cached_property
    def official_details(self):
        """The admission baseline rebuilt from the saved capture."""
        if not self.rows:
            invalid_baseline()
        return read_decision_baseline(self.capture, self.facts, self.disposition)

    @cached_property
    def official(self) -> Dict[str, Any]:
        """The admitted official projection: the active admission block, or the finished run's saved model."""
        if self.run["state"] in ("queued", "running"):
            return self._active_decision["official"]
        return decode_model(self.repo.decision_read_model(self.run["run_ref"], ("official",)), ("official",))["official"]

    @cached_property
    def official_arrangements(self): return analysis_arrangements(self.official["arrangements"])

    @property
    def official_tasks(self): return self.official_arrangements[0]

    @cached_property
    def official_members(self): return self.memberships.expand(self.context["official_members"])

    @cached_property
    def baseline(self):
        if self.comparison_mode == "admission_official":
            return {**self.official["identity"], "candidate_ref": None}
        row = self._reference_row
        return {"kind": "candidate", "candidate_ref": self.reference_ref, "baseline_ref": None, "version": None,
                "source_candidate_ref": None, "label": row["label"] if row else None,
                "state": "available" if row else "selection_required"}

    @cached_property
    def before_tasks(self):
        if self.comparison_mode == "admission_official":
            return [row for row in self.official_details["tasks"] if row["operation_ref"] in self.operation_refs]
        return self.tasks(self.reference_ref) if self.reference_ref else []

    def resource_tasks(self, candidate_ref):
        rows = self.analysis_tasks(candidate_ref)
        return rows if self.resource_view == "full_candidate" else [row for row in rows if row["operation_ref"] in self.operation_refs]

    @cached_property
    def operation_refs(self) -> Set[str]: return set(self.admitted_operation_refs)

    @cached_property
    def resource_before_tasks(self): return self.resource_tasks("reference")

    @cached_property
    def resource_cohort(self):
        ordered = {}
        keys = dict.fromkeys(self.computation_key(key) for key in [c["candidate_ref"] for c in self.rows] + ["reference"])
        for key in keys:
            if key == "reference":
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
        from .decision_resource_engine import DecisionResources
        return DecisionResources(self)

    @cached_property
    def operation_efforts(self): return saved_operation_efforts(self.receipt.operation_effort, identities=self.facts.operations)

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
    def deferred_refs(self): return set(self._members("deferred_operation_refs"))

    @cached_property
    def reference_deferred_ids(self):
        refs = self.deferred_refs if self.comparison_mode == "candidates" else self.reference_deferred_refs
        return {self.facts.operations[ref] for ref in refs}

    @cached_property
    def reference_deferred_refs(self):
        return self.deferred_refs if self.comparison_mode == "candidates" else set(self.memberships.refs(self.official["deferred_operation_refs"], "operation"))

    def state(self):
        return {"run": self.run, "capture_ref": self.run["run_ref"], "metric_version": METRIC_VERSION,
                "recommendation_version": "decision-recommendation-v1",
                "official_sources": self.official["source_states"] if self.comparison_mode == "admission_official" else [],
                "candidates": [{"candidate_ref": row["candidate_ref"], "task_count": row["task_count"]} for row in self.rows]}
