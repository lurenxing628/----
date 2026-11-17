from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Tuple

from core.algorithm_contracts.sort_strategies import WeightedParams
from core.algorithms.evaluation import objective_score
from core.models.enums import SortStrategy

from .candidate_comparison import candidate_is_preferred
from .grasp_ig_specs import build_grasp_ig_candidate_specs
from .search_stage import SearchStage
from .search_state import OptimizerSearchState
from .shared_budget import SharedSearchSkip
from .shared_decode import decode_and_metrics

if TYPE_CHECKING:
    from .search_report import OptimizationSearchReportState
    from .shared_decode import SharedDecodeSession


GRASP_IG_PHASE = "grasp_ig_candidate_construction"


def _evaluate_candidate(
    *,
    strategy: SortStrategy,
    params: Optional[WeightedParams],
    order: List[str],
    dispatch_mode: str,
    dispatch_rule: str,
    objective_name: str,
    decode_session: SharedDecodeSession,
) -> Dict[str, Any]:
    decoded = decode_and_metrics(
        decode_session=decode_session, objective_name=objective_name,
        strategy=strategy,
        strategy_params=params,
        batch_order_override=order,
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
        graph_enabled=False,
        graph_score_enabled=False,
        graph_priority_key_by_op_id=None,
        resource_pair_rank={},
    )
    candidate = {
        "results": decoded.results,
        "summary": decoded.summary,
        "strategy": decoded.used_strategy,
        "params": params,
        "graph_ready_profile": None,
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "repair_decision": None,
        "order": order,
        "decoded_batch_order": decoded.decoded_batch_order,
        "metrics": decoded.metrics,
        "score": (float(decoded.summary.failed_ops),) + objective_score(objective_name, decoded.metrics),
        "algo_stats": decoded.algo_stats,
        "resource_pair_rank": {},
    }
    candidate["archive_ref"] = decoded.archive_ref()
    candidate["decode_receipt"] = decoded.receipt
    if decoded.receipt["execution_kind"] == "decision_reused":
        source_runtime = decoded.receipt["source_runtime_ms"]
        source_initial = decoded.receipt["source_initial_decode_runtime_ms"]
        candidate["runtime_ms"] = source_runtime if source_runtime is not None else decoded.receipt["original_decode_ms"]
        candidate["initial_decode_runtime_ms"] = (
            source_initial if source_initial is not None else decoded.receipt["original_decode_ms"])
    return candidate


def _record_candidate(
    *,
    best: Optional[Dict[str, Any]],
    candidate: Dict[str, Any],
    origin: str,
    search_report_state: OptimizationSearchReportState,
) -> Optional[Dict[str, Any]]:
    fingerprint = search_report_state.mark_candidate_evaluated(candidate, origin=origin)
    duplicate = fingerprint.same_as_parent or fingerprint.same_as_seen
    accepted = not duplicate and candidate_is_preferred(
        candidate=candidate,
        incumbent=best,
        candidate_origin=origin,
        incumbent_origin=str(search_report_state.best_origin or "baseline"),
        candidate_fingerprint=fingerprint,
        incumbent_fingerprint_changed=search_report_state.best_fingerprint_changed(),
    )
    if not accepted:
        return best
    search_report_state.mark_candidate_accepted(candidate, origin=origin, fingerprint=fingerprint)
    return candidate


def _candidate_specs_for_run(
    *,
    best: Optional[Dict[str, Any]],
    base_strategy: SortStrategy,
    base_params: Optional[WeightedParams],
    build_order: Callable[[SortStrategy, Optional[WeightedParams]], Tuple[str, ...]],
    version: int,
    candidate_construction: Dict[str, Any],
    dispatch_rule_cfg: str,
    batch_order_enabled: bool,
    decode_session: SharedDecodeSession,
) -> Optional[List[Dict[str, Any]]]:
    if not bool(batch_order_enabled):
        return None

    base_order = build_order(base_strategy, base_params)
    if len(base_order) < 2:
        return None

    specs = build_grasp_ig_candidate_specs(
        base_order=base_order,
        parent_order=(best or {}).get("order") or base_order,
        version=int(version),
        candidate_construction=candidate_construction,
        dispatch_rule_cfg=dispatch_rule_cfg,
    )
    return _dedupe_candidate_specs(specs, initial_seen=decode_session.executed_decision_keys())


