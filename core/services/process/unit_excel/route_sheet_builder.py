from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Sequence, Set

from core.models.enums import SourceType, SupplierStatus
from core.services.common.degradation import DegradationCollector

from .template_validation import record_diagnostic


def build_op_types_rows(op_records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    op_type_states: Dict[str, Set[str]] = defaultdict(set)
    for rec in op_records:
        nm = str(rec.get("final_name") or "")
        st = SourceType.INTERNAL.value if rec.get("source_internal") else SourceType.EXTERNAL.value
        op_type_states[nm].add(st)

    op_types_rows: List[Dict[str, Any]] = []
    for idx, op_name in enumerate(sorted(op_type_states.keys()), start=1):
        cat = SourceType.INTERNAL.value if SourceType.INTERNAL.value in op_type_states[op_name] else SourceType.EXTERNAL.value
        op_types_rows.append({"工种ID": f"OT{idx:03d}", "工种名称": op_name, "归属": cat})
    return op_types_rows


def build_suppliers_rows(
    op_records: Sequence[Dict[str, Any]],
    op_types_rows: Sequence[Dict[str, Any]],
    *,
    collector: DegradationCollector,
    samples: Dict[str, List[Any]],
) -> List[Dict[str, Any]]:
    external_days_by_name = _external_days_by_name(op_records)
    external_names = _external_op_type_names(op_types_rows)
    return [
        _supplier_row(idx, op_name, external_days_by_name.get(op_name) or [], collector=collector, samples=samples)
        for idx, op_name in enumerate(sorted(external_names), start=1)
    ]


def _external_days_by_name(op_records: Sequence[Dict[str, Any]]) -> Dict[str, List[float]]:
    external_days_by_name: Dict[str, List[float]] = defaultdict(list)
    for rec in op_records:
        if rec.get("source_internal"):
            continue
        name = str(rec.get("final_name") or "")
        hint = rec.get("ext_days_hint")
        if isinstance(hint, (int, float)) and float(hint) > 0:
            external_days_by_name[name].append(float(hint))
    return external_days_by_name


def _external_op_type_names(op_types_rows: Sequence[Dict[str, Any]]) -> List[str]:
    return [
        str(r.get("工种名称") or "")
        for r in op_types_rows
        if str(r.get("归属") or "").strip() == SourceType.EXTERNAL.value and str(r.get("工种名称") or "")
    ]


def _supplier_row(
    idx: int,
    op_name: str,
    days_list: Sequence[float],
    *,
    collector: DegradationCollector,
    samples: Dict[str, List[Any]],
) -> Dict[str, Any]:
    default_days = _supplier_default_days(op_name, days_list, collector=collector, samples=samples)
    _record_supplier_defaults(op_name, collector=collector, samples=samples)
    return {
        "供应商ID": f"S{idx:03d}",
        "名称": f"外协-{op_name}",
        "对应工种": op_name,
        "默认周期": default_days,
        "状态": SupplierStatus.ACTIVE.value,
        "备注": None,
    }


def _supplier_default_days(
    op_name: str,
    days_list: Sequence[float],
    *,
    collector: DegradationCollector,
    samples: Dict[str, List[Any]],
) -> float:
    if days_list:
        return round(sum(days_list) / len(days_list), 4)
    record_diagnostic(
        collector,
        samples,
        code="default_filled",
        scope="unit_excel.suppliers",
        field="默认周期",
        message="外协供应商缺少周期样本，已默认补齐为 1.0 天。",
        sample={"对应工种": op_name, "value": 1.0},
    )
    return 1.0


def _record_supplier_defaults(
    op_name: str,
    *,
    collector: DegradationCollector,
    samples: Dict[str, List[Any]],
) -> None:
    record_diagnostic(
        collector,
        samples,
        code="default_filled",
        scope="unit_excel.suppliers",
        field="状态",
        message="外协供应商状态未提供，已默认补齐为 active。",
        sample={"对应工种": op_name, "value": SupplierStatus.ACTIVE.value},
    )
    record_diagnostic(
        collector,
        samples,
        code="default_filled",
        scope="unit_excel.suppliers",
        field="备注",
        message="外协供应商备注未提供，已默认补齐为空。",
        sample={"对应工种": op_name, "value": None},
    )
