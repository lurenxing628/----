"""Read immutable decision projections without loading their source archives."""

from collections import defaultdict
from datetime import timedelta
from typing import Any, Dict, List, Literal, Union, overload

from core.models.content import read_stored_json
from core.models.enums import RUN_RESULT_STATE_VALUES, RUN_TERMINAL_STATES, RunStage
from core.models.workbench_run_candidate import MAX_COLLECTION_BYTES, local_time, reference
from core.shared.local_datetime import datetime_to_us
from core.shared.local_datetime import parse_local_datetime as parse_dt

from .candidate_tasks import operation_labels, operation_sequence_value
from .candidate_values import bounded_size, corrupt
from .changeovers import subject_arrangements
from .decision_metrics import RESOURCE_METRICS, metric_value
from .operation_effort_evidence import archived_standard_effort
from .resource_projection import RESOURCE_METRIC_VERSION
from .run_history_projection import failure_reason, job_clocks

OPERATION_MEMBERS = frozenset(("operation_refs", "admission_operation_refs", "expected_operation_refs",
    "scheduled_operation_refs", "deferred_operation_refs", "unplanned_operation_refs", "covered_operation_refs"))
BATCH_MEMBERS = frozenset(("batch_refs", "covered_batch_refs", "complete_batch_refs", "incomplete_batch_refs",
    "ordinary_incomplete_batch_refs", "deferred_batch_refs", "unknown_batch_refs"))
_PREPARATION_ALLOCATION_MEMBERS = frozenset(("new_schedule", "retained", "execution", "completed", "external",
                                          "unplanned", "deferred", "unknown"))
ARRANGEMENT_COLUMNS = (
    "row_ref", "operation_ref", "batch_ref", "batch_label", "process_label", "process_type_ref", "process_type_label",
    "start", "end", "machine_resource_index", "operator_resource_index", "supplier_resource_index", "source", "locked",
    "event_kind", "occupies_resources", "data_gaps",
)
_RESOURCE_FLAGS = {
    "high_pressure_count": "high_pressure",
    "zero_capacity_task_count": "zero_capacity_task",
    "conflict_resource_count": "conflict",
}
_DISPLAY_SEGMENT_FIELDS = (
    "row_ref", "start", "end", "machine", "operator", "supplier",
    "source", "locked", "data_gaps",
)


def resource_metric_known(row: Dict[str, Any], field: str) -> bool:
    if field in _RESOURCE_FLAGS:
        return row[_RESOURCE_FLAGS[field]] is not None
    if field == "unknown_day_resource_count":
        return row["unknown_days"] is not None
    if field == "used_resource_count":
        return row["operation_count"] is not None
    if field == "utilization_ratio":
        return row["available_hours"] is not None and row["occupied_hours"] is not None
    if field == "balance_cv":
        return row["available_hours"] is not None and (row["available_hours"] == 0 or row["occupied_hours"] is not None)
    return row[field] is not None


def build_resource_metrics_from_summaries(summaries, window_rows_by_ref, resources, work_available: bool) -> Dict[str, Any]:
    result = {}
    for kind in ("machine", "operator"):
        summary = summaries[kind]
        total = summary["resource_count"]
        kind_resources = [row for row in resources if row["kind"] == kind]
        for field, _label, _unit, _precision, _improvement, _common in RESOURCE_METRICS:
            value = summary[field]
            missing_work = summary["unknown_workload_count"] > 0 or not work_available
            empty = (
                total == 0 and not missing_work
                or field == "balance_cv" and summary["balance_state"] == "not_applicable"
                or field == "utilization_ratio" and summary["available_hours"] == 0 and not missing_work
            )
            known_refs = [row["ref"] for row in kind_resources if resource_metric_known(window_rows_by_ref[row["ref"]], field)]
            unknown = total - len(known_refs)
            state = "not_applicable" if empty else "complete" if value is not None else "partial" if known_refs else "unavailable"
            if field == "balance_cv":
                state = summary["balance_state"]
            reason = (
                summary["balance_reason"] if field == "balance_cv" else
                {"code": "resource_evidence_incomplete", "message": "归档班表、任务时间或资源身份缺项，显示可核对的已知小计。"}
                if value is None and not empty else
                {"code": "zero_available_capacity", "message": "共同资源窗口内没有正容量，占用率不适用。"}
                if field == "utilization_ratio" and empty else None
            )
            if field == "zero_capacity_task_count" and value is None and any(
                window_rows_by_ref[row["ref"]]["zero_capacity_reason"] is not None for row in kind_resources
            ):
                reason = {"code": "actual_work_fragments_not_recorded", "message": "零容量时段的安排跨度未提供实际工作片段，工作证据未知。"}
            item = metric_value(value, total=total, unknown=unknown, subtotal=summary["known_" + field], state=state,
                                scope="fixed_resource_window", reason=reason, metric_version=RESOURCE_METRIC_VERSION, member_unit=kind)
            item.update(covered_resource_refs=known_refs, issues=summary["issues"],
                        unknown_workload_count=summary["unknown_workload_count"])
            if field == "utilization_ratio":
                item.update(numerator_hours=summary["numerator_hours"], denominator_hours=summary["denominator_hours"])
            result[kind + "_" + field] = item
    return result


