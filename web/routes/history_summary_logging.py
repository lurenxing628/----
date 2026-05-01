from __future__ import annotations

from typing import Any, Dict, Optional

from flask import current_app


def log_history_summary_parse_warning(
    parse_state: Dict[str, Any],
    *,
    log_label: str,
    version: Any,
    source: Optional[str] = None,
) -> None:
    if not bool((parse_state or {}).get("parse_failed")):
        return

    reason = str((parse_state or {}).get("reason") or "")
    raw_type = str((parse_state or {}).get("raw_type") or "")
    issue = "解析失败" if reason == "json_decode_error" else "结构不合法"
    detail = "error=JSONDecodeError" if reason == "json_decode_error" else f"type={raw_type}"
    if source is not None:
        current_app.logger.warning(
            "%s result_summary %s（version=%s, source=%s, %s）",
            log_label,
            issue,
            version,
            source,
            detail,
        )
        return
    current_app.logger.warning("%s result_summary %s（version=%s, %s）", log_label, issue, version, detail)


__all__ = ["log_history_summary_parse_warning"]
