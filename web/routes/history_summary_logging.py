from __future__ import annotations

from typing import Any, Dict, Optional

from flask import current_app

from web.viewmodels.scheduler_history_summary import parse_history_summary_state


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


def log_history_version_option_parse_warnings(
    versions: Any,
    *,
    log_label: str,
    source: str = "version_option",
) -> None:
    for raw in list(versions or []):
        row = dict(raw or {})
        parse_state = parse_history_summary_state(row.get("result_summary"))
        log_history_summary_parse_warning(
            parse_state,
            version=row.get("version"),
            log_label=log_label,
            source=source,
        )


__all__ = ["log_history_summary_parse_warning", "log_history_version_option_parse_warnings"]
