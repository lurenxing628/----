"""Adapt a batch's frozen context to scheduling; never query live templates."""

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from core.errors import BusinessError, ErrorCode, ValidationError
from core.models import ExternalGroup, PartOperation
from core.services.scheduler.contracts.external_context import (
    context_group_key,
    member_index,
    merged_supplier_problem,
    require_context,
)
from data.repositories.batch_external_context_repo import BatchExternalContextRepository


@dataclass(frozen=True)
class FrozenExternalContext:
    row: Mapping[str, Any]
    group_key: Optional[str]


def _stored_context(svc, operation_id, *, cache: Dict[str, Any]):
    if "external_contexts" in cache:
        return cache["external_contexts"].get(operation_id)
    repo = BatchExternalContextRepository(svc.conn)
    if not repo.available():
        raise ValidationError("批次外协周期记录尚未安装，请完成统一版本升级后再排产。", field="external_context")
    return repo.get(operation_id)


def verified_external_context_for_op(svc, op: Any) -> FrozenExternalContext:
    cache = getattr(svc, "_aps_schedule_input_cache", None)
    if not isinstance(cache, dict):
        cache = {}
        svc._aps_schedule_input_cache = cache
    batches = cache.setdefault("batch", {})
    batch = batches.get(op.batch_id)
    if batch is None:
        batch = svc.batch_repo.get(op.batch_id)
        if batch is None:
            raise BusinessError(ErrorCode.BATCH_NOT_FOUND, f"批次“{op.batch_id}”不存在")
        batches[op.batch_id] = batch
    row = require_context(_stored_context(svc, op.id, cache=cache), operation_id=op.id,
                          part_no=batch.part_no, sequence=op.seq)
    group_key = context_group_key(row)
    if row["merge_mode"] == "merged":
        key = (op.batch_id, group_key, getattr(op, "piece_id", None))
        checks = cache.setdefault("external_members", {})
        if key not in checks and not cache.get("external_contexts_bound"):
            members = BatchExternalContextRepository(svc.conn).group_members(op.batch_id, row["group_ref"], key[2])
            current = [dict(id=m["operation_id"], batch_id=op.batch_id, piece_id=key[2], seq=m["current_sequence"],
                            source=m["current_source"], supplier_id=m["current_supplier_id"]) for m in members]
            checks.update(member_index({m["operation_id"]: m for m in members}, current))
        problem = merged_supplier_problem(row, getattr(op, "supplier_id", None), checks.get(key))
        if problem:
            raise ValidationError(problem, field="external_context")
    return FrozenExternalContext(row, group_key)


def get_template_and_group_for_op(svc, op):
    """Adapt verified frozen facts to the template-shaped scheduling view."""
    facts = verified_external_context_for_op(svc, op)
    row, group_key = facts.row, facts.group_key
    # The permanent group identity prevents a reused business code merging unrelated groups.
    template = PartOperation(id=row["template_operation_id"], part_no=row["part_no"], seq=row["sequence"],
                             source="external", ext_group_id=group_key, status=row["template_status"])
    group = None
    if group_key is not None:
        group = ExternalGroup(group_id=group_key, part_no=row["group_part_no"],
                              start_seq=row["start_sequence"], end_seq=row["end_sequence"],
                              merge_mode=row["merge_mode"], total_days=row["total_days"],
                              supplier_id=row["supplier_id"], created_at=row["captured_at"])
    return template, group
