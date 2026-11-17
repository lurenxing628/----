"""Decode admission facts and bind their saved self-contained Schedule identities."""

from typing import NoReturn

from core.models.enums import SOURCE_TYPE_VALUES
from core.models.workbench_load_limits import MAX_RUN_RECORD_TASKS
from core.models.workbench_run_candidate import reference, reject
from core.models.workbench_run_compute import CandidateRunInputError
from core.shared.local_datetime import row_interval
from core.shared.strict_parse import is_stored_time_us

from .candidate_values import bounded_size, gap, text
from .decision_metrics import admission_operation_refs
from .production_capture import archived_columns
from .run_input_codec import prepare_execution_projections
from .zero_duration import point_event_dto


def invalid_baseline() -> NoReturn:
    reject("candidate_baseline_invalid", "排产时的对照资料不完整，无法对比。请重新排产后查看。", 500)


class ArchivedAdmissionPlan:
    """Verify the captured official plan against its archived ScheduleHistory and Schedule rows."""

    def __init__(self, capture, facts):
        self.facts = facts
        self.history = facts.table("ScheduleHistory")
        self.schedule = facts.table("Schedule")
        self.baseline = capture["baseline"]
        self._check_baseline()
        self._bindings()

    def _check_baseline(self):
        baseline = self.baseline
        if set(baseline) != {"plan_ref", "version", "rows"} or type(baseline["rows"]) is not list:
            invalid_baseline()
        bounded_size(len(baseline["rows"]), MAX_RUN_RECORD_TASKS)
        history = self.history
        if any(type(row["version"]) is not int or row["version"] < 1 for row in history):
            invalid_baseline()
        version = max((row["version"] for row in history), default=None)
        if type(baseline["version"]) is not type(version) or baseline["version"] != version:
            invalid_baseline()
        self._check_baseline_ref(version)

    def _check_baseline_ref(self, version):
        baseline = self.baseline
        if version is None:
            if baseline["plan_ref"] is not None or baseline["rows"]:
                invalid_baseline()
            return
        match = next((row for row in self.history if row["version"] == version), None)
        if match is None or match["plan_ref"] != baseline["plan_ref"]:
            invalid_baseline()
        reference(baseline["plan_ref"], stored=True)

    def _bindings(self):
        """Saved baseline rows are a JSON copy of one version's Schedule rows (``jobs_facts.run_baseline``), each with
        exactly that table's columns, without its CHECKs or unique index. Their key set, identities, one row per
        operation (``idx_schedule_version_op_unique``), the stored instants and point flag ``segment`` converts
        (``start_us <= end_us`` and ``is_point_event = (start_us = end_us)``) and the ``source`` it reports, as
        Schedule's CHECKs hold, are admitted here. A row's ``op_id`` must be its ``operation_ref``'s, so one row per
        ``op_id`` is also one row per operation."""
        columns = frozenset(archived_columns()["Schedule"])
        self.by_operation = {}
        op_ids = set()
        for row in self.baseline["rows"]:
            if (type(row) is not dict or row.keys() != columns
                    or type(row["id"]) is not int or row["version"] != self.baseline["version"]
                    or not is_stored_time_us(row["start_us"]) or not is_stored_time_us(row["end_us"])
                    or row["start_us"] > row["end_us"] or type(row["is_point_event"]) is not int
                    or row["is_point_event"] != int(row["start_us"] == row["end_us"])
                    or row["source"] not in SOURCE_TYPE_VALUES):
                invalid_baseline()
            ref = reference(row["operation_ref"], stored=True)
            task_ref = reference(row["task_ref"], stored=True)
            if (
                self.facts.operations.get(ref) != row["op_id"]
                or row["op_id"] not in self.facts.tables["BatchOperations"]
                or row["op_id"] in op_ids
            ):
                invalid_baseline()
            op_ids.add(row["op_id"])
            self.by_operation[ref] = {**row, "row_ref": task_ref}


