"""Decode admission facts and bind their saved operation and task identities."""

import base64
import binascii
from collections import defaultdict
from typing import NoReturn

from core.algorithm_contracts.value_domains import OPERATION_SOURCES
from core.models.content import unpacked
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.models.workbench_preflight import normalize_preflight_input
from core.models.workbench_run_candidate import MAX_TASKS, local_time, reference, reject
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.scheduler.run.schedule_payload_contract import ValidatedScheduleRow

from .candidate_facts import index_rows
from .candidate_tasks import task_resource
from .candidate_values import bounded_size, gap
from .run_input_codec import prepare_execution_projections
from .zero_duration import point_event_dto

_ORIGIN_NOT_RECORDED = {"code": "adoption_not_recorded", "message": "此正式版本未保存可核对的采用来源。"}


def invalid_baseline() -> NoReturn:
    reject("candidate_baseline_invalid", "排产时的对照资料不完整，无法对比。请重新排产后查看。", 500)


class ArchivedAdmissionPlan:
    """Verify the captured official plan against its archived rows and identities."""

    def __init__(self, capture, facts):
        self.facts = facts
        self.sources = self._required("WorkbenchPlanSourceRefs")
        self.tasks = index_rows(self._required("WorkbenchTaskRefs"), "ref")
        self.history = self._required("ScheduleHistory")
        self.schedule = self._required("Schedule")
        self.baseline = capture["baseline"]
        self._check_baseline()
        self._bindings()

    def _required(self, name):
        rows = self.facts.table(name)
        if rows is None:
            invalid_baseline()
        return rows

    def _check_baseline(self):
        baseline = self.baseline
        if set(baseline) != {"plan_ref", "version", "rows"} or type(baseline["rows"]) is not list:
            invalid_baseline()
        bounded_size(len(baseline["rows"]), MAX_TASKS)
        history = self.history
        if any(type(row.get("version")) is not int or row["version"] < 1 for row in history):
            invalid_baseline()
        version = max((row["version"] for row in history), default=None)
        if type(baseline["version"]) is not type(version) or baseline["version"] != version:
            invalid_baseline()
        self._check_baseline_rows(version)
        self._check_baseline_ref(version)

    def _check_baseline_rows(self, version):
        schedule = self.schedule
        rows = [row for row in schedule if row.get("version") == version] if version is not None else []
        if any(type(row.get("id")) is not int or type(row.get("op_id")) is not int for row in rows):
            invalid_baseline()
        rows.sort(key=lambda row: row["id"])
        if canonical_json(rows) != canonical_json(self.baseline["rows"]):
            invalid_baseline()

    def _check_baseline_ref(self, version):
        baseline = self.baseline
        if version is None:
            if baseline["plan_ref"] is not None:
                invalid_baseline()
            return
        refs = [row for row in self.sources if row.get("kind") == "official" and row.get("active") == 1
                and row.get("version") == version]
        if len(refs) != 1 or refs[0].get("ref") != baseline["plan_ref"]:
            invalid_baseline()
        reference(baseline["plan_ref"], stored=True)

    def _bindings(self):
        source_refs = index_rows(self.sources, "ref")
        active_rows = defaultdict(list)
        for row in source_refs.values():
            if row.get("kind") == "schedule_row" and row.get("active") == 1:
                active_rows[(row.get("version"), row.get("source_key"))].append(row)
        self.schedule_bindings = active_rows
        self.by_operation = defaultdict(list)
        for row in self.baseline["rows"]:
            matches = active_rows[(self.baseline["version"], str(row["id"]))]
            if len(matches) != 1:
                invalid_baseline()
            source = matches[0]
            ref = reference(source.get("operation_ref"), stored=True)
            row_ref = reference(source.get("ref"), stored=True)
            if (self.facts.operations.get(ref) != row["op_id"] or row["op_id"] not in self.facts.tables["BatchOperations"]
                    or source.get("operation_id") != row["op_id"] or source.get("source_table") != "schedule"):
                invalid_baseline()
            self.by_operation[ref].append({**row, "row_ref": row_ref})


