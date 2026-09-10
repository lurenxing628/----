"""Real scheduler, candidate entry points and proof must use completion evidence."""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.algorithms import GreedyScheduler, SortStrategy
from core.algorithms.evaluation import compute_metrics, objective_score
from core.algorithms.evaluation_completion import UNKNOWN_OBJECTIVE_VALUE
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run import optimizer_proof_harness as harness
from core.services.scheduler.run import optimizer_proof_oracle as oracle
from core.services.scheduler.run import schedule_optimizer_steps as steps
from core.services.scheduler.run.optimizer_grasp_ig_candidates import _evaluate_candidate
from core.services.scheduler.run.optimizer_local_search_candidate_eval import evaluate_local_search_candidate
from core.services.scheduler.run.optimizer_neighborhood_moves import NeighborhoodMove

START = datetime(2026, 1, 1, 8)


def _operations():
    return [
        SimpleNamespace(
            id=op_id, batch_id="B1", op_code=f"OP{op_id}", seq=op_id,
            source="internal", setup_hours=hours, unit_hours=0.0,
            machine_id="M1", operator_id="O1", op_type_id="", op_type_name="cut",
        )
        for op_id, hours in ((1, 1.0), (2, 48.0))
    ]


def _batches():
    return {"B1": SimpleNamespace(batch_id="B1", due_date="2026-01-01", priority="normal", quantity=1)}


def _scheduler():
    return GreedyScheduler(calendar_service=oracle._ContinuousCalendar(), config_service=oracle._default_config())


@pytest.mark.parametrize("mode", ["batch_order", "sgs"])
def test_real_scheduler_partial_output_does_not_look_like_zero_tardiness(mode):
    operations, batches = _operations(), _batches()
    results, summary, _strategy, _params = _scheduler().schedule(
        operations=operations, batches=batches, strategy=SortStrategy.PRIORITY_FIRST,
        start_dt=START, end_date=START.date(), dispatch_mode=mode, strict_mode=True,
    )
    assert summary.failed_ops == 1
    assert [row.op_id for row in results] == [1]
    assert summary.failure_details[0]["op_id"] == 2
    metrics = compute_metrics(
        results, batches, expected_operations=operations, seed_results=[], failure_details=summary.failure_details,
    )
    assert metrics.completion.missing_operation_count == 1
    assert metrics.completion.failure_batch_ids == ("B1",)
    assert objective_score("min_tardiness", metrics) == (UNKNOWN_OBJECTIVE_VALUE,) * 5


def test_real_merged_external_scheduler_keeps_all_member_identities():
    operations = _operations()
    for operation in operations:
        operation.source = "external"
        operation.ext_merge_mode = "merged"
        operation.ext_group_id = "EXT"
        operation.ext_group_total_days = 1.0
    results, summary, _strategy, _params = _scheduler().schedule(
        operations=operations, batches=_batches(), strategy=SortStrategy.PRIORITY_FIRST,
        start_dt=START, dispatch_mode="batch_order", strict_mode=True,
    )
    assert summary.failed_ops == 0
    assert [row.op_id for row in results] == [1, 2]
    assert results[0].end_time == results[1].end_time
    metrics = compute_metrics(results, _batches(), expected_operations=operations, failure_details=summary.failure_details)
    assert metrics.completion.objective_defined
    assert metrics.total_tardiness_hours == 8.0


def _candidate_kwargs():
    return dict(
        scheduler=_scheduler(), strict_mode=True, algo_ops_to_schedule=_operations(), batches=_batches(),
        strategy=SortStrategy.PRIORITY_FIRST, params={}, start_dt=START, end_date=START.date(),
        downtime_map={}, order=["B1"], seed_sr_list=[], dispatch_mode="batch_order", dispatch_rule="slack",
        resource_pool=None, objective_name="min_overdue", optimizer_algo_stats=None,
        readiness_gate_enabled=False, graph_ready_context=None,
    )


