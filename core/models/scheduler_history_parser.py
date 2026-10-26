from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, NoReturn, Optional

from core.shared.strict_json import load_strict_json


class NonFiniteSummaryNumber(ValueError):
    """排产摘要里包含 JSON 不支持的非有限数字。"""


@dataclass(frozen=True)
class ResultSummaryParseResult:
    payload: Optional[Dict[str, Any]]
    parse_failed: bool
    reason: str
    raw_type: str


def _unreadable_summary() -> NoReturn:
    raise ValueError("排产摘要不是严格的 JSON。")


def _non_finite_summary() -> NoReturn:
    raise NonFiniteSummaryNumber("排产摘要包含非有限数字。")


def _has_non_finite_number(value: Any) -> bool:
    # 只给已解码的 dict 用：unpacked 会把无损保存的 {"$sqlite_real": "inf"} 还原成真正的非有限数。
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, dict):
        return any(_has_non_finite_number(child) for child in value.values())
    if isinstance(value, (list, tuple)):
        return any(_has_non_finite_number(child) for child in value)
    return False


def _non_finite_result(raw_type: str) -> ResultSummaryParseResult:
    return ResultSummaryParseResult(
        payload=None,
        parse_failed=True,
        reason="non_finite_number",
        raw_type=raw_type,
    )


def parse_result_summary_payload(raw_summary: Any) -> ResultSummaryParseResult:
    if raw_summary is None or raw_summary == "":
        return ResultSummaryParseResult(
            payload=None,
            parse_failed=False,
            reason="missing",
            raw_type=type(raw_summary).__name__,
        )

    if isinstance(raw_summary, dict):
        if _has_non_finite_number(raw_summary):
            return _non_finite_result("dict")
        return ResultSummaryParseResult(
            payload=raw_summary,
            parse_failed=False,
            reason="dict",
            raw_type="dict",
        )

    if isinstance(raw_summary, list):
        return ResultSummaryParseResult(
            payload=None,
            parse_failed=True,
            reason="invalid_structure",
            raw_type="list",
        )

    if not isinstance(raw_summary, str):
        return ResultSummaryParseResult(
            payload=None,
            parse_failed=True,
            reason="invalid_structure",
            raw_type=type(raw_summary).__name__,
        )

    try:
        # 重复键按解析失败计；非有限数字（含溢出成无穷的数字）单独记原因。
        parsed = load_strict_json(raw_summary, on_malformed=_unreadable_summary, on_nonfinite=_non_finite_summary)
    except NonFiniteSummaryNumber:
        return _non_finite_result("str")
    except ValueError:
        return ResultSummaryParseResult(
            payload=None,
            parse_failed=True,
            reason="json_decode_error",
            raw_type="str",
        )

    if type(parsed) is not dict:
        return ResultSummaryParseResult(
            payload=None,
            parse_failed=True,
            reason="invalid_structure",
            raw_type=type(parsed).__name__,
        )

    return ResultSummaryParseResult(
        payload=parsed,
        parse_failed=False,
        reason="json",
        raw_type="str",
    )


__all__ = ["NonFiniteSummaryNumber", "ResultSummaryParseResult", "parse_result_summary_payload"]
