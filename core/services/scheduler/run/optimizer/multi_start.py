"""Multi-start construction and evaluation through the shared decode session."""
from __future__ import annotations

import time
from datetime import date, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterator, List, Optional, Set, Tuple, cast

from core.algorithm_contracts.dispatch_rules import dispatch_rule_search_pool
from core.algorithm_contracts.sort_strategies import SortStrategy
from core.algorithms.evaluation import objective_score
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot

from .attempt_records import candidate_tag
from .config import weighted_strategy_params
from .search_stage import SearchStage
from .search_state import OptimizerSearchState
from .shared_budget import SharedSearchSkip
from .shared_decode import decode_and_metrics
from .step_report_hooks import _record_multi_start_candidate

if TYPE_CHECKING:
    from .search_report import OptimizationSearchReportState
    from .shared_decode import SharedDecodeSession


def _dispatch_rules_for_mode(dispatch_mode: str, dispatch_rule_cfg: str, valid_dispatch_rules: List[str]) -> List[str]:
    if dispatch_mode != "sgs":
        return [dispatch_rule_cfg]
    # Configured rule first, then the registry rules, then the ATC k ladder nearest-first; the
    # phase slice truncates from the far end when decodes are expensive.
    pool = dispatch_rule_search_pool(valid_dispatch_rules)
    return [dispatch_rule_cfg] + [rule for rule in pool if rule != dispatch_rule_cfg]


def _resolve_multi_start_strategy_params(
    *,
    strategy: SortStrategy,
    cfg: ScheduleConfigSnapshot,
) -> Dict[str, Any]:
    if strategy != SortStrategy.WEIGHTED:
        return {}
    return weighted_strategy_params(cfg)


def _get_cached_multi_start_order(
    *,
    strategy: SortStrategy,
    params: Dict[str, Any],
    order_cache: Dict[Tuple[str, Tuple[Tuple[str, Any], ...]], List[str]],
    build_order: Any,
) -> List[str]:
    cache_key = (str(strategy.value), tuple(sorted((str(key), value) for key, value in params.items())))
    if cache_key not in order_cache:
        order_cache[cache_key] = list(build_order(strategy, params))
    return order_cache[cache_key]


