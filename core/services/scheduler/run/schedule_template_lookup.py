from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import ValidationError
from core.models import Batch, BatchOperation, ExternalGroup, PartOperation
from core.shared.degradation import DegradationCollector, DegradationEvent


@dataclass
class TemplateGroupLookupOutcome:
    template: Optional[PartOperation]
    group: Optional[ExternalGroup]
    merge_context_degraded: bool = False
    events: List[DegradationEvent] = field(default_factory=list)


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


def _lookup_scope(op: BatchOperation, scope: Optional[str]) -> str:
    if scope:
        return str(scope)
    op_id = getattr(op, "id", None)
    if op_id not in (None, ""):
        return f"schedule_input.op[{op_id}]"
    batch_id = str(getattr(op, "batch_id", "") or "").strip() or "?"
    seq = int(getattr(op, "seq", 0) or 0)
    return f"schedule_input.batch[{batch_id}].seq[{seq}]"


def _template_missing_outcome(
    *,
    strict_mode: bool,
    collector: DegradationCollector,
    event_scope: str,
    op_code: str,
    batch_id: str,
    part_no: str,
    seq: int,
) -> TemplateGroupLookupOutcome:
    message = f"外协工序 {op_code} 缺少模板工序（batch={batch_id}, part={part_no or '?'}，seq={seq}），组合并语义已退化。"
    if strict_mode:
        raise ValidationError(message, field="template")
    collector.add(
        code="template_missing",
        scope=event_scope,
        field="template",
        message=message,
        sample=f"batch_id={batch_id},part_no={part_no or '?'},seq={seq}",
    )
    return TemplateGroupLookupOutcome(None, None, True, collector.to_list())


def _template_ext_group_id(tmpl: PartOperation) -> str:
    return str(getattr(tmpl, "ext_group_id", None) or "").strip()


def _external_group_missing_outcome(
    *,
    strict_mode: bool,
    collector: DegradationCollector,
    event_scope: str,
    tmpl: PartOperation,
    ext_group_id: str,
    op_code: str,
    batch_id: str,
    seq: int,
) -> TemplateGroupLookupOutcome:
    message = f"外协工序 {op_code} 引用的外部组 {ext_group_id} 不存在（batch={batch_id}, seq={seq}），组合并语义已退化。"
    if strict_mode:
        raise ValidationError(message, field="ext_group_id")
    collector.add(
        code="external_group_missing",
        scope=event_scope,
        field="ext_group_id",
        message=message,
        sample=f"batch_id={batch_id},ext_group_id={ext_group_id},seq={seq}",
    )
    return TemplateGroupLookupOutcome(tmpl, None, True, collector.to_list())


def lookup_template_group_context_for_op(
    svc: Any,
    op: BatchOperation,
    *,
    strict_mode: bool = False,
    scope: Optional[str] = None,
) -> TemplateGroupLookupOutcome:
    collector = DegradationCollector()
    event_scope = _lookup_scope(op, scope)

    cache = getattr(svc, "_aps_schedule_input_cache", None)
    batch_cache = tmpl_cache = grp_cache = None
    if isinstance(cache, dict):
        batch_cache = _ensure_dict_bucket(cache, "batch")
        tmpl_cache = _ensure_dict_bucket(cache, "tmpl")
        grp_cache = _ensure_dict_bucket(cache, "grp")

    batch = _get_batch_cached(svc, batch_cache, op.batch_id)
    seq = int(getattr(op, "seq", 0) or 0)
    op_code = str(getattr(op, "op_code", "") or "").strip() or "-"
    batch_id = str(getattr(op, "batch_id", "") or "").strip() or "?"
    part_no = str(getattr(batch, "part_no", "") or "").strip()

    tmpl = _get_template_cached(svc, tmpl_cache, part_no=part_no, seq=seq)
    if not tmpl:
        return _template_missing_outcome(
            strict_mode=bool(strict_mode),
            collector=collector,
            event_scope=event_scope,
            op_code=op_code,
            batch_id=batch_id,
            part_no=part_no,
            seq=seq,
        )

    ext_group_id = _template_ext_group_id(tmpl)
    if not ext_group_id:
        return TemplateGroupLookupOutcome(tmpl, None, False, collector.to_list())

    grp = _get_group_cached(svc, grp_cache, ext_group_id)
    if grp is None:
        return _external_group_missing_outcome(
            strict_mode=bool(strict_mode),
            collector=collector,
            event_scope=event_scope,
            tmpl=tmpl,
            ext_group_id=ext_group_id,
            op_code=op_code,
            batch_id=batch_id,
            seq=seq,
        )

    return TemplateGroupLookupOutcome(tmpl, grp, False, collector.to_list())


def get_template_and_group_for_op(
    svc: Any,
    op: BatchOperation,
) -> Tuple[Optional[PartOperation], Optional[ExternalGroup]]:
    """
    通过 Batch.part_no + op.seq 回查“零件模板工序”与“外部组”信息。

    说明：BatchOperations 表不存 ext_group_id，因此这里以模板为事实来源。
    """
    outcome = lookup_template_group_context_for_op(svc, op)
    return outcome.template, outcome.group
