"""Serialization and formal scoring of a decoded graph candidate."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from core.algorithms import ScheduleResult
from core.algorithms.evaluation import objective_score
from core.algorithms.greedy.algo_stats import merge_algo_stats, snapshot_algo_stats

from .optimizer_graph_ready_profiles import (
    GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN,
    GRAPH_READY_V2_REPAIRED_ORIGIN,
    GraphReadyWeightProfile,
    profile_payload,
)
from .optimizer_graph_ready_reporting import public_params


def build_graph_ready_candidate_payload(**kwargs: Any) -> Dict[str, Any]:
    profile = kwargs["profile"]
    metrics = kwargs["metrics"]
    decision_order = list(kwargs["order"])
    decoded_batch_order = _decoded_batch_order(kwargs["res"])
    result_order = _result_batch_order(decoded_batch_order, decision_order=decision_order)
    payload = {
        "results": kwargs["res"],
        "summary": kwargs["summ"],
        "strategy": kwargs["used_strat"],
        "params": public_params(kwargs["used_params"]),
        "dispatch_mode": "sgs",
        "dispatch_rule": str(kwargs["dispatch_rule"] or ""),
        "order": result_order,
        "decision_batch_order": decision_order,
        "decoded_batch_order": decoded_batch_order,
        "metrics": metrics,
        "score": (float(kwargs["summ"].failed_ops),) + objective_score(kwargs["objective_name"], metrics),
        "algo_stats": merge_algo_stats(kwargs["optimizer_algo_stats"], snapshot_algo_stats(kwargs["scheduler"])),
        "resource_pool": kwargs["resource_pool"] or {},
        "seed_result_count": len(kwargs["seed_sr_list"] or []),
        "locked_seed_range": [getattr(item, "op_id", None) for item in list(kwargs["seed_sr_list"] or [])],
        "mutable_scope": _mutable_scope(profile, version=int(kwargs["version"])),
        "candidate_origin": profile.candidate_origin,
        "runtime_ms": int(kwargs["runtime_ms"]),
        "graph_ready_profile": profile_payload(profile, version=int(kwargs["version"])),
    }
    decision = kwargs.get("repair_decision")
    if decision is not None:
        payload["repair_decision"] = {
            "batch_order": list(decision.batch_order), "operation_order": list(decision.operation_order),
            "resource_overrides": [list(item) for item in decision.resource_overrides],
        }
        payload["mutable_scope"].update({key: payload["repair_decision"][key] for key in ("operation_order", "resource_overrides")})
    return payload


def _decoded_batch_order(results: List[ScheduleResult]) -> List[str]:
    order: List[str] = []
    seen = set()
    for result in sorted(
        list(results or []),
        key=lambda item: (
            getattr(item, "start_time", None) or datetime.max,
            getattr(item, "end_time", None) or datetime.max,
            int(getattr(item, "seq", 0) or 0),
            int(getattr(item, "op_id", 0) or 0),
        ),
    ):
        batch_id = str(getattr(result, "batch_id", "") or "").strip()
        if not batch_id or batch_id in seen:
            continue
        seen.add(batch_id)
        order.append(batch_id)
    return order


# Public name for stages that rebuild a decision from decoded results (elite repair, iterated greedy).
decoded_batch_order = _decoded_batch_order


def _result_batch_order(decoded_batch_order: List[str], *, decision_order: List[str]) -> List[str]:
    out = list(decoded_batch_order or [])
    seen = set(out)
    for batch_id in list(decision_order or []):
        text = str(batch_id or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


_SCOPE_BY_ORIGIN = {GRAPH_READY_V2_REPAIRED_ORIGIN: "graph_ready_elite_repair",
                    GRAPH_READY_V2_ITERATED_GREEDY_ORIGIN: "graph_ready_iterated_greedy"}


def _mutable_scope(profile: GraphReadyWeightProfile, *, version: int) -> Dict[str, Any]:
    return {
        "scope": _SCOPE_BY_ORIGIN.get(profile.candidate_origin, "graph_ready_priority"),
        "weight_profile_slug": profile.slug,
        "raw_weights": dict(profile.raw_weights),
        "candidate_policy": profile.candidate_policy,
        "seed": int(version),
    }
