from __future__ import annotations

from time import monotonic
from typing import Any, Callable, Optional

from .optimizer.search_budget import SearchBudget, SearchBudgetExhausted
from .optimizer.shared_process import numeric_score, score_scope_payload
from .schedule_candidate_plan import CandidateComparisonOutcome, CandidatePlan
from .schedule_candidate_selection import BusinessObjectiveSelectionResult
from .schedule_graph_report import prepare_schedule_graph_for_dispatch
from .schedule_input_contracts import ScheduleRunInput
from .schedule_shared_optimizer import optimize_shared_schedule


def run_candidate_comparison(
    *, schedule_input: ScheduleRunInput,
    prepare_graph_fn: Optional[Callable[[Any], Any]] = None,
) -> CandidateComparisonOutcome:
    """Publish the actual business representatives from one shared search archive."""
    cfg = schedule_input.cfg
    total_budget = float(cfg.time_budget_seconds)
    started = monotonic()
    deadline = started + total_budget
    budget = SearchBudget(clock=monotonic, started_at=started, deadline=deadline,
                          assigned_seconds=total_budget)
    prepare_graph = prepare_graph_fn or prepare_schedule_graph_for_dispatch
    preparation = None

    def graph_prepare():
        nonlocal preparation
        preparation = prepare_graph(schedule_input)
        return preparation

    shared = optimize_shared_schedule(
        calendar_service=schedule_input.cal_svc, cfg=cfg,
        algo_ops_to_schedule=schedule_input.algo_ops_to_schedule, batches=schedule_input.batches,
        start_dt=schedule_input.start_dt_norm, end_date=schedule_input.end_date_norm,
        downtime_map=schedule_input.downtime_map, seed_results=schedule_input.seed_results,
        resource_pool=schedule_input.resource_pool, version=schedule_input.optimizer_seed_version,
        readiness_gate_enabled=schedule_input.readiness_gate_enabled,
        graph_prepare=graph_prepare, search_budget=budget,
    )
    primary = shared.archive.primary_objective
    targets = shared.target_objectives
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
        candidates=candidates, selection=selection,
        time_budget_reached=shared.process_facts["stop_reason"] == "time_budget",
        run_time_budget_seconds=total_budget,
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
    # 只在本处补一个键：浅拷一层，不改归档里的来源记录。
    origin = dict(entry.evidence_origin)
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
        results=candidate["results"], summary=candidate["summary"], metrics=candidate["metrics"],
        graph_analysis_public=preparation.graph_analysis_public if preparation is not None else None,
        graph_analysis_diagnostics=preparation.graph_analysis_diagnostics if preparation is not None else None,
        # Every verified decode is observed before it can be selected, which merges its order (finish_observation).
        used_strategy=candidate["strategy"], used_params=params, best_order=candidate["order"],
        algo_mode=cfg.algo_mode, objective_name=primary,
        algo_stats=candidate["algo_stats"], time_budget_seconds=total_budget,
        sort_strategy=candidate["strategy"].value,
        dispatch_mode=params["dispatch_mode"], dispatch_rule=params["dispatch_rule"],
        adopted_dispatch_rule=params["dispatch_rule"], generation_policy_version="unified_search_v1",
        representative_objectives=representatives,
        evaluations={target: {"field_order": list(entry.evaluations[target].field_order),
            "score": numeric_score(entry.evaluations[target].score, components_known=scope["components_known"]),
            "scoring_scope": dict(scope)} for target in targets},
        origin=origin, first_found_elapsed_ms=entry.first_found_elapsed_ms,
        search_evidence_ref={"source_event_id": shared.process_facts["evidence_event_ids_by_entry"].get(entry.entry_id)},
    )



__all__ = ["CandidateComparisonOutcome", "CandidatePlan", "run_candidate_comparison"]
