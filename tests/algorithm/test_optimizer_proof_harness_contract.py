"""Regression tests for the scheduler optimizer proof harness reference contract."""

from __future__ import annotations

import importlib.util
import json
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_proof_harness import (
    FORBIDDEN_PUBLIC_TOKENS,
    REFERENCE_FOLDED_NOT_COMPARABLE,
    REFERENCE_PROVEN_OPTIMUM,
    TinyBatchSpec,
    TinyBenchmarkCase,
    TinyOperationSpec,
    assert_benchmark_reference_contract,
    assert_oracle_decoder_matches_greedy,
    assert_public_payload_safe,
    build_default_tiny_cases,
    build_folded_fjsp_reference,
    build_tiny_case_reference,
    render_optimizer_proof_report,
    run_case_with_greedy,
    run_optimizer_proof_harness,
)
from tests._support.paths import REPO_ROOT


def test_optimizer_proof_harness_emits_comparable_tiny_oracle_reference() -> None:
    reference = _default_reference()

    assert reference["reference_type"] == REFERENCE_PROVEN_OPTIMUM
    assert reference["oracle_status"] == "proven_optimal"
    assert reference["objective_name"] == "min_overdue"
    assert reference["bound_metric"] == "objective_score"
    assert reference["bound_scope"] == "same_model"
    assert reference["bound_is_objective_comparable"] is True
    assert reference["gap_to_oracle_pct"] == 0.0
    assert reference["diagnostics_ref"] is None


def test_optimizer_proof_harness_emits_tiny_oracle_metrics_and_bounds() -> None:
    payload = run_optimizer_proof_harness(require_optimal=True)
    reference = payload["references"][0]

    assert payload["status"] == "passed"
    assert payload["schema_version"] == 1
    assert len(payload["references"]) == 1
    assert reference["objective_metric_keys"] == [
        "overdue_count",
        "weighted_tardiness_hours",
        "total_tardiness_hours",
        "makespan_hours",
        "changeover_count",
    ]
    assert reference["lower_bound_sources"] == ["exact_oracle"]
    assert reference["makespan_lower_bound_sources"] == [
        "critical_path",
        "machine_workload",
        "operator_workload",
    ]
    assert reference["makespan_lower_bound_value"] == 3.0
    assert_public_payload_safe(payload["public"])


def test_oracle_decoder_parity_guard_passes_for_degenerate_default_case() -> None:
    case = build_default_tiny_cases()[0]
    results, _summary = run_case_with_greedy(case)

    # On the single-resource degenerate case the oracle decoder must reproduce
    # greedy exactly, so the same-model guard is a no-op (no raise).
    assert_oracle_decoder_matches_greedy(case, results)


def test_oracle_decoder_parity_guard_rejects_schedule_the_oracle_decoder_cannot_reproduce() -> None:
    case = build_default_tiny_cases()[0]
    results, _summary = run_case_with_greedy(case)
    tampered = [
        replace(result, end_time=result.end_time + timedelta(hours=1)) if index == 0 else result
        for index, result in enumerate(results)
    ]

    with pytest.raises(ValidationError) as exc_info:
        assert_oracle_decoder_matches_greedy(case, tampered)

    assert exc_info.value.field == "oracle_decoder_parity"


def test_folded_fjsp_reference_is_explicitly_not_objective_comparable() -> None:
    reference = build_folded_fjsp_reference(
        case_slug="mk01",
        objective_name="min_overdue",
        actual_makespan_hours=44.0,
        reference_makespan_hours=40.0,
        reference_label="BKS",
    )

    assert reference["reference_type"] == REFERENCE_FOLDED_NOT_COMPARABLE
    assert reference["bound_metric"] == "makespan_hours"
    assert reference["bound_scope"] == "folded_fjsp"
    assert reference["bound_is_objective_comparable"] is False
    assert reference["oracle_status"] == "not_run"
    assert reference["gap_to_oracle_pct"] is None
    assert reference["gap_to_best_known_pct"] == 10.0
    assert reference["public"]["oracle_status"] == "not_run"
    assert reference["public"]["objective_score_matched"] is False
    assert reference["public"]["gap_to_oracle_pct"] is None
    assert_public_payload_safe(reference["public"])


def test_unproven_oracle_does_not_publish_oracle_optimum_or_gap() -> None:
    case = replace(build_default_tiny_cases()[0], oracle_node_limit=1)

    reference = build_tiny_case_reference(case)
    payload = run_optimizer_proof_harness([case], require_optimal=True)

    assert reference["reference_type"] == "lower_bound"
    assert reference["oracle_status"] == "node_limit"
    assert reference["oracle_optimum"] is None
    assert reference["oracle_objective_score"] == []
    assert reference["gap_to_oracle_pct"] is None
    assert reference["public"]["gap_to_oracle_pct"] is None
    assert reference["bound_metric"] == "makespan_hours"
    assert reference["bound_is_objective_comparable"] is False
    assert reference["lower_bound_value"] == 3.0
    assert reference["lower_bound_sources"] == [
        "critical_path",
        "machine_workload",
        "operator_workload",
    ]
    assert payload["blockers"] == [{"case_slug": "tiny-sgs-single-machine", "reason": "oracle_not_proven"}]


