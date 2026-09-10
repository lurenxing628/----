"""Compare only the original admission capture, under BL's bounded read snapshot."""

import base64
import binascii
import sqlite3
from collections import Counter, defaultdict
from typing import NoReturn

from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_objects
from core.infrastructure.workbench_metadata_schema import _canonical_sql
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json, input_fingerprint
from core.models.workbench_preflight import normalize_preflight_input, preflight_window
from core.models.workbench_run_baseline import RunBaselineComparison, baseline_reason, elapsed_hours
from core.models.workbench_run_candidate import MAX_RESPONSE_BYTES, MAX_TASKS, local_time, reference, reject
from core.models.workbench_run_compute import CandidateRunInputError

from .execution_ledger_projection import project_execution, report_dto
from .run_candidate_facts import GenerationFacts, _index, _table
from .run_candidate_projection import candidate_summary
from .run_candidate_tasks import _resource, operation_labels, tasks_projection
from .run_candidate_values import bounded_size, corrupt, gap, stored_json
from .run_candidates import WorkbenchRunCandidateQueryService
from .run_input_projection_codec import restore_execution_projections


def _invalid() -> NoReturn:
    reject("candidate_baseline_invalid", "受理时基线、输入、执行快照或永久引用缺失或不一致，未替换为当前数据。", 500)