class AdmissionBaseline(ArchivedAdmissionPlan):
    """Bind saved admission execution without replaying its historical formulas."""

    def __init__(self, capture, facts, disposition):
        super().__init__(capture, facts)
        self.segment_intervals = {}
        self.settings = self._settings(capture["input"])
        self.selected = self._selected(disposition)
        self._execution(capture)

    def _settings(self, value):
        """``value`` is the run's admitted input: ``run_history_projection.admitted_run_input`` on every stored read,
        the preflight's normalized settings while the run is being accepted. Only this baseline's own conditions
        remain: at least one batch, each one an archived batch."""
        if not value["batch_refs"]:
            invalid_baseline()
        batches = {
            ref
            for (kind, key), ref in self.facts.entity_refs.items()
            if kind == "batch" and key in self.facts.tables["Batches"]
        }
        if not set(value["batch_refs"]) <= batches:
            invalid_baseline()
        return value

    def _selected(self, disposition):
        """The admitted operations, which ``disposition`` must cover exactly, each with its archived operation and batch.

        A selected operation's archived row and batch ref are read through the archive relations
        (``GenerationFacts.operation``, ``entity_ref``); ``admission_operation_refs`` already read both for every
        selected ref. Each row's ``op_id`` is indexed directly (``completed_dispositions`` admits it on stored reads;
        acceptance builds it). A stored row's ``batch_ref`` is admitted only here, so its absence stays a mismatch."""
        facts = self.facts
        selected = admission_operation_refs(facts, self.settings)
        if selected != set(disposition):
            invalid_baseline()
        for ref, item in disposition.items():
            op = facts.operation(ref)
            if item["op_id"] != op["id"] or item.get("batch_ref") != facts.entity_ref("batch", op["batch_id"]):
                invalid_baseline()
        return selected

    def _execution_scope(self):
        version = self.baseline["version"]
        if version is None:
            return self.selected
        scheduled = {row["op_id"] for row in self.schedule if row["version"] <= version}
        identities = {key: ref for ref, key in self.facts.operations.items()}
        if not scheduled <= set(identities):
            invalid_baseline()
        return self.selected | {identities[key] for key in scheduled}

    def _execution(self, capture):
        expected = self._execution_scope()
        raw = capture["execution"]
        try:
            projections = prepare_execution_projections(raw)
        except (CandidateRunInputError, TypeError, ValueError):
            invalid_baseline()
        if {row["operation_ref"] for row in projections} != expected:
            invalid_baseline()
        for projection in projections:
            ref = projection["operation_ref"]
            current = projection["current_task_ref"]
            if ref in self.by_operation:
                if current != self.by_operation[ref]["task_ref"]:
                    invalid_baseline()
            elif current is not None:
                invalid_baseline()

    def operation_segment(self, ref):
        """The operation's one baseline row (one Schedule row per version and operation), or None when unarranged."""
        return self.segment(self.by_operation[ref]) if ref in self.by_operation else None

    def _row_resource(self, row, kind, gaps):
        if row[kind + "_id"] is None and row[kind + "_ref"] is None:
            return None
        ref = row[kind + "_ref"]
        if ref is None:
            gaps.append(gap(kind + ".ref", "source_missing"))
        raw_label = row[kind + "_label"]
        label = text(raw_label, kind + ".label", gaps) if raw_label is not None else None
        if kind == "supplier" and label is None and not any(item["field"] == "supplier.label" for item in gaps):
            gaps.append(gap("supplier.label", "source_missing"))
        return {"ref": ref, "label": label}

    def segment(self, row):
        gaps = []
        start, end = row_interval(row)
        point = point_event_dto(start, end) if row["is_point_event"] else {}
        self.segment_intervals[row["row_ref"]] = (start, end)
        return {
            "row_ref": row["row_ref"],
            "start": start.isoformat(),
            "end": end.isoformat(),
            **point,
            "elapsed_hours": (end - start).total_seconds() / 3600,
            "machine": self._row_resource(row, "machine", gaps),
            "operator": self._row_resource(row, "operator", gaps),
            "source": row["source"],
            "supplier": self._row_resource(row, "supplier", gaps),
            "effective_processing_hours": None,
            "data_gaps": gaps,
        }
