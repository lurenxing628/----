from __future__ import annotations

from typing import Any

from .scheduler_summary_result_state import resolve_result_status, result_status_display_labels

# 展示字典从唯一字源派生（fusion-label-single-source）；别名归一交给 resolve
_RESULT_STATUS_LABELS = result_status_display_labels()

_SUMMARY_PARSE_REASON_MESSAGES = {
    "json_decode_error": "排产摘要内容不是有效 JSON",
    "invalid_structure": "排产摘要结构不符合页面要求",
    "non_finite_number": "排产摘要里有异常数字",
    "missing": "本方案暂无排产摘要",
    "排产摘要缺失": "本方案暂无排产摘要",
    "当前排产摘要结构无法安全解析。": "当前排产摘要结构无法安全解析",
    "当前排产摘要结构无法安全解析": "当前排产摘要结构无法安全解析",
}
_SUMMARY_MISSING_REASONS = frozenset(("missing", "排产摘要缺失"))


def _text(value: Any) -> str:
    return str(value or "").strip()


def result_status_label(value: Any) -> str:
    # 未知态文案统一「有问题，需检查」（fusion-label-single-source 定版，与真源 unknown 同词）
    text = resolve_result_status(value)
    return _RESULT_STATUS_LABELS.get(text, _RESULT_STATUS_LABELS["unknown"] if text else "未记录")


def summary_parse_failure_message(value: Any) -> str:
    text = _text(value)
    if not text:
        return "当前排产摘要结构无法安全解析"
    return _SUMMARY_PARSE_REASON_MESSAGES.get(text, "当前排产摘要结构无法安全解析")


def summary_unavailable_guardrail_text(value: Any, *, blocked_action: str) -> str:
    reason = summary_parse_failure_message(value)
    action = _text(blocked_action)
    if _text(value) in _SUMMARY_MISSING_REASONS:
        return f"{reason}。页面仅展示基础历史信息，{action}。"
    return f"当前排产摘要读取失败：{reason}。页面仅展示基础历史信息，{action}。"


__all__ = ["result_status_label", "summary_parse_failure_message", "summary_unavailable_guardrail_text"]
