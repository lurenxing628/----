from __future__ import annotations

from core.errors import ValidationError


def _unsupported_schedule_keyword_message(keyword: str) -> str:
    if keyword == "graph_ready_context":
        return "当前调度器不支持 graph_ready_context，不能执行启用工序图 ready 队列的排产。"
    if keyword == "readiness_gate_enabled":
        return "当前调度器不支持 readiness_gate_enabled，不能执行启用齐套检查的排产。"
    return f"当前调度器不支持 {keyword}，不能执行本次排产。"


def raise_unsupported_schedule_keyword(keyword: str) -> None:
    raise ValidationError(_unsupported_schedule_keyword_message(keyword), field=str(keyword))
