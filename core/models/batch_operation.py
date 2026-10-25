from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ._helpers import (
    RowLike,
    get,
    parse_float_or_default,
    parse_int,
    parse_int_or_default,
    parse_optional_float,
)
from .enums import BatchOperationStatus, SourceType


def _clean_optional_str(value: Any) -> Optional[str]:
    # 行映射清洗：非 None 且非空串才 str() 化；保留 0→"0" 行为，禁简化成 `str(v) if v else None`（会把 0 当 falsy）。
    return str(value) if value is not None and value != "" else None


def _normalize_enum(value: Any, default: str) -> str:
    # 枚举值归一：双层兜底——内层 `value or default` 防 None/""/0，外层 `... or default` 防 strip 后空串。
    return str(value or default).strip().lower() or default


def _str_or_empty(value: Any) -> str:
    return str(value or "")


@dataclass
class BatchOperation:
    id: Optional[int]
    op_code: str
    batch_id: str
    piece_id: Optional[str] = None
    seq: int = 0
    op_type_id: Optional[str] = None
    op_type_name: str = ""
    source: str = SourceType.INTERNAL.value  # internal/external
    machine_id: Optional[str] = None
    operator_id: Optional[str] = None
    supplier_id: Optional[str] = None
    setup_hours: float = 0.0
    unit_hours: float = 0.0
    ext_days: Optional[float] = None
    status: str = BatchOperationStatus.PENDING.value  # pending/scheduled/processing/completed/skipped
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> BatchOperation:
        # cls(...) 关键字实参从上到下求值——顺序即多坏字段时 ValueError 的先后契约，禁重排。
        return cls(
            id=parse_int(get(row, "id"), default=None),
            op_code=_str_or_empty(get(row, "op_code")),
            batch_id=_str_or_empty(get(row, "batch_id")),
            piece_id=_clean_optional_str(get(row, "piece_id")),
            seq=parse_int_or_default(get(row, "seq"), 0, field="seq"),
            op_type_id=_clean_optional_str(get(row, "op_type_id")),
            op_type_name=_str_or_empty(get(row, "op_type_name")),
            source=_normalize_enum(get(row, "source"), SourceType.INTERNAL.value),
            machine_id=_clean_optional_str(get(row, "machine_id")),
            operator_id=_clean_optional_str(get(row, "operator_id")),
            supplier_id=_clean_optional_str(get(row, "supplier_id")),
            setup_hours=parse_float_or_default(get(row, "setup_hours"), 0.0, field="setup_hours"),
            unit_hours=parse_float_or_default(get(row, "unit_hours"), 0.0, field="unit_hours"),
            ext_days=parse_optional_float(get(row, "ext_days"), field="ext_days"),
            status=_normalize_enum(get(row, "status"), BatchOperationStatus.PENDING.value),
            created_at=get(row, "created_at"),
        )
