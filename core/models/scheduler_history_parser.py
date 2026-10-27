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


def _unreadable_summary() -> NoReturn:
    raise ValueError("排产摘要不是严格的 JSON。")


def _non_finite_summary() -> NoReturn:
    raise NonFiniteSummaryNumber("排产摘要包含非有限数字。")


def parse_result_summary_payload(raw_summary: Any) -> ResultSummaryParseResult:
    """Parse one stored ``result_summary`` column value (TEXT, or NULL when absent)."""
    if raw_summary is None or raw_summary == "":
        return ResultSummaryParseResult(
            payload=None,
            parse_failed=False,
            reason="missing",
        )

    if not isinstance(raw_summary, str):
        return ResultSummaryParseResult(
            payload=None,
            parse_failed=True,
            reason="invalid_structure",
        )

    try:
        # 重复键按解析失败计；非有限数字（含溢出成无穷的数字）单独记原因。
        parsed = load_strict_json(raw_summary, on_malformed=_unreadable_summary, on_nonfinite=_non_finite_summary)
    except NonFiniteSummaryNumber:
        return ResultSummaryParseResult(
            payload=None,
            parse_failed=True,
            reason="non_finite_number",
        )
    except ValueError:
        return ResultSummaryParseResult(
            payload=None,
            parse_failed=True,
            reason="json_decode_error",
        )

    if type(parsed) is not dict:
        return ResultSummaryParseResult(
            payload=None,
            parse_failed=True,
            reason="invalid_structure",
        )

    return ResultSummaryParseResult(
        payload=parsed,
        parse_failed=False,
        reason="json",
    )


__all__ = ["NonFiniteSummaryNumber", "ResultSummaryParseResult", "parse_result_summary_payload"]