def test_require_optimal_checks_full_objective_score_not_only_primary_metric() -> None:
    case = TinyBenchmarkCase(
        slug="tiny-greedy-nonoptimal-tardiness",
        objective_name="min_overdue",
        start_dt=datetime(2026, 1, 1, 23, 0, 0),
        dispatch_mode="batch_order",
        batches=(
            TinyBatchSpec(batch_id="batch-a", due_date="2026-01-01", priority="normal"),
            TinyBatchSpec(batch_id="batch-b", due_date="2026-01-01", priority="normal"),
        ),
        operations=(
            TinyOperationSpec(
                op_id=1,
                op_code="LONG-A",
                batch_id="batch-a",
                seq=1,
                machine_id="machine-main",
                operator_id="operator-main",
                duration_hours=3.0,
            ),
            TinyOperationSpec(
                op_id=2,
                op_code="SHORT-B",
                batch_id="batch-b",
                seq=1,
                machine_id="machine-main",
                operator_id="operator-main",
                duration_hours=2.0,
            ),
        ),
    )

    reference = build_tiny_case_reference(case)
    payload = run_optimizer_proof_harness([case], require_optimal=True)

    assert reference["oracle_status"] == "proven_optimal"
    assert reference["actual_objective_score"][1] == reference["oracle_objective_score"][1]
    assert reference["actual_objective_score"] != reference["oracle_objective_score"]
    assert reference["objective_score_matched"] is False
    assert reference["gap_to_oracle_pct"] == 20.0
    assert reference["gap_to_best_known_pct"] == 20.0
    assert reference["gap_to_best_known_metric_key"] == "weighted_tardiness_hours"
    assert payload["status"] == "failed"
    assert payload["blockers"] == [
        {"case_slug": "tiny-greedy-nonoptimal-tardiness", "reason": "actual_not_oracle_optimal"}
    ]


def test_benchmark_reference_contract_rejects_lower_bound_above_actual_metric() -> None:
    case = replace(build_default_tiny_cases()[0], oracle_node_limit=1)
    reference = dict(build_tiny_case_reference(case))
    reference["lower_bound_value"] = float(reference["actual_metric_value"]) + 1.0

    with pytest.raises(ValidationError) as exc_info:
        assert_benchmark_reference_contract(reference)

    assert exc_info.value.field == "lower_bound_value"


def test_benchmark_reference_contract_rejects_negative_bound_gap() -> None:
    case = replace(build_default_tiny_cases()[0], oracle_node_limit=1)
    reference = dict(build_tiny_case_reference(case))
    reference["gap_to_bound_pct"] = -25.0

    with pytest.raises(ValidationError) as exc_info:
        assert_benchmark_reference_contract(reference)

    assert exc_info.value.field == "gap_to_bound_pct"


def test_benchmark_reference_contract_rejects_proven_reference_outside_same_model_scope() -> None:
    reference = dict(build_tiny_case_reference(build_default_tiny_cases()[0]))
    reference["bound_scope"] = "folded_fjsp"

    with pytest.raises(ValidationError) as exc_info:
        assert_benchmark_reference_contract(reference)

    assert exc_info.value.field == "bound_scope"


def test_benchmark_reference_contract_rejects_folded_reference_with_bad_best_known_gap() -> None:
    reference = build_folded_fjsp_reference(
        case_slug="mk01",
        objective_name="min_overdue",
        actual_makespan_hours=44.0,
        reference_makespan_hours=40.0,
        reference_label="BKS",
    )
    reference["gap_to_best_known_pct"] = 999.0

    with pytest.raises(ValidationError) as exc_info:
        assert_benchmark_reference_contract(reference)

    assert exc_info.value.field == "gap_to_best_known_pct"


def test_benchmark_reference_contract_rejects_folded_reference_with_bad_gap_metric_key() -> None:
    reference = build_folded_fjsp_reference(
        case_slug="mk01",
        objective_name="min_overdue",
        actual_makespan_hours=44.0,
        reference_makespan_hours=40.0,
        reference_label="BKS",
    )
    reference["gap_to_best_known_metric_key"] = "objective_score"

    with pytest.raises(ValidationError) as exc_info:
        assert_benchmark_reference_contract(reference)

    assert exc_info.value.field == "gap_to_best_known_metric_key"