def _evaluate_multi_start_candidate(
    *,
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
    graph_ready_context: Optional[Any],
    decode_session: SharedDecodeSession,
    before_decode: Optional[Callable[[], None]] = None,
) -> Dict[str, Any]:
    decoded = decode_and_metrics(
        decode_session=decode_session, objective_name=objective_name,
        optimizer_algo_stats=optimizer_algo_stats, before_decode=before_decode,
        strategy=strategy,
        strategy_params=params,
        start_dt=start_dt,
        end_date=end_date,
        batch_order_override=order,
        dispatch_mode=dispatch_mode,
        dispatch_rule=dispatch_rule,
        readiness_gate_enabled=bool(readiness_gate_enabled),
        graph_enabled=graph_ready_context is not None,
        graph_score_enabled=bool(graph_ready_context and graph_ready_context.get("score_enabled")),
        graph_priority_key_by_op_id=(graph_ready_context or {}).get("graph_priority_key_by_op_id"),
    )
    candidate = {
        "results": decoded.results,
        "summary": decoded.summary,
        "strategy": decoded.used_strategy,
        "params": decoded.used_params,
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "order": order,
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


def _iter_multi_start_specs(
    *, keys: List[str], dispatch_modes: List[str], snapshot: ScheduleConfigSnapshot,
    deadline_reached: Callable[[], bool], rules_by_mode: Dict[str, List[str]],
    order_cache: Dict[Tuple[str, Tuple[Tuple[str, Any], ...]], List[str]],
    build_order: Callable[[SortStrategy, Dict[str, Any]], List[str]],
    on_duplicate_order: Callable[[int], None],
) -> Iterator[Tuple[str, str, str, SortStrategy, Dict[str, Any]]]:
    strategy_cache: Dict[str, Tuple[SortStrategy, Dict[str, Any]]] = {}
    for dm in dispatch_modes:
        if deadline_reached():
            break
        dispatch_rules = rules_by_mode[dm]
        seen_orders: Set[Tuple[str, ...]] = set()
        first_strategy: Optional[Tuple[SortStrategy, Dict[str, Any]]] = None
        for key in keys:
            if deadline_reached():
                break
            if key not in strategy_cache:
                strategy = SortStrategy(key)
                strategy_cache[key] = (
                    strategy, _resolve_multi_start_strategy_params(strategy=strategy, cfg=snapshot),
                )
            strategy, params = strategy_cache[key]
            if first_strategy is None:
                first_strategy = (strategy, params)
            else:
                if not seen_orders:
                    seen_orders.add(
                        tuple(
                            _get_cached_multi_start_order(
                                strategy=first_strategy[0],
                                params=first_strategy[1],
                                order_cache=order_cache,
                                build_order=build_order,
                            )
                        )
                    )
                order_key = tuple(
                    _get_cached_multi_start_order(
                        strategy=strategy, params=params, order_cache=order_cache, build_order=build_order,
                    )
                )
                if order_key in seen_orders:
                    on_duplicate_order(len(dispatch_rules))
                    continue
                seen_orders.add(order_key)
            for rule in dispatch_rules:
                if deadline_reached():
                    break
                yield dm, key, rule, strategy, params


class MultiStartStage(SearchStage):
    """One configured construction per task, retaining the prepared order cache."""

    name = "multi_start"

    def __init__(
        self, *, keys: List[str], dispatch_modes: List[str], dispatch_rule_cfg: str,
        valid_dispatch_rules: List[str], start_dt: datetime, end_date: Optional[date],
        cfg: ScheduleConfigSnapshot, resource_pool: Optional[Dict[str, Any]], objective_name: str, deadline: float,
        t_begin: float, build_order: Any,
        optimizer_algo_stats: Optional[Dict[str, Any]] = None, readiness_gate_enabled: bool = False,
        graph_ready_context: Optional[Any] = None,
        clock: Optional[Callable[[], float]] = None,
        search_report_state: OptimizationSearchReportState,
        state: OptimizerSearchState,
        decode_session: SharedDecodeSession,
    ) -> None:
        self.state = state
        self.order_cache: Dict[Tuple[str, Tuple[Tuple[str, Any], ...]], List[str]] = {}
        self.build_order = build_order
        self.now = clock or time.time
        self.deadline = deadline
        self.search_report_state = search_report_state
        self.t_begin = t_begin
        self.decode_session = decode_session
        self.evaluate = partial(
            _evaluate_multi_start_candidate, start_dt=start_dt, end_date=end_date,
            resource_pool=resource_pool, objective_name=objective_name, optimizer_algo_stats=optimizer_algo_stats,
            readiness_gate_enabled=bool(readiness_gate_enabled), graph_ready_context=graph_ready_context,
            decode_session=decode_session, before_decode=self._note_decode,
        )
        rules_by_mode = {
            dm: _dispatch_rules_for_mode(dm, dispatch_rule_cfg, valid_dispatch_rules)
            for dm in dispatch_modes
        }
        self.efficiency: Dict[str, Any] = {
            "proof": "shared_decode_request",
            "configured_candidates": sum(len(keys) * len(rules_by_mode[dm]) for dm in dispatch_modes),
            "eligible_candidates": 0, "decoded_candidates": 0,
            "skipped_by_budget": 0, "reused_candidates": 0,
        }
        self.specs = _iter_multi_start_specs(
            keys=keys, dispatch_modes=dispatch_modes, snapshot=cfg,
            deadline_reached=self._deadline_reached, rules_by_mode=rules_by_mode,
            order_cache=self.order_cache, build_order=self.build_order,
            on_duplicate_order=self._note_duplicate_order,
        )
        self.index = 0
        self._pending_spec: Optional[Tuple[str, str, str, SortStrategy, Dict[str, Any]]] = None
        self._unaffordable_modes: Set[str] = set()
        self._stop_reason: Optional[str] = None
        self.exhausted = False
        self.finished = False

    def _deadline_reached(self) -> bool:
        return self.now() >= self.deadline

    def _note_decode(self) -> None:
        self.efficiency["decoded_candidates"] += 1

    def _note_duplicate_order(self, skipped_rules: int) -> None:
        self.efficiency["configured_candidates"] = max(
            self.efficiency["configured_candidates"] - int(skipped_rules), 0,
        )

    def available(self) -> bool:
        if self.finished or self.exhausted:
            return False
        while self._pending_spec is None or self._pending_spec[0] in self._unaffordable_modes:
            self._pending_spec = next(self.specs, None)
            if self._pending_spec is None:
                self.exhausted = True
                break
        return not self.exhausted

    def unavailable_reason(self) -> Optional[str]:
        current = self.now()
        if current >= self.deadline:
            return "time_budget"
        if self.exhausted:
            return self._stop_reason or "specs_exhausted"
        return "finished" if self.finished else None

    def run_task(self) -> None:
        if self.finished or self.exhausted or (self._pending_spec is None and not self.available()):
            return
        dm, key, rule, strategy, params = cast(
            Tuple[str, str, str, SortStrategy, Dict[str, Any]], self._pending_spec,
        )
        self._pending_spec = None
        self.index += 1
        order = _get_cached_multi_start_order(
            strategy=strategy, params=params, order_cache=self.order_cache, build_order=self.build_order,
        )
        self.efficiency["eligible_candidates"] += 1
        if self._deadline_reached():
            return
        decode_started = self.now()
        try:
            candidate = self.evaluate(strategy=strategy, params=params, order=order, dispatch_mode=dm, dispatch_rule=rule)
        except SharedSearchSkip as exc:
            self.state.attempts.append({
                "tag": candidate_tag(key, dm, rule), "candidate_status": "skipped", "reason": exc.reason,
                "request_id": exc.request_id, "decode_receipt": exc.receipt,
                "strategy": key, "dispatch_mode": dm, "dispatch_rule": rule,
            })
            if exc.reason == "estimated_decode_cost":
                self._unaffordable_modes.add(dm)
                self._stop_reason = exc.reason
            elif exc.reason == "time_budget":
                self._stop_reason = exc.reason
                self.exhausted = True
            return
        if candidate["decode_receipt"]["execution_kind"] == "decision_reused":
            self.efficiency["reused_candidates"] += 1
        else:
            decode_runtime_ms = max((self.now() - decode_started) * 1000.0, 0.0)
            candidate["initial_decode_runtime_ms"] = decode_runtime_ms
            candidate["runtime_ms"] = int(decode_runtime_ms)
        self.state.best = _record_multi_start_candidate(
            best=self.state.best, candidate=candidate, strategy_key=key,
            attempts=self.state.attempts, improvement_trace=self.state.improvement_trace,
            search_report_state=self.search_report_state, now=self.now, t_begin=self.t_begin,
        )

    def finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        self.efficiency["skipped_by_budget"] = (
            self.efficiency["configured_candidates"] - self.efficiency["decoded_candidates"]
            - self.efficiency["reused_candidates"]
        )
        if self.efficiency["skipped_by_budget"]:
            self.state.attempts.append({"tag": "multi_start_efficiency", "candidate_status": "phase_summary",
                                        "multi_start_efficiency": self.efficiency})
