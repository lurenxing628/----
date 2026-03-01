from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def _safe_load_detail_obj(detail_raw: Any) -> Optional[Dict[str, Any]]:
    if detail_raw is None:
        return None
    s = str(detail_raw).strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def build_operation_log_view_rows(items: List[Any]) -> List[Dict[str, Any]]:
    """
    将 OperationLog model 列表转为模板可直接渲染的 dict rows：
    - 展开 detail JSON 为 detail_obj（仅 dict 才展开）
    - 解析失败/非 dict → detail_obj=None（模板会回退显示 detail 原文）
    """
    out: List[Dict[str, Any]] = []
    for it in items or []:
        try:
            d = it.to_dict() if hasattr(it, "to_dict") else (it if isinstance(it, dict) else {})
        except Exception:
            d = {}
        d["detail_obj"] = _safe_load_detail_obj(d.get("detail"))
        out.append(d)
    return out

