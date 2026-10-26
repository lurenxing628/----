from __future__ import annotations

from datetime import date, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Tuple

from core.algorithm_contracts.sort_strategies import SortStrategy
from core.algorithms.evaluation import objective_score
from core.errors import ValidationError

from .attempt_records import attempt_decision_evidence, validation_error_origin
from .candidate_comparison import candidate_is_preferred
from .grasp_ig_specs import build_grasp_ig_candidate_specs
from .search_stage import SearchStage
from .search_state import OptimizerSearchState, append_unique_rejected_attempt
from .shared_budget import SharedSearchSkip
from .shared_decode import decode_and_metrics

if TYPE_CHECKING:
    from .search_report import OptimizationSearchReportState
    from .shared_decode import SharedDecodeSession


GRASP_IG_PHASE = "grasp_ig_candidate_construction"



def _candidate_tag(origin: str, index: int, dispatch_mode: str, dispatch_rule: str) -> str:
    return f"{origin}:r{int(index)}|{dispatch_mode}:{dispatch_rule}"


def _evaluate_candidate(
    *,
    strict_mode: bool,
    strategy: SortStrategy,
    params: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    order: List[str],
    dispatch_mode: str,
    dispatch_rule: str,
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    optimizer_algo_stats: Optional[Dict[str, Any]],
    readiness_gate_enabled: bool,
    decode_session: SharedDecodeSession,
) -> Dict[str, Any]:
    decoded = decode_and_metrics(
        decode_session=decode_session, objective_name=objective_name,
        optimizer_algo_stats=optimizer_algo_stats,
        strict_mode=bool(strict_mode),
        strategy=strategy,
        strategy_params=dict(params),
        start_dt=start_dt,
        end_date=end_date,
        batch_order_override=list(order),
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
        readiness_gate_enabled=bool(readiness_gate_enabled),
        graph_enabled=False,
        graph_score_enabled=False,
        graph_priority_key_by_op_id=None,
    )
    candidate = {
        "results": decoded.results,
        "summary": decoded.summary,
        "strategy": decoded.used_strategy,
        "params": dict(decoded.used_params),
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "order": list(order),
        "metrics": decoded.metrics,
        "score": (float(decoded.summary.failed_ops),) + objective_score(objective_name, decoded.metrics),
        "algo_stats": decoded.algo_stats,
        "resource_pool": resource_pool or {},
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


def _append_attempt(
    *, attempts: List[Dict[str, Any]], candidate: Dict[str, Any], origin: str, index: int,
    decision_evidence: Dict[str, Any],
) -> None:
    metrics = candidate["metrics"]
    dispatch_mode = candidate["dispatch_mode"]
    dispatch_rule = candidate["dispatch_rule"]
    attempt = {
        "tag": _candidate_tag(origin, index, dispatch_mode, dispatch_rule),
        "source": origin,
        "strategy": candidate["strategy"].value,
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "used_params": dict(candidate["params"]),
        "score": list(candidate["score"]),
        "failed_ops": int(candidate["summary"].failed_ops),
        "metrics": metrics.to_dict(),
        "algo_stats": candidate["algo_stats"],
    }
    attempt.update(decision_evidence)
    attempts.append(attempt)


def _append_trace(
    *,
    improvement_trace: List[Dict[str, Any]],
    candidate: Dict[str, Any],
    origin: str,
    index: int,
    now: Callable[[], float],
    t_begin: float,
) -> None:
    metrics = candidate["metrics"]
    dispatch_mode = candidate["dispatch_mode"]
    dispatch_rule = candidate["dispatch_rule"]
    improvement_trace.append(
        {
            "elapsed_ms": int((now() - t_begin) * 1000),
            "tag": _candidate_tag(origin, index, dispatch_mode, dispatch_rule),
            "strategy": candidate["strategy"].value,
            "dispatch_mode": dispatch_mode,
            "dispatch_rule": dispatch_rule,
            "score": list(candidate["score"]),
            "metrics": metrics.to_dict(),
        }
    )


def _append_rejected_attempt(
    *,
    attempts: List[Dict[str, Any]],
    origin: str,
    index: int,
    strategy: SortStrategy,
    dispatch_mode: str,
    dispatch_rule: str,
    exc: ValidationError,
) -> None:
    append_unique_rejected_attempt(
        attempts,
        {
            "tag": _candidate_tag(origin, index, dispatch_mode, dispatch_rule),
            "strategy": strategy.value,
            "dispatch_mode": dispatch_mode,
            "dispatch_rule": dispatch_rule,
            "source": "candidate_rejected",
            "origin": validation_error_origin(exc),
        },
    )


def _record_candidate(
    *,
    best: Optional[Dict[str, Any]],
    candidate: Dict[str, Any],
    origin: str,
    index: int,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    search_report_state: OptimizationSearchReportState,
    now: Callable[[], float],
    t_begin: float,
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
    _append_attempt(
        attempts=attempts, candidate=candidate, origin=origin, index=index,
        decision_evidence=attempt_decision_evidence(
            candidate=candidate, reference=best, accepted=accepted,
            search_report_state=search_report_state, clock=now, t_begin=t_begin,
        ),
    )
    if not accepted:
        return best
    search_report_state.mark_candidate_accepted(candidate, origin=origin, fingerprint=fingerprint)
    _append_trace(
        improvement_trace=improvement_trace,
        candidate=candidate,
        origin=origin,
        index=index,
        now=now,
        t_begin=t_begin,
    )
    return candidate


def _candidate_specs_for_run(
    *,
    best: Optional[Dict[str, Any]],
    base_strategy: SortStrategy,
    base_params: Dict[str, Any],
    build_order: Callable[[SortStrategy, Dict[str, Any]], List[str]],
    version: int,
    candidate_construction: Dict[str, Any],
    dispatch_rule_cfg: str,
    batch_order_enabled: bool,
    rng_factory: Callable[[int], Any],
) -> Optional[List[Dict[str, Any]]]:
    if not bool(batch_order_enabled):
        return None

    base_order = list(build_order(base_strategy, base_params))
    if len(base_order) < 2:
        return None

    parent_order = list((best or {}).get("order") or base_order)
    specs = build_grasp_ig_candidate_specs(
        base_order=base_order,
        parent_order=parent_order,
        version=int(version),
        candidate_construction=candidate_construction,
        dispatch_rule_cfg=dispatch_rule_cfg,
        rng_factory=rng_factory,
    )
    # The configured rule is already a validated choice (optimizer/config.require_choice).
    initial_seen = {
        ("batch_order", dispatch_rule_cfg, tuple(base_order)),
        ("batch_order", dispatch_rule_cfg, tuple(parent_order)),
    }
    return _dedupe_candidate_specs(specs, initial_seen=initial_seen)


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
    strict_mode: bool,
    base_strategy: SortStrategy,
    base_params: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    optimizer_algo_stats: Optional[Dict[str, Any]],
    readiness_gate_enabled: bool,
    attempts: List[Dict[str, Any]],
    improvement_trace: List[Dict[str, Any]],
    search_report_state: OptimizationSearchReportState,
    clock: Callable[[], float],
    t_begin: float,
    decode_session: SharedDecodeSession,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    origin = str(spec["origin"])
    index = int(spec["restart_index"])
    dispatch_mode = spec["dispatch_mode"]
    dispatch_rule = str(spec["dispatch_rule"])
    decode_started = clock()
    try:
        candidate = _evaluate_candidate(
            strict_mode=bool(strict_mode),
            strategy=base_strategy,
            params=base_params,
            start_dt=start_dt,
            end_date=end_date,
            order=spec["order"],
            dispatch_mode=dispatch_mode,
            dispatch_rule=dispatch_rule,
            resource_pool=resource_pool,
            objective_name=objective_name,
            optimizer_algo_stats=optimizer_algo_stats,
            readiness_gate_enabled=bool(readiness_gate_enabled),
            decode_session=decode_session,
        )
    except SharedSearchSkip as exc:
        attempts.append({
            "tag": _candidate_tag(origin, index, dispatch_mode, dispatch_rule),
            "source": origin, "candidate_status": "skipped", "reason": exc.reason,
            "request_id": exc.request_id, "decode_receipt": exc.receipt,
            "strategy": base_strategy.value, "dispatch_mode": dispatch_mode, "dispatch_rule": dispatch_rule,
        })
        return best, exc.reason
    except ValidationError as exc:
        if bool(strict_mode):
            raise
        _append_rejected_attempt(
            attempts=attempts,
            origin=origin,
            index=index,
            strategy=base_strategy,
            dispatch_mode=dispatch_mode,
            dispatch_rule=dispatch_rule,
            exc=exc,
        )
        return best, None
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
        index=index,
        attempts=attempts,
        improvement_trace=improvement_trace,
        search_report_state=search_report_state,
        now=clock,
        t_begin=t_begin,
    ), None


class GraspIGStage(SearchStage):
    """Retain one set of ordinary batch-order construction specs across task rotation."""

    name = GRASP_IG_PHASE

    def __init__(
        self, *, version: int, candidate_construction: Dict[str, Any],
        start_dt: datetime, end_date: Optional[date], base_strategy: SortStrategy, base_params: Dict[str, Any],
        build_order: Callable[[SortStrategy, Dict[str, Any]], List[str]], dispatch_rule_cfg: str,
        resource_pool: Optional[Dict[str, Any]], objective_name: str,
        deadline: float, optimizer_algo_stats: Optional[Dict[str, Any]], t_begin: float,
        readiness_gate_enabled: bool, strict_mode: bool,
        clock: Callable[[], float], rng_factory: Callable[[int], Any],
        batch_order_enabled: bool = True,
        search_report_state: OptimizationSearchReportState,
        state: OptimizerSearchState,
        decode_session: SharedDecodeSession,
    ) -> None:
        self.state = state
        self.clock = clock
        self.deadline = deadline
        self.index = 0
        self.finished = False
        self._stop_reason: Optional[str] = None
        self.run_spec = partial(
            _run_candidate_spec, strict_mode=bool(strict_mode), base_strategy=base_strategy,
            base_params=base_params, start_dt=start_dt, end_date=end_date,
            resource_pool=resource_pool, objective_name=objective_name,
            optimizer_algo_stats=optimizer_algo_stats, readiness_gate_enabled=bool(readiness_gate_enabled),
            attempts=self.state.attempts, improvement_trace=self.state.improvement_trace,
            search_report_state=search_report_state, clock=clock, t_begin=t_begin, decode_session=decode_session,
        )
        specs = _candidate_specs_for_run(
            best=self.state.best, base_strategy=base_strategy, base_params=base_params,
            build_order=build_order, version=int(version), candidate_construction=candidate_construction,
            dispatch_rule_cfg=dispatch_rule_cfg, batch_order_enabled=batch_order_enabled, rng_factory=rng_factory,
        )
        self.specs: List[Dict[str, Any]] = specs if specs is not None else []
        if specs is None:
            self._stop_reason = "candidate_specs_unavailable"

    def available(self) -> bool:
        if self.finished or self._stop_reason is not None or self.index >= len(self.specs):
            return False
        if self.clock() >= self.deadline:
            self._stop_reason = "time_budget"
            return False
        return True

    def unavailable_reason(self) -> Optional[str]:
        if self._stop_reason is not None:
            return self._stop_reason
        if self.index >= len(self.specs):
            return "specs_exhausted"
        if self.finished:
            return "finished"
        return None if self.available() else self._stop_reason

    def run_task(self) -> None:
        if not self.available():
            return
        spec = self.specs[self.index]
        self.index += 1
        self.state.best, skip_reason = self.run_spec(spec=spec, best=self.state.best)
        if skip_reason in ("estimated_decode_cost", "time_budget"):
            self._stop_reason = skip_reason

    def finish(self) -> None:
        self.finished = True


__all__ = [
    "GRASP_IG_PHASE",
    "GraspIGStage",
]
