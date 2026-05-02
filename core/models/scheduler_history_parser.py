from __future__ import annotations

import json
from dataclasses import dataclass
from json import JSONDecodeError
from typing import Any, Dict, Optional


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


def parse_result_summary_payload(raw_summary: Any) -> ResultSummaryParseResult:
    if raw_summary is None or raw_summary == "":
        return ResultSummaryParseResult(
            payload=None,
            parse_failed=False,
            reason="missing",
            raw_type=type(raw_summary).__name__,
        )

    if isinstance(raw_summary, dict):
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
        parsed = json.loads(raw_summary)
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

    return ResultSummaryParseResult(
        payload=parsed,
        parse_failed=False,
        reason="json",
        raw_type="str",
    )


__all__ = ["ResultSummaryParseResult", "parse_result_summary_payload"]
