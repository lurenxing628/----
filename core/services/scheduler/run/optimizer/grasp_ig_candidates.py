from __future__ import annotations

from datetime import date, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from core.algorithms import SortStrategy
from core.algorithms.evaluation import objective_score
from core.errors import ValidationError

from .attempt_records import attempt_decision_evidence, validation_error_origin
from .candidate_comparison import candidate_is_preferred
from .candidate_fingerprint import score_strictly_better
from .grasp_ig_specs import GRASP_ORIGIN, IG_ORIGIN, build_grasp_ig_candidate_specs
from .search_stage import SearchStage
from .search_state import OptimizerSearchState, append_unique_rejected_attempt
from .shared_budget import SharedSearchSkip
from .shared_decode import decode_and_metrics

if TYPE_CHECKING:
    from .search_report import OptimizationSearchReportState
    from .shared_decode import SharedDecodeSession


GRASP_IG_PHASE = "grasp_ig_candidate_construction"


def _safe_strategy_value(strategy: Any) -> str:
    return str(getattr(strategy, "value", strategy) or "")


def _public_candidate_params(params: Any) -> Dict[str, Any]:
    if not isinstance(params, dict):
        return {}
    out = dict(params)
    out.pop("candidate_construction", None)
    return out


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
    construction: Dict[str, Any],
    decode_session: SharedDecodeSession,
) -> Dict[str, Any]:
    candidate_params = dict(params or {})
    candidate_params["candidate_construction"] = dict(construction or {})
    decoded = decode_and_metrics(
        decode_session=decode_session, objective_name=objective_name,
        optimizer_algo_stats=optimizer_algo_stats,
        strict_mode=bool(strict_mode),
        strategy=strategy,
        strategy_params=candidate_params,
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
        "params": _public_candidate_params(decoded.used_params),
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "order": list(order),
        "metrics": decoded.metrics,
        "score": (float(decoded.summary.failed_ops),) + objective_score(objective_name, decoded.metrics),
        "algo_stats": decoded.algo_stats,
        "resource_pool": resource_pool or {},
    }
    candidate["_shared_entry_id"] = decoded.entry_id
    candidate["_archive_observation"] = decoded.archive_observation
    if decoded.receipt is not None:
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
    decision_evidence: Optional[Dict[str, Any]] = None,
) -> None:
    metrics = candidate["metrics"]
    dispatch_mode = str(candidate.get("dispatch_mode") or "")
    dispatch_rule = str(candidate.get("dispatch_rule") or "")
    attempt = {
        "tag": _candidate_tag(origin, index, dispatch_mode, dispatch_rule),
        "source": origin,
        "strategy": _safe_strategy_value(candidate.get("strategy")),
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "used_params": dict(candidate.get("params") or {}),
        "score": list(candidate.get("score") or []),
        "failed_ops": int(getattr(candidate.get("summary"), "failed_ops", 0) or 0),
        "metrics": metrics.to_dict(),
        "algo_stats": candidate.get("algo_stats") or {},
    }
    if decision_evidence is not None:
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
    dispatch_mode = str(candidate.get("dispatch_mode") or "")
    dispatch_rule = str(candidate.get("dispatch_rule") or "")
    improvement_trace.append(
        {
            "elapsed_ms": int((now() - t_begin) * 1000),
            "tag": _candidate_tag(origin, index, dispatch_mode, dispatch_rule),
            "strategy": _safe_strategy_value(candidate.get("strategy")),
            "dispatch_mode": dispatch_mode,
            "dispatch_rule": dispatch_rule,
            "score": list(candidate.get("score") or []),
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
    search_report_state: Optional[OptimizationSearchReportState],
    now: Callable[[], float],
    t_begin: float,
) -> Optional[Dict[str, Any]]:
    fingerprint = None
    if search_report_state is not None:
        fingerprint = search_report_state.mark_candidate_evaluated(candidate, origin=origin)
    duplicate = bool(fingerprint is not None and (fingerprint.same_as_parent or fingerprint.same_as_seen))
    accepted = not duplicate and candidate_is_preferred(
        candidate=candidate,
        incumbent=best,
        candidate_origin=origin,
        incumbent_origin=_incumbent_origin(best, search_report_state),
        candidate_fingerprint=fingerprint,
        incumbent_fingerprint_changed=bool(search_report_state and search_report_state.best_fingerprint_changed()),
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
    if search_report_state is not None:
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


def _incumbent_origin(
    best: Optional[Dict[str, Any]],
    search_report_state: Optional[OptimizationSearchReportState],
) -> str:
    if search_report_state is not None:
        return str(search_report_state.best_origin or "baseline")
    return str((best or {}).get("candidate_origin") or "baseline")


def _mark_phase_skipped(
    search_report_state: Optional[OptimizationSearchReportState],
    reason: str,
    **extra: Any,
) -> None:
    if search_report_state is not None:
        search_report_state.mark_phase_skipped(GRASP_IG_PHASE, reason, **extra)


def _deadline_reached(now: Callable[[], float], deadline: float, search_report_state: Optional[OptimizationSearchReportState]) -> bool:
    if now() < deadline:
        return False
    if search_report_state is not None:
        search_report_state.mark_deadline_reached()
    return True


def _candidate_specs_for_run(
    *,
    algo_mode: str,
    best: Optional[Dict[str, Any]],
    base_strategy: SortStrategy,
    base_params: Dict[str, Any],
    build_order: Callable[[SortStrategy, Dict[str, Any]], List[str]],
    version: int,
    candidate_construction: Dict[str, Any],
    dispatch_rule_cfg: str,
    batch_order_enabled: bool,
    rng_factory: Callable[[int], Any],
    search_report_state: Optional[OptimizationSearchReportState],
) -> Optional[List[Dict[str, Any]]]:
    if str(algo_mode or "").strip().lower() != "improve":
        _mark_phase_skipped(search_report_state, "algo_mode_not_improve")
        return None
    if not bool(batch_order_enabled):
        _mark_phase_skipped(search_report_state, "batch_order_dispatch_unavailable")
        return None

    base_order = list(build_order(base_strategy, base_params or {}))
    if len(base_order) < 2:
        _mark_phase_skipped(search_report_state, "order_too_short", order_length=len(base_order))
        return None

    parent_order = list((best or {}).get("order") or base_order)
    specs = build_grasp_ig_candidate_specs(
        base_order=base_order,
        parent_order=parent_order,
        version=int(version),
        candidate_construction=candidate_construction if isinstance(candidate_construction, dict) else {},
        dispatch_rule_cfg=dispatch_rule_cfg,
        rng_factory=rng_factory,
    )
    if not specs:
        _mark_phase_skipped(search_report_state, "candidate_budget_empty")
        return None
    return _dedupe_candidate_specs(specs)


def _dedupe_candidate_specs(specs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for spec in list(specs or []):
        fingerprint = _spec_decision_key(spec)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        out.append(spec)
    return out


def _spec_decision_key(spec: Dict[str, Any]) -> Tuple[str, str, Tuple[Any, ...]]:
    return (str(spec.get("dispatch_mode") or "batch_order"),
            str(spec.get("dispatch_rule") or ""), tuple(spec.get("order") or []))


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
    search_report_state: Optional[OptimizationSearchReportState],
    clock: Callable[[], float],
    t_begin: float,
    decode_session: SharedDecodeSession,
) -> Optional[Dict[str, Any]]:
    origin = str(spec["origin"])
    index = int(spec["restart_index"])
    dispatch_mode = str(spec.get("dispatch_mode") or "batch_order")
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
            construction=spec["construction"],
            decode_session=decode_session,
        )
    except SharedSearchSkip as exc:
        attempts.append({
            "tag": _candidate_tag(origin, index, dispatch_mode, dispatch_rule),
            "source": origin, "candidate_status": "skipped", "reason": exc.reason,
            "request_id": exc.request_id, "decode_receipt": exc.receipt,
            "strategy": base_strategy.value, "dispatch_mode": dispatch_mode, "dispatch_rule": dispatch_rule,
        })
        return best
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
        if search_report_state is not None:
            search_report_state.mark_candidate_rejected(reason="validation_error")
        return best
    # Measured decode time travels with the candidate so a GRASP/IG incumbent can still budget
    # the local search and later guards (the key name is shared with multi-start starts).
    if (candidate.get("decode_receipt") or {}).get("execution_kind") != "decision_reused":
        candidate["initial_decode_runtime_ms"] = max((clock() - decode_started) * 1000.0, 0.0)
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
    )


