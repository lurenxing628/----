from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, cast

from core.infrastructure.errors import ValidationError
from core.models import Batch, BatchOperation, ExternalGroup, PartOperation
from core.models.enums import PartOperationStatus
from core.shared.degradation import DegradationCollector, DegradationEvent


@dataclass
class TemplateGroupLookupOutcome:
    template: Optional[PartOperation]
    group: Optional[ExternalGroup]
    merge_context_degraded: bool = False
    events: List[DegradationEvent] = field(default_factory=list)


@dataclass(frozen=True)
class _LookupContext:
    event_scope: str
    seq: int
    op_code: str
    batch_id: str
    part_no: str


@dataclass(frozen=True)
class _ExternalGroupViolation:
    reason: str
    sample: str


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


def _lookup_cache_buckets(
    svc: Any,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[Any, Any]], Optional[Dict[str, Any]]]:
    cache = getattr(svc, "_aps_schedule_input_cache", None)
    if not isinstance(cache, dict):
        return None, None, None
    return (
        _ensure_dict_bucket(cache, "batch"),
        _ensure_dict_bucket(cache, "tmpl"),
        _ensure_dict_bucket(cache, "grp"),
    )


def _lookup_context(
    svc: Any,
    op: BatchOperation,
    *,
    scope: Optional[str],
    batch_cache: Optional[Dict[str, Any]],
) -> _LookupContext:
    event_scope = _lookup_scope(op, scope)
    batch = _get_batch_cached(svc, batch_cache, op.batch_id)
    seq = int(getattr(op, "seq", 0) or 0)
    return _LookupContext(
        event_scope=event_scope,
        seq=seq,
        op_code=str(getattr(op, "op_code", "") or "").strip() or "-",
        batch_id=str(getattr(op, "batch_id", "") or "").strip() or "?",
        part_no=str(getattr(batch, "part_no", "") or "").strip(),
    )


def _template_missing_outcome(
    *,
    strict_mode: bool,
    collector: DegradationCollector,
    ctx: _LookupContext,
) -> TemplateGroupLookupOutcome:
    message = (
        f"外协工序 {ctx.op_code} 缺少模板工序"
        f"（batch={ctx.batch_id}, part={ctx.part_no or '?'}，seq={ctx.seq}），组合并语义已退化。"
    )
    if strict_mode:
        raise ValidationError(message, field="template")
    collector.add(
        code="template_missing",
        scope=ctx.event_scope,
        field="template",
        message=message,
        sample=f"batch_id={ctx.batch_id},part_no={ctx.part_no or '?'},seq={ctx.seq}",
    )
    return TemplateGroupLookupOutcome(None, None, True, collector.to_list())


def _template_ext_group_id(tmpl: PartOperation) -> str:
    return str(getattr(tmpl, "ext_group_id", None) or "").strip()


def _template_status(tmpl: PartOperation) -> str:
    return (
        str(getattr(tmpl, "status", None) or PartOperationStatus.ACTIVE.value).strip().lower()
        or PartOperationStatus.ACTIVE.value
    )


def _template_unavailable_outcome(
    *,
    strict_mode: bool,
    collector: DegradationCollector,
    ctx: _LookupContext,
    status: str,
) -> TemplateGroupLookupOutcome:
    message = (
        f"外协工序 {ctx.op_code} 的模板工序不可用（batch={ctx.batch_id}, part={ctx.part_no or '?'}，"
        f"seq={ctx.seq}, status={status or '?'}），组合并语义已退化。"
    )
    if strict_mode:
        raise ValidationError(message, field="template")
    collector.add(
        code="template_missing",
        scope=ctx.event_scope,
        field="template",
        message=message,
        sample=f"batch_id={ctx.batch_id},part_no={ctx.part_no or '?'},seq={ctx.seq},status={status or '?'}",
    )
    return TemplateGroupLookupOutcome(None, None, True, collector.to_list())


def _group_seq_bounds(grp: ExternalGroup) -> Optional[Tuple[int, int]]:
    try:
        start_seq = int(grp.start_seq)
        end_seq = int(grp.end_seq)
    except (AttributeError, TypeError, ValueError):
        return None
    return (min(start_seq, end_seq), max(start_seq, end_seq))


def _external_group_invalid_outcome(
    *,
    strict_mode: bool,
    collector: DegradationCollector,
    ctx: _LookupContext,
    tmpl: PartOperation,
    ext_group_id: str,
    reason: str,
    sample: str,
) -> TemplateGroupLookupOutcome:
    message = (
        f"外协工序 {ctx.op_code} 引用的外部组 {ext_group_id} 不可用于当前模板"
        f"（batch={ctx.batch_id}, part={ctx.part_no or '?'}, seq={ctx.seq}，原因：{reason}），组合并语义已退化。"
    )
    if strict_mode:
        raise ValidationError(message, field="ext_group_id")
    collector.add(
        code="external_group_missing",
        scope=ctx.event_scope,
        field="ext_group_id",
        message=message,
        sample=sample,
    )
    return TemplateGroupLookupOutcome(tmpl, None, True, collector.to_list())


