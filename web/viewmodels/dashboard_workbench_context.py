from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, Optional, Tuple

from .scheduler_workbench_links import FULL_PLAN_GUARD_FIELDS, ROLE_ADOPTED, build_workbench_plan_context


def _text(value: Any) -> str:
    return str(value or "").strip()


def _date_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    text = _text(value).replace("/", "-").replace("T", " ")
    if not text:
        return ""
    # 整串匹配验证全串是合法日期/时间后再取日期部分；坏后缀（"2026-06-01 08:00:00xyz"）整串解析失败
    # 返回 ""，不截前缀冒充合法日期（与 _parse_dt/_parse_datetime 同口径；否则会与 data_gap 的严格
    # 日期校验自相矛盾——一边判「缺少日期范围」、一边又截出日期进 context_summary 与链接）。
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


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


def _filter_text(filters: Dict[str, Any], key: str) -> str:
    return _text(filters.get(key))


def _first_filter_text(filters: Dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        text = _filter_text(filters, key)
        if text:
            return text
    return ""


def _filter_or_none(filters: Dict[str, Any], keys: Iterable[str], fallback: Any = None) -> Any:
    text = _first_filter_text(filters, keys)
    if text:
        return text
    return fallback if fallback else None


def _context_kwargs(
    filters: Dict[str, Any], *, version: Optional[int], date_from: str, date_to: str, plan_time_span_load_error: str
) -> Dict[str, Any]:
    effective_version = _filter_or_none(filters, ("version",), version)
    date_from_value = date_from if plan_time_span_load_error else _filter_or_none(filters, ("date_from",), date_from)
    date_to_value = date_to if plan_time_span_load_error else _filter_or_none(filters, ("date_to",), date_to)
    return {
        "version": effective_version,
        "plan_role": _filter_or_none(filters, ("requested_plan_role", "plan_role"), ROLE_ADOPTED),
        "plan_role_label_value": _filter_or_none(filters, ("plan_identity_label", "requested_plan_role_label"), ""),
        "scenario_id": _filter_or_none(filters, ("scenario_id",)),
        "plan_context_token": _filter_or_none(filters, ("plan_context_token",)),
        "scenario_display_label": _filter_text(filters, "scenario_display_name"),
        "date_from": date_from_value,
        "date_to": date_to_value,
        "query_date": _filter_or_none(filters, ("query_date",)),
        "period_preset": _filter_or_none(filters, ("period_preset",)),
        "batch_id": _filter_or_none(filters, ("batch_id",)),
        "resource_type": _filter_or_none(filters, ("resource_type",)),
        "resource_id": _filter_or_none(filters, ("resource_id",)),
        "resource_label": _filter_text(filters, "resource_label"),
        "back_to": _filter_or_none(filters, ("back_to",)),
        "can_write_feedback": filters.get("can_write_feedback") if "can_write_feedback" in filters else False,
        "plan_resolution": filters,
        "plan_guard_fields": FULL_PLAN_GUARD_FIELDS,
    }


def latest_plan_context(
    *,
    latest_history: Any,
    plan_time_span: Optional[Dict[str, Any]],
    plan_time_span_load_error: str = "",
    navigation_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    date_from, date_to = _plan_dates(plan_time_span)
    filters = dict(navigation_context or {})
    kwargs = _context_kwargs(
        filters,
        version=_version_value(latest_history),
        date_from=date_from,
        date_to=date_to,
        plan_time_span_load_error=_text(plan_time_span_load_error),
    )
    # 壳层胶囊喂参（4.2）：raw 值进合同，label 转换只在合同内一处。
    # 本函数是 dashboard 第二次发布（后写覆盖第一次）的 context 构造处——
    # 喂参必须落这里，否则首页胶囊被覆盖成"-"
    if latest_history is not None:
        kwargs["generated_at"] = getattr(latest_history, "schedule_time", None)
        kwargs["strategy"] = getattr(latest_history, "strategy", None)
    context = build_workbench_plan_context(**kwargs)
    if _text(plan_time_span_load_error):
        context["plan_time_span_load_error"] = _text(plan_time_span_load_error)
    return context


__all__ = ["latest_plan_context"]
