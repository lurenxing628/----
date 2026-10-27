"""Read immutable decision projections without loading their source archives."""

from typing import Any, Dict, List, Literal, Union, overload

from core.models.workbench_run_candidate import MAX_COLLECTION_BYTES, reference
from core.models.workbench_run_history import STATES, TERMINAL_STATES, inconsistent
from core.models.workbench_run_job import PROJECTION_VERSION

from .candidate_values import bounded_size, corrupt, stored_json
from .run_history_projection import failure_reason, job_clocks, job_lifecycle

OPERATION_MEMBERS = frozenset(("operation_refs", "admission_operation_refs", "expected_operation_refs",
    "scheduled_operation_refs", "deferred_operation_refs", "unplanned_operation_refs", "covered_operation_refs"))
BATCH_MEMBERS = frozenset(("batch_refs", "covered_batch_refs", "complete_batch_refs", "incomplete_batch_refs",
    "ordinary_incomplete_batch_refs", "deferred_batch_refs", "unknown_batch_refs", "common_completed_batch_refs"))
_PREPARATION_ALLOCATION_MEMBERS = frozenset(("new_schedule", "retained", "execution", "completed", "external",
                                          "unplanned", "deferred", "unknown"))
ARRANGEMENT_COLUMNS = (
    "row_ref", "operation_ref", "batch_ref", "batch_label", "process_label", "process_type_ref", "process_type_label",
    "start", "end", "machine_resource_index", "operator_resource_index", "supplier_resource_index", "source", "locked", "interval_comparable",
    "event_kind", "occupies_resources", "data_gaps",
)


class Memberships:
    """Known operation/batch fields reference one ordered permanent directory."""

    def __init__(self, value):
        if type(value) is not dict or set(value) != {"operation_refs", "batch_refs", "operation_sets", "batch_sets"}:
            corrupt()
        self.value, self._resolved = value, {}
        for kind in ("operation", "batch"):
            refs, sets = value[kind + "_refs"], value[kind + "_sets"]
            if type(refs) is not list or type(sets) is not list:
                corrupt()
            for ref in refs:
                reference(ref, stored=True)
            if len(set(refs)) != len(refs):
                corrupt()
            for values in sets:
                if type(values) is not list or any(type(index) is not int or not 0 <= index < len(refs) for index in values):
                    corrupt()

    def refs(self, value, kind):
        if type(value) is list:
            return value
        if (type(value) is not dict or set(value) != {"membership_kind", "membership_index"} or
                value["membership_kind"] != kind or type(value["membership_index"]) is not int):
            corrupt()
        index = value["membership_index"]
        sets = self.value[kind + "_sets"]
        if not 0 <= index < len(sets):
            corrupt()
        key = kind, index
        if key not in self._resolved:
            refs = self.value[kind + "_refs"]
            self._resolved[key] = [refs[position] for position in sets[index]]
        return self._resolved[key]

    @overload
    def expand(self, value: Dict[str, Any], *, allocation_coverage: bool = False) -> Dict[str, Any]: ...

    @overload
    def expand(self, value: List[Any], *, allocation_coverage: bool = False) -> List[Any]: ...

    @overload
    def expand(self, value: Any, *, allocation_coverage: bool = False) -> Any: ...

    def expand(self, value: Any, *, allocation_coverage: bool = False) -> Any:
        """Restore only the contract's named membership fields where consumed."""
        if type(value) is list:
            return [self.expand(item) for item in value]
        if type(value) is not dict:
            return value
        result = {}
        for field, item in value.items():
            if allocation_coverage and field in _PREPARATION_ALLOCATION_MEMBERS:
                result[field] = list(self.refs(item, "operation"))
            elif field in OPERATION_MEMBERS and item is not None:
                result[field] = list(self.refs(item, "operation"))
            elif field in BATCH_MEMBERS and item is not None:
                result[field] = list(self.refs(item, "batch"))
            else:
                coverage = field in ("coverage", "allocation_groups") and type(item) is dict and set(item) <= _PREPARATION_ALLOCATION_MEMBERS
                result[field] = self.expand(item, allocation_coverage=coverage)
        return result


def analysis_arrangements(value):
    """Restore the fixed compact analysis rows and their saved resource labels."""
    if (type(value) is not dict or type(value.get("columns")) is not list or
            type(value.get("rows")) is not list or type(value.get("resource_values")) is not list):
        corrupt()
    columns = value["columns"]
    if columns != list(ARRANGEMENT_COLUMNS):
        corrupt()
    result = []
    resources = value["resource_values"]
    for item in resources:
        if (type(item) is not dict or set(item) != {"kind", "ref", "label"} or
                item["kind"] not in ("machine", "operator", "supplier") or
                item["label"] is not None and type(item["label"]) is not str):
            corrupt()
        if item["ref"] is not None:
            reference(item["ref"], stored=True)
    for values in value["rows"]:
        if type(values) is not list or len(values) != len(columns):
            corrupt()
        row = dict(zip(columns, values))
        for field in ("event_kind", "occupies_resources"):
            if row[field] is None:
                del row[field]
        for kind in ("machine", "operator", "supplier"):
            index = row.pop(kind + "_resource_index")
            if index is None:
                row[kind] = None
                continue
            if type(index) is not int or not 0 <= index < len(resources) or resources[index]["kind"] != kind:
                corrupt()
            item = resources[index]
            row[kind] = {"ref": item["ref"], "label": item["label"]}
        result.append(row)
    return result


