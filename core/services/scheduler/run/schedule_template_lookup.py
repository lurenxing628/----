"""Adapt a batch's frozen context to scheduling; never query live templates."""

from dataclasses import dataclass, field
from typing import Any, List, Optional

from core.errors import ValidationError
from core.models import ExternalGroup, PartOperation
from core.services.scheduler.contracts.external_context import (
    context_group_key,
    member_index,
    merged_supplier_problem,
    require_context,
)
from core.shared.degradation import DegradationEvent
from data.repositories.batch_external_context_repo import BatchExternalContextRepository


@dataclass
class TemplateGroupLookupOutcome:
    template: Optional[PartOperation]
    group: Optional[ExternalGroup]
    merge_context_degraded: bool = False
    events: List[DegradationEvent] = field(default_factory=list)


def _stored_context(svc, operation_id):
    cache = getattr(svc, "_aps_schedule_input_cache", None)
    if isinstance(cache, dict) and "external_contexts" in cache:
        return cache["external_contexts"].get(operation_id)
    repo = BatchExternalContextRepository(svc.conn)
    if not repo.available():
        raise ValidationError("批次外协周期记录尚未安装，请完成统一版本升级后再排产。", field="external_context")
    return repo.get(operation_id)


def lookup_template_group_context_for_op(svc, op: Any, *, strict_mode=False, scope=None):
    cache = getattr(svc, "_aps_schedule_input_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        svc._aps_schedule_input_cache = cache
    batches = cache.setdefault("batch", {})
    batch = batches.get(op.batch_id)
    if batch is None:
        batch = svc._get_batch_or_raise(op.batch_id)
        batches[op.batch_id] = batch
    row = require_context(_stored_context(svc, op.id), operation_id=op.id,
                          part_no=batch.part_no, sequence=op.seq)
    if row["merge_mode"] == "merged":
        key = (op.batch_id, context_group_key(row), getattr(op, "piece_id", None))
        checks = cache.setdefault("external_members", {})
        if key not in checks and not cache.get("external_contexts_bound"):
            members = BatchExternalContextRepository(svc.conn).group_members(op.batch_id, row["group_ref"], key[2])
            current = [dict(id=m["operation_id"], batch_id=op.batch_id, piece_id=key[2], seq=m["current_sequence"],
                            source=m["current_source"], supplier_id=m["current_supplier_id"]) for m in members]
            checks.update(member_index({m["operation_id"]: m for m in members}, current))
        problem = merged_supplier_problem(row, getattr(op, "supplier_id", None), checks.get(key))
        if problem:
            raise ValidationError(problem, field="external_context")
    # The permanent group identity prevents a reused business code merging unrelated groups.
    group_key = context_group_key(row)
    template = PartOperation(id=row["template_operation_id"], part_no=row["part_no"], seq=row["sequence"],
                             source="external", ext_group_id=group_key, status=row["template_status"])
    group = None
    if group_key is not None:
        group = ExternalGroup(group_id=group_key, part_no=row["group_part_no"],
                              start_seq=row["start_sequence"], end_seq=row["end_sequence"],
                              merge_mode=row["merge_mode"], total_days=row["total_days"],
                              supplier_id=row["supplier_id"], created_at=row["captured_at"])
    return TemplateGroupLookupOutcome(template, group)


def get_template_and_group_for_op(svc, op):
    outcome = lookup_template_group_context_for_op(svc, op)
    return outcome.template, outcome.group
