"""首页值班台风险卡与快捷入口装配。

负荷阈值唯一真相源：LOAD_WARNING_RATIO / LOAD_DANGER_RATIO 在此公开定义
（roadmap 4.4 契约——Python 单点、CSS 侧只消费 severity-* 类名；
dashboard_workbench.py 与未来 fusion-gantt-load-strip 均 import 此处常量）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .scheduler_workbench_links import build_workbench_link

LOAD_WARNING_RATIO = 0.75
LOAD_DANGER_RATIO = 0.90


def _link(context: Dict[str, Any], target_page: str, label: str, **kwargs: Any) -> Dict[str, Any]:
    return build_workbench_link(context, target_page, label=label, **kwargs)


def _risk_card(
    *,
    kind: str,
    label: str,
    value: str,
    helper_text: str,
    severity: str,
    link: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "kind": kind,
        "label": label,
        "value": value,
        "helper_text": helper_text,
        "severity": severity,
        "link": link,
        "target_url": link.get("url") or "",
    }


def _resource_load_card(context: Dict[str, Any], resource_load_ratio: Optional[float]) -> Dict[str, Any]:
    if resource_load_ratio is None:
        return _risk_card(
            kind="resource_overload",
            label="资源负荷",
            value="数据不足",
            helper_text="当前摘要里没有可安全展示的设备平均利用率。",
            severity="notice",
            link=_link(context, "utilization_report", "查看资源负荷"),
        )

    percent = round(resource_load_ratio * 100, 1)
    if resource_load_ratio >= LOAD_DANGER_RATIO:
        severity = "danger"
        helper = "设备平均利用率已经很高，建议先看资源排班。"
    elif resource_load_ratio >= LOAD_WARNING_RATIO:
        severity = "warning"
        helper = "设备平均利用率偏高，建议留意资源压力。"
    else:
        severity = "ok"
        helper = "按当前排产摘要看，整体设备压力暂时可控。"

    return _risk_card(
        kind="resource_overload",
        label="资源负荷",
        value=f"{percent}%",
        helper_text=helper,
        severity=severity,
        link=_link(context, "utilization_report", "查看资源负荷"),
    )


def _overdue_card(context: Dict[str, Any], overdue_count: Optional[int]) -> Dict[str, Any]:
    if overdue_count is None or overdue_count < 0:
        return _risk_card(
            kind="overdue_batches",
            label="超期批次",
            value="数据不足",
            helper_text="当前摘要不可用，不能把缺失的超期统计显示成 0。",
            severity="notice",
            link=_link(context, "overdue_report", "查看超期清单"),
        )
    return _risk_card(
        kind="overdue_batches",
        label="超期批次",
        value=str(max(0, int(overdue_count or 0))),
        helper_text="按当前排产摘要统计，同类超期只汇总显示。",
        severity="danger" if overdue_count else "ok",
        link=_link(context, "overdue_report", "查看超期清单"),
    )


def build_dashboard_risk_cards(
    *,
    context: Dict[str, Any],
    pending_count: int,
    scheduled_count: int,
    overdue_count: Optional[int],
    latest_history: Any,
    resource_load_ratio: Optional[float],
    site_gap_count: Optional[int],
) -> List[Dict[str, Any]]:
    site_gap_card = _risk_card(
        kind="site_record_gap",
        label="现场情况",
        value=str(site_gap_count) if site_gap_count else "暂未发现",
        helper_text="只统计今天已到计划开始时间、但暂未收到进展的任务。",
        severity="warning" if site_gap_count else "ok",
        link=_link(context, "execution_review", "查看计划和现场实际"),
    )
    if site_gap_count is None:
        site_gap_card.update(
            value="数据不足",
            helper_text="今日计划或现场事实暂时读不到，不能判断现场情况是否都已反馈。",
            severity="notice",
        )
    return [
        _risk_card(
            kind="latest_version",
            label="当前计划",
            value=f"v{getattr(latest_history, 'version', '')}" if latest_history is not None else "暂无版本",
            helper_text="首页按当前查看方案生成提醒。",
            severity="ok" if latest_history is not None else "notice",
            link=_link(context, "analysis", "查看排产分析"),
        ),
        _risk_card(
            kind="pending_batches",
            label="待排批次",
            value=str(max(0, int(pending_count or 0))),
            helper_text="还没有进入排产结果的批次数量。",
            severity="notice" if pending_count else "ok",
            link=_link(context, "dashboard", "回到计划工作台"),
        ),
        _risk_card(
            kind="scheduled_batches",
            label="已排批次",
            value=str(max(0, int(scheduled_count or 0))),
            helper_text="当前已形成排产结果的批次数量。",
            severity="ok",
            link=_link(context, "analysis", "查看排产分析"),
        ),
        _overdue_card(context, overdue_count),
        _resource_load_card(context, resource_load_ratio),
        site_gap_card,
    ]


def build_dashboard_quick_links(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        _link(context, "analysis", "排产分析", allow_empty_plan_context=True),
        _link(context, "gantt", "设备甘特图", view="machine", allow_empty_plan_context=True),
        _link(context, "resource_dispatch", "资源派工", allow_empty_plan_context=True),
        _link(context, "reports_index", "报表中心", allow_empty_plan_context=True),
        _link(context, "week_plan", "周计划", allow_empty_plan_context=True),
        _link(context, "execution_review", "计划和现场实际"),
    ]


__all__ = ["build_dashboard_quick_links", "build_dashboard_risk_cards"]
