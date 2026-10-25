"""Fixed native inputs owned by one scheduling operation or search session."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithm_runtime.checkpoint_calendar import checkpoint_calendar_signature
from core.algorithm_runtime.checkpoint_inputs import input_record, input_value
from core.algorithm_runtime.piece_input import operation_batch
from core.algorithm_runtime.resource_demand import ResourceClaim
from core.errors import ValidationError


@dataclass
class NativeSchedulePreparation:
    normalized_machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]]
    calendar: Any
    run_context: Any
    operations: Any
    records_by_token: Dict[int, Any]
    batches: Any
    seed_results: Any
    seed_applications: Any
    seed_external_group_cache: Dict[Any, Any]
    seed_op_ids: Any
    unseeded_operations: Any
    resource_pool: Any
    graph_ready_context: Any
    warnings: Tuple[str, ...]
    algo_stats: Dict[str, Any]
    plain_classes: Dict[type, bool]
    topology: Any
    score_cache_factory: Any = None
    resource_candidates: Dict[Any, Any] = field(default_factory=dict)
    resource_claims: Dict[int, Any] = field(default_factory=dict)
    piece_batches: Dict[int, Any] = field(default_factory=dict)
    pruning_records: Dict[int, bool] = field(default_factory=dict)
    total_hours_by_op_id: Dict[int, float] = field(default_factory=dict)
    _variant_operations: List[Any] = field(default_factory=list)
    _calendar_signature: Any = field(init=False, repr=False, default=None)
    _checkpoint_parts: Any = field(init=False, repr=False, default=None)

    def operation_batch(self, op: Any, batch: Any) -> Any:
        piece = getattr(op, "piece_id", None)
        if piece is None:
            return batch
        if type(piece) is not str or not piece or piece.strip() != piece:
            raise ValidationError("Piece identity must be canonical.", field="piece_id")
        token = id(batch)
        if token not in self.piece_batches:
            self.piece_batches[token] = operation_batch(op, batch)
        return self.piece_batches[token]

    def resource_candidates_for(self, op: Any) -> Any:
        from .auto_assign import fixed_resource_inputs, prepare_resource_candidates
        key = fixed_resource_inputs(op)
        if key not in self.resource_candidates:
            self.resource_candidates[key] = prepare_resource_candidates(op, self.resource_pool)
        return self.resource_candidates[key]

    def qualified_resource_pairs(self, op: Any) -> Any:
        return self.resource_candidates_for(op).pairs

    def eligible_auto_assign_resources(self, op: Any) -> Any:
        return self.resource_candidates_for(op).eligible_resources

    def resource_claim_for(self, op: Any) -> Any:
        token = id(op)
        if token in self.resource_claims:
            return self.resource_claims[token]
        claim = None
        if self.plain_classes.get(type(op), False):
            values = vars(op)
            op_id, batch_id, piece = values.get("id"), values.get("batch_id"), values.get("piece_id")
            source = str(values.get("source", "internal") or "internal").strip().lower()
            if (type(op_id) is int and op_id > 0 and type(batch_id) in (str, int) and batch_id
                    and source == "internal" and (piece is None or (type(piece) is str and piece and piece.strip() == piece))):
                try:
                    pairs = frozenset(self.qualified_resource_pairs(op))
                except ValidationError:
                    # Reservation hints do not admit bad input; the real assignment reports it at its original use.
                    return None
                claim = ResourceClaim(token, op_id, str(batch_id).strip(), (str(batch_id).strip(), piece), pairs,
                                      Counter(mid for mid, _ in pairs), Counter(oid for _, oid in pairs))
        if token in self.records_by_token:
            self.resource_claims[token] = claim
        return claim

    def register_operation_variant(self, base_op: Any, variant_op: Any) -> None:
        base_token = id(base_op)
        variant_token = id(variant_op)
        self.records_by_token[variant_token] = variant_op
        if base_token in self.pruning_records:
            from .dispatch.sgs_priority_pruning import prepare_pruning_record
            self.pruning_records[variant_token] = prepare_pruning_record(variant_op, self.plain_classes)
        if self._checkpoint_parts is not None:
            self._checkpoint_parts["operations"][variant_token] = input_record(variant_op, field="operations")
        else:
            self._variant_operations.append(variant_op)
        self.resource_claim_for(variant_op)

    def checkpoint_calendar_component(self) -> Tuple[Any, ...]:
        if self._calendar_signature is None:
            self._calendar_signature = input_value(checkpoint_calendar_signature(self.calendar), field="calendar_signature")
        return self._calendar_signature

    def checkpoint_fixed_parts(self) -> Dict[str, Any]:
        """Encode fixed checkpoint records lazily; ordinary full decodes never need them."""
        if self._checkpoint_parts is None:
            from .dispatch.sgs_checkpoint import seed_signature
            self._checkpoint_parts = {
                "operations": {
                    id(op): input_record(op, field="operations")
                    for op in list(self.unseeded_operations) + self._variant_operations
                },
                "batches": tuple((key, input_record(batch, field="batches")) for key, batch in self.batches.items()),
                "downtimes": input_value(self.normalized_machine_downtimes, field="machine_downtimes"),
                "resources": input_value(self.resource_pool, field="resource_pool"),
                "seeds": tuple(seed_signature(result) for result in self.seed_results or ()),
                "contexts": {},
            }
        return self._checkpoint_parts