def build_changeover_metrics(projected, tasks, operation_refs, task_intervals) -> Dict[str, Any]:
    reason = (
        {"code": "changeover_sequence_incomplete", "message": "部分实际设备序列缺少工种身份、时间或存在重叠，切换统计保留已知小计。"}
        if projected["state"] != "complete" else None
    )
    arrangements = subject_arrangements(tasks, operation_refs, task_intervals=task_intervals)
    covered = sorted({task["operation_ref"] for task in arrangements})
    values = {}
    for name, value, subtotal in (
        ("type_changeover_count", projected["count"], projected["known_count"]),
        ("changed_machine_count", projected["changed_machine_count"], projected["known_changed_machine_count"]),
    ):
        unknown = projected["unknown_count"]
        item = metric_value(value, total=max(len(arrangements), unknown), unknown=unknown, subtotal=subtotal,
                            state=projected["state"], scope="fixed_changeover_window", reason=reason, member_unit="operation")
        item["covered_operation_refs"] = covered
        values[name] = item
    return values


def by_operation(tasks):
    """Each operation's one arranged task: candidate tasks hold ``UNIQUE(candidate_ref, operation_ref)`` and the
    official plan one Schedule row per operation (``idx_schedule_version_op_unique``)."""
    return {task["operation_ref"]: task for task in tasks}


def _task_bounds_us(tasks, intervals):
    spans = [intervals[row["row_ref"]] for row in tasks]
    low, high = min(pair[0] for pair in spans), max(pair[1] for pair in spans)
    if any(pair[0] == pair[1] == high for pair in spans):
        high += timedelta(microseconds=1)
    return [datetime_to_us(low), datetime_to_us(high)]


def _resource_diff_token(seg: Dict[str, Any], kind: str):
    res = seg[kind]
    if (res is not None and res["ref"] is None) or any(
        gap["field"] in (kind, kind + ".ref") for gap in seg["data_gaps"]
    ):
        return None
    return "" if res is None else res["ref"]


def build_operation_catalog_rows(facts, refs, disposition) -> List[Dict[str, Any]]:
    rows = []
    for ref in sorted(refs):
        labels, operation = operation_labels(facts, ref)
        seq_val = operation_sequence_value(labels["sequence"])
        saved_id = operation["machine_id"]
        saved_ref = facts.entity_ref("machine", saved_id) if saved_id is not None else None
        saved_machine = (
            {"ref": saved_ref, "label": facts.related("Machines", saved_id)["name"]}
            if saved_id is not None else None
        )
        execution = facts.execution[ref]
        disp = disposition[ref]
        label_dict = {
            "operation_ref": ref,
            "batch_ref": labels["batch_ref"],
            "batch_label": labels["batch_label"],
            "part_label": labels["part_label"],
            "sequence": labels["sequence"],
            "process_label": labels["process_label"],
            "piece_id": labels["piece_id"],
            "quantity": labels["quantity"],
            "data_gaps": labels["data_gaps"],
            "saved_machine": saved_machine,
            "effort": archived_standard_effort(operation, execution),
            "disposition": {"status": disp["status"], "issues": disp["issues"]},
            "execution_constraints": {
                key: execution.get(key)
                for key in ("execution_state", "known_completed_quantity", "remaining_quantity",
                            "data_quality", "first_actual_start", "confirmed_finish")
            },
        }
        rows.append({
            "operation_ref": ref,
            "batch_ref": labels["batch_ref"],
            "batch_label": labels["batch_label"],
            "sequence": seq_val,
            "sequence_unknown": 1 if seq_val is None else 0,
            "op_id": facts.operations[ref],
            "saved_machine_ref": saved_ref,
            "label": label_dict,
        })
    return rows


