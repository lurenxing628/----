"""Frozen candidate-selection-v1 run archives written beside a real current computation.

Current engines supply legal arrangements for the test database. These fixtures
then write the saved shape of retired candidate-selection-v1 runs (fixed candidate
directory, health and selection dictionaries) through the worker's own
persistence transaction. Production no longer writes this shape; it only reads
saved archives (``core/infrastructure/migrations/v41.py`` derives their read
models). The material does not represent the frozen U0/20k archive or rerun the
retired trial engine.
"""

import json
from copy import deepcopy
from dataclasses import fields, replace
from pathlib import Path

from core.algorithm_contracts.operation_effort import RUNTIME_REQUIREMENT_BASIS
from core.algorithms.evaluation import compute_metrics
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.models.objective import best_score_schema
from core.models.workbench_run_compute import PreparedRunResult
from core.models.workbench_run_job import durable_value, new_run_ref
from core.services.scheduler.run.schedule_seed_contracts import coerce_seed_results
from core.services.workbench.facts.decision_read_model import build_decision_read_models
from core.services.workbench.run import worker as worker_module
from core.services.workbench.run.compute_validation import validate_candidate
from data.repositories.workbench_run_repo import encode_decision_read_models, encode_result
from data.repositories.workbench_run_result_repo import encode_candidate_rows
from tests._support.schedule_decode import production_decode

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

# Candidate-selection-v1 artifacts never carried the fields unified_search_v1 introduced.
_UNIFIED_ONLY_FIELDS = ("generation_policy_version", "representative_objectives", "evaluations", "origin",
                        "first_found_elapsed_ms", "search_evidence_ref")
_TASK_OWNED_FIELDS = ("machine_id", "operator_id", "start_time", "end_time", "source")
_SAVED_SELECTION_REFS = {
    "selected_candidate_key": "selected_candidate_ref", "raw_score_best_key": "raw_score_best_candidate_ref",
    "baseline_best_key": "health_reference_candidate_ref", "critical_best_key": "critical_best_candidate_ref",
    "critical_health_best_key": "critical_health_best_candidate_ref",
}


def load_legacy_process_evidence(key, *, source_candidate_key=None, reason=None):
    """Load a deep copy of an explicit historical saved process dictionary."""
    path = Path(__file__).with_name("fixtures") / "legacy_process_evidence.json"
    saved = deepcopy(json.loads(path.read_text(encoding="utf-8"))["evidence"][key])
    if source_candidate_key is not None:
        saved["source"]["reused_from_candidate_key"] = source_candidate_key
    if reason is not None:
        saved["stop_reason"] = reason
    return saved


def _legacy_plan(original, directory_entry, schedule_input):
    metrics = compute_metrics(original.results, schedule_input.batches,
        expected_operations=schedule_input.algo_ops_to_schedule,
        seed_results=coerce_seed_results(schedule_input.seed_results, optimizer_algo_stats={}),
        failure_details=original.summary.failure_details)
    values = {**metrics.to_dict(), "failed_ops": original.summary.failed_ops}
    return replace(original, **directory_entry, metrics=metrics,
        score=tuple(values[item["key"]] for item in best_score_schema(original.objective_name)),
        health=deepcopy(LEGACY_SAME_HEALTH))


