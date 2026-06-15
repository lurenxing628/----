from __future__ import annotations

from typing import Any

# 公开甘特数据响应里禁止出现的内部定位字段（递归剔除）。
# 注意：这是“黑名单”——日后给甘特数据结构新增任何内部字段，必须同步登记到这里，否则会自动外泄。
# 当前甘特 task 不含 op_id/schedule_id（前端用合成 task.id），此表是纵深防御兜底。
_FORBIDDEN_PUBLIC_GANTT_KEYS = {
    "op_id",
    "schedule_id",
    "scenario_id",
    "candidate_id",
    "selection_candidate_id",
    "resolved_candidate_id",
    "candidate_key",
    "source_row_id",
    "source_table",
}


def public_gantt_data_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: public_gantt_data_payload(child)
            for key, child in value.items()
            if str(key) not in _FORBIDDEN_PUBLIC_GANTT_KEYS
        }
    if isinstance(value, list):
        return [public_gantt_data_payload(item) for item in value]
    return value


__all__ = ["public_gantt_data_payload"]