class AdmissionBaseline:
    """Cross-check redundant captures against the SHA-256-checked archived facts."""

    def __init__(self, capture, facts, disposition, accepted_at):
        self.facts = facts
        archive = stored_json(capture["facts_text"])
        self.sources = self._required(archive, "WorkbenchPlanSourceRefs")
        self.tasks = _index(self._required(archive, "WorkbenchTaskRefs"), "ref")
        self.baseline = capture["baseline"]
        self._check_baseline(archive)
        self.settings = self._settings(capture["input"])
        self.selected = self._selected(disposition)
        self._bindings()
        self._execution(capture, disposition, archive, accepted_at)

    @staticmethod
    def _required(archive, name):
        rows = _report_revisions(archive) if name == "WorkbenchProductionReportRevisions" else _table(archive, name)
        if rows is None:
            _invalid()
        return rows

    def _check_baseline(self, archive):
        baseline = self.baseline
        if set(baseline) != {"plan_ref", "version", "rows"} or type(baseline["rows"]) is not list:
            _invalid()
        bounded_size(len(baseline["rows"]), MAX_TASKS)
        history = self._required(archive, "ScheduleHistory")
        if any(type(row.get("version")) is not int or row["version"] < 1 for row in history):
            _invalid()
        version = max((row["version"] for row in history), default=None)
        if type(baseline["version"]) is not type(version) or baseline["version"] != version:
            _invalid()
        self._check_baseline_rows(archive, version)
        self._check_baseline_ref(version)

    def _check_baseline_rows(self, archive, version):
        schedule = self._required(archive, "Schedule")
        rows = [row for row in schedule if row.get("version") == version] if version is not None else []
        if any(type(row.get("id")) is not int or type(row.get("op_id")) is not int for row in rows):
            _invalid()
        rows.sort(key=lambda row: row["id"])
        if input_fingerprint(rows) != input_fingerprint(self.baseline["rows"]):
            _invalid()

    def _check_baseline_ref(self, version):
        baseline = self.baseline
        if version is None:
            if baseline["plan_ref"] is not None:
                _invalid()
            return
        refs = [row for row in self.sources if row.get("kind") == "official" and row.get("active") == 1
                and row.get("version") == version]
        if len(refs) != 1 or refs[0].get("ref") != baseline["plan_ref"]:
            _invalid()
        reference(baseline["plan_ref"], stored=True)

    def _settings(self, value):
        try:
            settings = normalize_preflight_input(value)
        except WorkbenchCommandRejected:
            _invalid()
        if not settings["batch_refs"] or settings != value:
            _invalid()
        batches = {ref for (kind, key), ref in self.facts.entity_refs.items()
                   if kind == "batch" and key in self.facts.tables["Batches"]}
        if not set(settings["batch_refs"]) <= batches:
            _invalid()
        return settings

    def _selected(self, disposition):
        if disposition is None:
            _invalid()
        facts = self.facts
        batch_refs = set(self.settings["batch_refs"])
        if len(set(facts.operations.values())) != len(facts.operations):
            _invalid()
        selected = {ref for ref, key in facts.operations.items() if
                    facts.entity_refs.get(("batch", facts.tables["BatchOperations"].get(key, {}).get("batch_id")))
                    in batch_refs}
        if selected != set(disposition):
            _invalid()
        for ref, item in disposition.items():
            op = facts.tables["BatchOperations"].get(facts.operations.get(ref))
            if (op is None or item.get("op_id") != op["id"]
                    or item.get("batch_ref") != facts.entity_refs.get(("batch", op["batch_id"]))):
                _invalid()
        return selected

    def _bindings(self):
        source_refs = _index(self.sources, "ref")
        active_rows = defaultdict(list)
        for row in source_refs.values():
            if row.get("kind") == "schedule_row" and row.get("active") == 1:
                active_rows[(row.get("version"), row.get("source_key"))].append(row)
        self.by_operation = defaultdict(list)
        for row in self.baseline["rows"]:
            matches = active_rows[(self.baseline["version"], str(row["id"]))]
            if len(matches) != 1:
                _invalid()
            source = matches[0]
            ref = reference(source.get("operation_ref"), stored=True)
            row_ref = reference(source.get("ref"), stored=True)
            if (self.facts.operations.get(ref) != row["op_id"] or row["op_id"] not in self.facts.tables["BatchOperations"]
                    or source.get("operation_id") != row["op_id"] or source.get("source_table") != "schedule"):
                _invalid()
            self.by_operation[ref].append({**row, "row_ref": row_ref})

    def _execution(self, capture, disposition, archive, accepted_at):
        try:
            projections = restore_execution_projections(capture["execution"])
        except (CandidateRunInputError, TypeError, ValueError):
            _invalid()
        if {row.operation_ref for row in projections} != self.selected | set(self.by_operation):
            _invalid()
        for projection in projections:
            ref = projection.operation_ref
            if ref in disposition and input_fingerprint(disposition[ref].get("execution")) != input_fingerprint(projection.to_dict()):
                _invalid()
            current = projection.current_task_ref
            if ref in self.by_operation:
                task = self.tasks.get(current)
                if (task is None or task.get("plan_ref") != self.baseline["plan_ref"]
                        or task.get("row_ref") not in {row["row_ref"] for row in self.by_operation[ref]}):
                    _invalid()
            elif current is not None:
                _invalid()
        self._verify_execution_values(projections, archive, accepted_at)

    def _verify_execution_values(self, projections, archive, accepted_at):
        reports = _archived_reports(archive)
        legacy, unresolved = defaultdict(list), set()
        for raw in self._required(archive, "WorkbenchExecutionLegacyFacts"):
            row = {key: _blob(value) for key, value in raw.items()}
            legacy[row.get("operation_ref")].append(row)
            if row.get("operation_ref") is None or row.get("recorded_against_task_ref") is None:
                unresolved.add(row.get("op_id"))
        fields = ("target_quantity", "target_basis", "known_completed_quantity", "quantity_complete", "unknown_record_count",
                  "records_complete", "first_actual_start", "confirmed_finish", "execution_state", "completion_basis",
                  "data_quality", "remaining_quantity", "remaining_plan", "reports", "legacy_facts")
        for projection in projections:
            ref = projection.operation_ref
            operation = self.facts.tables["BatchOperations"].get(self.facts.operations.get(ref))
            if operation is None:
                _invalid()
            batch = self.facts.tables["Batches"].get(operation.get("batch_id"), {})
            try:
                checked = project_execution(
                    {**operation, "operation_ref": ref, "identity_active": 1, "batch_quantity": batch.get("quantity")},
                    reports.get(ref, []), sorted(legacy.get(ref, []), key=lambda row: row["id"]),
                    current_task=None, comparison_task=None, plan_identity=None,
                    now=local_time(accepted_at), unresolved=operation["id"] in unresolved,
                ).to_dict()
            except (KeyError, TypeError, ValueError, OverflowError):
                _invalid()
            saved = projection.to_dict()
            if input_fingerprint({key: checked[key] for key in fields}) != input_fingerprint({key: saved[key] for key in fields}):
                _invalid()

    def segments(self, ref):
        return [self._segment(row) for row in self.by_operation.get(ref, [])]

    def _segment(self, row):
        gaps = []
        start, end = _baseline_interval(row, gaps)
        return {"row_ref": row["row_ref"], "start": start, "end": end,
                "elapsed_hours": elapsed_hours(start, end) if start is not None and end is not None else None,
                "interval_comparable": start is not None and end is not None and local_time(start) < local_time(end),
                "machine": _resource(self.facts, "machine", row.get("machine_id"), gaps),
                "operator": _resource(self.facts, "operator", row.get("operator_id"), gaps),
                "supplier": None, "effective_processing_hours": None, "data_gaps": gaps}


