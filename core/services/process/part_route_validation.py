from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.models.enums import MergeMode, PartOperationStatus, SourceType

from .route_parser import ParseResult


def build_internal_hours_snapshot(op_repo: Any, part_no: str) -> Dict[int, Tuple[Optional[str], Optional[float], Optional[float]]]:
    snapshot: Dict[int, Tuple[Optional[str], Optional[float], Optional[float]]] = {}
    for op in op_repo.list_by_part(part_no, include_deleted=False):
        if not op.is_internal():
            continue
        snapshot[op.seq] = (op.op_type_id, op.setup_hours, op.unit_hours)
    return snapshot


def save_template_no_tx(
    *,
    op_repo: Any,
    group_repo: Any,
    part_no: str,
    parse_result: ParseResult,
    preserved_internal_hours: Optional[Dict[int, Tuple[Optional[str], Optional[float], Optional[float]]]] = None,
) -> None:
    for op in parse_result.operations:
        if op.source == SourceType.INTERNAL.value:
            _create_internal_operation(
                op_repo=op_repo,
                part_no=part_no,
                op=op,
                preserved_internal_hours=preserved_internal_hours,
            )
            continue
        _create_external_operation(op_repo=op_repo, part_no=part_no, op=op)

    for group in parse_result.external_groups:
        group_repo.create(
            {
                "group_id": group.group_id,
                "part_no": part_no,
                "start_seq": int(group.start_seq),
                "end_seq": int(group.end_seq),
                "merge_mode": MergeMode.SEPARATE.value,
                "total_days": None,
                "supplier_id": _first_supplier_id(group),
                "remark": None,
            }
        )


def _create_internal_operation(
    *,
    op_repo: Any,
    part_no: str,
    op: Any,
    preserved_internal_hours: Optional[Dict[int, Tuple[Optional[str], Optional[float], Optional[float]]]],
) -> None:
    seq = int(op.seq)
    setup_hours = 0.0
    unit_hours = 0.0
    if preserved_internal_hours and seq in preserved_internal_hours:
        old_type, old_setup, old_unit = preserved_internal_hours[seq]
        if old_type == op.op_type_id:
            setup_hours, unit_hours = old_setup, old_unit
        else:
            setup_hours = unit_hours = None
    op_repo.create(
        {
            "part_no": part_no,
            "seq": seq,
            "op_type_id": op.op_type_id,
            "op_type_name": op.op_type_name,
            "source": SourceType.INTERNAL.value,
            "supplier_id": None,
            "ext_days": None,
            "ext_group_id": None,
            "setup_hours": setup_hours,
            "unit_hours": unit_hours,
            "status": PartOperationStatus.ACTIVE.value,
        }
    )


def _create_external_operation(
    *,
    op_repo: Any,
    part_no: str,
    op: Any,
) -> None:
    op_repo.create(
        {
            "part_no": part_no,
            "seq": int(op.seq),
            "op_type_id": op.op_type_id,
            "op_type_name": op.op_type_name,
            "source": SourceType.EXTERNAL.value,
            "supplier_id": op.supplier_id,
            "ext_days": op.default_days,
            "ext_group_id": op.ext_group_id,
            "setup_hours": 0.0,
            "unit_hours": 0.0,
            "status": PartOperationStatus.ACTIVE.value,
        }
    )


def _first_supplier_id(group: Any) -> Optional[str]:
    for op in group.operations:
        if op.supplier_id:
            return op.supplier_id
    return None