def _external_group_missing_outcome(
    *,
    strict_mode: bool,
    collector: DegradationCollector,
    ctx: _LookupContext,
    tmpl: PartOperation,
    ext_group_id: str,
) -> TemplateGroupLookupOutcome:
    message = (
        f"外协工序 {ctx.op_code} 引用的外部组 {ext_group_id} 不存在"
        f"（batch={ctx.batch_id}, seq={ctx.seq}），组合并语义已退化。"
    )
    if strict_mode:
        raise ValidationError(message, field="ext_group_id")
    collector.add(
        code="external_group_missing",
        scope=ctx.event_scope,
        field="ext_group_id",
        message=message,
        sample=f"batch_id={ctx.batch_id},ext_group_id={ext_group_id},seq={ctx.seq}",
    )
    return TemplateGroupLookupOutcome(tmpl, None, True, collector.to_list())


def _lookup_active_template_context(
    svc: Any,
    *,
    tmpl_cache: Optional[Dict[Any, Any]],
    ctx: _LookupContext,
    strict_mode: bool,
    collector: DegradationCollector,
) -> TemplateGroupLookupOutcome:
    tmpl = _get_template_cached(svc, tmpl_cache, part_no=ctx.part_no, seq=ctx.seq)
    if not tmpl:
        return _template_missing_outcome(
            strict_mode=strict_mode,
            collector=collector,
            ctx=ctx,
        )
    template_status = _template_status(tmpl)
    if template_status != PartOperationStatus.ACTIVE.value:
        return _template_unavailable_outcome(
            strict_mode=strict_mode,
            collector=collector,
            ctx=ctx,
            status=template_status,
        )
    return TemplateGroupLookupOutcome(tmpl, None, False, collector.to_list())


def _template_lookup_finished(outcome: TemplateGroupLookupOutcome) -> bool:
    return outcome.template is None or outcome.merge_context_degraded


def _external_group_violation(
    grp: ExternalGroup,
    *,
    ctx: _LookupContext,
    ext_group_id: str,
) -> Optional[_ExternalGroupViolation]:
    group_part_no = str(getattr(grp, "part_no", "") or "").strip()
    if group_part_no != ctx.part_no:
        return _ExternalGroupViolation(
            reason=f"外部组图号为 {group_part_no or '?'}",
            sample=(
                f"batch_id={ctx.batch_id},part_no={ctx.part_no or '?'},"
                f"ext_group_id={ext_group_id},group_part_no={group_part_no or '?'}"
            ),
        )

    seq_bounds = _group_seq_bounds(grp)
    if seq_bounds is not None and seq_bounds[0] <= ctx.seq <= seq_bounds[1]:
        return None
    range_sample = "?" if seq_bounds is None else f"{seq_bounds[0]}..{seq_bounds[1]}"
    return _ExternalGroupViolation(
        reason=f"工序号不在外部组范围 {range_sample} 内",
        sample=f"batch_id={ctx.batch_id},ext_group_id={ext_group_id},seq={ctx.seq},group_range={range_sample}",
    )


def _lookup_external_group_context(
    svc: Any,
    *,
    grp_cache: Optional[Dict[str, Any]],
    tmpl: PartOperation,
    ctx: _LookupContext,
    strict_mode: bool,
    collector: DegradationCollector,
) -> TemplateGroupLookupOutcome:
    ext_group_id = _template_ext_group_id(tmpl)
    if not ext_group_id:
        return TemplateGroupLookupOutcome(tmpl, None, False, collector.to_list())

    grp = _get_group_cached(svc, grp_cache, ext_group_id)
    if grp is None:
        return _external_group_missing_outcome(
            strict_mode=strict_mode,
            collector=collector,
            ctx=ctx,
            tmpl=tmpl,
            ext_group_id=ext_group_id,
        )

    violation = _external_group_violation(grp, ctx=ctx, ext_group_id=ext_group_id)
    if violation is not None:
        return _external_group_invalid_outcome(
            strict_mode=strict_mode,
            collector=collector,
            ctx=ctx,
            tmpl=tmpl,
            ext_group_id=ext_group_id,
            reason=violation.reason,
            sample=violation.sample,
        )

    return TemplateGroupLookupOutcome(tmpl, grp, False, collector.to_list())


def lookup_template_group_context_for_op(
    svc: Any,
    op: BatchOperation,
    *,
    strict_mode: bool = False,
    scope: Optional[str] = None,
) -> TemplateGroupLookupOutcome:
    collector = DegradationCollector()
    batch_cache, tmpl_cache, grp_cache = _lookup_cache_buckets(svc)
    ctx = _lookup_context(svc, op, scope=scope, batch_cache=batch_cache)

    template_outcome = _lookup_active_template_context(
        svc,
        tmpl_cache=tmpl_cache,
        ctx=ctx,
        strict_mode=bool(strict_mode),
        collector=collector,
    )
    if _template_lookup_finished(template_outcome):
        return template_outcome

    return _lookup_external_group_context(
        svc,
        grp_cache=grp_cache,
        tmpl=cast(PartOperation, template_outcome.template),
        ctx=ctx,
        strict_mode=bool(strict_mode),
        collector=collector,
    )


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