def _blob(value):
    if type(value) is not dict:
        return value
    if set(value) != {"sqlite_blob_base64"} or type(value["sqlite_blob_base64"]) is not str:
        _invalid()
    try:
        return base64.b64decode(value["sqlite_blob_base64"], validate=True)
    except (ValueError, binascii.Error):
        _invalid()


def _report_revisions(archive):
    name = "WorkbenchProductionReportRevisions"
    sql = execution_ledger_objects()[name]
    ddl = [row[3] for row in archive["schema"] if type(row) is list and len(row) == 4 and row[0:2] == ["table", name]]
    if len(ddl) != 1 or type(ddl[0]) is not str or _canonical_sql(ddl[0]) != _canonical_sql(sql):
        _invalid()
    # Only the known application DDL is parsed; archived SQL is never executed here.
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(sql)
        columns = [row[1] for row in conn.execute("PRAGMA table_info(WorkbenchProductionReportRevisions)")]
    finally:
        conn.close()
    rows = archive["tables"].get(name)
    if type(rows) is not list or any(type(row) is not list or len(row) != len(columns) for row in rows):
        _invalid()
    return [dict(zip(columns, row)) for row in rows]


def _archived_reports(archive):
    headers = _index(AdmissionBaseline._required(archive, "WorkbenchProductionReports"), "report_ref")
    receipts = _index(AdmissionBaseline._required(archive, "WorkbenchCommandReceipts"), "request_key")
    histories, result = defaultdict(list), defaultdict(list)
    for row in AdmissionBaseline._required(archive, "WorkbenchProductionReportRevisions"):
        histories[row.get("report_ref")].append(row)
    if set(histories) != set(headers):
        _invalid()
    for ref, header in headers.items():
        history = []
        for ordinal, revision in enumerate(sorted(histories[ref], key=lambda row: row["sequence"]), 1):
            if revision["sequence"] != ordinal:
                _invalid()
            history.append({**header, **{key: value for key, value in revision.items() if key != "recorded_at"},
                            "revision_at": revision["recorded_at"], "values": stored_json(revision["values_json"]),
                            "receipt_ref": receipts.get(revision["request_key"], {}).get("receipt_ref")})
        try:
            result[header["operation_ref"]].append(report_dto(history))
        except (KeyError, TypeError, ValueError):
            _invalid()
    return {ref: sorted(rows, key=lambda row: (row.recorded_at, row.report_no)) for ref, rows in result.items()}


