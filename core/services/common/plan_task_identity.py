from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Sequence

_TASK_ID_READABLE_RE = re.compile(r"[^0-9A-Za-z_-]+")


def _text(value: Any) -> str:
    return str(value or "").strip()


def row_identity(row: Mapping[str, Any]) -> str:
    schedule_id = row.get("schedule_id")
    if schedule_id is not None:
        return f"schedule:{schedule_id}"
    op_id = row.get("op_id")
    if op_id is not None:
        return ":".join(
            (
                "op",
                _text(op_id),
                _text(row.get("start_time")),
                _text(row.get("end_time")),
                *_resource_identity_parts(row),
            )
        )
    parts = [
        _text(row.get("op_code")),
        _text(row.get("batch_id")),
        _text(row.get("piece_id")),
        _text(row.get("seq")),
        _text(row.get("start_time")),
        _text(row.get("end_time")),
        *_resource_identity_parts(row),
    ]
    return "public:" + "|".join(parts)


def _safe_task_id_readable_part(parts: Sequence[str]) -> str:
    readable = next((part for part in parts[:4] if part), "task")
    safe = _TASK_ID_READABLE_RE.sub("_", readable).strip("_")
    return safe or "task"


def _resource_identity_parts(normalized: Mapping[str, Any]) -> Sequence[str]:
    machine_id = _text(normalized.get("machine_id"))
    operator_id = _text(normalized.get("operator_id"))
    if machine_id or operator_id:
        return (machine_id, operator_id)
    current_id = _text(normalized.get("current_resource_id"))
    counterpart_id = _text(normalized.get("counterpart_resource_id"))
    if current_id and counterpart_id:
        return tuple(sorted((current_id, counterpart_id)))
    return (current_id, counterpart_id)


def public_task_id(normalized: Mapping[str, Any]) -> str:
    """Read an assigned public identity; never derive one from a hidden row ID."""
    for key in ("task_id", "public_task_id"):
        value = normalized.get(key)
        if type(value) is str and value:
            return value
    task_ref = normalized.get("task_ref")
    if type(task_ref) is str and task_ref:
        return "task_" + task_ref
    raise ValueError("Plan task identity is missing; load the complete original plan before filtering")


def _plan_label(identity: Mapping[str, Any]) -> str:
    plan_ref = identity.get("plan_ref")
    if type(plan_ref) is str and plan_ref:
        return plan_ref
    version, role = identity.get("version"), identity.get("effective_plan_role")
    if type(version) is not int or version <= 0 or type(role) is not str or not role:
        raise ValueError("Original plan version and role are required for legacy task identities")
    label = f"v{version}_{role}"
    scenario = identity.get("scenario_id")
    if scenario is not None:
        if type(scenario) is not str or not scenario:
            raise ValueError("Original scenario identity is invalid")
        label += "_" + scenario
    if re.fullmatch(r"[0-9A-Za-z_-]+", label) is None:
        raise ValueError("Original plan identity contains unsupported separators")
    return label


def assign_task_ids(rows: Sequence[Mapping[str, Any]], *, plan_identity: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Assign over the full saved source; filters retain the resulting IDs.

    Internal row identities only establish a stable ordering and source lookup.
    Public IDs use permanent references, or an actual legacy plan and row ordinal.
    Existing issued public IDs remain unchanged.
    """
    result = [dict(row) for row in rows]
    keys = [row_identity(row) for row in result]
    if len(set(keys)) != len(keys):
        raise ValueError("The complete plan contains ambiguous task row identities")
    ordinals = {key: index for index, key in enumerate(sorted(keys), start=1)}
    plan_label = None
    for row, key in zip(result, keys):
        for field in ("op_code", "batch_id", "piece_id"):
            _text(row.get(field)).encode("utf-8")
        if any(type(row.get(field)) is str and row[field] for field in ("task_id", "public_task_id", "task_ref")):
            row["task_id"] = public_task_id(row)
            continue
        if plan_label is None:
            plan_label = _plan_label(plan_identity)
        parts = [_text(row.get(field)) for field in ("op_code", "batch_id", "piece_id", "seq")]
        row["task_id"] = f"task_{_safe_task_id_readable_part(parts)}_{plan_label}_r{ordinals[key]}"
    return result
