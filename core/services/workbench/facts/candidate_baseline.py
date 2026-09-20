"""Cross-check the original admission capture against the archived candidate facts."""

import base64
import binascii
from collections import defaultdict
from typing import NoReturn

from core.infrastructure.snapshot_connection import ddl_columns
from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_objects
from core.infrastructure.workbench_execution_void_schema import execution_void_objects
from core.infrastructure.workbench_metadata_schema import _canonical_sql
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_preflight import normalize_preflight_input
from core.models.workbench_run_baseline import elapsed_hours
from core.models.workbench_run_candidate import MAX_TASKS, local_time, reference, reject
from core.models.workbench_run_compute import CandidateRunInputError

from .candidate_facts import _index, _table
from .candidate_tasks import _resource
from .candidate_values import bounded_size, gap, stored_json
from .execution_projection import project_execution, report_dto
from .run_input_codec import restore_execution_projections


def invalid_baseline() -> NoReturn:
    reject("candidate_baseline_invalid", "排产时的对照资料不完整，无法对比。请重新排产后查看。", 500)


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
            invalid_baseline()
        return rows

    def _check_baseline(self, archive):
        baseline = self.baseline
        if set(baseline) != {"plan_ref", "version", "rows"} or type(baseline["rows"]) is not list:
            invalid_baseline()
        bounded_size(len(baseline["rows"]), MAX_TASKS)
        history = self._required(archive, "ScheduleHistory")
        if any(type(row.get("version")) is not int or row["version"] < 1 for row in history):
            invalid_baseline()
        version = max((row["version"] for row in history), default=None)
        if type(baseline["version"]) is not type(version) or baseline["version"] != version:
            invalid_baseline()
        self._check_baseline_rows(archive, version)
        self._check_baseline_ref(version)

    def _check_baseline_rows(self, archive, version):
        schedule = self._required(archive, "Schedule")
        rows = [row for row in schedule if row.get("version") == version] if version is not None else []
        if any(type(row.get("id")) is not int or type(row.get("op_id")) is not int for row in rows):
            invalid_baseline()
        rows.sort(key=lambda row: row["id"])
        if input_fingerprint(rows) != input_fingerprint(self.baseline["rows"]):
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
        if disposition is None:
            invalid_baseline()
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
                invalid_baseline()
            source = matches[0]
            ref = reference(source.get("operation_ref"), stored=True)
            row_ref = reference(source.get("ref"), stored=True)
            if (self.facts.operations.get(ref) != row["op_id"] or row["op_id"] not in self.facts.tables["BatchOperations"]
                    or source.get("operation_id") != row["op_id"] or source.get("source_table") != "schedule"):
                invalid_baseline()
            self.by_operation[ref].append({**row, "row_ref": row_ref})

    def _execution_scope(self, archive):
        # Admission also captures each operation's last official execution,
        # including operations absent from the latest (possibly partial) plan.
        # These rows validate execution evidence; they do not extend the latest
        # plan's comparison baseline or become its current task bindings.
        version = self.baseline["version"]
        if version is None:
            return self.selected
        scheduled = set()
        for row in self._required(archive, "Schedule"):
            if type(row.get("version")) is not int or type(row.get("op_id")) is not int:
                invalid_baseline()
            if row["version"] <= version:
                scheduled.add(row["op_id"])
        identities = {key: ref for ref, key in self.facts.operations.items()}
        if not scheduled <= set(identities):
            invalid_baseline()
        return self.selected | {identities[key] for key in scheduled}

    def _execution(self, capture, disposition, archive, accepted_at):
        try:
            projections = restore_execution_projections(capture["execution"])
        except (CandidateRunInputError, TypeError, ValueError):
            invalid_baseline()
        if {row.operation_ref for row in projections} != self._execution_scope(archive):
            invalid_baseline()
        for projection in projections:
            ref = projection.operation_ref
            if ref in disposition:
                try:
                    original = restore_execution_projections([disposition[ref].get("execution")])[0]
                except (CandidateRunInputError, TypeError, ValueError):
                    invalid_baseline()
                if input_fingerprint(original.to_dict()) != input_fingerprint(projection.to_dict()):
                    invalid_baseline()
            current = projection.current_task_ref
            if ref in self.by_operation:
                task = self.tasks.get(current)
                if (task is None or task.get("plan_ref") != self.baseline["plan_ref"]
                        or task.get("row_ref") not in {row["row_ref"] for row in self.by_operation[ref]}):
                    invalid_baseline()
            elif current is not None:
                invalid_baseline()
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
                invalid_baseline()
            batch = self.facts.tables["Batches"].get(operation.get("batch_id"), {})
            try:
                checked = project_execution(
                    {**operation, "operation_ref": ref, "identity_active": 1, "batch_quantity": batch.get("quantity")},
                    reports.get(ref, []), sorted(legacy.get(ref, []), key=lambda row: row["id"]),
                    current_task=None, comparison_task=None, plan_identity=None,
                    now=local_time(accepted_at), unresolved=operation["id"] in unresolved,
                ).to_dict()
            except (KeyError, TypeError, ValueError, OverflowError):
                invalid_baseline()
            saved = projection.to_dict()
            if input_fingerprint({key: checked[key] for key in fields}) != input_fingerprint({key: saved[key] for key in fields}):
                invalid_baseline()

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
        invalid_baseline()
    try:
        return base64.b64decode(value["sqlite_blob_base64"], validate=True)
    except (ValueError, binascii.Error):
        invalid_baseline()


