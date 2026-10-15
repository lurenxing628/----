"""Small storage/read fixtures with a fixed historical candidate directory.

Current engines supply legal arrangements. Historical directory, selection and
health dictionaries are explicit saved material for reading contracts; they do
not represent the frozen U0/20k archive or rerun the retired trial engine.
"""

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from core.algorithms import GreedyScheduler
from core.algorithms.evaluation import compute_metrics
from core.models.objective import best_score_schema
from core.services.scheduler.run.schedule_candidate_plan import CandidateComparisonOutcome
from core.services.scheduler.run.schedule_candidate_runner import run_candidate_comparison
from core.services.scheduler.run.schedule_seed_contracts import coerce_seed_results
from core.services.workbench.run import compute as compute_module

# Fixed stored directory, independent of the retired 3/5/7 generation algorithm.
LEGACY_CANDIDATE_DIRECTORY = (
    {"sequence": 0, "candidate_key": "baseline", "kind": "baseline", "label": "原算法",
     "graph_critical_weight": 0, "graph_impact_weight": 0, "graph_downstream_weight": 0},
    {"sequence": 1, "candidate_key": "graph_w1_of_3", "kind": "critical_chain", "label": "重点工序优先方案 1/3",
     "graph_critical_weight": 250, "graph_impact_weight": 5, "graph_downstream_weight": 1},
    {"sequence": 2, "candidate_key": "graph_w2_of_3", "kind": "critical_chain", "label": "重点工序优先方案 2/3",
     "graph_critical_weight": 500, "graph_impact_weight": 10, "graph_downstream_weight": 1},
    {"sequence": 3, "candidate_key": "graph_w3_of_3", "kind": "critical_chain", "label": "重点工序优先方案 3/3",
     "graph_critical_weight": 750, "graph_impact_weight": 15, "graph_downstream_weight": 2},
)
LEGACY_SAME_HEALTH = {
    "state": "same", "score": 0, "reason_code": "critical_chain_same",
    "critical_chain_finish_hours_delta": 0.0, "critical_chain_wait_hours_delta": 0.0,
    "top_impact_ops_avg_start_hours_delta": None, "critical_chain_slack_hours_delta": None,
    "critical_chain_node_count": 1, "top_impact_op_count": 0,
}


# Original saved selection evidence for the default failed-baseline reading fixture.
LEGACY_FAILED_BASELINE_DECISION_EVIDENCE = {'version': 'candidate-selection-evidence-v1',
 'state': 'complete',
 'anchors': {'raw_score_best': {'candidate_key': 'graph_w1_of_3',
                                'score': [0.0, 0.0, 0.0, 0.0, 0.75, 0.0],
                                'failed_ops': 0.0,
                                'primary_score': 0.0,
                                'overdue_count': 0.0,
                                'total_tardiness_hours': 0.0},
             'health_reference': None},
 'selected': {'candidate_key': 'graph_w1_of_3',
              'score': [0.0, 0.0, 0.0, 0.0, 0.75, 0.0],
              'failed_ops': 0.0,
              'primary_score': 0.0,
              'overdue_count': 0.0,
              'total_tardiness_hours': 0.0},
 'tiebreak': {'rule': 'full_score_baseline_sequence_v1',
              'raw_score_best_candidate_key': 'graph_w1_of_3',
              'runner_up_candidate_key': 'graph_w2_of_3',
              'decisive_step': 'candidate_sequence',
              'decisive_score_index': None,
              'primary_tied_candidate_keys': ['graph_w1_of_3', 'graph_w2_of_3', 'graph_w3_of_3'],
              'full_score_tied_candidate_keys': ['graph_w1_of_3', 'graph_w2_of_3', 'graph_w3_of_3']},
 'balanced_checks': {'eligible': False,
                     'checked': False,
                     'reason_code': 'baseline_unavailable',
                     'candidate_key': 'graph_w1_of_3',
                     'reference_candidate_key': 'graph_w1_of_3',
                     'health_reference_candidate_key': None,
                     'health_state': None,
                     'checks': [],
                     'accepted': False,
                     'override_applied': False}}


def load_legacy_process_evidence(key, *, source_candidate_key=None, reason=None):
    """Load a deep copy of an explicit historical saved process dictionary."""
    path = Path(__file__).with_name("fixtures") / "legacy_process_evidence.json"
    saved = deepcopy(json.loads(path.read_text(encoding="utf-8"))["evidence"][key])
    if source_candidate_key is not None:
        saved["source"]["reused_from_candidate_key"] = source_candidate_key
    if reason is not None:
        saved["stop_reason"] = reason
    return saved


def stored_legacy_selection(snapshot, selected_plan):
    """Adapt an explicit saved dictionary to the persistence protocol."""
    saved = deepcopy(snapshot)
    return SimpleNamespace(**saved, selected_plan=selected_plan,
                           to_dict=lambda: deepcopy(saved))


def _legacy_plan(original, directory_entry, schedule_input):
    metrics = compute_metrics(original.results, schedule_input.batches,
        expected_operations=schedule_input.algo_ops_to_schedule,
        seed_results=coerce_seed_results(schedule_input.seed_results, optimizer_algo_stats={}),
        failure_details=original.summary.failure_details)
    values = {**metrics.to_dict(), "failed_ops": original.summary.failed_ops}
    objective = original.objective_name
    return replace(original, **directory_entry,
        metrics=metrics, score=tuple(values[item["key"]] for item in best_score_schema(objective)),
        health=deepcopy(LEGACY_SAME_HEALTH), generation_policy_version=None,
        representative_objectives=[], evaluations={}, origin=None,
        first_found_elapsed_ms=None, search_evidence_ref=None)