def build_side_batch_rows(side_key: str, batch_refs, scope_op_refs, delivery_items, tasks, intervals) -> List[Dict[str, Any]]:
    delivery_by_ref = {row["batch_ref"]: row for row in delivery_items}
    tasks_by_batch = defaultdict(list)
    for task in tasks:
        if task["operation_ref"] in scope_op_refs:
            tasks_by_batch[task["batch_ref"]].append(task)
    rows = []
    for ref in batch_refs:
        item = delivery_by_ref[ref]
        batch_tasks = tasks_by_batch[ref]
        finish_time = item["planned_finish"]
        finish_dt = parse_dt(finish_time) if finish_time is not None else None
        finish_us = datetime_to_us(finish_dt) if finish_dt is not None else None
        is_overdue = None if item["is_overdue"] is None else (1 if item["is_overdue"] else 0)
        rows.append({
            "side_key": side_key,
            "batch_ref": ref,
            "batch_label": item["batch_id"],
            "due_date": item["due_date"],
            "is_overdue": is_overdue,
            "delay_hours": item["delay_hours"],
            "finish_time": finish_time,
            "finish_us": finish_us,
            "status": item["completion_state"],
            "scheduled_count": item["scheduled_operation_count"] or 0,
            "total_count": item["operation_count"] or 0,
            "deferred_count": item["deferred_operation_count"] or 0,
            "unplanned_count": item["ordinary_unscheduled_operation_count"] or 0,
            "detail": {
                "delivery": item,
                "task_bounds_us": _task_bounds_us(batch_tasks, intervals) if batch_tasks else None,
            },
        })
    return rows


def build_side_operation_rows(side_key: str, refs, arrangements, intervals, prep_rows,
                              deferred_refs, remaining_refs) -> List[Dict[str, Any]]:
    """``arrangements`` maps each operation to its one arranged task (``by_operation``)."""
    prep_by_ref = {row["operation_ref"]: row for row in prep_rows}
    rows = []
    for ref in sorted(refs):
        task = arrangements.get(ref)
        prep = prep_by_ref[ref]
        if task is not None:
            seg = {**{k: task[k] for k in _DISPLAY_SEGMENT_FIELDS},
                   **{k: task[k] for k in ("event_kind", "occupies_resources") if k in task}}
            span = intervals[seg["row_ref"]]
            start_us, end_us = datetime_to_us(span[0]), datetime_to_us(span[1])
            machine_ref = seg["machine"]["ref"] if seg["machine"] is not None else None
            operator_ref = seg["operator"]["ref"] if seg["operator"] is not None else None
            res_refs = sorted({value for value in (machine_ref, operator_ref) if value is not None})
            arrangement = {"segment": seg, "bounds_us": _task_bounds_us([task], intervals),
                           "m_tok": _resource_diff_token(seg, "machine"), "o_tok": _resource_diff_token(seg, "operator"),
                           "s_tok": _resource_diff_token(seg, "supplier"), "src": seg["source"]}
        else:
            start_us = end_us = machine_ref = operator_ref = arrangement = None
            res_refs = []
        rows.append({
            "side_key": side_key,
            "operation_ref": ref,
            "arranged": 1 if task is not None else 0,
            "deferred": 1 if ref in deferred_refs else 0,
            "allocation_state": prep["allocation_state"],
            "is_remaining": 1 if ref in remaining_refs else 0,
            "start_us": start_us,
            "end_us": end_us,
            "machine_ref": machine_ref,
            "operator_ref": operator_ref,
            "resource_refs": res_refs,
            "setup_hours": prep["setup_standard_hours"],
            "required_hours": prep["required_standard_hours"],
            "arrangement": arrangement,
            "preparation": {k: v for k, v in prep.items() if k not in ("operation_ref", "arranged")},
        })
    return rows


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
                result[field] = self.refs(item, "operation")
            elif field in OPERATION_MEMBERS and item is not None:
                result[field] = self.refs(item, "operation")
            elif field in BATCH_MEMBERS and item is not None:
                result[field] = self.refs(item, "batch")
            else:
                coverage = field == "coverage" and type(item) is dict and set(item) <= _PREPARATION_ALLOCATION_MEMBERS
                result[field] = self.expand(item, allocation_coverage=coverage)
        return result


