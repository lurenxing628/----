"""Reuse a sibling plan when two outer candidates would run the optimizer on identical inputs.

The workbench compares one baseline with N graph tiers whose configs differ only in the
three graph weights. Those weights reach the optimizer solely through the graph ready
context: one priority key per operation, which the SGS decoder consumes by comparison
only. Tiers whose keys induce the same weak order over the schedulable operations decode
identically, and the deterministic search that follows sees identical inputs. Such a tier
reuses its completed sibling's plan instead of spending its slice on the same search, is
reported as reused, and the shared budget is split among the plans that still need a
search of their own.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from datetime import date, datetime
from types import SimpleNamespace
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

from core.infrastructure.errors import ValidationError

from .optimizer_graph_ready_predecode import graph_priority_preorder
from .schedule_candidate_runtime_helpers import (
    _candidate_cfg,
    _candidate_health,
    _dict_or_none,
    _replace_schedule_input_cfg,
)

_WEIGHT_FIELDS = ("graph_critical_weight", "graph_impact_weight", "graph_downstream_weight")
_BOOKKEEPING_FIELDS = ("degradation_events", "degradation_counters")
# Raw weights and raw keys are replaced by the weak order the keys induce.
_ORDER_ONLY_CONTEXT_KEYS = ("graph_priority_key_by_op_id", "score_weights")
Fingerprint = Tuple[Any, ...]


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return ("dict", tuple(sorted((_canonical(key), _canonical(item)) for key, item in value.items())))
    if isinstance(value, (set, frozenset)):
        return ("set", tuple(sorted(_canonical(item) for item in value)))
    if isinstance(value, (list, tuple)):
        return ("seq", tuple(_canonical(item) for item in value))
    if value is None or isinstance(value, (bool, int, float, str)):
        return (type(value).__name__, value)
    if isinstance(value, (datetime, date)):
        return (type(value).__name__, value.isoformat())
    if is_dataclass(value) and not isinstance(value, type):
        return ("dataclass", type(value).__name__, _canonical({field.name: getattr(value, field.name) for field in fields(value)}))
    raise TypeError("optimizer input cannot be fingerprinted: " + type(value).__name__)


def _weight_free_cfg(cfg: Any) -> Dict[str, Any]:
    if is_dataclass(cfg) and not isinstance(cfg, type):
        names = [field.name for field in fields(cfg)]
    elif hasattr(cfg, "__dict__"):
        names = list(vars(cfg))
    else:
        raise TypeError("candidate cfg must be a dataclass or a plain object")
    return {name: getattr(cfg, name) for name in names if name not in _WEIGHT_FIELDS and name not in _BOOKKEEPING_FIELDS}


def optimizer_input_fingerprint(candidate_cfg: Any, graph_preparation: Any) -> Optional[Fingerprint]:
    """Everything the optimizer sees, with raw graph weights replaced by the order they induce.

    Returns None when the inputs cannot be certified, in which case the candidate always runs.
    """
    try:
        cfg_part = _canonical(_weight_free_cfg(candidate_cfg))
        context = getattr(graph_preparation, "graph_ready_context", None)
        if context is None:
            context_part: Any = None
        elif isinstance(context, dict):
            keys = context.get("graph_priority_key_by_op_id")
            preorder = None if keys is None else graph_priority_preorder(dict(keys))
            rest = {key: item for key, item in context.items() if key not in _ORDER_ONLY_CONTEXT_KEYS}
            context_part = (_canonical(rest), preorder)
        else:
            return None
        override = getattr(graph_preparation, "graph_dispatch_mode_override", None)
        return cfg_part, context_part, (None if override is None else str(override))
    except (TypeError, ValueError, ValidationError):
        return None


class CandidateInputLedger:
    """Prepared graph inputs, their fingerprints, and the first completed plan per fingerprint."""

    def __init__(self, *, schedule_input: Any, base_cfg: Any, prepare_graph_fn: Callable[[Any], Any]) -> None:
        self._schedule_input = schedule_input
        self._base_cfg = base_cfg
        self._prepare = prepare_graph_fn
        self._prepared: Dict[int, Tuple[Any, Any]] = {}
        self._fingerprints: Dict[int, Optional[Fingerprint]] = {}
        self._completed: Dict[Fingerprint, Any] = {}

    def prepare_graph_specs(self, specs: Sequence[Any]) -> None:
        """Prepare every graph plan that has no preparation yet, in spec order."""
        for spec in specs:
            sequence = int(spec.sequence)
            if spec.graph_enabled and sequence not in self._prepared:
                cfg = _candidate_cfg(self._base_cfg, spec)
                preparation = self._prepare(_replace_schedule_input_cfg(self._schedule_input, cfg=cfg))
                self._prepared[sequence] = (cfg, preparation)
                self._fingerprints[sequence] = optimizer_input_fingerprint(cfg, preparation)

    def prepared(self, spec: Any) -> Optional[Tuple[Any, Any]]:
        return self._prepared.get(int(spec.sequence))

    def completed_twin(self, spec: Any) -> Any:
        fingerprint = self._fingerprints.get(int(spec.sequence))
        return None if fingerprint is None else self._completed.get(fingerprint)

    def observe(self, spec: Any, plan: Any, *, completed: bool) -> None:
        fingerprint = self._fingerprints.get(int(spec.sequence))
        if completed and fingerprint is not None and fingerprint not in self._completed:
            self._completed[fingerprint] = plan

    def distinct_remaining(self, specs: Sequence[Any]) -> int:
        """How many of ``specs`` still need a search of their own; unprepared plans count as distinct."""
        seen = set(self._completed)
        count = 0
        for spec in specs:
            fingerprint = self._fingerprints.get(int(spec.sequence))
            token: Any = ("unique", int(spec.sequence)) if fingerprint is None else fingerprint
            if token not in seen:
                seen.add(token)
                count += 1
        return count


def reused_candidate_plan(spec: Any, twin: Any, *, prepared: Tuple[Any, Any], baseline_results: Any, elapsed_seconds: float) -> Any:
    """The twin's plan under this spec's identity, with this spec's own graph report and health."""
    candidate_cfg, graph_preparation = prepared
    results = list(twin.results or [])
    health = _candidate_health(
        spec, baseline_results=baseline_results, outcome=SimpleNamespace(results=results), graph_preparation=graph_preparation,
    )
    return replace(
        twin,
        sequence=int(spec.sequence),
        candidate_key=spec.candidate_key,
        kind=spec.kind,
        label=spec.label,
        graph_critical_weight=int(spec.graph_critical_weight),
        graph_impact_weight=int(spec.graph_impact_weight),
        graph_downstream_weight=int(spec.graph_downstream_weight),
        results=results,
        health=health,
        graph_analysis_public=_dict_or_none(getattr(graph_preparation, "graph_analysis_public", None)),
        graph_analysis_diagnostics=_dict_or_none(getattr(graph_preparation, "graph_analysis_diagnostics", None)),
        used_params=dict(twin.used_params or {}),
        best_order=list(twin.best_order or []),
        attempts=[dict(item) for item in (twin.attempts or [])],
        improvement_trace=[dict(item) for item in (twin.improvement_trace or [])],
        algo_stats=dict(twin.algo_stats or {}),
        search_report=dict(twin.search_report or {}),
        sort_strategy=str(candidate_cfg.sort_strategy),
        dispatch_mode=str(candidate_cfg.dispatch_mode),
        dispatch_rule=str(candidate_cfg.dispatch_rule),
        objective=str(candidate_cfg.objective),
        failure_reason=None,
        elapsed_seconds=max(float(elapsed_seconds), 0.0),
        reused_from_candidate_key=str(twin.candidate_key),
        reused_from_label=str(twin.label),
    )


__all__ = ["CandidateInputLedger", "optimizer_input_fingerprint", "reused_candidate_plan"]
