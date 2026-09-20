from __future__ import annotations

from collections.abc import Iterable as IterableABC
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.errors import ValidationError

# 保留在原始行数据中的导入元数据键（导入执行器读 Excel 时写入，预览 / 确认阶段据此保真源行号）。
SOURCE_ROW_NUM_KEY = "__source_row_num"
SOURCE_SHEET_NAME_KEY = "__source_sheet_name"

SOURCE_METADATA_KEYS = frozenset((SOURCE_ROW_NUM_KEY, SOURCE_SHEET_NAME_KEY))


class ImportMode(Enum):
    APPEND = "append"  # 追加，不影响已有
    OVERWRITE = "overwrite"  # 相同编号覆盖
    REPLACE = "replace"  # 清空后导入（Phase1 只做预览，真正清空落库在各模块实现）


class RowStatus(Enum):
    NEW = "new"
    UPDATE = "update"
    UNCHANGED = "unchanged"
    ERROR = "error"
    SKIP = "skip"


@dataclass
class ImportPreviewRow:
    """导入预览行（row_num 为兼容字段；source_row_num 为稳定源行号）。"""

    row_num: int
    status: RowStatus
    data: Dict[str, Any]
    message: str = ""
    changes: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)  # {field: (old, new)}
    source_row_num: Optional[int] = None
    source_sheet_name: Optional[str] = None


@dataclass
class ImportResult:
    """导入结果（Phase1 主要用于留痕统计字段）。"""

    success: bool
    total: int
    new_count: int
    update_count: int
    skip_count: int
    error_count: int
    errors: List[Dict[str, Any]]  # [{row: int, field: str, message: str}]
    warnings: List[str]


def resolve_source_row_num(row: Dict[str, Any], *, fallback: int) -> int:
    raw = None
    if isinstance(row, dict):
        raw = row.get(SOURCE_ROW_NUM_KEY)
    if raw is None:
        return int(fallback)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return int(fallback)
    if value > 0:
        return value
    return int(fallback)


def resolve_source_sheet_name(row: Dict[str, Any]) -> Optional[str]:
    if not isinstance(row, dict):
        return None
    text = str(row.get(SOURCE_SHEET_NAME_KEY) or "").strip()
    return text or None


def strip_source_metadata(row: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    return {key: value for key, value in row.items() if key not in SOURCE_METADATA_KEYS}
