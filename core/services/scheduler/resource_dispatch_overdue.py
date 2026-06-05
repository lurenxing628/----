from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


def _text(value: Any) -> str:
    return str(value or "").strip()


def _overdue_meta() -> Dict[str, Any]:
    return {
        "ids": [],
        "degraded": False,
        "partial": False,
        "message": "",
        "reason": "",
    }


def _mark_overdue_degraded(meta: Dict[str, Any], *, reason: str, message: str) -> None:
    meta["degraded"] = True
    meta["message"] = message
    meta["reason"] = reason


def _load_result_summary_payload(result_summary: Any, meta: Dict[str, Any]) -> Any:
    if not result_summary:
        _mark_overdue_degraded(
            meta,
            reason="result_summary_missing",
            message="排产摘要缺失，超期统计和标记可能不完整。",
        )
        return None
    try:
        return result_summary if isinstance(result_summary, dict) else json.loads(result_summary or "{}")
    except Exception as exc:
        _mark_overdue_degraded(
            meta,
            reason=f"result_summary_json:{exc.__class__.__name__}",
            message="排产摘要读取失败，超期统计和标记可能不完整。",
        )
        return None


def _extract_overdue_items(payload: Any, meta: Dict[str, Any]) -> Optional[Sequence[Any]]:
    overdue = payload.get("overdue_batches")
    if overdue is None:
        _mark_overdue_degraded(
            meta,
            reason="overdue_batches_missing",
            message="排产摘要缺少超期清单，超期统计和标记可能不完整。",
        )
        return None
    if isinstance(overdue, dict):
        overdue = overdue.get("items")
        if overdue is None:
            _mark_overdue_degraded(
                meta,
                reason="overdue_items_missing",
                message="排产摘要的超期清单明细缺失，超期统计和标记可能不完整。",
            )
            return None
    if not isinstance(overdue, Sequence) or isinstance(overdue, (str, bytes, bytearray)):
        _mark_overdue_degraded(
            meta,
            reason="overdue_batches_invalid_type",
            message="排产摘要的超期清单格式不正确，超期统计和标记可能不完整。",
        )
        return None
    return overdue


def _overdue_item_text(item: Any) -> str:
    if isinstance(item, dict):
        return _text(item.get("batch_id") or item.get("id") or item.get("value"))
    return _text(item)


def _collect_overdue_ids(overdue: Sequence[Any]) -> Tuple[List[str], int]:
    result: List[str] = []
    seen: Set[str] = set()
    invalid_items = 0
    for item in overdue:
        text = _overdue_item_text(item)
        if text:
            if text not in seen:
                seen.add(text)
                result.append(text)
        else:
            invalid_items += 1
    return result, invalid_items


def _mark_overdue_item_quality(meta: Dict[str, Any], *, invalid_items: int, result: Sequence[str]) -> None:
    if invalid_items > 0 and result:
        meta["partial"] = True
        meta["message"] = "排产摘要中的部分超期明细格式不正确，当前仅按已识别条目标记，结果可能仍有遗漏。"
        meta["reason"] = "overdue_item_partial"
    elif invalid_items > 0:
        _mark_overdue_degraded(
            meta,
            reason="overdue_item_invalid",
            message="排产摘要中的超期明细格式不正确，无法识别超期批次，超期统计和标记可能不完整。",
        )


def extract_overdue_batch_ids_with_meta(result_summary: Any) -> Dict[str, Any]:
    meta = _overdue_meta()
    payload = _load_result_summary_payload(result_summary, meta)
    if payload is None:
        return meta
    overdue = _extract_overdue_items(payload, meta)
    if overdue is None:
        return meta
    result, invalid_items = _collect_overdue_ids(overdue)
    _mark_overdue_item_quality(meta, invalid_items=invalid_items, result=result)
    meta["ids"] = result
    return meta


def extract_overdue_batch_ids(result_summary: Any) -> Set[str]:
    meta = extract_overdue_batch_ids_with_meta(result_summary)
    result: Set[str] = set()
    for item in meta.get("ids") or []:
        text = _text(item)
        if text:
            result.add(text)
    return result
