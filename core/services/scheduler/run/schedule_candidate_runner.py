from __future__ import annotations

import math
import time
from copy import deepcopy
from dataclasses import is_dataclass, replace
from types import SimpleNamespace
from typing import Any, Callable, Optional, cast

from core.errors import ValidationError
from core.models.schedule_config_runtime import ensure_schedule_config_snapshot

from .optimizer.search_budget import SearchBudget, SearchBudgetExhausted
from .optimizer.shared_process import _numeric_score, score_scope_payload
from .schedule_candidate_plan import CandidateComparisonOutcome, CandidatePlan
from .schedule_candidate_selection import BusinessObjectiveSelectionResult
from .schedule_graph_report import prepare_schedule_graph_for_dispatch
from .schedule_shared_optimizer import optimize_shared_schedule


def _replace_schedule_input_cfg(schedule_input: Any, *, cfg: Any) -> Any:
    if is_dataclass(schedule_input) and not isinstance(schedule_input, type):
        return replace(cast(Any, schedule_input), cfg=cfg)
    if hasattr(schedule_input, "__dict__"):
        data = dict(vars(schedule_input))
        data["cfg"] = cfg
        return SimpleNamespace(**data)
    raise TypeError("schedule_input 必须是 dataclass 或普通对象，才能构造候选级输入。")


def _resolve_total_budget(run_time_budget_seconds: Optional[float], *, cfg: Any) -> float:
    if run_time_budget_seconds is None:
        return float(cfg.time_budget_seconds)
    if isinstance(run_time_budget_seconds, bool):
        raise ValidationError("这次找更好排法先试多久必须是数字。", field="run_time_budget_seconds")
    try:
        budget = float(run_time_budget_seconds)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError("这次找更好排法先试多久必须是数字。", field="run_time_budget_seconds") from exc
    if math.isnan(budget) or budget <= 0:
        raise ValidationError("这次找更好排法先试多久必须大于 0 秒。", field="run_time_budget_seconds")
    return budget


def _public_budget(total_budget: float) -> Optional[float]:
    if not math.isfinite(total_budget):
        return None
    return float(total_budget)


def run_candidate_comparison(
    *, schedule_input: Any,
    optimize_shared_schedule_fn: Optional[Callable[..., Any]] = None,
    prepare_graph_fn: Optional[Callable[[Any], Any]] = None,
    clock: Optional[Callable[[], float]] = None,
    run_time_budget_seconds: Optional[float] = None,
    strict_mode: bool = False, logger: Any = None,
) -> CandidateComparisonOutcome:
    """Publish the actual business representatives from one shared search archive."""
    now = clock or time.monotonic
    cfg = ensure_schedule_config_snapshot(schedule_input.cfg, strict_mode=bool(strict_mode))
    total_budget = _resolve_total_budget(run_time_budget_seconds, cfg=cfg)
    if math.isfinite(total_budget) and total_budget.is_integer() and total_budget >= 1:
        cfg = replace(cfg, time_budget_seconds=int(total_budget))
    started = now()
    deadline = started + total_budget
    budget = SearchBudget(clock=now, started_at=started, deadline=deadline,
                          assigned_seconds=total_budget)
    prepare_graph = prepare_graph_fn or prepare_schedule_graph_for_dispatch
    preparation = None

    def graph_prepare():
        nonlocal preparation
        preparation = prepare_graph(_replace_schedule_input_cfg(schedule_input, cfg=cfg))
        return preparation

    shared = (optimize_shared_schedule_fn or optimize_shared_schedule)(
        calendar_service=schedule_input.cal_svc, cfg_svc=schedule_input.cfg_svc, cfg=cfg,
        algo_ops_to_schedule=schedule_input.algo_ops_to_schedule, batches=schedule_input.batches,
        start_dt=schedule_input.start_dt_norm, end_date=schedule_input.end_date_norm,
        downtime_map=schedule_input.downtime_map, seed_results=schedule_input.seed_results,
        resource_pool=schedule_input.resource_pool, version=int(schedule_input.optimizer_seed_version),
        logger=logger, readiness_gate_enabled=bool(schedule_input.readiness_gate_enabled),
        strict_mode=bool(strict_mode), graph_prepare=graph_prepare, search_budget=budget,
    )
    primary = shared.archive.primary_objective
    targets = tuple(shared.target_objectives)
    selected_entries = shared.process_facts["selected_entries_by_objective"]
    candidates, entries = [], {}
    for target in targets:
        entry_id = selected_entries[target]
        if entry_id is None or entry_id in entries:
            continue
        entry = shared.archive.entry(entry_id)
        candidate = _business_representative(
            shared, entry, sequence=len(candidates), primary=primary, targets=targets,
            cfg=cfg, preparation=preparation, total_budget=total_budget)
        entries[entry_id] = candidate
        candidates.append(candidate)
    if not candidates:
        raise SearchBudgetExhausted("candidate_time_budget_reached")
    selected = entries[selected_entries[primary]]
    scope = dict(selected.evaluations[primary]["scoring_scope"])
    known = scope["components_known"]
    winners = {target: entries[selected_entries[target]].candidate_key if known and selected_entries[target] is not None else None
               for target in targets}
    selection = BusinessObjectiveSelectionResult(
        selected_candidate_key=selected.candidate_key, selected_plan=selected,
        primary_objective=primary, target_objectives=targets, objective_winners=winners,
        objective_winner_reasons={target: None if known else "score_components_unavailable" for target in targets},
        objective_field_order={target: list(selected.evaluations[target]["field_order"]) for target in targets},
        selected_score=tuple(selected.score), scoring_scope=scope,
        reason_code=("primary_objective_best_found" if scope["is_complete"] else
                     "primary_objective_best_in_completed_scope" if known else "partial_scope_score_unavailable"),
        evidence_state="complete" if scope["is_complete"] and known else "partial",
    )
    return CandidateComparisonOutcome(
        candidates=candidates, selection=selection, planned_count=len(candidates), completed_count=len(candidates),
        failed_count=0, skipped_count=0, reused_count=0,
        time_budget_reached=shared.process_facts["stop_reason"] == "time_budget",
        selection_policy="business_objectives_v1", run_time_budget_seconds=_public_budget(total_budget),
        skipped_candidate_labels=[], baseline_missing_or_failed=False,
        generation_policy_version="unified_search_v1", primary_objective=primary,
        target_objectives=list(targets), unified_process=shared.process_facts["unified_process"],
    )


