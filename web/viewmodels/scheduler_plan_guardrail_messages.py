from __future__ import annotations

from typing import Any

_RESULT_STATUS_LABELS = {
    "success": "成功",
    "partial": "部分成功",
    "failed": "失败",
    "simulated": "模拟排产",
    "ok": "成功",
    "fail": "失败",
    "ok2": "成功",
    "unknown": "有问题，需检查",
}

_SUMMARY_PARSE_REASON_MESSAGES = {
    "json_decode_error": "排产摘要内容不是有效 JSON",
    "invalid_structure": "排产摘要结构不符合页面要求",
    "non_finite_number": "排产摘要里有异常数字",
    "missing": "排产摘要缺失",
    "排产摘要缺失": "排产摘要缺失",
    "当前排产摘要结构无法安全解析。": "当前排产摘要结构无法安全解析",
    "当前排产摘要结构无法安全解析": "当前排产摘要结构无法安全解析",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def result_status_label(value: Any) -> str:
    text = _text(value).lower()
    return _RESULT_STATUS_LABELS.get(text, "结果状态异常" if text else "未记录")


def summary_parse_failure_message(value: Any) -> str:
    text = _text(value)
    if not text:
        return "当前排产摘要结构无法安全解析"
    return _SUMMARY_PARSE_REASON_MESSAGES.get(text, "当前排产摘要结构无法安全解析")


__all__ = ["result_status_label", "summary_parse_failure_message"]
