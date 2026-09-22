"""Interpret preserved legacy evidence without inventing production reports."""

import math
from collections import defaultdict
from dataclasses import dataclass, field

from core.models.operation_execution_event import (
    OperationExecutionEvent,
    parse_operation_event_time,
    validate_operation_execution_event_sequence,
)

from .quality import gap


@dataclass
class LegacyEvidence:
    starts: list = field(default_factory=list)
    finishes: list = field(default_factory=list)
    state: str = ""
    records: list = field(default_factory=list)
    gaps: list = field(default_factory=list)


def _validate_group(group, now):
    if any(not row["recorded_against_task_ref"] for row in group):
        raise ValueError("unbound legacy task")
    events = [OperationExecutionEvent.from_row(row) for row in group]
    validate_operation_execution_event_sequence(events)
    if any(parse_operation_event_time(row["event_time"]) > now for row in group):
        raise ValueError("future legacy event")


def _public_legacy(row):
    fields = ("event_type", "reported_status", "event_time", "quantity_done", "quantity_scrapped",
              "reason_code", "reason_detail", "severity", "impact_minutes", "handling_status",
              "suggest_reschedule", "remark", "created_by", "created_at")
    unavailable, values = [], {}
    for key in fields:
        value = row[key]
        displayable = value is None or type(value) in (str, int, bool) or (type(value) is float and math.isfinite(value))
        values[key] = value if displayable else None
        if not displayable:
            unavailable.append({"field": key, "storage_type": type(value).__name__})
    return {"legacy_fact_ref": row["legacy_fact_ref"], "operation_ref": row["operation_ref"],
            "recorded_against_task_ref": row["recorded_against_task_ref"],
            "recorded_against_plan_ref": row["recorded_against_plan_ref"],
            **values, "actual_machine_ref": row["actual_machine_ref"], "actual_operator_ref": row["actual_operator_ref"],
            "effective_processing_hours": None, "unavailable_fields": unavailable,
            "created_at_time_basis": "legacy_storage", "created_at_default_basis": "utc"}


def _display_gaps(raw, public):
    result = []
    if public["unavailable_fields"]:
        result.append(gap("legacy_field_not_displayable", "这条旧记录有部分内容的格式无法在界面显示，原值已保留，没有改写。",
                          legacy_fact_ref=public["legacy_fact_ref"], fields=public["unavailable_fields"]))
    missing = []
    for kind in ("machine", "operator"):
        if raw.get("actual_" + kind + "_id") is not None and public["actual_" + kind + "_ref"] is None:
            missing.append("actual_" + kind + "_ref")
    if missing:
        result.append(gap("legacy_resource_identity_unresolved", "这条旧记录里的实际设备或人员对不上现在的资料。筛选需要判断这条记录的实际设备或人员时，系统会停止并提示，避免静默漏掉这条记录；请先核对资料。",
                          legacy_fact_ref=public["legacy_fact_ref"], fields=missing))
    return result


def legacy_evidence(rows, now):
    evidence = LegacyEvidence()
    groups = defaultdict(list)
    for row in rows:
        public = _public_legacy(row)
        evidence.records.append(public)
        evidence.gaps.extend(_display_gaps(row, public))
        groups[(row["schedule_version"], row["schedule_id"], row["op_id"], row["batch_id"])].append(row)
    status = None
    for group in groups.values():
        try:
            _validate_group(group, now)
        except ValueError:
            evidence.gaps.append(gap("invalid_legacy_sequence", "这些旧现场记录的归属、先后顺序或时间不对，系统没有采用它们，请核对原始记录。"))
            continue
        evidence.starts.extend(parse_operation_event_time(row["event_time"]).isoformat(timespec="seconds") for row in group if row["event_type"] == "start")
        evidence.finishes.extend(row for row in group if row["event_type"] == "finish")
        latest = group[-1]
        key = (parse_operation_event_time(latest["event_time"]), latest["id"])
        if status is None or key > status:
            status, evidence.state = key, latest["event_type"]
    return evidence
