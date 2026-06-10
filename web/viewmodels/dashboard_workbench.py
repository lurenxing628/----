from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.models.operation_execution_event import EXECUTION_STATUS_NOT_STARTED

from .dashboard_workbench_cards import build_dashboard_quick_links, build_dashboard_risk_cards
from .dashboard_workbench_context import latest_plan_context
from .dashboard_workbench_data_gap import dashboard_data_gap_reason
from .scheduler_workbench_links import build_workbench_link

_MAX_TODO_ITEMS = 6
_LOAD_WARNING_RATIO = 0.75
_LOAD_DANGER_RATIO = 0.90
_SEVERITY_ORDER = {"danger": 0, "warning": 1, "notice": 2, "ok": 3}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return int(default)


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _datetime_label(value: Any) -> str:
    if isinstance(value, datetime):
        return f"{value.year}年{value.month}月{value.day}日 {value.hour:02d}:{value.minute:02d}"
    text = _text(value)
    if not text:
        return "-"
    try:
        parsed = _parse_datetime(text)
    except ValueError:
        return text
    return f"{parsed.year}年{parsed.month}月{parsed.day}日 {parsed.hour:02d}:{parsed.minute:02d}"


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    text = _text(value).replace("/", "-").replace("T", " ").replace("：", ":")
    for fmt, size in (
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%d %H:%M", 16),
        ("%Y-%m-%d", 10),
    ):
        try:
            return datetime.strptime(text[:size], fmt)
        except ValueError:
            continue
    raise ValueError("datetime value is required")


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


