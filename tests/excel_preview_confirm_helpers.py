from __future__ import annotations

import re
from html import unescape as html_unescape
from typing import Any, Dict, Iterable, Optional


def extract_raw_rows_json(html: str) -> str:
    match = re.search(r'<textarea name="raw_rows_json"[^>]*>(.*?)</textarea>', html, re.S)
    if not match:
        raise RuntimeError("未能从预览页面提取 raw_rows_json（确认导入需要该字段）")
    return html_unescape(match.group(1)).strip()


def extract_hidden_input(html: str, name: str) -> str:
    for match in re.finditer(r"<input[^>]+>", html, re.I):
        tag = match.group(0)
        if re.search(rf'name=["\']{re.escape(name)}["\']', tag, re.I):
            value_match = re.search(r'value=["\']([^"\']*)["\']', tag, re.I)
            value = value_match.group(1) if value_match else ""
            return html_unescape(value).strip()
    return ""


def require_preview_baseline(html: str, context: str) -> str:
    preview_baseline = extract_hidden_input(html, "preview_baseline")
    if not preview_baseline:
        raise RuntimeError(f"{context} 预览页面缺少 preview_baseline")
    return preview_baseline


def build_confirm_payload(
    preview_html: str,
    *,
    mode: str,
    filename: str,
    context: str,
    confirm_extra: Optional[Dict[str, Any]] = None,
    confirm_hidden_fields: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "mode": mode,
        "filename": filename,
        "raw_rows_json": extract_raw_rows_json(preview_html),
        "preview_baseline": require_preview_baseline(preview_html, context),
    }
    for field_name in confirm_hidden_fields or []:
        hidden_value = extract_hidden_input(preview_html, str(field_name))
        if hidden_value != "":
            payload[str(field_name)] = hidden_value
    if confirm_extra:
        payload.update(dict(confirm_extra))
    return payload


__all__ = [
    "build_confirm_payload",
    "extract_hidden_input",
    "extract_raw_rows_json",
    "require_preview_baseline",
]
