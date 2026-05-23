from __future__ import annotations

import json
import math
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any, Dict, Optional


class NonFiniteSummaryNumber(ValueError):
    """排产摘要里包含 JSON 不支持的非有限数字。"""


@dataclass(frozen=True)
class ResultSummaryParseResult:
    payload: Optional[Dict[str, Any]]
    parse_failed: bool
    reason: str
    raw_type: str

    def to_parse_state(self, *, user_message: Optional[str] = None) -> Dict[str, Any]:
        return {
            "payload": self.payload,
            "parse_failed": bool(self.parse_failed),
            "user_message": user_message if self.parse_failed else None,
            "reason": self.reason,
        }


def _reject_json_non_finite_constant(value: str) -> None:
    raise NonFiniteSummaryNumber(f"排产摘要包含非有限数字：{value}")


def _has_non_finite_number(value: Any) -> bool:
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
        parsed = json.loads(raw_summary, parse_constant=_reject_json_non_finite_constant)
    except NonFiniteSummaryNumber:
        return _non_finite_result("str")
    except JSONDecodeError:
        return ResultSummaryParseResult(
            payload=None,
            parse_failed=True,
            reason="json_decode_error",
            raw_type="str",
        )

    if not isinstance(parsed, dict):
        return ResultSummaryParseResult(
            payload=None,
            parse_failed=True,
            reason="invalid_structure",
            raw_type=type(parsed).__name__,
        )

    if _has_non_finite_number(parsed):
        return _non_finite_result("str")

    return ResultSummaryParseResult(
        payload=parsed,
        parse_failed=False,
        reason="json",
        raw_type="str",
    )


__all__ = ["NonFiniteSummaryNumber", "ResultSummaryParseResult", "parse_result_summary_payload"]