def _dedupe_candidate_specs(
    specs: List[Dict[str, Any]],
    *,
    initial_seen: Set[Tuple[str, str, Tuple[Any, ...]]],
) -> List[Dict[str, Any]]:
    seen = set(initial_seen)
    out: List[Dict[str, Any]] = []
    for spec in specs:
        fingerprint = _spec_decision_key(spec)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        out.append(spec)
    return out


def _spec_decision_key(spec: Dict[str, Any]) -> Tuple[str, str, Tuple[Any, ...]]:
    # Specs come only from build_grasp_ig_candidate_specs, which writes every key.
    return spec["dispatch_mode"], spec["dispatch_rule"], tuple(spec["order"])


def _run_candidate_spec(
    *,
    spec: Dict[str, Any],
    best: Optional[Dict[str, Any]],
    base_strategy: SortStrategy,
    base_params: Optional[WeightedParams],
    objective_name: str,
    search_report_state: OptimizationSearchReportState,
    decode_session: SharedDecodeSession,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    origin = str(spec["origin"])
    dispatch_mode = spec["dispatch_mode"]
    dispatch_rule = str(spec["dispatch_rule"])
    clock = decode_session.budget.clock
    decode_started = clock()
    try:
        candidate = _evaluate_candidate(
            strategy=base_strategy,
            params=base_params,
            order=spec["order"],
            dispatch_mode=dispatch_mode,
            dispatch_rule=dispatch_rule,
            objective_name=objective_name,
            decode_session=decode_session,
        )
    except SharedSearchSkip as exc:
        return best, exc.reason
    # Measured decode time travels with the candidate so a GRASP/IG incumbent can still budget
    # the local search and later guards (the key name is shared with multi-start starts); its
    # integer runtime_ms is the candidate's own cost for equal-score tie-breaks.
    if candidate["decode_receipt"]["execution_kind"] != "decision_reused":
        decode_runtime_ms = max((clock() - decode_started) * 1000.0, 0.0)
        candidate["initial_decode_runtime_ms"] = decode_runtime_ms
        candidate["runtime_ms"] = int(decode_runtime_ms)
    return _record_candidate(
        best=best,
        candidate=candidate,
        origin=origin,
        search_report_state=search_report_state,
    ), None


class GraspIGStage(SearchStage):
    """Retain one set of ordinary batch-order construction specs across task rotation."""

    name = GRASP_IG_PHASE

    def __init__(
        self, *, version: int, candidate_construction: Dict[str, Any],
        base_strategy: SortStrategy, base_params: Optional[WeightedParams],
        build_order: Callable[[SortStrategy, Optional[WeightedParams]], Tuple[str, ...]], dispatch_rule_cfg: str,
        objective_name: str, batch_order_enabled: bool,
        search_report_state: OptimizationSearchReportState,
        state: OptimizerSearchState,
        decode_session: SharedDecodeSession,
    ) -> None:
        self.state = state
        self.budget = decode_session.budget
        self.index = 0
        self._stop_reason: Optional[str] = None
        self.run_spec = partial(
            _run_candidate_spec, base_strategy=base_strategy, base_params=base_params, objective_name=objective_name,
            search_report_state=search_report_state, decode_session=decode_session,
        )
        specs = _candidate_specs_for_run(
            best=self.state.best, base_strategy=base_strategy, base_params=base_params,
            build_order=build_order, version=int(version), candidate_construction=candidate_construction,
            dispatch_rule_cfg=dispatch_rule_cfg, batch_order_enabled=batch_order_enabled,
            decode_session=decode_session,
        )
        self.specs: List[Dict[str, Any]] = specs if specs is not None else []
        if specs is None:
            self._stop_reason = "candidate_specs_unavailable"

    def available(self) -> bool:
        if self._stop_reason is not None or self.index >= len(self.specs):
            return False
        if self.budget.clock() >= self.budget.deadline:
            self._stop_reason = "time_budget"
            return False
        return True

    def unavailable_reason(self) -> Optional[str]:
        if self._stop_reason is not None:
            return self._stop_reason
        if self.index >= len(self.specs):
            return "specs_exhausted"
        return None if self.available() else self._stop_reason

    def run_task(self) -> None:
        if not self.available():
            return
        spec = self.specs[self.index]
        self.index += 1
        self.state.best, skip_reason = self.run_spec(spec=spec, best=self.state.best)
        if skip_reason in ("estimated_decode_cost", "time_budget"):
            self._stop_reason = skip_reason


__all__ = [
    "GRASP_IG_PHASE",
    "GraspIGStage",
]
