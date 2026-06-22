"""人员-设备 Excel 关联导入的纯预览辅助逻辑。

从 OperatorMachineService 抽出的无状态行级辅助：可选列探测与“同一人员只能有一条主操设备”
的文件内唯一性强制。这些函数只读 / 改写传入的预览行，不触达 DB 与 repo，便于独立复用与测试，
并让 operator_machine_service.py 回到超长文件门禁阈值以内。行为与原内联实现逐字等价。
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from core.models.enums import YesNo
from core.services.common.excel_service import ImportPreviewRow, RowStatus
from core.services.common.normalize import to_str_or_blank

from . import operator_machine_normalizers as om_normalizers


def detect_optional_columns(rows: List[Dict[str, Any]]) -> Tuple[bool, bool]:
    has_skill_col = any(("技能等级" in (r or {})) or ("skill_level" in (r or {})) for r in (rows or []))
    has_primary_col = any(("主操设备" in (r or {})) or ("is_primary" in (r or {})) for r in (rows or []))
    return bool(has_skill_col), bool(has_primary_col)


def detect_optional_columns_from_preview(preview_rows: List[ImportPreviewRow]) -> Tuple[bool, bool]:
    has_skill_col = any(("技能等级" in (pr.data or {})) or ("skill_level" in (pr.data or {})) for pr in (preview_rows or []))
    has_primary_col = any(("主操设备" in (pr.data or {})) or ("is_primary" in (pr.data or {})) for pr in (preview_rows or []))
    return bool(has_skill_col), bool(has_primary_col)


def _is_primary_yes(data: Dict[str, Any]) -> bool:
    primary_raw = (data or {}).get("主操设备")
    if primary_raw is None or to_str_or_blank(primary_raw) == "":
        primary_raw = (data or {}).get("is_primary")
    v = to_str_or_blank(primary_raw).lower()
    return v == YesNo.YES.value


def _collect_dup_primary_yes_operators(preview: List[ImportPreviewRow]) -> Set[str]:
    counts: Dict[str, int] = {}
    for pr in preview or []:
        if pr.status == RowStatus.ERROR:
            continue
        op_id = om_normalizers.normalize_operator_machine_text((pr.data or {}).get("工号")) or ""
        if not op_id:
            continue
        if _is_primary_yes(pr.data or {}):
            counts[op_id] = int(counts.get(op_id, 0)) + 1
    return {op_id for op_id, cnt in counts.items() if int(cnt) > 1}


def _mark_dup_primary_yes(preview: List[ImportPreviewRow], dup_ops: Set[str]) -> None:
    for pr in preview or []:
        if pr.status == RowStatus.ERROR:
            continue
        op_id = to_str_or_blank((pr.data or {}).get("工号"))
        if not op_id:
            continue
        if op_id in dup_ops and _is_primary_yes(pr.data or {}):
            pr.status = RowStatus.ERROR
            pr.message = f"人员“{op_id}”在 Excel 中设置了多个主操设备；同一个人员只能有一条主操设备填“是”。"
            pr.changes = {}


def enforce_primary_unique_in_file(preview: List[ImportPreviewRow]) -> None:
    dup_ops = _collect_dup_primary_yes_operators(preview)
    if dup_ops:
        _mark_dup_primary_yes(preview, dup_ops)