class AdmissionBaseline(ArchivedAdmissionPlan):
    """Bind saved admission execution without replaying its historical formulas."""

    def __init__(self, capture, facts, disposition, *, point_work=None, origins=None, origin_issue=None):
        super().__init__(capture, facts)
        self.bind_origin({} if origins is None else origins,
                         _ORIGIN_NOT_RECORDED if origin_issue is None else origin_issue, point_work)
        self.settings = self._settings(capture["input"])
        self.selected = self._selected(disposition)
        self._execution(capture)

    def _settings(self, value):
        try:
            settings = normalize_preflight_input(value)
        except WorkbenchCommandRejected:
            invalid_baseline()
        if not settings["batch_refs"] or settings != value:
            invalid_baseline()
        batches = {ref for (kind, key), ref in self.facts.entity_refs.items()
                   if kind == "batch" and key in self.facts.tables["Batches"]}
        if not set(settings["batch_refs"]) <= batches:
            invalid_baseline()
        return settings

    def _selected(self, disposition):
        facts = self.facts
        batch_refs = set(self.settings["batch_refs"])
        if len(set(facts.operations.values())) != len(facts.operations):
            invalid_baseline()
        selected = {ref for ref, key in facts.operations.items() if
                    facts.entity_refs.get(("batch", facts.tables["BatchOperations"].get(key, {}).get("batch_id")))
                    in batch_refs}
        if selected != set(disposition):
            invalid_baseline()
        for ref, item in disposition.items():
            op = facts.tables["BatchOperations"].get(facts.operations.get(ref))
            if (op is None or item.get("op_id") != op["id"]
                    or item.get("batch_ref") != facts.entity_refs.get(("batch", op["batch_id"]))):
                invalid_baseline()
        return selected

    def _execution_scope(self):
        # Admission also captures each operation's last official execution,
        # including operations absent from the latest (possibly partial) plan.
        # These rows validate execution evidence; they do not extend the latest
        # plan's comparison baseline or become its current task bindings.
        version = self.baseline["version"]
        if version is None:
            return self.selected
        scheduled = set()
        for row in self.schedule:
            if type(row.get("version")) is not int or type(row.get("op_id")) is not int:
                invalid_baseline()
            if row["version"] <= version:
                scheduled.add(row["op_id"])
        identities = {key: ref for ref, key in self.facts.operations.items()}
        if not scheduled <= set(identities):
            invalid_baseline()
        return self.selected | {identities[key] for key in scheduled}

    def _execution(self, capture):
        expected = self._execution_scope()
        raw = capture["execution"]
        try:
            projections = prepare_execution_projections(raw, max_operations=None)
        except (CandidateRunInputError, TypeError, ValueError):
            invalid_baseline()
        if {row["operation_ref"] for row in projections} != expected:
            invalid_baseline()
        for projection in projections:
            ref = projection["operation_ref"]
            current = projection["current_task_ref"]
            if ref in self.by_operation:
                task = self.tasks.get(current)
                if (task is None or task.get("plan_ref") != self.baseline["plan_ref"]
                        or task.get("row_ref") not in {row["row_ref"] for row in self.by_operation[ref]}):
                    invalid_baseline()
            elif current is not None:
                invalid_baseline()

    def bind_origin(self, origins, origin_issue, point_work):
        """Read segments against one official version's adoption origins and point work.

        ``point_work`` is a zero-argument loader of that version's point witnesses, or
        None when the version has no adoption evidence; it is loaded once per binding.
        """
        self._origins, self._origin_issue = origins, origin_issue
        self._point_work_loader, self._point_work = point_work, None

    def origin(self, op_id):
        return self._origins.get(op_id, {})

    def segments(self, ref):
        return [self.segment(row) for row in self.by_operation.get(ref, [])]

    def segment(self, row):
        gaps = []
        start, end = baseline_interval(row, gaps)
        point = self._point(row, start, end, gaps) if start is not None and start == end else {}
        origin = self.origin(row["op_id"])
        source = row.get("source", origin.get("source"))
        gaps.extend(origin.get("data_gaps", []))
        if type(source) is not str or source not in OPERATION_SOURCES:
            source = None
            if not any(row["field"] == "source" for row in gaps):
                gaps.append({"field": "source", **self._origin_issue})
        if not origin and source != "internal":
            gaps.append({"field": "supplier", **self._origin_issue})
        return {"row_ref": row["row_ref"], "start": start.isoformat() if start is not None else None,
                "end": end.isoformat() if end is not None else None, **point,
                "elapsed_hours": (end - start).total_seconds() / 3600 if start is not None and end is not None else None,
                "interval_comparable": bool(point) or start is not None and end is not None and start != end,
                "machine": task_resource(self.facts, "machine", row.get("machine_id"), gaps),
                "operator": task_resource(self.facts, "operator", row.get("operator_id"), gaps),
                "source": source, "supplier": origin.get("supplier"), "effective_processing_hours": None, "data_gaps": gaps}

    def _point(self, row, start, end, gaps):
        if self._point_work is None:
            try:
                self._point_work = self._point_work_loader() if self._point_work_loader is not None else {}
            except WorkbenchCommandRejected as exc:
                if exc.code != "point_evidence_unproven":
                    raise
                self._point_work = {}
        work = self._point_work.get(row["op_id"])
        original = ValidatedScheduleRow(op_id=row["op_id"], source="internal", machine_id=row.get("machine_id"),
                                        operator_id=row.get("operator_id"), start_time=start, end_time=end)
        if work is None or not work["witness"].matches(original):
            gaps.append(gap("point_evidence", "source_missing" if work is None else "invalid_stored_value"))
            return {}
        return point_event_dto(start, end)


def unpack_blob(value):
    if type(value) is dict and set(value) in ({"$sqlite_blob"}, {"$sqlite_real"}):
        return unpacked(value)
    if type(value) is not dict:
        return value
    if set(value) != {"sqlite_blob_base64"} or type(value["sqlite_blob_base64"]) is not str:
        invalid_baseline()
    try:
        return base64.b64decode(value["sqlite_blob_base64"], validate=True)
    except (ValueError, binascii.Error):
        invalid_baseline()


def baseline_interval(row, gaps):
    values = []
    for field in ("start_time", "end_time"):
        value = row.get(field)
        try:
            # Schedule historically stores both SQLite's space and ISO's T separator.
            if type(value) is not str:
                raise ValueError("Not a saved timestamp")
            values.append(local_time(value.replace(" ", "T", 1)))
        except (TypeError, ValueError):
            gaps.append(gap(field, "blob_metadata" if type(value) is dict and "sqlite_blob_base64" in value else "invalid_stored_value"))
            values.append(None)
    if values[0] is not None and values[1] is not None and values[0] > values[1]:
        gaps.append(gap("interval", "invalid_stored_value"))
        return None, None
    return tuple(values)
