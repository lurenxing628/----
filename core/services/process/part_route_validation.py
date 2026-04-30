from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.infrastructure.errors import ValidationError
from core.models.enums import MergeMode, PartOperationStatus, SourceType
from core.services.common.normalize import normalize_text
from core.services.common.safe_logging import safe_warning

from .route_parser import ParseResult, ParseStatus


def build_internal_hours_snapshot(op_repo: Any, part_no: str) -> Dict[int, Tuple[float, float]]:
    snapshot: Dict[int, Tuple[float, float]] = {}
    for op in op_repo.list_by_part(part_no, include_deleted=False):
        if not op.is_internal():
            continue
        try:
            seq = int(op.seq)
        except Exception:
            continue
        snapshot[seq] = (float(op.setup_hours or 0.0), float(op.unit_hours or 0.0))
    return snapshot


def coerce_external_default_days(
    op: Any,
    *,
    logger: Any = None,
    warnings: Optional[List[str]] = None,
) -> Tuple[float, bool]:
    raw_default_days = getattr(op, "default_days", None)
    seq = int(getattr(op, "seq", 0) or 0)
    op_type_name = normalize_text(getattr(op, "op_type_name", None)) or f"seq={seq}"

    def _warn(message: str) -> None:
        if warnings is not None:
            warnings.append(message)
        safe_warning(logger, message)

    if raw_default_days is None or (isinstance(raw_default_days, str) and raw_default_days.strip() == ""):
        _warn(f"外部工序 {seq}（{op_type_name}）缺少默认周期，保存模板时已按 1.0 天写入外协周期")
        return 1.0, True

    try:
        parsed_days = float(raw_default_days)
    except Exception:
        _warn(f"外部工序 {seq}（{op_type_name}）默认周期无法解析，保存模板时已按 1.0 天写入外协周期")
        return 1.0, True

    if not math.isfinite(parsed_days) or parsed_days <= 0:
        _warn(f"外部工序 {seq}（{op_type_name}）默认周期无效，保存模板时已按 1.0 天写入外协周期")
        return 1.0, True

    return float(parsed_days), False


def operation_source_or_raise(op: Any) -> str:
    source = str(getattr(op, "source", "") or "").strip().lower()
    if source in (SourceType.INTERNAL.value, SourceType.EXTERNAL.value):
        return source

    seq = getattr(op, "seq", None)
    seq_label = f"工序 {seq}" if seq not in (None, "") else "工序"
    raise ValidationError(f"{seq_label}来源无效，只能是 internal 或 external", field="source")


def save_template_no_tx(
    *,
    op_repo: Any,
    group_repo: Any,
    logger: Any,
    part_no: str,
    parse_result: ParseResult,
    preserved_internal_hours: Optional[Dict[int, Tuple[float, float]]] = None,
) -> None:
    for op in parse_result.operations:
        source = operation_source_or_raise(op)
        if source == SourceType.INTERNAL.value:
            _create_internal_operation(
                op_repo=op_repo,
                part_no=part_no,
                op=op,
                preserved_internal_hours=preserved_internal_hours,
            )
            continue
        _create_external_operation(op_repo=op_repo, logger=logger, part_no=part_no, op=op, parse_result=parse_result)

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


def build_route_parse_baseline_snapshot(
    *,
    part_nos: List[str],
    parts_cache: Optional[Dict[str, Any]],
    list_parts: Callable[[], List[Any]],
    parse_route: Callable[[Any, str], ParseResult],
) -> List[Dict[str, Any]]:
    if not part_nos:
        return []

    cache = parts_cache if isinstance(parts_cache, dict) else {part.part_no: part for part in list_parts()}
    snapshot: List[Dict[str, Any]] = []
    for raw_part_no in part_nos:
        part_no = normalize_text(raw_part_no)
        if not part_no:
            continue
        part = cache.get(part_no)
        route_raw = getattr(part, "route_raw", None) if part is not None else None
        snapshot.append(_build_route_parse_baseline_entry(part_no=part_no, route_raw=route_raw, parse_route=parse_route))
    return snapshot


def _create_internal_operation(
    *,
    op_repo: Any,
    part_no: str,
    op: Any,
    preserved_internal_hours: Optional[Dict[int, Tuple[float, float]]],
) -> None:
    seq = int(op.seq)
    setup_hours = 0.0
    unit_hours = 0.0
    if preserved_internal_hours and seq in preserved_internal_hours:
        old_setup, old_unit = preserved_internal_hours.get(seq, (0.0, 0.0))
        setup_hours = float(old_setup or 0.0)
        unit_hours = float(old_unit or 0.0)
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
    logger: Any,
    part_no: str,
    op: Any,
    parse_result: ParseResult,
) -> None:
    ext_days, used_fallback = coerce_external_default_days(op, logger=logger, warnings=parse_result.warnings)
    if used_fallback and parse_result.status != ParseStatus.FAILED:
        parse_result.status = ParseStatus.PARTIAL
    op_repo.create(
        {
            "part_no": part_no,
            "seq": int(op.seq),
            "op_type_id": op.op_type_id,
            "op_type_name": op.op_type_name,
            "source": SourceType.EXTERNAL.value,
            "supplier_id": op.supplier_id,
            "ext_days": float(ext_days),
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


def _build_route_parse_baseline_entry(
    *,
    part_no: str,
    route_raw: Any,
    parse_route: Callable[[Any, str], ParseResult],
) -> Dict[str, Any]:
    parse_result = parse_route(route_raw, part_no)
    route_op_types: List[Dict[str, Any]] = []
    suppliers: List[Dict[str, Any]] = []
    seen_op_type_names = set()
    seen_supplier_names = set()
    for op in list(getattr(parse_result, "operations", None) or []):
        operation_snapshot = _build_route_parse_operation_snapshot(op)
        if operation_snapshot is None:
            continue
        op_type_name = str(operation_snapshot["name"])
        if op_type_name not in seen_op_type_names:
            seen_op_type_names.add(op_type_name)
            route_op_types.append(operation_snapshot)
        supplier_snapshot = _build_route_parse_supplier_snapshot(
            op,
            source=operation_snapshot.get("source"),
            op_type_name=op_type_name,
        )
        if supplier_snapshot is None or op_type_name in seen_supplier_names:
            continue
        seen_supplier_names.add(op_type_name)
        suppliers.append(supplier_snapshot)
    return {"part_no": part_no, "route_op_types": route_op_types, "suppliers": suppliers}


def _build_route_parse_operation_snapshot(op: Any) -> Optional[Dict[str, Any]]:
    op_type_name = normalize_text(getattr(op, "op_type_name", None))
    if not op_type_name:
        return None
    source = (normalize_text(getattr(op, "source", None)) or "").strip().lower() or None
    return {
        "name": op_type_name,
        "matched_op_type_id": normalize_text(getattr(op, "op_type_id", None)),
        "source": source,
    }


def _build_route_parse_supplier_snapshot(
    op: Any,
    *,
    source: Optional[str],
    op_type_name: str,
) -> Optional[Dict[str, Any]]:
    supplier_id = normalize_text(getattr(op, "supplier_id", None))
    if source != SourceType.EXTERNAL.value or not supplier_id:
        return None
    return {
        "supplier_id": supplier_id,
        "op_type_id": normalize_text(getattr(op, "op_type_id", None)),
        "op_type_name": op_type_name,
        "default_days": getattr(op, "default_days", None),
    }