def _baseline_interval(row, gaps):
    values = []
    for field in ("start_time", "end_time"):
        value = row.get(field)
        try:
            # Schedule historically stores both SQLite's space and ISO's T separator.
            if type(value) is not str:
                raise ValueError("Not a saved timestamp")
            parsed = local_time(value.replace(" ", "T", 1))
            values.append(parsed.isoformat())
        except (TypeError, ValueError):
            gaps.append(gap(field, "blob_metadata" if type(value) is dict and "sqlite_blob_base64" in value else "invalid_stored_value"))
            values.append(None)
    if all(value is not None for value in values) and local_time(values[0]) > local_time(values[1]):
        gaps.append(gap("interval", "invalid_stored_value"))
        return None, None
    return tuple(values)


def _candidate_interval(task):
    fields = ("row_ref", "start", "end", "source", "machine", "operator", "supplier", "locked", "data_gaps")
    result = {**{key: task[key] for key in fields}, "elapsed_hours": elapsed_hours(task["start"], task["end"]),
              "effective_processing_hours": None}
    if task.get("event_kind") == "point":
        result.update(event_kind="point", duration_seconds=0, occupies_resources=False)
    return result


def _check_task_window(tasks, admission, disposition):
    start, end = (local_time(value) for value in preflight_window(admission.settings))
    for task in tasks:
        protected = disposition.get(task["operation_ref"], {}).get("status") == "protected" or task["locked"]
        if not protected and (local_time(task["start"]) < start or local_time(task["end"]) > end):
            _invalid()


def _comparison_labels(facts, ref):
    labels, _ = operation_labels(facts, ref)
    execution = facts.execution[ref]
    labels["execution_at_generation"].update({key: execution[key] for key in (
        "first_actual_start", "confirmed_finish", "unknown_record_count", "records_complete", "quantity_complete", "completion_basis")})
    labels["execution_at_generation"].update(
        report_count=len(execution["reports"]), legacy_fact_count=len(execution["legacy_facts"]),
        legacy_unavailable_field_count=sum(len(row["unavailable_fields"]) for row in execution["legacy_facts"]))
    return labels


def _comparison_row(ref, task, admission, disposition):
    labels = _comparison_labels(admission.facts, ref)
    return RunBaselineComparison(
        ref, task["row_ref"] if task else None, labels, _candidate_interval(task) if task else None,
        admission.segments(ref), ref in admission.selected,
        "scheduled" if task else "skipped" if disposition.get(ref, {}).get("status") == "skipped"
        else "unscheduled" if ref in admission.selected else None,
    ).to_dict()


def _rows(tasks, admission, disposition):
    by_ref = {task["operation_ref"]: task for task in tasks}
    if not set(by_ref) <= admission.selected | set(admission.by_operation):
        _invalid()
    _check_task_window(tasks, admission, disposition)
    return [_comparison_row(ref, by_ref.get(ref), admission, disposition)
            for ref in sorted(admission.selected | set(admission.by_operation) | set(by_ref))]


def _in_time(row, start, end):
    from .zero_duration_evidence import overlaps

    if row["candidate"] is None:
        return True
    intervals = [row["candidate"]] + row["baseline_segments"]
    if any(item["start"] is None or item["end"] is None or
           (item["start"] == item["end"] and item.get("event_kind") != "point") for item in intervals):
        return True
    return any(overlaps(local_time(item["start"]), local_time(item["end"]), start, end) for item in intervals)


def _scope_rows(rows, scope):
    if scope.batch_ref is not None:
        if scope.batch_ref not in {row["batch_ref"] for row in rows}:
            reject("entity_not_found", "该批次不属于受理时对照范围，未查询当前同号批次。", 404)
        rows = [row for row in rows if row["batch_ref"] == scope.batch_ref]
    if scope.range_start is not None:
        start, end = local_time(scope.range_start), local_time(scope.range_end)
        rows = [row for row in rows if _in_time(row, start, end)]

    def key(row):
        if scope.sort == "sequence":
            value = row["sequence"]
            return value is None, int(value) if value is not None else 0, row["operation_ref"]
        intervals = [row["candidate"]] if row["candidate"] else row["baseline_segments"]
        values = [item[scope.sort] for item in intervals if item[scope.sort] is not None]
        return not values, min(values) if values else "", row["operation_ref"]

    return sorted(rows, key=key, reverse=scope.order == "desc")


