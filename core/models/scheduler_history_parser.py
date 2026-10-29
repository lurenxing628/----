from __future__ import annotations

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


def _fail(reason: str) -> NoReturn:
    raise ValueError(reason)


def parse_result_summary_payload(raw_summary: Any) -> ResultSummaryParseResult:
    """Parse one stored ``result_summary`` column value (TEXT, or NULL when absent)."""
    if raw_summary is None or raw_summary == "":
        return ResultSummaryParseResult(None, False, "missing")
    if not isinstance(raw_summary, str):
        return ResultSummaryParseResult(None, True, "invalid_structure")
    try:
        parsed = load_strict_json(
            raw_summary,
            on_malformed=lambda: _fail("json_decode_error"),
            on_nonfinite=lambda: _fail("non_finite_number"),
            expected=dict,
            on_unexpected=lambda: _fail("invalid_structure"),
        )
    except ValueError as exc:
        return ResultSummaryParseResult(None, True, str(exc))
    return ResultSummaryParseResult(parsed, False, "json")


__all__ = ["NonFiniteSummaryNumber", "ResultSummaryParseResult", "parse_result_summary_payload"]