@overload
def read_model_json(row, column: Literal["scope_json", "header_json"]) -> Dict[str, Any]:
    ...


@overload
def read_model_json(row, column: str) -> Union[Dict[str, Any], List[Any]]:
    ...


def read_model_json(row, column: str) -> Union[Dict[str, Any], List[Any]]:
    """Decode a requested physical JSON column; absent/versioned records fail."""
    if row is None:
        corrupt()
    alias = "scope_version" if column == "scope_json" else "header_version" if column == "header_json" else None
    version = row.get(alias) if alias is not None and alias in row else row.get("projection_version")
    raw = row.get(column)
    if version != PROJECTION_VERSION or type(raw) is not str:
        corrupt()
    bounded_size(len(raw.encode("utf-8")), MAX_COLLECTION_BYTES)
    expected = list if column in ("delivery_json", "delivery_detail_json") else dict
    return stored_json(raw, expected)


def decode_model(row, fields) -> Dict[str, Any]:
    if row is None or row.get("projection_version") != PROJECTION_VERSION:
        corrupt()
    return {field: None if field == "process" and row.get("process_json") is None else
            read_model_json(row, field + "_json") for field in fields}


def _head_candidates(head, admission, header):
    """Lifecycle and permanent manifest checks shared by both public shapes."""
    state, stage = head["state"], head["stage"]
    if state not in STATES or stage not in {
            "queued": ("queued", "awaiting_reconciliation"),
            "running": ("computing", "awaiting_reconciliation")}.get(state, ("finished",)):
        inconsistent()
    started, finished = job_clocks(head)
    job_lifecycle(head, started, finished)
    if type(admission) is not dict or type(admission.get("scope_summary")) is not dict:
        corrupt()
    if state in TERMINAL_STATES:
        if type(header) is not dict or header.get("state") != state or type(header.get("candidates")) is not list:
            corrupt()
        candidates = header["candidates"]
        if header.get("result_persisted") is not (state in ("complete", "partial")):
            corrupt()
    else:
        if header is not None:
            corrupt()
        candidates = []
    seen = set()
    for row in candidates:
        if type(row) is not dict:
            corrupt()
        reference(row.get("candidate_ref"), stored=True)
        count = row.get("task_count")
        if (row["candidate_ref"] in seen or type(count) is not int or count < 0 or
                row.get("status") != "completed"):
            corrupt()
        seen.add(row["candidate_ref"])
    return candidates


def public_run_head(head, admission, header):
    """The directory DTO from validated lifecycle and saved small claims."""
    candidates = _head_candidates(head, admission, header)
    state, stage = head["state"], head["stage"]
    pending = stage == "awaiting_reconciliation"
    result = {"run_ref": head["run_ref"], "state": state, "stage": stage,
        "accepted_at": head["accepted_at"], "started_at": head["started_at"], "finished_at": head["finished_at"],
        "candidate_count": len(candidates), "task_count": sum(row["task_count"] for row in candidates),
        "task_count_basis": "persisted_rows_across_candidates", "counts_final": state in TERMINAL_STATES,
        "scope_summary": admission["scope_summary"], "recovery_required": pending,
        "recovery_reason": {"code": "awaiting_reconciliation", "message": "运行状态待核对，本次读取未恢复或重跑。"} if pending else None,
        "error": failure_reason(head, header), "completion_semantics": "execution_state_only",
        "constraint_verification": "not_checked_by_history", "task_content_verification": "candidate_workspace_required"}
    return result


def public_job_head(head, admission, header):
    """Keep the job status payload's exact shape from its saved small claims."""
    candidates = _head_candidates(head, admission, header)
    scope = {**admission["scope_summary"],
        **{field: admission[field] for field in ("batches", "operation_count", "objective", "objective_label")},
        "data_gaps": admission["workload_data_gaps"]}
    return {"run_ref": head["run_ref"], "job_ref": head["run_ref"], "state": head["state"], "stage": head["stage"],
        "progress": None, "plans": [], "plan_catalog_connected": False,
        "candidates": [{field: candidate[field] for field in ("candidate_ref", "label", "status", "task_count", "selected")}
                       for candidate in candidates],
        "result_persisted": bool(header and header["result_persisted"]), "scope_summary": scope,
        "accepted_at": head["accepted_at"], "started_at": head["started_at"], "finished_at": head["finished_at"],
        "receipt_ref": head.get("receipt_ref"), "error": failure_reason(head, header),
        "recovery_required": head["stage"] == "awaiting_reconciliation"}


def public_job_status(row):
    """Adapt one repository status row for jobs and worker return paths."""
    admission = read_model_json(row, "scope_json")
    header = (read_model_json(row, "header_json")
              if row.get("header_version") is not None or row.get("header_json") is not None else None)
    return public_job_head(row, admission, header)
