"""Inline process confirmations and shared invalidation primitives."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from core.errors import BusinessError, ErrorCode, ValidationError
from core.shared.strict_parse import is_stored_number
from data.repositories.part_operation_repo import PartOperationRepository
from data.repositories.part_repo import PartRepository

from .template_source import TemplateSourceFacts

_STAGES = ("route", "source", "hours")


def _require_transaction(conn: sqlite3.Connection) -> None:
    if not conn.in_transaction:
        raise RuntimeError("Process confirmations require a caller transaction.")


def project_part_workflow(part_row: Mapping[str, Any], has_active_operations: bool) -> Dict[str, Any]:
    origin = part_row["workflow_origin"]
    route_at = part_row["route_confirmed_at"]
    source_at = part_row["source_confirmed_at"]
    hours_at = part_row["hours_confirmed_at"]
    route_unlocked = bool(route_at) or (origin == "legacy" and has_active_operations)
    route_state = (
        "confirmed"
        if route_at
        else "missing"
        if not has_active_operations
        else "present"
        if origin == "legacy"
        else "unconfirmed"
    )
    source_state = "confirmed" if source_at else "unconfirmed" if route_unlocked else "locked"
    hours_state = "confirmed" if hours_at else "unconfirmed" if source_at else "locked"
    stage = (
        "ready"
        if hours_at
        else "hours"
        if source_at
        else "source"
        if route_unlocked
        else "route"
    )
    return {
        "origin": origin,
        "stage": stage,
        "ready": stage == "ready",
        "route": {"state": route_state, "confirmed_at": route_at, "confirmed_by": None},
        "source": {"state": source_state, "confirmed_at": source_at, "confirmed_by": None},
        "hours": {"state": hours_state, "confirmed_at": hours_at, "confirmed_by": None},
    }


def project_operation_confirmation(op_row: Mapping[str, Any]) -> Dict[str, Any]:
    source_at = op_row["source_confirmed_at"]
    hours_at = op_row["hours_confirmed_at"]
    return {
        "source": {
            "state": "confirmed" if source_at else "unconfirmed",
            "confirmed_at": source_at,
            "confirmed_by": None,
        },
        "hours": {
            "state": "confirmed" if hours_at else "unconfirmed",
            "confirmed_at": hours_at,
            "confirmed_by": None,
        },
    }


def _part_with_ref(part_repo: PartRepository, part_no: str) -> Dict[str, Any]:
    part = part_repo.part_with_ref(part_no)
    if part is None:
        raise BusinessError(ErrorCode.PART_NOT_FOUND, "零件不存在。")
    if part["ref"] is None:
        raise RuntimeError("Missing process workflow entity identity; no metadata was repaired.")
    return part


def _valid_route_operation(op: Mapping[str, Any]) -> bool:
    return (
        type(op["seq"]) is int
        and op["seq"] > 0
        and isinstance(op["op_type_name"], str)
        and bool(op["op_type_name"].strip())
    )


def _valid_hours(op: Mapping[str, Any], group: Optional[Mapping[str, Any]]) -> bool:
    if op["source"] == "internal":
        return is_stored_number(op["setup_hours"]) and is_stored_number(op["unit_hours"])
    # 外协周期的值域由表约束保证，有值即可用。
    if group and group["merge_mode"] == "merged":
        return group["total_days"] is not None
    return op["ext_days"] is not None


def _load_related_groups(
    op_repo: PartOperationRepository, part_no: str, part_ops: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    group_ids = {op["ext_group_id"] for op in part_ops if op["ext_group_id"] is not None}
    group_ids.update(op_repo.part_external_group_ids(part_no))
    if not group_ids:
        return [], list(part_ops)
    group_json = json.dumps(sorted(group_ids))
    groups = op_repo.external_groups_by_ids(group_json)
    cross_ops = op_repo.cross_part_group_operations(part_no, group_json)
    return groups, list(part_ops) + cross_ops


def _load_supplier_catalog(
    op_repo: PartOperationRepository, all_ops: List[Dict[str, Any]], groups: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    supplier_ids = sorted(
        {row["supplier_id"] for rows in (all_ops, groups) for row in rows if row["supplier_id"] is not None}
    )
    if not supplier_ids:
        return [], []
    return op_repo.supplier_confirmation_catalog(json.dumps(supplier_ids))


def _load_part_confirmation_facts(
    op_repo: PartOperationRepository, part_no: str, *, need_source: bool
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]], Optional[TemplateSourceFacts]]:
    part_ops = op_repo.active_confirmation_operations(part_no)
    if not need_source or not part_ops:
        return part_ops, {}, None
    groups, all_ops = _load_related_groups(op_repo, part_no, part_ops)
    suppliers, capabilities = _load_supplier_catalog(op_repo, all_ops, groups)
    groups_by_id = {group["group_id"]: group for group in groups}
    source_facts = TemplateSourceFacts(all_ops, groups, suppliers, capabilities, suppliers)
    return part_ops, groups_by_id, source_facts


def _validate_stage_ready(
    stage: str,
    view: Mapping[str, Any],
    part_ops: List[Dict[str, Any]],
    groups_by_id: Mapping[str, Mapping[str, Any]],
    source_facts: Optional[TemplateSourceFacts],
) -> None:
    previous = {"source": "route", "hours": "source"}.get(stage)
    if previous and view[previous]["state"] != "confirmed":
        raise ValidationError("请先确认上一工艺阶段的当前资料。", field="stage", details={"reason": "process_stage_locked"})
    if stage == "hours" and any(op["source_confirmed_at"] is None for op in part_ops):
        raise ValidationError("请先确认上一工艺阶段的当前资料。", field="stage", details={"reason": "process_stage_locked"})
    if not part_ops or not all(_valid_route_operation(op) for op in part_ops):
        raise ValidationError("当前工艺资料不完整或不合法，不能确认。", field=stage, details={"reason": "process_facts_invalid"})
    if source_facts is not None and any(
        source_facts.issues(op, type_name=op["type_name"], category=op["category"]) for op in part_ops
    ):
        raise ValidationError("当前工艺资料不完整或不合法，不能确认。", field=stage, details={"reason": "process_facts_invalid"})
    if stage == "hours" and not all(_valid_hours(op, groups_by_id.get(op["ext_group_id"])) for op in part_ops):
        raise ValidationError("当前工艺资料不完整或不合法，不能确认。", field=stage, details={"reason": "process_facts_invalid"})


def _stamp_stage_confirmation(
    part_repo: PartRepository, op_repo: PartOperationRepository, part: Mapping[str, Any], stage: str, stamp: str
) -> None:
    part_no = part["part_no"]
    if stage == "route":
        if part["workflow_origin"] != "managed" or part["route_confirmed_at"] is None:
            part_repo.set_stage_confirmed_at(part_no, "route", stamp)
        return
    op_repo.set_stage_confirmed_at(part_no, stage, stamp)
    if part[stage + "_confirmed_at"] is None:
        part_repo.set_stage_confirmed_at(part_no, stage, stamp)


def confirmation_stamp(now: datetime) -> str:
    """工艺确认列的存储文本：应用墙钟给出的工厂本地时刻换算成 UTC，精确到微秒，以 ``Z`` 结尾。

    命令在真正落时的那一刻从应用墙钟取一次时间，立即换算；同一命令里确认的每一项共用这个结果。
    """
    return now.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def record_confirmation(conn: sqlite3.Connection, part_no: str, stage: str, *, confirmed_at: str) -> str:
    """Validate current domain facts and stamp inline confirmation columns in caller transaction."""
    _require_transaction(conn)
    if stage not in _STAGES:
        raise ValidationError("工艺确认阶段无效。", field="stage")
    part_repo = PartRepository(conn)
    op_repo = PartOperationRepository(conn)
    part = _part_with_ref(part_repo, part_no)
    part_ops, groups_by_id, source_facts = _load_part_confirmation_facts(
        op_repo, part_no, need_source=stage in ("source", "hours")
    )
    view = project_part_workflow(part, bool(part_ops))
    _validate_stage_ready(stage, view, part_ops, groups_by_id, source_facts)
    _stamp_stage_confirmation(part_repo, op_repo, part, stage, confirmed_at)
    return part["ref"]


def reset_part_confirmations_from(conn: sqlite3.Connection, part_no: str, stage: str) -> None:
    _require_transaction(conn)
    PartRepository(conn).reset_confirmations_from(part_no, stage)


def reset_group_hours_confirmations(conn: sqlite3.Connection, group_ids: Iterable[str]) -> None:
    _require_transaction(conn)
    keys = sorted(set(group_ids))
    if not keys:
        return
    PartOperationRepository(conn).reset_group_hours_confirmations(json.dumps(keys))


def invalidate_op_type_confirmations(conn: sqlite3.Connection, op_type_id: str) -> None:
    _require_transaction(conn)
    PartOperationRepository(conn).invalidate_op_type_confirmations(op_type_id)


def invalidate_supplier_confirmations(
    conn: sqlite3.Connection,
    supplier_id: str,
    *,
    became_unavailable: bool,
    removed_op_types: Iterable[str],
) -> None:
    _require_transaction(conn)
    removed = sorted(set(removed_op_types))
    if not became_unavailable and not removed:
        return
    PartOperationRepository(conn).invalidate_supplier_confirmations(
        supplier_id,
        became_unavailable=became_unavailable,
        removed_op_types_json=json.dumps(removed) if removed else None,
    )
