from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core.services.common.normalize import to_str_or_blank


def renamed_column_values(
    row: Dict[str, Any],
    *,
    current_column: str,
    legacy_column: str,
) -> Tuple[str, str]:
    current_text = to_str_or_blank(row.get(current_column)) if current_column in row else ""
    legacy_text = to_str_or_blank(row.get(legacy_column)) if legacy_column in row else ""
    return current_text, legacy_text


def renamed_column_conflict_message(
    row: Dict[str, Any],
    *,
    current_column: str,
    legacy_column: str,
) -> Optional[str]:
    current_text, legacy_text = renamed_column_values(
        row,
        current_column=current_column,
        legacy_column=legacy_column,
    )
    if not current_text or not legacy_text or current_text == legacy_text:
        return None
    return (
        f"“{current_column}”和旧列“{legacy_column}”不能同时填写不同值："
        f"当前“{current_column}”为“{current_text}”，“{legacy_column}”为“{legacy_text}”。"
        f"请保留一个编号列，或把两个值改成一致后重新导入。"
    )


def normalize_renamed_column(
    row: Dict[str, Any],
    *,
    current_column: str,
    legacy_column: str,
) -> None:
    if legacy_column not in row:
        return
    if renamed_column_conflict_message(row, current_column=current_column, legacy_column=legacy_column):
        return
    current_text, legacy_text = renamed_column_values(
        row,
        current_column=current_column,
        legacy_column=legacy_column,
    )
    if not current_text and legacy_text:
        row[current_column] = row.get(legacy_column)
    row.pop(legacy_column, None)
