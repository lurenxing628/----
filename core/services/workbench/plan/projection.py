"""Allowlisted plan/task DTOs over self-contained ScheduleHistory and Schedule rows."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.history_documents import HistoryDocuments
from core.services.workbench.facts.zero_duration import point_event_dto
from core.shared.local_datetime import format_local_datetime, parse_local_datetime, us_to_datetime, us_to_iso
from core.shared.strict_parse import wire_int

# A catalog entry's only blocked reason is ``plan_unavailable`` (``plan_catalog_entry``); its exception text stays internal.
_PLAN_UNAVAILABLE_MESSAGE = "这个计划的类型关系或明细无效，暂时看不了。请刷新计划列表后重试。"


def project_plan(entry, plan_ref):
    """``entry.locator.version`` is a ScheduleHistory key: an INTEGER PRIMARY KEY that only ScheduleVersionSeq
    (AUTOINCREMENT) allocates, so it is a positive int."""
    identity = entry.plan_identity
    return {
        "plan_ref": plan_ref,
        "version": wire_int(entry.locator.version),
        "kind": entry.kind,
        "is_current_official": (
            entry.can_view and identity is not None and identity.is_current_executable_official_version
        ),
        "display_name": entry.display_name,
        "completeness": entry.completeness,
        "capabilities": {
            "view": entry.can_view,
            "export": entry.can_view,
            "edit_draft": False,
            "adopt": False,
            "report_actual": False,
        },
        "blocked_reasons": [
            {"code": issue.code, "message": _PLAN_UNAVAILABLE_MESSAGE} for issue in entry.blocked_reasons
        ],
    }


def public_time(value):
    parsed = parse_local_datetime(value)
    if parsed is None:
        raise WorkbenchCommandRejected("plan_unavailable", "工序安排的起止时间无效，请核对计划资料。")
    return format_local_datetime(parsed).replace(" ", "T")


def resource_ref(row, kind, identities):
    key = row[kind + "_id"]
    if key is None or key == "":
        return None
    return identities[kind][str(key)].ref


def build_plan_provenance(history: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "state": "available",
        "reason": None,
        "source_kind": history["source_kind"],
        "source_ref": history["source_ref"],
        "source_label": history["source_label"],
        "run_ref": history["run_ref"],
        "accepted_at": history["accepted_at"],
        "finished_at": history["finished_at"],
        "adopted_at": history["adopted_at"],
        "algorithm": HistoryDocuments(history).algorithm,
        "baseline": {
            "baseline_ref": history["baseline_ref"],
            "version": history["baseline_version"],
            "kind": history["baseline_kind"],
            "captured_at": history["baseline_captured_at"],
            "captured_task_count": history["baseline_captured_task_count"],
        },
    }


def row_resource_entries(rows, resources):
    """Directory entries of current-plan rows: machines and operators under their live names, suppliers under
    the label frozen in the row.

    Master names are not admitted on every write path, so the live name is admitted here, its one read-side check.
    """
    entries = []
    for row in rows:
        for kind in ("machine", "operator"):
            key = row[kind + "_id"]
            if key in (None, ""):
                continue
            identity = resources[kind][str(key)]
            label = row[kind + "_name"]
            if label is not None and (type(label) is not str or not label.strip()):
                raise WorkbenchCommandRejected("plan_unavailable", "设备或人员名称无效，请到资料总览补填。")
            entries.append({"kind": kind, "ref": identity.ref, "business_code": identity.entity_key, "label": label})
        if row["supplier_ref"] is not None:
            entries.append(
                {
                    "kind": "supplier",
                    "ref": row["supplier_ref"],
                    "business_code": row["supplier_id"],
                    "label": row["supplier_label"],
                }
            )
    return entries


def row_frozen_resource_entries(rows):
    entries = []
    for row in rows:
        for kind in ("machine", "operator", "supplier"):
            ref = row[kind + "_ref"]
            if ref is not None:
                entries.append(
                    {
                        "kind": kind,
                        "ref": ref,
                        "business_code": row[kind + "_id"],
                        "label": row[kind + "_label"],
                    }
                )
    return entries


def resource_directory(entries):
    """One entry per resource, ordered by kind and ref. The first entry wins, so callers list the current plan's
    live-named entries before baseline-only frozen ones."""
    directory = {}
    for entry in entries:
        directory.setdefault((entry["kind"], entry["ref"]), entry)
    return [directory[key] for key in sorted(directory)]


def _build_task_dto(
    plan_ref: str,
    row: Mapping[str, Any],
    *,
    machine_ref: Optional[str],
    operator_ref: Optional[str],
) -> Dict[str, Any]:
    task = {
        "task_ref": row["task_ref"],
        "operation_ref": row["operation_ref"],
        "plan_ref": plan_ref,
        "batch_id": row["batch_id"],
        "sequence": wire_int(row["seq"]),
        "process_label": row["op_type_name"],
        "piece_id": row["piece_id"],
        "quantity": row["quantity"],
        "batch_quantity": row["batch_quantity"],
        "quantity_basis": row["quantity_basis"],
        "quantity_reason": row["quantity_reason"],
        "machine_ref": machine_ref,
        "operator_ref": operator_ref,
        "supplier_ref": row["supplier_ref"],
        "start": us_to_iso(row["start_us"]),
        "end": us_to_iso(row["end_us"]),
    }
    if row["is_point_event"]:
        point_dt = us_to_datetime(row["start_us"])
        task.update(point_event_dto(point_dt, point_dt))
    return task


def project_tasks(plan_ref, rows, resources):
    return [
        _build_task_dto(
            plan_ref,
            row,
            machine_ref=resource_ref(row, "machine", resources),
            operator_ref=resource_ref(row, "operator", resources),
        )
        for row in rows
    ]


def project_frozen_tasks(plan_ref, rows):
    return [
        _build_task_dto(
            plan_ref,
            row,
            machine_ref=row["machine_ref"],
            operator_ref=row["operator_ref"],
        )
        for row in rows
    ]