def analysis_arrangements(value):
    """Restore the fixed compact analysis rows, their saved resource labels and each row's interval.

    The rows are a projection of admitted tasks (candidate store rows or the admission's Schedule copy), so
    their saved instants convert directly, once per read.
    """
    if (type(value) is not dict or type(value.get("columns")) is not list or
            type(value.get("rows")) is not list or type(value.get("resource_values")) is not list):
        corrupt()
    columns = value["columns"]
    if columns != list(ARRANGEMENT_COLUMNS):
        corrupt()
    result, intervals = [], {}
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
        intervals[row["row_ref"]] = local_time(row["start"]), local_time(row["end"])
    return result, intervals


@overload
def read_model_json(row, column: Literal["scope_json", "header_json"]) -> Dict[str, Any]:
    ...


@overload
def read_model_json(row, column: str) -> Union[Dict[str, Any], List[Any]]:
    ...


def read_model_json(row, column: str) -> Union[Dict[str, Any], List[Any]]:
    """Decode a requested physical JSON column; an absent record or column value fails."""
    if row is None:
        corrupt()
    raw = row[column]
    if type(raw) is not str:
        corrupt()
    bounded_size(len(raw.encode("utf-8")), MAX_COLLECTION_BYTES)
    return read_stored_json(raw, list if column in ("delivery_json", "delivery_detail_json") else dict)


def decode_model(row, fields) -> Dict[str, Any]:
    return {field: read_model_json(row, field + "_json") for field in fields}


def _head_candidates(head, admission, header):
    """Lifecycle and permanent manifest checks shared by both public shapes."""
    # 状态与阶段的值域和对应关系、各状态下执行者与开始、结束时间是否齐全，由 WorkbenchRunJobs 的 CHECK 保证；
    # 这里只解析保存的时刻并核对先后。
    state = head["state"]
    job_clocks(head)
    if type(admission) is not dict or type(admission.get("scope_summary")) is not dict:
        corrupt()
    if state in RUN_TERMINAL_STATES:
        if type(header) is not dict or header.get("state") != state or type(header.get("candidates")) is not list:
            corrupt()
        candidates = header["candidates"]
        if header.get("result_persisted") is not (state in RUN_RESULT_STATE_VALUES):
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
        if row["candidate_ref"] in seen or type(count) is not int or count < 0:
            corrupt()
        seen.add(row["candidate_ref"])
    return candidates


def public_run_head(head, admission, header):
    """The directory DTO from validated lifecycle and saved small claims."""
    candidates = _head_candidates(head, admission, header)
    state, stage = head["state"], head["stage"]
    pending = stage == RunStage.AWAITING_RECONCILIATION.value
    return {"run_ref": head["run_ref"], "state": state, "stage": stage,
        "accepted_at": head["accepted_at"], "started_at": head["started_at"], "finished_at": head["finished_at"],
        "candidate_count": len(candidates), "task_count": sum(row["task_count"] for row in candidates),
        "task_count_basis": "persisted_rows_across_candidates", "counts_final": state in RUN_TERMINAL_STATES,
        "scope_summary": admission["scope_summary"], "recovery_required": pending,
        "recovery_reason": {"code": "awaiting_reconciliation", "message": "运行状态待核对，本次读取未恢复或重跑。"} if pending else None,
        "error": failure_reason(head, header)}


def public_job_head(head, admission, header):
    """Keep the job status payload's exact shape from its saved small claims."""
    candidates = _head_candidates(head, admission, header)
    scope = {**admission["scope_summary"],
        **{field: admission[field] for field in ("batches", "operation_count", "objective", "objective_label")},
        "data_gaps": admission["workload_data_gaps"]}
    return {"run_ref": head["run_ref"], "job_ref": head["run_ref"], "state": head["state"], "stage": head["stage"],
        "progress": None, "plans": [], "plan_catalog_connected": False,
        "candidates": [{field: candidate[field] for field in ("candidate_ref", "label", "task_count", "selected")}
                       for candidate in candidates],
        "result_persisted": bool(header and header["result_persisted"]), "scope_summary": scope,
        "accepted_at": head["accepted_at"], "started_at": head["started_at"], "finished_at": head["finished_at"],
        "receipt_ref": head.get("receipt_ref"), "error": failure_reason(head, header),
        "recovery_required": head["stage"] == RunStage.AWAITING_RECONCILIATION.value}


def public_job_status(row):
    """Adapt one repository status row for jobs and worker return paths."""
    admission = read_model_json(row, "scope_json")
    header = read_model_json(row, "header_json") if row["header_json"] is not None else None
    return public_job_head(row, admission, header)
