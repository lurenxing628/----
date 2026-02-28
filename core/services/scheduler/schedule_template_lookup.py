from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core.models import Batch, BatchOperation, ExternalGroup, PartOperation


def _ensure_dict_bucket(cache: Dict[str, Any], key: str) -> Dict[Any, Any]:
    bucket = cache.get(key)
    if isinstance(bucket, dict):
        return bucket
    bucket = {}
    cache[key] = bucket
    return bucket


def _get_batch_cached(svc: Any, batch_cache: Optional[Dict[str, Any]], batch_id: str) -> Batch:
    bid = (str(batch_id or "")).strip()
    if batch_cache is not None and bid:
        cached = batch_cache.get(bid)
        if cached is not None:
            return cached
    b = svc._get_batch_or_raise(batch_id)
    if batch_cache is not None and bid:
        batch_cache[bid] = b
    return b


def _get_template_cached(
    svc: Any,
    tmpl_cache: Optional[Dict[Any, Any]],
    *,
    part_no: str,
    seq: int,
) -> Optional[PartOperation]:
    key = (str(part_no or ""), int(seq))
    if tmpl_cache is not None and key in tmpl_cache:
        return tmpl_cache.get(key)
    tmpl = svc.part_op_repo.get(part_no, int(seq))
    if tmpl_cache is not None:
        tmpl_cache[key] = tmpl
    return tmpl


def _get_group_cached(
    svc: Any,
    grp_cache: Optional[Dict[str, Any]],
    ext_group_id: Any,
) -> Optional[ExternalGroup]:
    gid = (str(ext_group_id or "")).strip()
    if not gid:
        return None
    if grp_cache is not None and gid in grp_cache:
        return grp_cache.get(gid)
    grp = svc.group_repo.get(gid)
    if grp_cache is not None:
        grp_cache[gid] = grp
    return grp


def get_template_and_group_for_op(
    svc: Any,
    op: BatchOperation,
) -> Tuple[Optional[PartOperation], Optional[ExternalGroup]]:
    """
    通过 Batch.part_no + op.seq 回查“零件模板工序”与“外部组”信息。

    说明：BatchOperations 表不存 ext_group_id，因此这里以模板为事实来源。
    """
    cache = getattr(svc, "_aps_schedule_input_cache", None)
    batch_cache = tmpl_cache = grp_cache = None
    if isinstance(cache, dict):
        batch_cache = _ensure_dict_bucket(cache, "batch")
        tmpl_cache = _ensure_dict_bucket(cache, "tmpl")
        grp_cache = _ensure_dict_bucket(cache, "grp")

    batch = _get_batch_cached(svc, batch_cache, op.batch_id)
    seq = int(getattr(op, "seq", 0) or 0)
    tmpl = _get_template_cached(svc, tmpl_cache, part_no=str(getattr(batch, "part_no", "") or ""), seq=seq)
    if not tmpl:
        return None, None
    if not getattr(tmpl, "ext_group_id", None):
        return tmpl, None
    grp = _get_group_cached(svc, grp_cache, getattr(tmpl, "ext_group_id", None))
    return tmpl, grp