def _install_archive_fixture(monkeypatch, build_plans, *, time_budget_reached=False,
                             selected_key="baseline", baseline_key="baseline", critical_key="graph_w1_of_3",
                             selection_snapshot=None):
    def archived_comparison(**kwargs):
        actual = run_candidate_comparison(**kwargs)
        plans = build_plans(kwargs["schedule_input"], actual.selection.selected_plan)
        selected = next(plan for plan in plans if plan.candidate_key == selected_key)
        selection = stored_legacy_selection({
            "selected_candidate_key": selected_key, "selected_kind": selected.kind,
            "selection_policy": "balanced", "reason_code": "balanced_raw_score_best",
            "raw_score_best_key": selected_key, "baseline_best_key": baseline_key,
            "critical_best_key": critical_key, "critical_health_best_key": None,
            "selected_score": list(selected.score), "selection_policy_version": "candidate-selection-v1",
            "overdue_tolerance_count": 1, "tardiness_tolerance_ratio": 0.10,
            **(selection_snapshot or {}),
        }, selected)
        return CandidateComparisonOutcome(candidates=plans, selection=selection,
            planned_count=len(plans), completed_count=sum(row.status == "completed" for row in plans),
            failed_count=sum(row.status == "failed" for row in plans),
            skipped_count=sum(row.status == "skipped" for row in plans),
            time_budget_reached=time_budget_reached, selection_policy="balanced",
            run_time_budget_seconds=actual.run_time_budget_seconds,
            skipped_candidate_labels=[row.label for row in plans if row.status == "skipped"],
            baseline_missing_or_failed=baseline_key is None)

    monkeypatch.setattr(compute_module, "run_candidate_comparison", archived_comparison)


def install_complete_legacy_archive(monkeypatch, *, selection_snapshot=None):
    def build(schedule_input, original):
        return [_legacy_plan(original, entry, schedule_input) for entry in LEGACY_CANDIDATE_DIRECTORY]

    _install_archive_fixture(monkeypatch, build, selection_snapshot=selection_snapshot)


def install_budget_skipped_archive(monkeypatch):
    def build(schedule_input, original):
        plans = [_legacy_plan(original, entry, schedule_input) for entry in LEGACY_CANDIDATE_DIRECTORY]
        return [plans[0]] + [replace(plan, status="skipped", score=None, results=[], summary=None,
            metrics=None, health=None, failure_reason="candidate_time_budget_reached",
            process_evidence=load_legacy_process_evidence(original.objective_name + "_not_started")) for plan in plans[1:]]

    _install_archive_fixture(monkeypatch, build, time_budget_reached=True, critical_key=None)


def install_failed_baseline_archive(monkeypatch):
    def build(schedule_input, original):
        plans = [_legacy_plan(original, entry, schedule_input) for entry in LEGACY_CANDIDATE_DIRECTORY]
        reason = "原算法候选计算失败：测试数据指定该次候选失败。"
        failed = replace(plans[0], status="failed", score=None, results=[], summary=None, metrics=None,
            health=None, failure_reason=reason,
            process_evidence=load_legacy_process_evidence(original.objective_name + "_failed_0", reason=reason))
        return [failed] + plans[1:]

    _install_archive_fixture(monkeypatch, build, selected_key="graph_w1_of_3", baseline_key=None,
        selection_snapshot={"decision_evidence": deepcopy(LEGACY_FAILED_BASELINE_DECISION_EVIDENCE)})


def install_different_work_archive(monkeypatch):
    def build(schedule_input, original):
        def arrangement(order):
            results, summary, strategy, params = GreedyScheduler(
                schedule_input.cal_svc, schedule_input.cfg).schedule(
                    operations=schedule_input.algo_ops_to_schedule, batches=schedule_input.batches,
                    strategy=original.used_strategy, strategy_params=original.used_params,
                    start_dt=schedule_input.start_dt_norm, end_date=schedule_input.end_date_norm,
                    machine_downtimes=schedule_input.downtime_map, batch_order_override=order,
                    seed_results=coerce_seed_results(schedule_input.seed_results, optimizer_algo_stats={}),
                    dispatch_mode=original.dispatch_mode, dispatch_rule=original.adopted_dispatch_rule,
                    resource_pool=schedule_input.resource_pool,
                    readiness_gate_enabled=schedule_input.readiness_gate_enabled)
            return replace(original, results=results, summary=summary,
                           used_strategy=strategy, used_params=params, best_order=order)

        baseline = _legacy_plan(arrangement(["B1", "B2"]), LEGACY_CANDIDATE_DIRECTORY[0], schedule_input)
        alternative = arrangement(["B2", "B1"])
        assert {row.op_id for row in baseline.results} != {row.op_id for row in alternative.results}
        return [baseline] + [_legacy_plan(alternative, entry, schedule_input) for entry in LEGACY_CANDIDATE_DIRECTORY[1:]]

    _install_archive_fixture(monkeypatch, build, selected_key="graph_w1_of_3")