def _key_references(value, refs):
    """Saved archives froze nested candidate keys as permanent candidate references."""
    if isinstance(value, list):
        return [_key_references(item, refs) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key == "candidate_key" or key.endswith("_candidate_key"):
            result[key[:-3] + "ref"] = refs[item] if item is not None else None
        elif key == "candidate_keys" or key.endswith("_candidate_keys"):
            result[key[:-4] + "refs"] = [refs[candidate] for candidate in item]
        else:
            result[key] = _key_references(item, refs)
    return result


def _saved_candidate(plan, payload, *, refs, identities, frozen_op_ids):
    artifact = {item.name: durable_value(getattr(plan, item.name)) for item in fields(plan)
                if item.name not in _UNIFIED_ONLY_FIELDS and not (payload is not None and item.name == "results")}
    artifact["analysis_contract_version"] = "decision-preparation-v4"
    if plan.process_evidence is not None:
        artifact["process_evidence"] = _key_references(artifact["process_evidence"], refs)
    tasks = []
    if payload is not None:
        tasks = [{"row_ref": new_run_ref(), "operation_ref": identities[row.op_id],
                  "payload": {**durable_value(row), "locked": row.op_id in frozen_op_ids}} for row in payload.schedule_rows]
        artifact["task_payload_source"] = "candidate_tasks_v1"
        artifact["results"] = [{item.name: durable_value(getattr(row, item.name)) for item in fields(row)
                                if item.name not in _TASK_OWNED_FIELDS} for row in plan.results]
        artifact["validated_payload"] = {item.name: durable_value(getattr(payload, item.name)) for item in fields(payload)
                                         if item.name not in ("schedule_rows", "assigned_by_op_id")}
    return {"candidate_ref": refs[plan.candidate_key], "key": plan.candidate_key, "sequence": plan.sequence,
            "status": plan.status, "label": plan.label, "artifact": artifact, "tasks": tasks}


def _saved_selection(snapshot, refs, objective):
    value = durable_value(snapshot)
    for source, target in _SAVED_SELECTION_REFS.items():
        key = value.pop(source)
        value[target] = refs[key] if key is not None else None
    value.update(objective_name=objective, objective_field_order=[field["key"] for field in best_score_schema(objective)])
    if "decision_evidence" in value:
        value["decision_evidence"] = _key_references(value["decision_evidence"], refs)
    return value


def _saved_comparison_summary(plans, snapshot, *, time_budget_reached, run_time_budget_seconds):
    counts = {status: sum(plan.status == status for plan in plans) for status in ("completed", "failed", "skipped")}
    return {"enabled": True, "planned_candidate_count": len(plans),
            "completed_candidate_count": counts["completed"], "failed_candidate_count": counts["failed"],
            "skipped_candidate_count": counts["skipped"], "reused_candidate_count": 0,
            "time_budget_reached": time_budget_reached, "run_time_budget_seconds": run_time_budget_seconds,
            "skipped_candidate_labels": [plan.label for plan in plans if plan.status == "skipped"],
            "baseline_missing_or_failed": snapshot["baseline_best_key"] is None,
            "selection_policy": snapshot["selection_policy"], "selection_reason_code": snapshot["reason_code"]}


def _install_archive_fixture(monkeypatch, build_plans, *, time_budget_reached=False,
                             selected_key="baseline", baseline_key="baseline", critical_key="graph_w1_of_3",
                             selection_snapshot=None):
    """Replace only the worker's result preparation; computation and persistence stay real."""

    def archived_result(computation, identities, *, run, capture, admission, facts):
        schedule_input = computation.schedule_input
        comparison = computation.orchestration.candidate_comparison
        original = comparison.selection.selected_plan
        pairs = build_plans(schedule_input, original, computation.candidate_payloads[original.candidate_key])
        plans = [plan for plan, _ in pairs]
        selected, selected_payload = next(pair for pair in pairs if pair[0].candidate_key == selected_key)
        snapshot = {
            "selected_candidate_key": selected_key, "selected_kind": selected.kind,
            "selection_policy": "balanced", "reason_code": "balanced_raw_score_best",
            "raw_score_best_key": selected_key, "baseline_best_key": baseline_key,
            "critical_best_key": critical_key, "critical_health_best_key": None,
            "selected_score": list(selected.score), "selection_policy_version": "candidate-selection-v1",
            "overdue_tolerance_count": 1, "tardiness_tolerance_ratio": 0.10,
            **deepcopy(selection_snapshot or {}),
        }
        refs = {plan.candidate_key: new_run_ref() for plan in plans}
        candidates = [_saved_candidate(plan, payload, refs=refs, identities=identities,
                                       frozen_op_ids=schedule_input.frozen_op_ids) for plan, payload in pairs]
        partial = (selected_payload.scheduled_op_ids != schedule_input.schedule_output_allowed_op_ids
                   or any(row["status"] == "skipped" for row in schedule_input.dispositions)
                   or any(plan.status != "completed" for plan in plans))
        summary = durable_value(computation.orchestration.result_summary_obj)
        summary["algo"]["candidate_comparison"] = _saved_comparison_summary(
            plans, snapshot, time_budget_reached=time_budget_reached,
            run_time_budget_seconds=comparison.run_time_budget_seconds)
        efforts = [{**durable_value(effort.to_dict()), "operation_ref": identities[effort.op_id]}
                   for effort in schedule_input.operation_efforts]
        result = {"result_persisted": True, "state": "partial" if partial else "complete", "error": None,
                  "candidates": [{"candidate_ref": row["candidate_ref"], "label": row["label"], "status": row["status"],
                                  "task_count": len(row["tasks"]), "selected": row["key"] == selected_key}
                                 for row in candidates],
                  "selection": _saved_selection(snapshot, refs, selected.objective_name),
                  "dispositions": durable_value(computation.dispositions), "summary": summary,
                  "operation_effort": {"effort_basis": RUNTIME_REQUIREMENT_BASIS, "items": efforts}}
        packets = {}
        for row, (_, payload) in zip(candidates, pairs):
            row.update(run_ref=run["run_ref"], task_count=len(row["tasks"]))
            packets[row["candidate_ref"]] = {
                "raw_tasks": row["tasks"],
                "intervals": ({task["row_ref"]: (item.start_time, item.end_time)
                               for task, item in zip(row["tasks"], payload.schedule_rows)} if payload is not None else {}),
                "scheduled_op_ids": payload.scheduled_op_ids if payload is not None else None}
        models = build_decision_read_models(run, capture, result, candidates, packets,
                                            facts=facts, admission=admission, process=None)
        return PreparedRunResult(encode_candidate_rows(candidates), encode_result(result),
                                 encode_decision_read_models(models), models["run_model"]["header"])

    monkeypatch.setattr(worker_module, "prepare_run_result", archived_result)


def install_complete_legacy_archive(monkeypatch, *, selection_snapshot=None):
    def build(schedule_input, original, payload):
        return [(_legacy_plan(original, entry, schedule_input), payload) for entry in LEGACY_CANDIDATE_DIRECTORY]

    _install_archive_fixture(monkeypatch, build, selection_snapshot=selection_snapshot)


def install_budget_skipped_archive(monkeypatch):
    def build(schedule_input, original, payload):
        plans = [_legacy_plan(original, entry, schedule_input) for entry in LEGACY_CANDIDATE_DIRECTORY]
        evidence = original.objective_name + "_not_started"
        return [(plans[0], payload)] + [(replace(plan, status="skipped", score=None, results=[], summary=None,
            metrics=None, health=None, failure_reason="candidate_time_budget_reached",
            process_evidence=load_legacy_process_evidence(evidence)), None) for plan in plans[1:]]

    _install_archive_fixture(monkeypatch, build, time_budget_reached=True, critical_key=None)


def install_failed_baseline_archive(monkeypatch):
    def build(schedule_input, original, payload):
        plans = [_legacy_plan(original, entry, schedule_input) for entry in LEGACY_CANDIDATE_DIRECTORY]
        reason = "原算法候选计算失败：测试数据指定该次候选失败。"
        failed = replace(plans[0], status="failed", score=None, results=[], summary=None, metrics=None,
            health=None, failure_reason=reason,
            process_evidence=load_legacy_process_evidence(original.objective_name + "_failed_0", reason=reason))
        return [(failed, None)] + [(plan, payload) for plan in plans[1:]]

    _install_archive_fixture(monkeypatch, build, selected_key="graph_w1_of_3", baseline_key=None,
        selection_snapshot={"decision_evidence": LEGACY_FAILED_BASELINE_DECISION_EVIDENCE})


def install_different_work_archive(monkeypatch):
    def build(schedule_input, original, _current_payload):
        # Piece candidates are validated against the connection; these archives only use plain batches.
        assert all(op.piece_id is None for op in schedule_input.operations)

        def arrangement(order, entries):
            decoded = production_decode(
                GreedyScheduler(schedule_input.cal_svc, schedule_input.cfg),
                operations=schedule_input.algo_ops_to_schedule, batches=schedule_input.batches,
                start_dt=schedule_input.start_dt_norm,
                seed_results=coerce_seed_results(schedule_input.seed_results, optimizer_algo_stats={}),
                machine_downtimes=schedule_input.downtime_map, resource_pool=schedule_input.resource_pool,
                strategy=original.used_strategy, strategy_params=original.used_params,
                end_date=schedule_input.end_date_norm, batch_order_override=order,
                dispatch_mode=original.dispatch_mode, dispatch_rule=original.adopted_dispatch_rule,
                readiness_gate_enabled=schedule_input.readiness_gate_enabled)
            plan = replace(original, results=decoded.results, summary=decoded.summary,
                           used_strategy=decoded.used_strategy, used_params=decoded.used_params, best_order=order)
            payload = validate_candidate(schedule_input, decoded.results, list(decoded.summary.errors))
            return [(_legacy_plan(plan, entry, schedule_input), payload) for entry in entries]

        baseline = arrangement(["B1", "B2"], LEGACY_CANDIDATE_DIRECTORY[:1])
        alternatives = arrangement(["B2", "B1"], LEGACY_CANDIDATE_DIRECTORY[1:])
        assert {row.op_id for row in baseline[0][0].results} != {row.op_id for row in alternatives[0][0].results}
        return baseline + alternatives

    _install_archive_fixture(monkeypatch, build, selected_key="graph_w1_of_3")