@pytest.mark.parametrize("entry", ["local_search", "grasp", "multi_start", "ortools"])
def test_candidate_entry_uses_expected_operations_even_if_summary_drops_failures(entry):
    kwargs = _candidate_kwargs()

    def schedule(scheduler, **inputs):
        results, summary, strategy, params = scheduler.schedule(**inputs)
        return results, replace(summary, failed_ops=0, failure_details=[], success=True), strategy, params

    if entry == "local_search":
        kwargs.update(
            schedule_fn=schedule,
            neighborhood_move=NeighborhoodMove(1, "critical_chain", "swap", "batch_order", ("B1",), 1, "test"),
        )
        candidate = evaluate_local_search_candidate(**kwargs)
    elif entry == "grasp":
        candidate = _evaluate_candidate(**kwargs, schedule_fn=schedule, construction={})
    else:
        # These production entry points call scheduler.schedule through the same adapter.
        scheduler = kwargs["scheduler"]
        kwargs["scheduler"] = SimpleNamespace(schedule=lambda **inputs: schedule(scheduler, **inputs))
        if entry == "multi_start":
            candidate = steps._evaluate_multi_start_candidate(**kwargs)
        else:
            kwargs["ort_order"] = kwargs.pop("order")
            kwargs["dispatch_mode_cfg"] = kwargs.pop("dispatch_mode")
            kwargs["dispatch_rule_cfg"] = kwargs.pop("dispatch_rule")
            candidate = steps._evaluate_ortools_candidate(**kwargs)
    assert candidate["summary"].failed_ops == 0
    assert candidate["metrics"].completion.missing_operation_count == 1
    assert not candidate["metrics"].completion.objective_defined
    assert candidate["score"] == (0.0,) + (UNKNOWN_OBJECTIVE_VALUE,) * 5


def test_every_production_metric_call_supplies_expected_universe_and_real_summary():
    root = Path(__file__).resolve().parents[2] / "core" / "services" / "scheduler" / "run"
    found = []
    for path in sorted(root.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "compute_metrics":
                continue
            names = {kw.arg for kw in node.keywords}
            assert "expected_operations" in names, (path.name, node.lineno)
            if path.name not in {"optimizer_proof_oracle.py"}:
                assert {"seed_results", "failure_details"} <= names, (path.name, node.lineno)
            found.append((path.name, node.lineno))
    assert len(found) == 8


def test_proof_rejects_missing_actual_operation_even_when_summary_reports_success(monkeypatch):
    case = harness.build_default_tiny_cases()[0]
    results, summary = oracle.run_case_with_greedy(case)
    monkeypatch.setattr(harness, "run_case_with_greedy", lambda _case: (results[:-1], summary))
    with pytest.raises(ValidationError) as exc_info:
        harness.build_tiny_case_reference(case)
    assert exc_info.value.field == "benchmark_completion"


def test_proof_rejects_failed_details_even_with_all_actual_results(monkeypatch):
    case = harness.build_default_tiny_cases()[0]
    results, summary = oracle.run_case_with_greedy(case)
    failed = replace(summary, failure_details=[{"batch_id": results[0].batch_id, "op_id": results[0].op_id}])
    monkeypatch.setattr(harness, "run_case_with_greedy", lambda _case: (results, failed))
    with pytest.raises(ValidationError) as exc_info:
        harness.build_tiny_case_reference(case)
    assert exc_info.value.field == "benchmark_completion"


def test_oracle_cannot_publish_optimum_for_truncated_decoder(monkeypatch):
    case = harness.build_default_tiny_cases()[0]
    decode = oracle._decode_sequence
    monkeypatch.setattr(oracle, "_decode_sequence", lambda scenario, sequence: decode(scenario, sequence)[:-1])
    with pytest.raises(ValidationError) as exc_info:
        oracle.run_exact_oracle(case, objective_name=case.objective_name)
    assert exc_info.value.field == "benchmark_completion"


def test_complete_tiny_proof_still_compares_original_score_and_reports_exact_optimum():
    reference = harness.build_tiny_case_reference(harness.build_default_tiny_cases()[0])
    assert reference["oracle_status"] == "proven_optimal"
    assert reference["actual_objective_score"] == reference["oracle_objective_score"]
    assert len(reference["actual_objective_score"]) == 6
    assert reference["gap_to_oracle_pct"] == 0.0


def test_candidate_fixture_identity_is_stable_across_reordering_and_subsets():
    from tests.algorithm.test_optimizer_grasp_ig_candidate_construction_contract import _results_for_order

    complete = {row.batch_id: row.op_id for row in _results_for_order(["B4", "B1", "B2", "B3"])}
    assert _results_for_order(["B3"])[0].op_id == complete["B3"]
    scene_ids = {"CUSTOM-A": 19, "CUSTOM-B": 25}
    assert _results_for_order(["CUSTOM-B"], op_id_by_batch=scene_ids)[0].op_id == 25
