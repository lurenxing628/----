from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, FrozenSet, Optional, Sequence, Tuple

from core.algorithm_contracts.sort_strategies import SortStrategy
from core.algorithms.greedy.dispatch.sgs_graph import graph_priority_key_map
from core.algorithms.greedy.dispatch.sgs_priority_keys import ValidatedGraphPriorityKeys
from core.services.scheduler.run.optimizer.graph_ready_feature_basis import (
    BASELINE_RANK_PREFIX,
    BATCH_WORKLOAD_BASIS,
    select_profile_metrics,
)
from core.services.scheduler.run.optimizer.graph_ready_profiles import (
    GraphReadyWeightProfile,
    profile_payload,
)

from .candidate_payload import build_graph_ready_candidate_payload
from .repair_decisions import RepairDecision, RepairParentPreparation, repair_decision_inputs
from .v2_keys import v2_formula_specs, v2_priority_key_for_metric
from .v2_ranks import metric_bonus, normalized_v2_metrics_by_op_id

if TYPE_CHECKING:
    from core.services.scheduler.run.optimizer.shared_decode import SharedDecodeSession


def _profile_identity(profile: GraphReadyWeightProfile) -> Tuple[Any, ...]:
    return (
        profile.formula_version,
        profile.formula_slug,
        profile.feature_basis,
        tuple(sorted(profile.effective_weights.items())),
        profile.jitter_seed,
    )


class PreparedDecisionFeatures:
    """Admit each effective profile once against one owned, fixed feature set.

    ``schedulable_ids`` is the preparation's own ``topology.schedulable_ids``; keys admitted against it pass
    every later decode request by identity.
    """

    def __init__(self, metrics_by_op_id: Dict[int, Dict[str, Any]],
                 v2_common_rank_cache: Dict[str, Dict[int, float]], *, schedulable_ids: FrozenSet[int]) -> None:
        self.metrics_by_op_id = metrics_by_op_id
        self.v2_common_rank_cache = v2_common_rank_cache
        self.schedulable_ids = schedulable_ids
        self._baseline_metrics: Optional[Dict[int, Dict[str, Any]]] = None
        self._normalized_metrics_by_basis_seed: Dict[Tuple[str, int], Dict[int, Dict[str, Any]]] = {}
        self._priority_keys_by_profile: Dict[Tuple[Any, ...], ValidatedGraphPriorityKeys] = {}

    def selected_metrics(self, profile: GraphReadyWeightProfile) -> Dict[int, Dict[str, Any]]:
        """The profile's feature set: a v2 basis selection (one shared baseline copy) or the shared metrics."""
        if _uses_v2_formula(profile) and profile.feature_basis == BATCH_WORKLOAD_BASIS:
            if self._baseline_metrics is None:
                self._baseline_metrics = select_profile_metrics(self.metrics_by_op_id, profile=profile)
            return self._baseline_metrics
        return select_profile_metrics(self.metrics_by_op_id, profile=profile)

    def priority_keys_for_profile(self, profile: GraphReadyWeightProfile) -> ValidatedGraphPriorityKeys:
        """Keys admitted once against this feature set's operations; decodes reuse them and their weak order."""
        identity = _profile_identity(profile)
        cached = self._priority_keys_by_profile.get(identity)
        if cached is not None:
            return cached
        keys = graph_priority_key_map(_priority_keys_for_profile(
            self.selected_metrics(profile), profile=profile, v2_common_rank_cache=self.v2_common_rank_cache,
            normalized_metrics_cache=self._normalized_metrics_by_basis_seed,
        ), schedulable_ids=self.schedulable_ids)
        self._priority_keys_by_profile[identity] = keys
        return keys