def _candidate_comparison(summary: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(summary, dict):
        return None
    algo = summary.get("algo")
    if not isinstance(algo, dict):
        return None
    comparison = algo.get("candidate_comparison")
    return comparison if isinstance(comparison, dict) else None


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


def _machine_util_ratio(latest_summary: Optional[Dict[str, Any]]) -> Optional[float]:
    if not isinstance(latest_summary, dict):
        return None
    algo = latest_summary.get("algo")
    if not isinstance(algo, dict):
        return None
    metrics = algo.get("metrics")
    if not isinstance(metrics, dict):
        return None
    if isinstance(metrics.get("machine_util_avg"), bool):
        return None
    raw = _safe_float(metrics.get("machine_util_avg"))
    if raw is None or raw < 0:
        return None
    if raw > 1:
        if raw <= 100:
            return raw / 100.0
        return None
    return raw


def _summary_metrics(latest_summary: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    algo = latest_summary.get("algo") if isinstance(latest_summary, dict) else None
    metrics = algo.get("metrics") if isinstance(algo, dict) else None
    return metrics if isinstance(metrics, dict) else None


def _metric_number(metrics: Dict[str, Any], key: str) -> Optional[float]:
    value = metrics.get(key)
    if value is None or value == "" or isinstance(value, bool):
        return None
    return _safe_float(value)


def _has_current_summary(
    latest_summary: Optional[Dict[str, Any]], latest_summary_parse_state: Optional[Dict[str, Any]]
) -> bool:
    parse_state = latest_summary_parse_state if isinstance(latest_summary_parse_state, dict) else {}
    return isinstance(latest_summary, dict) and bool(latest_summary) and not parse_state.get("parse_failed")


def _nonnegative_count(value: Any) -> Optional[int]:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return None
    return count if count >= 0 else None


def _site_gap_context(
    *,
    latest_summary: Optional[Dict[str, Any]],
    latest_summary_parse_state: Optional[Dict[str, Any]],
    rows: List[Dict[str, Any]],
    facts: Dict[int, Any],
    rows_load_error: str,
    facts_load_error: str,
    now: datetime,
) -> Tuple[bool, List[Dict[str, Any]], Optional[int]]:
    summary_available = _has_current_summary(latest_summary, latest_summary_parse_state)
    if not summary_available or rows_load_error or facts_load_error:
        return summary_available, [], None
    gap_rows = _site_record_gap_rows(today_rows=rows, execution_facts_by_op_id=facts, now=now)
    return summary_available, gap_rows, len(gap_rows)


def _recent_schedule_metrics(
    latest_summary: Optional[Dict[str, Any]], latest_summary_parse_state: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    parse_state = latest_summary_parse_state if isinstance(latest_summary_parse_state, dict) else {}
    if parse_state.get("parse_failed"):
        message = _text(parse_state.get("user_message")) or "当前排产摘要结构无法安全解析。"
        return {"status": "error", "message": f"当前排产摘要读取失败：{message}", "metric_items": []}
    metrics = _summary_metrics(latest_summary)
    util_ratio = _machine_util_ratio(latest_summary)
    if not metrics or util_ratio is None:
        return {"status": "missing", "message": "当前排产摘要缺少可信指标，不能把缺失值显示成 0。", "metric_items": []}
    tardiness = _metric_number(metrics, "total_tardiness_hours")
    makespan = _metric_number(metrics, "makespan_hours")
    if tardiness is None or makespan is None:
        return {"status": "missing", "message": "当前排产摘要缺少可信指标，不能把缺失值显示成 0。", "metric_items": []}
    return {
        "status": "ok",
        "message": "",
        "metric_items": [
            {"label": "拖期", "value": f"{round(tardiness, 1)} 小时"},
            {"label": "总工期", "value": f"{round(makespan, 1)} 小时"},
            {"label": "设备利用率", "value": f"{round(util_ratio * 100, 1)}%"},
        ],
    }


def _resource_load_todo(context: Dict[str, Any], latest_summary: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    ratio = _machine_util_ratio(latest_summary)
    if ratio is None or ratio < _LOAD_WARNING_RATIO:
        return None
    percent = round(ratio * 100, 1)
    severity = "danger" if ratio >= _LOAD_DANGER_RATIO else "warning"
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


def _fact_for_op(execution_facts_by_op_id: Dict[int, Any], op_id: Any) -> Any:
    try:
        key = int(op_id)
    except (TypeError, ValueError):
        return None
    return execution_facts_by_op_id.get(key)


def _fact_has_progress(fact: Any) -> bool:
    if fact is None:
        return False
    if getattr(fact, "actual_start_time", None) is not None:
        return True
    if getattr(fact, "actual_end_time", None) is not None:
        return True
    status = _text(getattr(fact, "actual_status", "")).lower()
    return bool(status and status != EXECUTION_STATUS_NOT_STARTED)


def _site_record_gap_rows(
    *,
    today_rows: Iterable[Dict[str, Any]],
    execution_facts_by_op_id: Dict[int, Any],
    now: datetime,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in today_rows or []:
        if not isinstance(row, dict):
            continue
        try:
            start_time = _parse_datetime(row.get("start_time"))
        except ValueError:
            continue
        if start_time > now:
            continue
        fact = _fact_for_op(execution_facts_by_op_id, row.get("op_id"))
        if _fact_has_progress(fact):
            continue
        out.append(row)
    return out


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


def _todo_items(
    *, context: Dict[str, Any], overdue_count: int, latest_history: Any,
    latest_summary: Optional[Dict[str, Any]], latest_summary_parse_state: Optional[Dict[str, Any]],
    plan_time_span: Optional[Dict[str, Any]], plan_time_span_load_error: str,
    site_gap_rows: Iterable[Dict[str, Any]], today_rows_load_error: str, execution_facts_load_error: str,
) -> List[Dict[str, Any]]:
    candidates = [
        _overdue_todo(context, overdue_count),
        _resource_load_todo(context, latest_summary),
        _site_record_gap_todo(context=context, site_gap_rows=site_gap_rows),
        _candidate_todo(context, latest_summary),
        _data_gap_todo(
            context=context,
            latest_history=latest_history,
            latest_summary=latest_summary,
            latest_summary_parse_state=latest_summary_parse_state,
            plan_time_span=plan_time_span,
            plan_time_span_load_error=plan_time_span_load_error,
            today_rows_load_error=today_rows_load_error,
            execution_facts_load_error=execution_facts_load_error,
        ),
    ]
    items = [item for item in candidates if item is not None]
    items.sort(key=lambda item: (_SEVERITY_ORDER.get(str(item.get("severity") or ""), 99), str(item.get("kind") or "")))
    return items[:_MAX_TODO_ITEMS]


def build_dashboard_workbench_summary(
    *,
    pending_count: int,
    scheduled_count: int,
    overdue_count: int,
    latest_history: Any = None,
    latest_summary: Optional[Dict[str, Any]] = None,
    latest_summary_parse_state: Optional[Dict[str, Any]] = None,
    plan_time_span: Optional[Dict[str, Any]] = None,
    plan_time_span_load_error: str = "",
    today_rows: Optional[List[Dict[str, Any]]] = None,
    today_rows_load_error: str = "",
    execution_facts_by_op_id: Optional[Dict[int, Any]] = None,
    execution_facts_load_error: str = "",
    navigation_context: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    current_now = now or datetime.now()
    rows = list(today_rows or [])
    facts = dict(execution_facts_by_op_id or {})
    rows_load_error = _text(today_rows_load_error)
    facts_load_error = _text(execution_facts_load_error)
    context = latest_plan_context(
        latest_history=latest_history,
        plan_time_span=plan_time_span,
        plan_time_span_load_error=plan_time_span_load_error,
        navigation_context=navigation_context,
    )
    current_summary_available, site_gap_rows, site_gap_count = _site_gap_context(
        latest_summary=latest_summary,
        latest_summary_parse_state=latest_summary_parse_state,
        rows=rows,
        facts=facts,
        rows_load_error=rows_load_error,
        facts_load_error=facts_load_error,
        now=current_now,
    )
    current_overdue_count = _nonnegative_count(overdue_count) if current_summary_available else None
    todo_items = _todo_items(
        context=context,
        overdue_count=current_overdue_count or 0,
        latest_history=latest_history,
        latest_summary=latest_summary,
        latest_summary_parse_state=latest_summary_parse_state,
        plan_time_span=plan_time_span,
        plan_time_span_load_error=plan_time_span_load_error,
        site_gap_rows=site_gap_rows,
        today_rows_load_error=rows_load_error,
        execution_facts_load_error=facts_load_error,
    )
    return {
        "generated_at_label": f"{current_now.year}年{current_now.month}月{current_now.day}日 {current_now.hour:02d}:{current_now.minute:02d}",
        "realtime_note": "待处理项根据当前数据实时生成，暂不保存已处理状态。",
        "latest_plan": context,
        "recent_metrics": _recent_schedule_metrics(latest_summary, latest_summary_parse_state),
        "summary_stats": {"overdue_count_value": str(current_overdue_count) if current_overdue_count is not None else "数据不足"},
        "risk_cards": build_dashboard_risk_cards(
            context=context,
            pending_count=pending_count,
            scheduled_count=scheduled_count,
            overdue_count=current_overdue_count,
            latest_history=latest_history,
            resource_load_ratio=_machine_util_ratio(latest_summary),
            site_gap_count=site_gap_count,
        ),
        "todo_items": todo_items,
        "quick_links": build_dashboard_quick_links(context),
        "empty_state": "当前没有必须马上处理的排产风险，可以继续查看甘特图或排产分析。",
    }


__all__ = ["build_dashboard_workbench_summary"]
