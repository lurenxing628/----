"""Multi-start construction and evaluation through the shared decode session."""
from __future__ import annotations

import math
import time
from datetime import date, datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterator, List, Optional, Tuple, cast

from core.algorithm_contracts.dispatch_rules import dispatch_rule_search_pool
from core.algorithms import SortStrategy
from core.algorithms.evaluation import objective_score

from .attempt_records import candidate_tag, evaluate_optional_start_candidate
from .candidate_fingerprint import score_strictly_better
from .config import ensure_optimizer_config_snapshot, weighted_strategy_params
from .search_stage import SearchStage
from .search_state import OptimizerSearchState
from .shared_budget import SharedSearchSkip
from .shared_decode import decode_and_metrics
from .step_report_hooks import _multi_start_deadline_reached, _record_multi_start_candidate

if TYPE_CHECKING:
    from .search_report import OptimizationSearchReportState
    from .shared_decode import SharedDecodeSession


GRAPH_RULE_SCOPE_CONFIGURED_ONLY = "configured_only"
GRAPH_RULE_SCOPE_REGISTRY_AND_LADDER = "registry_and_ladder"


def _finite_key(value: Any) -> Optional[Tuple[float, ...]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)) or not value:
        return None
    out: List[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(float(item)):
            return None
        out.append(float(item))
    return tuple(out)


def graph_rule_search_scope(graph_ready_context: Optional[Any]) -> Optional[Dict[str, Any]]:
    """How many rule starts a graph candidate needs, proven from the graph priority keys.

    SGS compares ``(penalty, *graph_key, *dispatch_key)`` and every schedulable operation must
    carry a graph key (the decoder rejects a missing one). When all keys are pairwise distinct
    the dispatch rule never breaks a tie, so every rule decodes the same schedule and only the
    configured rule is started. Ties hand the decision to the rule key, so the registry rules and
    the ATC k ladder are all worth a start. Returns None without a graph context.
    """
    if graph_ready_context is None:
        return None
    if not isinstance(graph_ready_context, dict):
        return {"policy": GRAPH_RULE_SCOPE_REGISTRY_AND_LADDER, "reason": "graph_context_not_mapping"}
    if graph_ready_context.get("score_enabled") is not True:
        return {"policy": GRAPH_RULE_SCOPE_REGISTRY_AND_LADDER, "reason": "graph_score_disabled"}
    raw_keys = graph_ready_context.get("graph_priority_key_by_op_id")
    if not isinstance(raw_keys, dict) or not raw_keys:
        return {"policy": GRAPH_RULE_SCOPE_REGISTRY_AND_LADDER, "reason": "graph_keys_missing"}
    keys = [_finite_key(value) for value in raw_keys.values()]
    if any(key is None for key in keys) or len({len(key) for key in keys if key is not None}) != 1:
        return {"policy": GRAPH_RULE_SCOPE_REGISTRY_AND_LADDER, "reason": "graph_keys_not_uniform_finite"}
    distinct = len(set(keys))
    scope: Dict[str, Any] = {"operation_count": len(keys), "distinct_key_count": distinct}
    if distinct == len(keys):
        scope.update(policy=GRAPH_RULE_SCOPE_CONFIGURED_ONLY, reason="graph_keys_pairwise_distinct")
    else:
        scope.update(policy=GRAPH_RULE_SCOPE_REGISTRY_AND_LADDER, reason="graph_key_ties")
    return scope


def _dispatch_rules_for_mode(dispatch_mode: str, dispatch_rule_cfg: str, valid_dispatch_rules: List[str],
                             *, graph_rule_scope: Optional[Dict[str, Any]] = None) -> List[str]:
    if dispatch_mode != "sgs":
        return [dispatch_rule_cfg]
    if graph_rule_scope is not None and graph_rule_scope.get("policy") == GRAPH_RULE_SCOPE_CONFIGURED_ONLY:
        return [dispatch_rule_cfg]
    # Configured rule first, then the registry rules, then the ATC k ladder nearest-first; the
    # phase slice truncates from the far end when decodes are expensive.
    pool = dispatch_rule_search_pool(valid_dispatch_rules)
    return [dispatch_rule_cfg] + [rule for rule in pool if rule != dispatch_rule_cfg]


def _resolve_multi_start_strategy_params(
    *,
    strategy: SortStrategy,
    cfg: Any,
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
    cache_key = (str(strategy.value), tuple(sorted((str(key), value) for key, value in (params or {}).items())))
    if cache_key not in order_cache:
        order_cache[cache_key] = list(build_order(strategy, params))
    return order_cache[cache_key]


def _evaluate_multi_start_candidate(
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
    graph_ready_context: Optional[Any],
    decode_session: SharedDecodeSession,
    before_decode: Optional[Callable[[], None]] = None,
) -> Dict[str, Any]:
    decoded = decode_and_metrics(
        decode_session=decode_session, objective_name=objective_name,
        optimizer_algo_stats=optimizer_algo_stats, before_decode=before_decode,
        strict_mode=bool(strict_mode),
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


def _iter_multi_start_specs(
    *, keys: List[str], dispatch_modes: List[str], dispatch_rule_cfg: str, valid_dispatch_rules: List[str],
    snapshot: Any, deadline_reached: Callable[[], bool],
    graph_rule_scope: Optional[Dict[str, Any]] = None,
    rules_by_mode: Optional[Dict[str, List[str]]] = None,
) -> Iterator[Tuple[str, str, str, SortStrategy, Dict[str, Any]]]:
    strategy_cache: Dict[str, Tuple[SortStrategy, Dict[str, Any]]] = {}
    for dm in dispatch_modes:
        if deadline_reached():
            break
        dispatch_rules = (
            rules_by_mode[dm] if rules_by_mode is not None else
            _dispatch_rules_for_mode(dm, dispatch_rule_cfg, valid_dispatch_rules, graph_rule_scope=graph_rule_scope)
        )
        for key in keys:
            if deadline_reached():
                break
            if key not in strategy_cache:
                strategy = SortStrategy(key)
                strategy_cache[key] = (
                    strategy, _resolve_multi_start_strategy_params(strategy=strategy, cfg=snapshot),
                )
            strategy, params = strategy_cache[key]
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
        cfg: Any, resource_pool: Optional[Dict[str, Any]], objective_name: str, deadline: float,
        t_begin: float, build_order: Any,
        optimizer_algo_stats: Optional[Dict[str, Any]] = None, readiness_gate_enabled: bool = False,
        graph_ready_context: Optional[Any] = None, strict_mode: bool = False,
        clock: Optional[Callable[[], float]] = None,
        search_report_state: Optional[OptimizationSearchReportState] = None,
        state: OptimizerSearchState,
        decode_session: SharedDecodeSession,
    ) -> None:
        self.state = state
        self.order_cache: Dict[Tuple[str, Tuple[Tuple[str, Any], ...]], List[str]] = {}
        self.build_order = build_order
        self.now = clock or time.time
        self.deadline = deadline
        self.search_report_state = search_report_state
        self.strict_mode = bool(strict_mode)
        self.t_begin = t_begin
        self.decode_session = decode_session
        self.primary = (
            str(keys[0]) if keys else "", str(dispatch_modes[0]) if dispatch_modes else "", str(dispatch_rule_cfg),
        )
        self.evaluate = partial(
            _evaluate_multi_start_candidate, strict_mode=self.strict_mode,
            start_dt=start_dt, end_date=end_date,
            resource_pool=resource_pool, objective_name=objective_name, optimizer_algo_stats=optimizer_algo_stats,
            readiness_gate_enabled=bool(readiness_gate_enabled), graph_ready_context=graph_ready_context,
            decode_session=decode_session, before_decode=self._note_decode,
        )
        graph_rule_scope = graph_rule_search_scope(graph_ready_context)
        rules_by_mode = {
            dm: _dispatch_rules_for_mode(dm, dispatch_rule_cfg, valid_dispatch_rules, graph_rule_scope=graph_rule_scope)
            for dm in dispatch_modes
        }
        snapshot = ensure_optimizer_config_snapshot(cfg, strict_mode=self.strict_mode)
        self.specs = _iter_multi_start_specs(
            keys=keys, dispatch_modes=dispatch_modes, dispatch_rule_cfg=dispatch_rule_cfg,
            valid_dispatch_rules=valid_dispatch_rules, snapshot=snapshot,
            deadline_reached=self._deadline_reached, rules_by_mode=rules_by_mode,
        )
        self.efficiency: Dict[str, Any] = {
            "proof": "shared_decode_request",
            "configured_candidates": sum(len(keys) * len(rules_by_mode[dm]) for dm in dispatch_modes),
            "eligible_candidates": 0, "decoded_candidates": 0, "predecode_pruned_candidates": 0,
            "skipped_by_budget": 0, "reused_candidates": 0,
        }
        if graph_rule_scope is not None:
            self.efficiency["graph_rule_scope"] = dict(graph_rule_scope)
        self.index = 0
        self._pending_spec: Optional[Tuple[str, str, str, SortStrategy, Dict[str, Any]]] = None
        self.exhausted = False
        self.finished = False

    def _deadline_reached(self) -> bool:
        return _multi_start_deadline_reached(
            now=self.now, deadline=self.deadline, search_report_state=self.search_report_state,
        )

    def _note_decode(self) -> None:
        self.efficiency["decoded_candidates"] += 1

    def available(self) -> bool:
        if self.finished or self.exhausted:
            return False
        if self._pending_spec is None:
            self._pending_spec = next(self.specs, None)
            self.exhausted = self._pending_spec is None
        return not self.exhausted

    def unavailable_reason(self) -> Optional[str]:
        current = self.now()
        if current >= self.deadline:
            return "time_budget"
        if self.exhausted:
            return "specs_exhausted"
        return "finished" if self.finished else None

    def run_task(self) -> int:
        if self.finished or self.exhausted or (self._pending_spec is None and not self.available()):
            return 0
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
            return 0
        decode_started = self.now()
        try:
            candidate = evaluate_optional_start_candidate(
                evaluate=partial(self.evaluate, strategy=strategy, params=params, order=order,
                                 dispatch_mode=dm, dispatch_rule=rule),
                attempts=self.state.attempts, strategy_key=key, dispatch_mode=dm, dispatch_rule=rule,
                primary=self.primary, strict_mode=self.strict_mode, search_report_state=self.search_report_state,
            )
        except SharedSearchSkip as exc:
            self.state.attempts.append({
                "tag": candidate_tag(key, dm, rule), "candidate_status": "skipped", "reason": exc.reason,
                "request_id": exc.request_id, "decode_receipt": exc.receipt,
                "strategy": key, "dispatch_mode": dm, "dispatch_rule": rule,
            })
            return 0
        if candidate is None:
            return 0
        if (candidate.get("decode_receipt") or {}).get("execution_kind") == "decision_reused":
            self.efficiency["reused_candidates"] += 1
        else:
            candidate["initial_decode_runtime_ms"] = max((self.now() - decode_started) * 1000.0, 0.0)
        previous = self.state.best
        self.state.best = _record_multi_start_candidate(
            best=previous, candidate=candidate, strategy_key=key, dispatch_mode=dm, dispatch_rule=rule,
            attempts=self.state.attempts, improvement_trace=self.state.improvement_trace,
            search_report_state=self.search_report_state, now=self.now, t_begin=self.t_begin,
        )
        return int(self.state.best is candidate and score_strictly_better(
            candidate.get("score"), (previous or {}).get("score"),
        ))

    def finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        self.efficiency["skipped_by_budget"] = (
            self.efficiency["configured_candidates"] - self.efficiency["decoded_candidates"]
            - self.efficiency["predecode_pruned_candidates"]
            - self.efficiency["reused_candidates"]
        )
        if self.search_report_state is not None:
            self.search_report_state.update_candidate_profile(multi_start_efficiency=self.efficiency)
        if self.efficiency["predecode_pruned_candidates"] or self.efficiency["skipped_by_budget"]:
            self.state.attempts.append({"tag": "multi_start_efficiency", "candidate_status": "phase_summary",
                                        "multi_start_efficiency": self.efficiency})