class WorkbenchRunCandidateBaselineQueryService:
    def __init__(self, conn):
        self.reader = WorkbenchRunCandidateQueryService(conn)

    def baseline(self, scope):
        store = self.reader.store
        with store.snapshot():
            run_ref = store.candidate_run(scope.candidate_ref)
            run, candidates, disposition = self.reader._load(run_ref)
            candidate = next((row for row in candidates if row["candidate_ref"] == scope.candidate_ref), None)
            if candidate is None:
                corrupt()
            summary = candidate_summary(candidate, disposition)
            capture = store.capture(run_ref)
            facts = GenerationFacts(capture)
            admission = AdmissionBaseline(capture, facts, disposition, run["accepted_at"])
            raw = store.tasks(scope.candidate_ref)
            if len(raw) != candidate["task_count"]:
                corrupt()
            # BL allows missing display metadata; comparison requires an exact captured identity.
            for row in raw:
                if facts.operations.get(row["operation_ref"]) != row["payload"].get("op_id"):
                    _invalid()
            tasks = tasks_projection(raw, candidate, facts)
            all_rows = _rows(tasks, admission, disposition)
            rows = _scope_rows(all_rows, scope)
            data = self._dto(run, summary, admission, rows, len(all_rows), scope)
            bounded_size(len(canonical_json(data).encode("utf-8")), MAX_RESPONSE_BYTES)
            return data, input_fingerprint(data)

    @staticmethod
    def _dto(run, candidate, admission, rows, count, scope):
        available = any(row["comparison_available"] for row in rows)
        captured = admission.baseline["version"] is not None
        reason = None if available else baseline_reason("no_comparable_operations" if captured else "no_admission_baseline")
        return {"candidate": candidate, "generation": {
                    "run_ref": run["run_ref"], "accepted_at": run["accepted_at"], "finished_at": run["finished_at"],
                    "metadata_basis": "captured_at_run_admission", "execution_basis": "captured_at_run_admission",
                    "current_entities_consulted": False, "formal_version_allocated": False, "input": admission.settings,
                    "source_verification": {"facts_digest_verified": True, "baseline_matches_archived_schedule": True,
                                            "execution_matches_archived_evidence": True, "input_independent_digest_recorded": False}},
                "baseline": {"baseline_ref": admission.baseline["plan_ref"], "kind": "admission_official",
                             "available": captured, "captured_task_count": len(admission.baseline["rows"]),
                             "comparison_available": available, "reason": reason},
                "comparisons": rows, "operation_count": len(rows), "full_operation_count": count, "rows_complete": True,
                "counts": dict(Counter(row["status"] for row in rows)),
                "execution_affected_count": sum(row["execution_affected"] for row in rows),
                "time_scope": {"range_start": scope.range_start, "range_end": scope.range_end,
                               "interval": "half_open_overlap", "membership": "either_side_overlap",
                               "counterpart_policy": "retain_complete_counterpart", "time_basis": "factory_local",
                               "unplanned_policy": "included_without_time_interval",
                               "unknown_or_zero_interval_policy": "included_without_time_interval"},
                "batch_ref": scope.batch_ref, "delta_basis": "candidate_minus_admission_baseline",
                "duration_basis": "elapsed_wall_clock_hours_not_effective_processing",
                "improvement_assessment": None, "capabilities": {"view": True, "adopt": False, "edit_draft": False,
                                                                       "report_actual": False, "export": False},
                "data_gaps": [baseline_reason(code) for code in ("effective_hours_not_recorded",
                              "historical_supplier_not_recorded", "not_an_optimization_score", "input_digest_not_recorded")]}