def test_benchmark_reference_contract_rejects_public_reference_type_mismatch() -> None:
    case = replace(build_default_tiny_cases()[0], oracle_node_limit=1)
    reference = build_tiny_case_reference(case)
    reference["public"] = dict(reference["public"])
    reference["public"]["reference_type"] = REFERENCE_PROVEN_OPTIMUM

    with pytest.raises(ValidationError) as exc_info:
        assert_benchmark_reference_contract(reference)

    assert exc_info.value.field == "public"


def test_benchmark_reference_contract_rejects_public_gap_or_match_mismatch() -> None:
    reference = build_tiny_case_reference(build_default_tiny_cases()[0])
    reference["public"] = dict(reference["public"])
    reference["public"]["gap_to_oracle_pct"] = 99.0

    with pytest.raises(ValidationError) as exc_info:
        assert_benchmark_reference_contract(reference)

    assert exc_info.value.field == "public"

    reference = build_tiny_case_reference(build_default_tiny_cases()[0])
    reference["public"] = dict(reference["public"])
    reference["public"]["objective_score_matched"] = False

    with pytest.raises(ValidationError) as exc_info:
        assert_benchmark_reference_contract(reference)

    assert exc_info.value.field == "public"


def test_benchmark_reference_contract_rejects_wrong_bound_gap_metric_key() -> None:
    case = replace(build_default_tiny_cases()[0], oracle_node_limit=1)
    reference = build_tiny_case_reference(case)
    reference["gap_to_bound_metric_key"] = "objective_score"

    with pytest.raises(ValidationError) as exc_info:
        assert_benchmark_reference_contract(reference)

    assert exc_info.value.field == "gap_to_bound_metric_key"


@pytest.mark.parametrize("actual_value", [float("nan"), float("inf"), -1.0, 0.0])
def test_folded_fjsp_reference_rejects_invalid_actual_makespan(actual_value: float) -> None:
    with pytest.raises(ValidationError) as exc_info:
        build_folded_fjsp_reference(
            case_slug="mk01",
            objective_name="min_overdue",
            actual_makespan_hours=actual_value,
            reference_makespan_hours=40.0,
            reference_label="BKS",
        )

    assert exc_info.value.field == "actual_makespan_hours"


def test_optimizer_proof_report_public_surface_has_no_internal_ids() -> None:
    payload = run_optimizer_proof_harness()
    report = render_optimizer_proof_report(payload)
    lowered = report.lower()

    for token in FORBIDDEN_PUBLIC_TOKENS:
        assert token not in lowered
    assert "tiny-sgs-single-machine" in report
    assert "oracle_status: proven_optimal" in report


def test_optimizer_proof_script_default_stdout_does_not_write_tracked_evidence(capsys) -> None:
    script = _load_script_module()
    report_path = REPO_ROOT / "evidence" / "Benchmark" / "optimizer_proof_harness_report.md"
    assert not report_path.exists()

    exit_code = script.main([])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert not report_path.exists()
    payload = json.loads(captured.out)
    assert payload["status"] == "passed"
    assert "references" not in payload
    assert payload["cases"][0]["reference_type"] == REFERENCE_PROVEN_OPTIMUM
    assert str(REPO_ROOT) not in captured.out
    for token in FORBIDDEN_PUBLIC_TOKENS:
        assert token not in captured.out.lower()


def test_optimizer_proof_script_diagnostics_stdout_is_explicit(capsys) -> None:
    script = _load_script_module()

    exit_code = script.main(["--include-diagnostics"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["references"][0]["reference_type"] == REFERENCE_PROVEN_OPTIMUM
    for token in FORBIDDEN_PUBLIC_TOKENS:
        assert token not in captured.out.lower()


def test_optimizer_proof_script_writes_report_only_when_explicit(tmp_path: Path, capsys) -> None:
    script = _load_script_module()
    report_path = tmp_path / "optimizer-proof.md"

    exit_code = script.main(["--write-report", "--report-path", str(report_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert report_path.exists()
    assert "report_written=true" in captured.out
    assert "optimizer-proof.md" in captured.out
    assert str(tmp_path) not in captured.out
    report = report_path.read_text(encoding="utf-8")
    assert "Optimizer Proof Harness Report" in report
    for token in FORBIDDEN_PUBLIC_TOKENS:
        assert token not in report.lower()


def _load_script_module():
    path = REPO_ROOT / "tests" / "_scripts_e2e" / "benchmark_optimizer_proof_harness.py"
    spec = importlib.util.spec_from_file_location("benchmark_optimizer_proof_harness_script", str(path))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _default_reference():
    payload = run_optimizer_proof_harness(require_optimal=True)
    assert len(payload["references"]) == 1
    return payload["references"][0]
