"""首页值班台摘要编排（fusion-due-soon-alert 微重构第 1 步后：纯工具拆至 dashboard_workbench_shared、
todo builders 拆至 dashboard_workbench_todos；本模块保留 build_summary 编排 + 现场缺口/候选计数等
非-todo 计算。单向 import shared/todos，不被它们反向 import——无循环依赖）。

注：从 dashboard_workbench_shared re-export 的 `_machine_util_ratio` / `_parse_datetime` 落在本模块
命名空间，test_dashboard_workbench_contract.py 的既有 import 路径保持可达。"""

from __future__ import annotations

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
from .dashboard_workbench_shared import (
    _candidate_comparison,
    _machine_util_ratio,
    _parse_datetime,
    _safe_int,
    _text,
)
from .dashboard_workbench_todos import (
    _candidate_todo,
    _data_gap_todo,
    _near_due_todo,
    _overdue_todo,
    _resource_load_todo,
    _site_record_gap_todo,
)

_MAX_TODO_ITEMS = 6
_SEVERITY_ORDER = {"danger": 0, "warning": 1, "notice": 2, "ok": 3}


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


def _todo_items(
    *, context: Dict[str, Any], overdue_count: int, near_due_count: int, latest_history: Any,
    latest_summary: Optional[Dict[str, Any]], latest_summary_parse_state: Optional[Dict[str, Any]],
    plan_time_span: Optional[Dict[str, Any]], plan_time_span_load_error: str,
    site_gap_rows: Iterable[Dict[str, Any]], today_rows_load_error: str, execution_facts_load_error: str,
) -> List[Dict[str, Any]]:
    candidates = [
        _overdue_todo(context, overdue_count),
        _near_due_todo(context, near_due_count),
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
    near_due_count: Optional[int] = None,
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
    # 临期 count 仅闸门化（不二次读，index() 是唯一读点）：摘要不可用→强制 None（第7格数据不足、临期 todo 缺席），
    # 与超期 overdue_count 同构；传入 None（缺键）经 _nonnegative_count 仍为 None。
    current_near_due_count = _nonnegative_count(near_due_count) if current_summary_available else None
    todo_items = _todo_items(
        context=context,
        overdue_count=current_overdue_count or 0,
        near_due_count=current_near_due_count or 0,
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
            near_due_count=current_near_due_count,
        ),
        "todo_items": todo_items,
        "quick_links": build_dashboard_quick_links(context),
        "empty_state": empty_state,
    }


# LOAD_*_RATIO 自 dashboard_workbench_cards re-export（单点真相源在 cards）：保持微重构前
# dashboard_workbench.LOAD_WARNING_RATIO/LOAD_DANGER_RATIO 对外可达，test_load_ratio_single_source 契约不破。
__all__ = ["LOAD_DANGER_RATIO", "LOAD_WARNING_RATIO", "build_dashboard_workbench_summary"]
