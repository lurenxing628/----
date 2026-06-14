"""首页值班台待办（todo）builders（fusion-due-soon-alert 微重构第 1 步，只搬不改行为）。

每个 builder 产出一条 todo_item 或 None。单向 import dashboard_workbench_shared（纯工具）、
dashboard_workbench_cards（负荷阈值常量）、dashboard_workbench_data_gap、scheduler_workbench_links；
**不 import dashboard_workbench**——避免与其形成循环依赖（顶层双向 import 会导入即崩）。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from .dashboard_workbench_cards import LOAD_DANGER_RATIO, LOAD_WARNING_RATIO
from .dashboard_workbench_data_gap import dashboard_data_gap_reason
from .dashboard_workbench_shared import (
    _candidate_comparison,
    _datetime_label,
    _machine_util_ratio,
    _parse_datetime,
    _safe_int,
    _text,
)
from .scheduler_workbench_links import build_workbench_link


def _link(context: Dict[str, Any], target_page: str, label: str, **kwargs: Any) -> Dict[str, Any]:
    return build_workbench_link(context, target_page, label=label, **kwargs)


def _todo_item(
    *,
    kind: str,
    severity: str,
    title: str,
    impact_text: str,
    evidence_text: str,
    handling_state_label: str,
    primary_action: Dict[str, Any],
    secondary_action: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "kind": kind,
        "severity": severity,
        "title": title,
        "impact_text": impact_text,
        "evidence_text": evidence_text,
        "handling_state_label": handling_state_label,
        "primary_action": primary_action,
        "secondary_action": secondary_action,
        "action_label": primary_action.get("label") or "",
        "target_url": primary_action.get("url") or "",
    }


def _overdue_todo(context: Dict[str, Any], overdue_count: int) -> Optional[Dict[str, Any]]:
    if overdue_count <= 0:
        return None
    return _todo_item(
        kind="overdue",
        severity="danger",
        title="超期批次需要先看",
        impact_text=f"{overdue_count} 个批次会晚于交期，同类提醒已合并成这一条。",
        evidence_text="根据当前排产摘要里的超期批次统计生成。",
        handling_state_label="实时生成，暂未保存已处理状态",
        primary_action=_link(context, "overdue_report", "查看超期清单"),
        secondary_action=_link(context, "delay_diagnosis", "查看延期说明"),
    )


def _near_due_todo(context: Dict[str, Any], near_due_count: int) -> Optional[Dict[str, Any]]:
    # 临期 todo：near_due_count>0 才出（<=0 缺席）；与超期同口径但提前预警，primary→甘特图、secondary→超期清单。
    if near_due_count <= 0:
        return None
    return _todo_item(
        kind="near_due",
        severity="warning",
        title="临期批次需要盯进度",
        impact_text=f"{near_due_count} 个批次的排程完工时间已临近交期、还没真正超期，同类提醒已合并成这一条。",
        evidence_text="按当前排产摘要的交期对比排程完工时间统计，与超期同口径，只是还没真正晚于交期。",
        handling_state_label="实时生成，暂未保存已处理状态",
        primary_action=_link(context, "gantt", "查看设备甘特图", view="machine"),
        secondary_action=_link(context, "overdue_report", "查看超期清单"),
    )


def _candidate_todo(context: Dict[str, Any], latest_summary: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    comparison = _candidate_comparison(latest_summary)
    if comparison is None:
        return None
    planned = _safe_int(comparison.get("planned_candidate_count"))
    completed = _safe_int(comparison.get("completed_candidate_count"))
    candidates = comparison.get("candidates")
    candidate_count = max(planned, completed, len(candidates) if isinstance(candidates, list) else 0)
    if candidate_count <= 0 and not _text(comparison.get("adopted_candidate_key")):
        return None
    count_text = f"{candidate_count} 套候选方案" if candidate_count > 0 else "本次候选方案"
    evidence_parts = [f"排产摘要记录了{count_text}"]
    if completed > 0:
        evidence_parts.append(f"其中 {completed} 套已算完")
    # O25：此分支经「baseline 缺失」路径生产可达（_baseline_missing_or_failed 无 baseline 候选
    # 返回 True），不是死分支——失败半边虽生产不可达但随枚举契约保留，禁裸删本分支。
    if comparison.get("baseline_missing_or_failed"):
        evidence_parts.append("原算法代表方案没有完整结果")
    return _todo_item(
        kind="candidate_review",
        severity="notice",
        title="方案需要确认",
        impact_text="本次排产有候选方案信息，建议先复核推荐结论再继续安排。",
        evidence_text="，".join(evidence_parts) + "。",
        handling_state_label="实时生成，暂未保存已处理状态",
        primary_action=_link(context, "analysis", "复核方案推荐"),
        secondary_action=_link(context, "gantt", "查看设备甘特图", view="machine"),
    )


def _resource_load_todo(context: Dict[str, Any], latest_summary: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    ratio = _machine_util_ratio(latest_summary)
    if ratio is None or ratio < LOAD_WARNING_RATIO:
        return None
    percent = round(ratio * 100, 1)
    severity = "danger" if ratio >= LOAD_DANGER_RATIO else "warning"
    return _todo_item(
        kind="resource_overload",
        severity=severity,
        title="资源负荷偏高",
        impact_text=f"设备平均利用率约 {percent}%，可能需要先看资源排班。",
        evidence_text="数据来源是当前排产摘要里的设备平均利用率；当前首页暂时只能看到整体压力，受影响批次要去资源页继续看。",
        handling_state_label="实时生成，暂未保存已处理状态",
        primary_action=_link(context, "resource_dispatch", "查看资源排班"),
        secondary_action=_link(context, "utilization_report", "查看资源负荷"),
    )


def _site_record_gap_todo(
    *,
    context: Dict[str, Any],
    site_gap_rows: Iterable[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    gap_rows = list(site_gap_rows or [])
    if not gap_rows:
        return None
    earliest = ""
    try:
        earliest = _datetime_label(min(_parse_datetime(row.get("start_time")) for row in gap_rows))
    except ValueError:
        earliest = "今天已到开始时间"
    count = len(gap_rows)
    return _todo_item(
        kind="site_record_gap",
        severity="warning",
        title="现场情况待确认",
        impact_text=f"{count} 道今天已到开始时间的工序暂未收到现场情况，同类提醒已合并成这一条。",
        evidence_text=f"按当前查看方案和今天计划开始时间统计，最早一条是 {earliest}；未来任务没有计入。",
        handling_state_label="实时生成，暂未保存已处理状态",
        primary_action=_link(context, "execution_review", "查看计划和现场实际"),
        secondary_action=_link(context, "resource_dispatch", "去资源派工查看"),
    )


def _data_gap_todo(
    *, context: Dict[str, Any], latest_history: Any,
    latest_summary: Optional[Dict[str, Any]], latest_summary_parse_state: Optional[Dict[str, Any]],
    plan_time_span: Optional[Dict[str, Any]], plan_time_span_load_error: str,
    today_rows_load_error: str, execution_facts_load_error: str,
) -> Optional[Dict[str, Any]]:
    reason = dashboard_data_gap_reason(
        latest_history=latest_history,
        context=context,
        latest_summary=latest_summary,
        latest_summary_parse_state=latest_summary_parse_state,
        plan_time_span=plan_time_span,
        plan_time_span_load_error=plan_time_span_load_error,
        today_rows_load_error=today_rows_load_error,
        execution_facts_load_error=execution_facts_load_error,
    )
    if reason is None:
        return None
    return _todo_item(
        kind="data_gap",
        severity="warning",
        title=reason["title"],
        impact_text=reason["impact"],
        evidence_text=reason["evidence"],
        handling_state_label="实时生成，暂未保存已处理状态",
        primary_action=_link(context, "analysis", "打开排产分析"),
        secondary_action=_link(context, "dashboard", "回到首页值班台"),
    )


__all__ = [
    "_link",
    "_todo_item",
    "_overdue_todo",
    "_near_due_todo",
    "_candidate_todo",
    "_resource_load_todo",
    "_site_record_gap_todo",
    "_data_gap_todo",
]