def _business_representative(shared, entry, *, sequence, primary, targets, cfg, preparation, total_budget):
    candidate = shared.archive.materialize(entry.entry_id, objective=primary)
    scope = score_scope_payload(entry.score_scope)
    representatives = ([target for target in targets
                        if shared.process_facts["selected_entries_by_objective"][target] == entry.entry_id]
                       if scope["components_known"] else [])
    labels = {"min_overdue": "交期优先", "min_tardiness": "拖期更轻", "min_changeover": "切换更少",
              "min_weighted_tardiness": "加权拖期更轻"}
    params = candidate["params"]
    origin = deepcopy(entry.evidence_origin)
    profile = params.get("graph_ready_profile")
    if profile is not None:
        origin["graph_ready_profile"] = profile
    weights = profile.get("effective_weights", {}) if isinstance(profile, dict) else {}
    return CandidatePlan(
        sequence=sequence, candidate_key="business_" + str(sequence + 1), kind="business_objective",
        label=" · ".join(labels[target] for target in representatives) if representatives else "算法选中的部分结果",
        status="completed", score=tuple(entry.evaluations[primary].score),
        graph_critical_weight=weights.get("critical_weight"), graph_impact_weight=weights.get("impact_weight"),
        graph_downstream_weight=weights.get("downstream_weight"),
        results=candidate["results"], summary=candidate["summary"], metrics=candidate["metrics"], health=None,
        graph_analysis_public=preparation.graph_analysis_public if preparation is not None else None,
        graph_analysis_diagnostics=preparation.graph_analysis_diagnostics if preparation is not None else None,
        used_strategy=candidate["strategy"], used_params=params, best_order=candidate.get("order") or [],
        algo_mode=str(cfg.algo_mode), objective_name=primary, objective=primary,
        algo_stats=candidate.get("algo_stats") or {}, time_budget_seconds=total_budget,
        sort_strategy=str(getattr(candidate["strategy"], "value", candidate["strategy"])),
        dispatch_mode=str(params["dispatch_mode"]), dispatch_rule=str(params["dispatch_rule"]),
        adopted_dispatch_rule=str(params["dispatch_rule"]), generation_policy_version="unified_search_v1",
        representative_objectives=representatives,
        evaluations={target: {"field_order": list(entry.evaluations[target].field_order),
            "score": _numeric_score(entry.evaluations[target].score, components_known=scope["components_known"]),
            "scoring_scope": dict(scope)} for target in targets},
        origin=origin, first_found_elapsed_ms=entry.first_found_elapsed_ms,
        search_evidence_ref={"source_event_id": shared.process_facts["evidence_event_ids_by_entry"].get(entry.entry_id)},
    )



__all__ = ["CandidateComparisonOutcome", "CandidatePlan", "run_candidate_comparison"]
