from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.models.operation_execution_event import EXECUTION_STATUS_NOT_STARTED

from .dashboard_cockpit_hero import build_cockpit_hero
from .dashboard_workbench_cards import (
    LOAD_DANGER_RATIO,
    LOAD_WARNING_RATIO,
    build_dashboard_quick_links,
    build_dashboard_risk_cards,
)
from .dashboard_workbench_context import latest_plan_context
from .dashboard_workbench_data_gap import dashboard_data_gap_reason
from .scheduler_workbench_links import build_workbench_link

_MAX_TODO_ITEMS = 6
_SEVERITY_ORDER = {"danger": 0, "warning": 1, "notice": 2, "ok": 3}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(default)  # bool 不是计数：int(True)==1 会把脏 True 冒充「1 套候选」，按类型混入剔除
    try:
        return int(value or default)
    except (TypeError, ValueError, OverflowError):
        return int(default)  # OverflowError：int(float('inf')) 等脏值不得冒泡崩溃首页


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None  # NaN/±Inf 不是可用数值，按脏值剔除（否则 nan<0 恒 False 会漏过冒充正常负荷）
    return number


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
    # 整串匹配（不截前缀）：坏后缀（'...08:00:00xyz'）应解析失败而非被截断成合法日期
    # 静默当成正常时间（与 dashboard_cockpit_hero._parse_dt 同口径）。
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
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
    if not isinstance(comparison, dict):
        return None
    # 与分析页同口径（scheduler_analysis_candidate_helpers._candidate_comparison_summary）：
    # 候选生成被显式关闭（enabled=False）时视为无候选，首页不误报「方案待确认」。
    if comparison.get("enabled") is False:
        return None
    return comparison


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


def _candidate_count(latest_summary: Optional[Dict[str, Any]]) -> int:
    """候选方案数（6 格「方案待确认」体检格用，纯值在 build_summary 先算再传 cards）：
    与 _candidate_todo 同口径——planned/completed/candidates 取最大；无计数但有 adopted_candidate_key
    视为至少 1（确有候选待确认）；无候选信息返回 0。"""
    comparison = _candidate_comparison(latest_summary)
    if comparison is None:
        return 0
    planned = _safe_int(comparison.get("planned_candidate_count"))
    completed = _safe_int(comparison.get("completed_candidate_count"))
    candidates = comparison.get("candidates")
    count = max(planned, completed, len(candidates) if isinstance(candidates, list) else 0)
    if count <= 0 and _text(comparison.get("adopted_candidate_key")):
        return 1
    return count


def _has_current_summary(
    latest_summary: Optional[Dict[str, Any]], latest_summary_parse_state: Optional[Dict[str, Any]]
) -> bool:
    parse_state = latest_summary_parse_state if isinstance(latest_summary_parse_state, dict) else {}
    return isinstance(latest_summary, dict) and bool(latest_summary) and not parse_state.get("parse_failed")


def _nonnegative_count(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None  # bool 不是计数：int(True)==1 会把脏 bool 当 1（与 _safe_int 同口径剔除类型混入）
    try:
        count = int(value)
    except (TypeError, ValueError, OverflowError):
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
    gap_rows, has_unparseable = _site_record_gap_rows(today_rows=rows, execution_facts_by_op_id=facts, now=now)
    if has_unparseable:
        # 今日计划存在无法解析的开始时间（坏数据）→ 现场缺口无法可靠判定，按「数据不足」诚实降级
        # （与读取失败同语义：count=None、空行），不静默跳过坏行后伪造「暂未发现/ok」（硬纪律7）。
        return summary_available, [], None
    return summary_available, gap_rows, len(gap_rows)


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
) -> Tuple[List[Dict[str, Any]], bool]:
    """返回 (现场缺口行, 是否存在无法解析开始时间的坏行)。坏行不静默吞掉冒充正常——
    上层据 has_unparseable 把现场格降级为「数据不足」，而非跳过后伪造「暂未发现/ok」。"""
    out: List[Dict[str, Any]] = []
    has_unparseable = False
    for row in today_rows or []:
        if not isinstance(row, dict):
            continue
        try:
            start_time = _parse_datetime(row.get("start_time"))
        except ValueError:
            has_unparseable = True  # 坏开始时间记账，不静默跳过当成正常无缺口
            continue
        if start_time > now:
            continue
        fact = _fact_for_op(execution_facts_by_op_id, row.get("op_id"))
        if _fact_has_progress(fact):
            continue
        out.append(row)
    return out, has_unparseable


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
    result_status: Any = None,
    failed_run_applies_to_current_view: bool = False,
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
    # 6 格新增「方案待确认/基础数据」的纯值：cards 禁扫 rows/禁 import core，故在此先算再传
    candidate_count = _candidate_count(latest_summary) if current_summary_available else None
    data_gap_reason = dashboard_data_gap_reason(
        latest_history=latest_history,
        context=context,
        latest_summary=latest_summary,
        latest_summary_parse_state=latest_summary_parse_state,
        plan_time_span=plan_time_span,
        plan_time_span_load_error=plan_time_span_load_error,
        today_rows_load_error=rows_load_error,
        execution_facts_load_error=facts_load_error,
    )
    empty_state = "当前没有必须马上处理的排产风险，可以继续查看甘特图或排产分析。"
    hero_bundle = build_cockpit_hero(
        context=context,
        todo_items=todo_items,
        latest_summary=latest_summary,
        result_status=result_status,
        failed_run_applies_to_current_view=failed_run_applies_to_current_view,
        empty_state=empty_state,
    )
    return {
        "generated_at_label": f"{current_now.year}年{current_now.month}月{current_now.day}日 {current_now.hour:02d}:{current_now.minute:02d}",
        "realtime_note": "待处理项根据当前数据实时生成，暂不保存已处理状态。",
        "latest_plan": context,
        "summary_stats": {"overdue_count_value": str(current_overdue_count) if current_overdue_count is not None else "数据不足"},
        "hero": hero_bundle["hero"],
        "rest_todos": hero_bundle["rest_todos"],
        "risk_cards": build_dashboard_risk_cards(
            context=context,
            pending_count=pending_count,
            overdue_count=current_overdue_count,
            candidate_count=candidate_count,
            data_gap_reason=data_gap_reason,
            resource_load_ratio=_machine_util_ratio(latest_summary),
            site_gap_count=site_gap_count,
        ),
        "todo_items": todo_items,
        "quick_links": build_dashboard_quick_links(context),
        "empty_state": empty_state,
    }


__all__ = ["build_dashboard_workbench_summary"]