def evaluate_graph_ready_candidate(
    *,
    profile: GraphReadyWeightProfile,
    strategy: SortStrategy,
    params: Dict[str, Any],
    start_dt: datetime,
    end_date: Optional[date],
    order: Sequence[str],
    dispatch_rule: str,
    resource_pool: Optional[Dict[str, Any]],
    objective_name: str,
    optimizer_algo_stats: Optional[Dict[str, Any]],
    readiness_gate_enabled: bool,
    version: int,
    clock: Callable[[], float],
    repair: Optional[Tuple[RepairDecision, RepairParentPreparation]] = None,
    before_decode: Optional[Callable[[], None]] = None,
    decode_resume: Optional[Any] = None,
    decode_checkpoints: Optional[Any] = None,
    decode_session: SharedDecodeSession,
    redecode_reason: Optional[str] = None,
    prepared_decision_features: PreparedDecisionFeatures,
) -> Dict[str, Any]:
    # runtime_ms 合同语义是"该候选自身的构造+解码+评估耗时"(同分 tie-break 偏好更快候选,
    # 见 optimizer_candidate_comparison.candidate_runtime_ms 与 GRAPH_READY_SELECTION_TIEBREAKER)。
    # 必须在这里 per-candidate 计时,不能由调用方传"自优化开始的累计流逝时间"——
    # 累计值随 profile 评估序号单调递增,会把"偏好更快"悄悄变成"偏好更早评估的 profile"。
    t_candidate_begin = clock()
    # Repair and iterated-greedy stages pass a decision together with the decoded parent it was
    # generated from (repair._repair_one_elite, _IteratedGreedySearch._decode); every other stage passes none.
    repair_decision = repair[0] if repair is not None else None
    operation_resources = None
    if repair is None:
        graph_priority_key_by_op_id = prepared_decision_features.priority_keys_for_profile(profile)
    else:
        graph_priority_key_by_op_id, operation_resources = repair_decision_inputs(*repair)
    # Decode checkpoints are an optimizer-internal trial accelerator; only forwarded when a stage asks.
    decode_kwargs: Dict[str, Any] = {}
    if decode_resume is not None:
        decode_kwargs["decode_resume"] = decode_resume
    if decode_checkpoints is not None:
        decode_kwargs["decode_checkpoints"] = decode_checkpoints
    from core.services.scheduler.run.optimizer.shared_decode import decode_and_metrics

    full_profile_payload = profile_payload(profile, version=version)
    decoded = decode_and_metrics(
        decode_session=decode_session, objective_name=objective_name,
        optimizer_algo_stats=optimizer_algo_stats,
        before_decode=before_decode,
        redecode_reason=redecode_reason,
        operation_resources=operation_resources,
        strategy=strategy, strategy_params=_candidate_params(params, profile_dict=full_profile_payload), start_dt=start_dt,
        end_date=end_date, batch_order_override=order,
        dispatch_mode="sgs", dispatch_rule=dispatch_rule,
        readiness_gate_enabled=readiness_gate_enabled, graph_enabled=True,
        graph_score_enabled=True,
        graph_priority_key_by_op_id=graph_priority_key_by_op_id, **decode_kwargs,
    )
    runtime_ms = max(int((clock() - t_candidate_begin) * 1000), 0)
    candidate = build_graph_ready_candidate_payload(
        res=decoded.results,
        decoded_order=decoded.decoded_batch_order,
        summ=decoded.summary,
        used_strat=decoded.used_strategy,
        used_params=decoded.used_params,
        metrics=decoded.metrics,
        profile=profile,
        order=order,
        dispatch_rule=dispatch_rule,
        objective_name=objective_name,
        algo_stats=decoded.algo_stats,
        resource_pool=resource_pool,
        runtime_ms=runtime_ms,
        repair_decision=repair_decision,
        profile_dict=full_profile_payload,
    )
    candidate["archive_ref"] = decoded.archive_ref()
    candidate["decode_receipt"] = decoded.receipt
    if decoded.receipt["execution_kind"] == "decision_reused":
        source_runtime_ms = decoded.receipt["source_runtime_ms"]
        candidate["runtime_ms"] = (source_runtime_ms if source_runtime_ms is not None
                                   else decoded.receipt["original_decode_ms"])
        if decoded.receipt["source_initial_decode_runtime_ms"] is not None:
            candidate["initial_decode_runtime_ms"] = decoded.receipt["source_initial_decode_runtime_ms"]
    return candidate


def _priority_keys_for_profile(
    metrics: Dict[int, Dict[str, Any]],
    *,
    profile: GraphReadyWeightProfile,
    v2_common_rank_cache: Dict[str, Dict[int, float]],
    normalized_metrics_cache: Dict[Tuple[str, int], Dict[int, Dict[str, Any]]],
) -> Dict[int, Tuple[float, ...]]:
    if not _uses_v2_formula(profile):
        return {op_id: _v1_priority_key(metric, profile=profile) for op_id, metric in sorted(metrics.items())}
    normalized = normalized_v2_metrics_by_op_id(
        metrics,
        profile=profile,
        v2_common_rank_cache=_profile_rank_cache(v2_common_rank_cache, profile),
        normalized_metrics_cache=normalized_metrics_cache,
    )
    if not normalized:
        return {}
    specs = v2_formula_specs(profile.formula_slug)
    return {op_id: v2_priority_key_for_metric(metric, specs=specs) for op_id, metric in sorted(normalized.items())}


def _v1_priority_key(metric: Dict[str, Any], *, profile: GraphReadyWeightProfile) -> Tuple[float, ...]:
    rank = metric["critical_path_rank"]
    bonus = metric_bonus(metric, weights=profile.effective_weights)
    return (
        float(round(-bonus, 6)),
        float(rank if rank is not None else 1_000_000_000.0),
    )


def _profile_rank_cache(v2_common_rank_cache: Dict[str, Dict[int, float]],
                        profile: GraphReadyWeightProfile) -> Dict[str, Dict[int, float]]:
    is_baseline = profile.feature_basis == BATCH_WORKLOAD_BASIS
    return {
        field[len(BASELINE_RANK_PREFIX):] if is_baseline else field: ranks
        for field, ranks in v2_common_rank_cache.items()
        if field.startswith(BASELINE_RANK_PREFIX) == is_baseline
    }


def _uses_v2_formula(profile: GraphReadyWeightProfile) -> bool:
    return profile.formula_version.startswith("graph_ready_v2")


def _candidate_params(params: Dict[str, Any], *, profile_dict: Dict[str, Any]) -> Dict[str, Any]:
    candidate_params = dict(params)
    candidate_params["graph_ready_profile"] = profile_dict
    return candidate_params
