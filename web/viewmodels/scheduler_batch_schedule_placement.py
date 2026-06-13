"""批次详情「排程去向卡」视图模型装配（fusion-batch-detail-schedule-card）。

纯函数，无 IO、不 import core.services、不接触 ScheduleDetailRow/ExecutionFact。
路由层负责全部取数与 fact→公开标签抽取 + span 日期解析，本模块只把干净数据
组装成模板消费的 schedule_placement 字典，并经 build_workbench_link 构造
「在甘特中定位本批次」链接（gantt 目标日期窗口经 ctx 注入）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .scheduler_workbench_links import build_workbench_link, build_workbench_plan_context

# 诚实态文案（4.11 借鉴：空态/失败态都给一句话，不静默隐藏）
_STATE_MESSAGES = {
    "no_official_plan": "尚无排产方案",
    "plan_empty": "最新方案暂无可用排程明细，请确认排产是否成功",
    "not_placed": "本批次未排入最新方案",
    "error": "排程信息读取失败，请到甘特图或排产历史确认。",
}

_NON_OK_FIELDS = {
    "version_label": "-",
    "generated_at_label": "-",
    "strategy_label": "-",
    "op_count": 0,
    "span_label": "-",
    "gantt_link": None,
    "op_rows": [],
}


def build_schedule_placement(
    *,
    state: str,
    batch_id: Optional[str] = None,
    version: Optional[int] = None,
    op_count: int = 0,
    op_rows: Optional[List[Dict[str, Any]]] = None,
    span_from_date: Optional[str] = None,
    span_to_date: Optional[str] = None,
    span_label: str = "-",
    generated_at: Any = None,
    strategy: Any = None,
    history_present: bool = False,
) -> Dict[str, Any]:
    """装配排程去向卡视图模型。

    state != "ok"：返回对应诚实文案 + 空字段（模板渲染 muted 提示、无工序表/按钮）。
    state == "ok"：用 build_workbench_plan_context 取版本/生成时间/策略 *_label 与
    定位甘特链接；history_present=False（极端竞态 hist 为 None）时不喂 generated_at/
    strategy，走 4.2 缺失态显示「-」而非崩。span 日期为 None（行时间全坏）时 ctx 缺
    date_from/date_to → build_workbench_link 判 disabled，模板据此不渲染按钮。
    """
    if state != "ok":
        return {"state": state, "message": _STATE_MESSAGES.get(state, ""), **_NON_OK_FIELDS}

    ctx_kwargs: Dict[str, Any] = {
        "version": version,
        "date_from": span_from_date,
        "date_to": span_to_date,
        "batch_id": batch_id,
    }
    # 仅在确有历史行时喂 generated_at/strategy；否则留默认 sentinel 走「-」（不喂 None，
    # None 会被词表判成「旧历史未记录」缺失态——本卡是"查无该版本历史行"非"历史未记录策略"）
    if history_present:
        ctx_kwargs["generated_at"] = generated_at
        ctx_kwargs["strategy"] = strategy
    ctx = build_workbench_plan_context(**ctx_kwargs)

    gantt_link = build_workbench_link(
        ctx, "gantt", label="在甘特中定位本批次", view="machine", batch_id=batch_id
    )

    return {
        "state": "ok",
        "message": "",
        "version_label": ctx.get("version_label") or "-",
        "generated_at_label": ctx.get("generated_at_label") or "-",
        "strategy_label": ctx.get("strategy_label") or "-",
        "op_count": op_count,
        "span_label": span_label or "-",
        "gantt_link": gantt_link,
        "op_rows": list(op_rows or []),
    }