class GraspIGStage(SearchStage):
    """Retain one set of ordinary batch-order construction specs across task rotation."""

    name = GRASP_IG_PHASE

    def __init__(
        self, *, algo_mode: str, version: int, candidate_construction: Dict[str, Any],
        start_dt: datetime, end_date: Optional[date], base_strategy: SortStrategy, base_params: Dict[str, Any],
        build_order: Callable[[SortStrategy, Dict[str, Any]], List[str]], dispatch_rule_cfg: str,
        resource_pool: Optional[Dict[str, Any]], objective_name: str,
        deadline: float, optimizer_algo_stats: Optional[Dict[str, Any]], t_begin: float,
        readiness_gate_enabled: bool, strict_mode: bool,
        clock: Callable[[], float], rng_factory: Callable[[int], Any],
        batch_order_enabled: bool = True,
        search_report_state: Optional[OptimizationSearchReportState] = None,
        state: OptimizerSearchState,
        decode_session: SharedDecodeSession,
    ) -> None:
        self.state = state
        self.clock = clock
        self.deadline = deadline
        self.search_report_state = search_report_state
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
            algo_mode=algo_mode, best=self.state.best, base_strategy=base_strategy, base_params=base_params,
            build_order=build_order, version=int(version), candidate_construction=candidate_construction,
            dispatch_rule_cfg=dispatch_rule_cfg, batch_order_enabled=batch_order_enabled, rng_factory=rng_factory,
            search_report_state=search_report_state,
        )
        self.specs: List[Dict[str, Any]] = specs if specs is not None else []
        if specs is None:
            self._stop_reason = "candidate_specs_unavailable"

    def available(self) -> bool:
        if self.finished or self._stop_reason is not None or self.index >= len(self.specs):
            return False
        if _deadline_reached(self.clock, self.deadline, self.search_report_state):
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

    def run_task(self) -> int:
        if not self.available():
            return 0
        spec = self.specs[self.index]
        self.index += 1
        previous = self.state.best
        self.state.best = self.run_spec(spec=spec, best=previous)
        return int(self.state.best is not previous and score_strictly_better(
            (self.state.best or {}).get("score"), (previous or {}).get("score"),
        ))

    def finish(self) -> None:
        self.finished = True


__all__ = [
    "GRASP_IG_PHASE",
    "GRASP_ORIGIN",
    "IG_ORIGIN",
    "GraspIGStage",
]
