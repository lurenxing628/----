"""Compatibility exports for core.algorithm_runtime.internal_slot."""
from __future__ import annotations

from core.algorithm_runtime.internal_slot import (
    _MISSING,
    InternalSlotEstimate,
    _abort_after_result,
    _abort_result,
    _adjust_slot_start,
    _build_slot_estimate,
    _changeover_penalty,
    _coerce_legacy_hours_value,
    _estimate_attempt,
    _internal_hour_fields,
    _latest_overlap_shift_end,
    _max_shift_count,
    _raise_if_invalid_strict_number,
    _read_legacy_field,
    _resolve_efficiency,
    _resolve_total_base,
    _shifted_start,
    _slot_segments,
    _SlotAttempt,
    estimate_internal_slot,
    raise_strict_internal_hours_validation,
    validate_internal_hours,
    validate_internal_hours_for_mode,
)

__all__ = ['_MISSING', 'InternalSlotEstimate', '_SlotAttempt', '_read_legacy_field', '_coerce_legacy_hours_value', 'validate_internal_hours', 'validate_internal_hours_for_mode', 'raise_strict_internal_hours_validation', '_internal_hour_fields', '_raise_if_invalid_strict_number', '_resolve_efficiency', '_changeover_penalty', '_abort_result', '_resolve_total_base', '_slot_segments', '_max_shift_count', '_adjust_slot_start', '_abort_after_result', '_estimate_attempt', '_latest_overlap_shift_end', '_shifted_start', '_build_slot_estimate', 'estimate_internal_slot']
