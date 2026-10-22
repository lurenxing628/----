from __future__ import annotations

from typing import Any, Dict, List

from core.shared.degradation import DegradationCollector
from core.shared.local_datetime import parse_local_datetime


def bad_time_row_sample(row: Dict[str, Any]) -> str:
    parts: List[str] = []
    op_code = str(row.get("op_code") or "").strip()
    if op_code:
        parts.append(f"工序编码={op_code}")
    batch_id = str(row.get("batch_id") or "").strip()
    if batch_id:
        parts.append(f"批次号={batch_id}")
    bad_fields: List[str] = []
    start_time = row.get("start_time")
    end_time = row.get("end_time")
    if start_time is not None and parse_local_datetime(start_time) is None:
        bad_fields.append("开始时间")
    if end_time is not None and parse_local_datetime(end_time) is None:
        bad_fields.append("结束时间")
    parts.append(f"字段={'、'.join(bad_fields) if bad_fields else '开始时间或结束时间'}")
    return " / ".join(parts)


def record_bad_time_row(
    collector: DegradationCollector,
    *,
    scope: str,
    row: Dict[str, Any],
) -> None:
    collector.add(
        code="bad_time_row_skipped",
        scope=scope,
        field="time_range",
        message="存在开始或结束时间写法不对的排程行，已跳过。",
        sample=bad_time_row_sample(row),
    )
