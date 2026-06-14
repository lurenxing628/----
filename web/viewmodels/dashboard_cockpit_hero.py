"""首页驾驶舱 hero 指令卡装配（fusion-dashboard-cockpit）。

三态：
- 失败态：当前最新正式位置（route 算独立门控 failed_run_applies_to_current_view）
  且 result_status 归一为 'failed' → danger hero「最近一次排产没有成功」。归一走唯一字源
  resolve_result_status（覆盖遗留别名 'fail'），**禁裸 == 'failed'**。
- 风险态：队列首条 todo 置顶（title 原样复用），超期为首条时 impact 注入「精简主导线索」
  （逾期最久批次 + 晚多久，零计划行扫描，只读已冻结的 overdue_batches.items）。
- 平静态：无 todo → severity-ok 绿 hero。

纪律：禁 import core.services；不反向 import dashboard_workbench（防循环）——本模块只消费
已构建好的 todo_items 列表 + latest_summary 原值 + build_workbench_link + resolve_result_status。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .scheduler_summary_result_state import resolve_result_status
from .scheduler_workbench_links import build_workbench_link

_CALM_TITLE = "当前没有必须马上处理的排产风险"
_FAILED_TITLE = "最近一次排产没有成功"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _link(context: Dict[str, Any], target_page: str, label: str) -> Dict[str, Any]:
    return build_workbench_link(context, target_page, label=label)


def _parse_dt(value: Any) -> Optional[datetime]:
    """宽松解析：兼容 `/`→`-`、T 分隔、纯日期/分钟/秒级时间。**整串匹配**（不截前缀）——
    坏后缀（'2026-06-12xyz'、含非法时间 '2026-06-13 99:99:99'）应解析失败返回 None，
    不被截断成合法日期而静默当成正常时间（否则该条不计 unparseable、会冒充正常逾期线索）。"""
    if isinstance(value, datetime):
        return value
    text = _text(value).replace("/", "-").replace("T", " ").replace("：", ":")
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _due_exclusive(due_value: Any) -> Optional[datetime]:
    """交期排他下界 = 交期当日 + 1 天 00:00（与 summary_runtime_state.due_exclusive 同口径，
    不可用 finish−due 否则多算一天）。本模块不 import core，按同口径就地计算。"""
    parsed = _parse_dt(due_value)
    if parsed is None:
        return None
    return datetime(parsed.year, parsed.month, parsed.day) + timedelta(days=1)


def _format_delta(delta: timedelta) -> str:
    days = delta.days
    hours = delta.seconds // 3600
    parts: List[str] = []
    if days > 0:
        parts.append(f"{days} 天")
    if hours > 0:
        parts.append(f"{hours} 小时")
    if not parts:
        return "不到 1 小时"
    return " ".join(parts)


def _overdue_payload(latest_summary: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(latest_summary, dict):
        return None
    payload = latest_summary.get("overdue_batches")
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return {"count": len(payload), "items": payload}
    return None


def _overdue_count_value(payload: Dict[str, Any]) -> Optional[int]:
    raw = payload.get("count")
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw >= 0 else None
    if isinstance(raw, str):
        text = raw.strip()
        # 须 isascii()：'²'/'③' 等 unicode 数字 isdigit()==True 但 int() 抛 ValueError，
        # 不能让坏 count 串冒泡（本函数语义是「无法解析→None 降级」，不抛）。
        if text.isascii() and text.isdigit():
            return int(text)
    return None


def _worst_overdue(items: List[Any]) -> Dict[str, Any]:
    """取逾期量最大的一条，并记账「日期解析失败」条数（unparseable，跳过会漏真值→下游诚实标注）。
    与 core 超期判定**同源**（schedule_summary_assembly.py:156 用 `finish < due_exclusive` 才非超期）：
    仅 delta<0 剔除；delta==0（finish 恰在 due_exclusive 边界）core 计为超期，保留参与「最久」竞选
    （配合 _format_delta 的「不到 1 小时」分支自然产出）。恒返回 dict（batch_id 为 "" 表示无可定位最久）。"""
    worst: Optional[Dict[str, Any]] = None
    worst_delta: Optional[timedelta] = None
    unparseable = 0
    for item in items:
        finish = _parse_dt(item.get("finish_time")) if isinstance(item, dict) else None
        due_exclusive = _due_exclusive(item.get("due_date")) if isinstance(item, dict) else None
        if finish is None or due_exclusive is None:
            unparseable += 1  # 交期/完工时间无法解析——跳过但记账，下游据此诚实标注
            continue
        delta = finish - due_exclusive
        if delta.total_seconds() < 0:
            continue  # finish < due_exclusive：core 亦不计超期，非「最久」候选
        if worst_delta is None or delta > worst_delta:
            worst_delta = delta
            worst = item
    return {
        "batch_id": _text(worst.get("batch_id")) if worst is not None else "",
        "delta": worst_delta,
        "unparseable": unparseable,
    }


def _overdue_hero_impact(latest_summary: Optional[Dict[str, Any]], fallback_impact: str) -> str:
    """超期顶 hero 的精简主导线索（零计划行扫描，多态诚实降级，不冒充/不掩盖）：
    - items 缺失/非 list（minimal 档）→ 笼统「N 个批次会晚于交期」；
    - count>len(items)（被裁剪）→「基于前 N 条…」不拿截断子集冒充全量最严重；
    - count 不可解析（脏值/缺失）→ 无法核验 items 是否全量，「可用清单里逾期最久…」限定，不冒充全量最严重；
    - 部分批次交期/完工时间无法解析 →「可解析批次里…」/「基于前 N 条中可解析的…」标注；
    - 全部无法解析（无可定位最久）→ 明示「暂不能判断逾期最久」，不静默退回笼统句掩盖。"""
    payload = _overdue_payload(latest_summary)
    if payload is None:
        return fallback_impact
    count = _overdue_count_value(payload)
    items = payload.get("items")
    count_text = f"{count} 个批次会晚于交期" if count is not None else "有批次会晚于交期"
    if not isinstance(items, list) or not items:
        return count_text
    worst = _worst_overdue(items)
    incomplete = worst["unparseable"] > 0
    truncated = count is not None and count > len(items)
    if not worst["batch_id"]:
        # 无可定位「最久」：若因解析失败则诚实说明无法判断，否则回笼统句
        if incomplete:
            return f"{count_text}（部分批次的交期或完工时间无法解析，暂不能判断逾期最久）"
        return count_text
    duration = _format_delta(worst["delta"])
    if truncated:
        scope = f"基于前 {len(items)} 条中可解析的" if incomplete else f"基于前 {len(items)} 条"
        return f"{count_text} · {scope}看，逾期最久 {worst['batch_id']} 晚 {duration}"
    if count is None:
        # count 脏值/缺失：无法核验 items 是否被裁剪过，不能用绝对口吻报「全量最严重」，
        # 限定到「可用清单里」；若同时有解析失败，再叠加「可解析批次中」标注。
        lead = "可用清单里可解析批次中逾期最久" if incomplete else "可用清单里逾期最久"
        return f"{count_text} · {lead} {worst['batch_id']} 晚 {duration}"
    if incomplete:
        return f"{count_text} · 可解析批次里逾期最久 {worst['batch_id']} 晚 {duration}"
    return f"{count_text} · 逾期最久 {worst['batch_id']} 晚 {duration}"


def _hero(
    *,
    mode: str,
    severity: str,
    title: str,
    impact_text: str,
    evidence_text: str,
    primary_action: Optional[Dict[str, Any]],
    secondary_action: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "mode": mode,
        "severity": severity,
        "title": title,
        "impact_text": impact_text,
        "evidence_text": evidence_text,
        "primary_action": primary_action,
        "secondary_action": secondary_action,
    }


def _failed_hero(context: Dict[str, Any]) -> Dict[str, Any]:
    return _hero(
        mode="failed",
        severity="danger",
        title=_FAILED_TITLE,
        impact_text="当前最新正式排产版本的结果是失败，下方摘要暂不可信，建议重新执行一次排产。",
        evidence_text="根据当前最新正式排产版本的结果状态判断。",
        primary_action=_link(context, "batches", "去执行排产"),
        secondary_action=_link(context, "history", "查看排产历史"),
    )


def _risk_hero(first_todo: Dict[str, Any], latest_summary: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    impact = _text(first_todo.get("impact_text"))
    if _text(first_todo.get("kind")) == "overdue":
        impact = _overdue_hero_impact(latest_summary, impact)
    return _hero(
        mode="risk",
        severity=_text(first_todo.get("severity")) or "warning",
        title=_text(first_todo.get("title")),
        impact_text=impact,
        evidence_text=_text(first_todo.get("evidence_text")),
        primary_action=first_todo.get("primary_action"),
        secondary_action=first_todo.get("secondary_action"),
    )


def _calm_hero(empty_state: str) -> Dict[str, Any]:
    return _hero(
        mode="calm",
        severity="ok",
        title=_CALM_TITLE,
        impact_text=_text(empty_state) or _CALM_TITLE,
        evidence_text="",
        primary_action=None,
        secondary_action=None,
    )


def build_cockpit_hero(
    *,
    context: Dict[str, Any],
    todo_items: List[Dict[str, Any]],
    latest_summary: Optional[Dict[str, Any]],
    result_status: Any,
    failed_run_applies_to_current_view: bool,
    empty_state: str,
) -> Dict[str, Any]:
    """返回 {"hero": {...}, "rest_todos": [...]}。

    失败态 hero 为 hero-only 合成物（不进 todo_items、rest=todo_items 全量）；
    风险态 hero=todo_items[0]（title 原样、rest=[1:]）；平静态无 todo（rest=[]）。
    """
    items = list(todo_items or [])
    if failed_run_applies_to_current_view and resolve_result_status(result_status) == "failed":
        return {"hero": _failed_hero(context), "rest_todos": items}
    if items:
        return {"hero": _risk_hero(items[0], latest_summary), "rest_todos": items[1:]}
    return {"hero": _calm_hero(empty_state), "rest_todos": []}


__all__ = ["build_cockpit_hero"]
