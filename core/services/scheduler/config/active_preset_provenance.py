from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence


def extract_repair_fields(reason: str) -> List[str]:
    marker = "已回写："
    if marker not in reason:
        return []
    suffix = str(reason.split(marker, 1)[1] or "").strip().rstrip("。")
    fields: List[str] = []
    for raw_field in suffix.split("、"):
        field = raw_field.strip()
        if "（" in field:
            field = field.split("（", 1)[0].strip()
        if "(" in field:
            field = field.split("(", 1)[0].strip()
        if field:
            fields.append(field)
    return fields


def repair_notice_from_reason(
    reason: str,
    *,
    hidden_repair_reason: str,
    visible_repair_reason: str,
) -> Dict[str, Any]:
    if hidden_repair_reason in reason:
        return {
            "kind": "hidden",
            "fields": extract_repair_fields(reason),
            "message": reason or hidden_repair_reason,
        }
    if visible_repair_reason in reason:
        return {
            "kind": "visible",
            "fields": [],
            "message": reason or visible_repair_reason,
        }
    return {"kind": "none", "fields": [], "message": None}


def normalize_repair_notice(notice: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(notice, dict):
        return None
    kind = str(notice.get("kind") or "").strip().lower()
    if kind not in {"visible", "hidden"}:
        return None
    fields: List[str] = []
    raw_fields = notice.get("fields")
    if isinstance(raw_fields, (list, tuple)):
        for raw_field in raw_fields:
            field = str(raw_field or "").strip()
            if field and field not in fields:
                fields.append(field)
    message = str(notice.get("message") or "").strip()
    return {
        "kind": kind,
        "fields": fields,
        "message": message or None,
    }


def active_preset_meta_payload(
    *,
    reason_code: Optional[str],
    repair_notices: Optional[Sequence[Dict[str, Any]]] = None,
    valid_reason_codes: Sequence[str],
) -> Dict[str, Any]:
    normalized_reason_code = str(reason_code or "").strip().lower() or None
    if normalized_reason_code not in set(valid_reason_codes):
        normalized_reason_code = None
    notices: List[Dict[str, Any]] = []
    for raw_notice in repair_notices or []:
        notice = normalize_repair_notice(raw_notice)
        if notice is not None:
            notices.append(notice)
    return {
        "reason_code": normalized_reason_code,
        "repair_notices": notices,
    }


def active_preset_meta_parse_warning(value: Any, *, field: str) -> Optional[Dict[str, Any]]:
    if not isinstance(value, str):
        return None
    text = str(value or "").strip()
    if not text:
        return None
    try:
        json.loads(text)
    except Exception:
        return {
            "field": field,
            "message": f"{field} 不是有效 JSON，已按历史来源信息继续显示。",
        }
    return None


def parse_active_preset_meta(
    value: Any,
    *,
    reason_fallback: Optional[str],
    valid_reason_codes: Sequence[str],
    legacy_meta_from_reason,
) -> Dict[str, Any]:
    data: Any = value
    if isinstance(data, str):
        text = str(data or "").strip()
        if text:
            try:
                data = json.loads(text)
            except Exception:
                data = None
        else:
            data = None
    if not isinstance(data, dict):
        data = {}
    meta = active_preset_meta_payload(
        reason_code=data.get("reason_code"),
        repair_notices=data.get("repair_notices"),
        valid_reason_codes=valid_reason_codes,
    )
    if meta["reason_code"] is None and not meta["repair_notices"]:
        legacy = legacy_meta_from_reason(reason_fallback)
        if legacy["reason_code"] is not None or legacy["repair_notices"]:
            return legacy
    return meta


def serialize_active_preset_meta(
    meta: Optional[Dict[str, Any]],
    *,
    valid_reason_codes: Sequence[str],
) -> str:
    payload = active_preset_meta_payload(
        reason_code=(meta or {}).get("reason_code"),
        repair_notices=(meta or {}).get("repair_notices"),
        valid_reason_codes=valid_reason_codes,
    )
    if payload["reason_code"] is None and not payload["repair_notices"]:
        return ""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


__all__ = [
    "active_preset_meta_parse_warning",
    "active_preset_meta_payload",
    "extract_repair_fields",
    "normalize_repair_notice",
    "parse_active_preset_meta",
    "repair_notice_from_reason",
    "serialize_active_preset_meta",
]