def _report_revisions(archive, name="WorkbenchProductionReportRevisions"):
    sql = {**execution_ledger_objects(), **execution_void_objects()}[name]
    ddl = [row[3] for row in archive["schema"] if type(row) is list and len(row) == 4 and row[0:2] == ["table", name]]
    if len(ddl) != 1 or type(ddl[0]) is not str or _canonical_sql(ddl[0]) != _canonical_sql(sql):
        invalid_baseline()
    # Only the known application DDL is parsed; archived SQL is never executed here.
    columns = ddl_columns(sql, name)
    rows = archive["tables"].get(name)
    if type(rows) is not list or any(type(row) is not list or len(row) != len(columns) for row in rows):
        invalid_baseline()
    return [dict(zip(columns, row)) for row in rows]


def _archived_reports(archive):
    headers = _index(AdmissionBaseline._required(archive, "WorkbenchProductionReports"), "report_ref")
    receipts = _index(AdmissionBaseline._required(archive, "WorkbenchCommandReceipts"), "request_key")
    histories, result = defaultdict(list), defaultdict(list)
    # A historical capture without this table predates explicit withdrawals.
    # Once the table is present its known DDL and every binding are mandatory.
    void_rows = _report_revisions(archive, "WorkbenchProductionReportVoids") if "WorkbenchProductionReportVoids" in archive["tables"] else []
    voids = _index(void_rows, "report_ref")
    if not set(voids) <= set(headers):
        invalid_baseline()
    for row in AdmissionBaseline._required(archive, "WorkbenchProductionReportRevisions"):
        histories[row.get("report_ref")].append(row)
    if set(histories) != set(headers):
        invalid_baseline()
    for ref, header in headers.items():
        history = []
        for ordinal, revision in enumerate(sorted(histories[ref], key=lambda row: row["sequence"]), 1):
            if revision["sequence"] != ordinal:
                invalid_baseline()
            history.append({**header, **{key: value for key, value in revision.items() if key != "recorded_at"},
                            "revision_at": revision["recorded_at"], "values": stored_json(revision["values_json"]),
                            "receipt_ref": receipts.get(revision["request_key"], {}).get("receipt_ref")})
        try:
            if ref in voids:
                if voids[ref]["original_revision_ref"] != history[-1]["revision_ref"]:
                    invalid_baseline()
                continue
            result[header["operation_ref"]].append(report_dto(history))
        except (KeyError, TypeError, ValueError):
            invalid_baseline()
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
