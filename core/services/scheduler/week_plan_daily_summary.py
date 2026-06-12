"""周计划每日合计工时/容量行（fusion-week-plan-enrich，契约 4.6 首个落地实例）。

容量分母按 4.6 共享协议：CalendarEngine 的 shift_hours × efficiency 同一公式，
采样时刻统一取**正午**——刻意不调 calculations.capacity_hours（其 midnight 采样
在跨午夜班次会把当日容量归属前一日窗口，4.6 红线）。
容量是「单资源可用工时」简化口径，页面必须明示「按全局工作日历估算，
未按单台设备/单人细分」；容量 0 或算不出时 load_label 诚实降级。

由路由层调用（calendar 取 g.services.calendar_service）——gantt_service
零 calendar 接触（495/500 行红线 + 4.6「新容量逻辑必须落新文件」双满足）。
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Any, Dict, List, Mapping

_NOON = time(12, 0)

LOAD_UNAVAILABLE_LABEL = "利用率暂时算不了"


def _capacity_hours_at_noon(calendar: Any, day: Any) -> float:
    """单日单资源容量：正午采样的 shift_hours×efficiency；休息日（shift_hours≤0）为 0。"""
    policy = calendar.policy_for_datetime(datetime.combine(day, _NOON))
    shift_hours = float(getattr(policy, "shift_hours", 0.0) or 0.0)
    if shift_hours <= 0:
        return 0.0
    return shift_hours * float(getattr(policy, "efficiency", 1.0) or 1.0)


def _hours_label(hours: float) -> str:
    text = f"{hours:.1f}".rstrip("0").rstrip(".")
    return f"{text} 小时"


def build_week_plan_daily_summary(
    minutes_by_date: Mapping[str, int],
    *,
    calendar: Any,
    week_start: Any,
    week_end: Any,
) -> List[Dict[str, Any]]:
    """按日聚合的计划工时/容量摘要行（仅有计划数据的日期，空周返回空列表）。

    minutes_by_date 是 build_week_plan_rows 的旁路返回值（{"2026-06-01": 420}）。
    单日容量算不出（policy 读取异常）按诚实降级：capacity 标「-」、
    load_label 标「利用率暂时算不了」，不吞错装健康但也不让汇总条炸掉页面主体。
    """
    out: List[Dict[str, Any]] = []
    for day_key in sorted(minutes_by_date):
        planned_hours = minutes_by_date[day_key] / 60.0
        try:
            day = datetime.strptime(day_key, "%Y-%m-%d").date()
            capacity = _capacity_hours_at_noon(calendar, day)
        except Exception:
            capacity = None
        if capacity is None:
            capacity_label = "-"
            load_label = LOAD_UNAVAILABLE_LABEL
        elif capacity <= 0:
            capacity_label = "0 小时"
            load_label = LOAD_UNAVAILABLE_LABEL
        else:
            capacity_label = _hours_label(capacity)
            load_label = f"{planned_hours / capacity * 100:.0f}%"
        out.append(
            {
                "date": day_key,
                "planned_hours_label": _hours_label(planned_hours),
                "capacity_hours_label": capacity_label,
                "load_label": load_label,
            }
        )
    return out


__all__ = ["LOAD_UNAVAILABLE_LABEL", "build_week_plan_daily_summary"]
