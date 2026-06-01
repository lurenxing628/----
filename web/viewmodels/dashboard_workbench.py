from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.models.operation_execution_event import EXECUTION_STATUS_NOT_STARTED

from .dashboard_workbench_cards import build_dashboard_quick_links, build_dashboard_risk_cards
from .scheduler_workbench_links import (
    ROLE_ADOPTED,
    build_workbench_link,
    build_workbench_plan_context,
)

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


def _date_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    text = _text(value)
    if len(text) >= 10:
        head = text[:10].replace("/", "-")
        parts = head.split("-")
        if len(parts) == 3 and all(part.isdigit() for part in parts):
            return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    return text


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


def _plan_dates(plan_time_span: Optional[Dict[str, Any]]) -> Tuple[str, str]:
    if not isinstance(plan_time_span, dict):
        return "", ""
    return _date_text(plan_time_span.get("start_time")), _date_text(plan_time_span.get("end_time"))


def _version_value(latest_history: Any) -> Optional[int]:
    raw = getattr(latest_history, "version", None) if latest_history is not None else None
    if raw is None:
        return None
    try:
        version = int(raw)
    except (TypeError, ValueError):
        return None
    return version if version > 0 else None


def _latest_plan_context(
    *,
    latest_history: Any,
    plan_time_span: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    date_from, date_to = _plan_dates(plan_time_span)
    version = _version_value(latest_history)
    return build_workbench_plan_context(
        version=version,
        plan_role=ROLE_ADOPTED,
        date_from=date_from or None,
        date_to=date_to or None,
        can_write_feedback=True if version else False,
    )


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
        evidence_text="根据最新排产摘要里的超期批次统计生成。",
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
    raw = _safe_float(metrics.get("machine_util_avg"))
    if raw is None or raw < 0:
        return None
    if raw > 1:
        if raw <= 100:
            return raw / 100.0
        return None
    return raw


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
        evidence_text="数据来源是最新排产摘要里的设备平均利用率；当前首页暂时只能看到整体压力，受影响批次要去资源页继续看。",
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
        evidence_text=f"按正式采用方案和今天计划开始时间统计，最早一条是 {earliest}；未来任务没有计入。",
        handling_state_label="实时生成，暂未保存已处理状态",
        primary_action=_link(context, "execution_review", "查看计划和现场实际"),
        secondary_action=_link(context, "resource_dispatch", "去资源派工查看"),
    )


def _data_gap_todo(
    *,
    context: Dict[str, Any],
    latest_history: Any,
    latest_summary: Optional[Dict[str, Any]],
    latest_summary_parse_state: Optional[Dict[str, Any]],
    plan_time_span: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if latest_history is None:
        title = "基础数据还不够"
        impact = "还没有排产版本，首页暂时不能生成排产风险、日期范围和现场复盘入口。"
        evidence = "数据库里还没有排产历史。"
    elif isinstance(latest_summary_parse_state, dict) and latest_summary_parse_state.get("parse_failed"):
        title = "最新排产摘要读取失败"
        impact = "部分风险只能显示基础信息，建议先打开排产分析核对这版结果。"
        evidence = _text(latest_summary_parse_state.get("user_message")) or "最新排产摘要结构无法安全解析。"
    elif latest_summary is None:
        title = "最新排产摘要为空"
        impact = "首页只能显示版本和基础统计，暂时不能判断方案、负荷和超期细节。"
        evidence = "最新排产历史没有可用的摘要内容。"
    elif not isinstance(plan_time_span, dict):
        title = "最新计划缺少日期范围"
        impact = "需要日期的甘特、资源派工和报表入口会先禁用，避免跳到不确定的范围。"
        evidence = "当前版本没有读到有效的计划开始和结束时间。"
    else:
        return None
    return _todo_item(
        kind="data_gap",
        severity="warning",
        title=title,
        impact_text=impact,
        evidence_text=evidence,
        handling_state_label="实时生成，暂未保存已处理状态",
        primary_action=_link(context, "analysis", "打开排产分析"),
        secondary_action=_link(context, "dashboard", "回到首页值班台"),
    )


def _todo_items(
    *,
    context: Dict[str, Any],
    overdue_count: int,
    latest_history: Any,
    latest_summary: Optional[Dict[str, Any]],
    latest_summary_parse_state: Optional[Dict[str, Any]],
    plan_time_span: Optional[Dict[str, Any]],
    site_gap_rows: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    candidates = [
        _overdue_todo(context, overdue_count),
        _resource_load_todo(context, latest_summary),
        _site_record_gap_todo(
            context=context,
            site_gap_rows=site_gap_rows,
        ),
        _candidate_todo(context, latest_summary),
        _data_gap_todo(
            context=context,
            latest_history=latest_history,
            latest_summary=latest_summary,
            latest_summary_parse_state=latest_summary_parse_state,
            plan_time_span=plan_time_span,
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
    today_rows: Optional[List[Dict[str, Any]]] = None,
    execution_facts_by_op_id: Optional[Dict[int, Any]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    current_now = now or datetime.now()
    rows = list(today_rows or [])
    facts = dict(execution_facts_by_op_id or {})
    context = _latest_plan_context(latest_history=latest_history, plan_time_span=plan_time_span)
    site_gap_rows = _site_record_gap_rows(
        today_rows=rows,
        execution_facts_by_op_id=facts,
        now=current_now,
    )
    todo_items = _todo_items(
        context=context,
        overdue_count=max(0, int(overdue_count or 0)),
        latest_history=latest_history,
        latest_summary=latest_summary,
        latest_summary_parse_state=latest_summary_parse_state,
        plan_time_span=plan_time_span,
        site_gap_rows=site_gap_rows,
    )
    return {
        "generated_at_label": f"{current_now.year}年{current_now.month}月{current_now.day}日 {current_now.hour:02d}:{current_now.minute:02d}",
        "realtime_note": "待处理项根据当前数据实时生成，暂不保存已处理状态。",
        "latest_plan": context,
        "risk_cards": build_dashboard_risk_cards(
            context=context,
            pending_count=pending_count,
            scheduled_count=scheduled_count,
            overdue_count=overdue_count,
            latest_history=latest_history,
            resource_load_ratio=_machine_util_ratio(latest_summary),
            site_gap_count=len(site_gap_rows),
        ),
        "todo_items": todo_items,
        "quick_links": build_dashboard_quick_links(context),
        "empty_state": "当前没有必须马上处理的排产风险，可以继续查看甘特图或排产分析。",
    }


__all__ = ["build_dashboard_workbench_summary"]
