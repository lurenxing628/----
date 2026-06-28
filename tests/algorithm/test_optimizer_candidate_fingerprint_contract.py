"""回归测试：optimizer CandidateFingerprint 合同（roadmap item 5）。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from core.algorithms.evaluation import ScheduleMetrics, objective_score
from core.algorithms.types import ScheduleResult, ScheduleSummary
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_candidate_fingerprint import (
    DISTINCT_FINGERPRINT_DESCRIPTION,
    DISTINCT_FINGERPRINT_SCOPE,
    OUTPUT_FINGERPRINT_SCOPE,
    build_candidate_fingerprint,
)
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from core.services.scheduler.run.schedule_candidate_persistence_models import operation_log_algo_summary
from core.services.scheduler.summary.optimizer_public_search_report import project_search_report
from core.services.scheduler.summary.summary_size_guard_fields import minimal_summary_for_size_guard

_START = datetime(2026, 1, 1, 8, 0, 0)
_OBJECTIVE = "min_overdue"


def _summary(*, total_ops: int = 2, scheduled_ops: int = 2, failed_ops: int = 0) -> ScheduleSummary:
    return ScheduleSummary(
        success=failed_ops == 0,
        total_ops=total_ops,
        scheduled_ops=scheduled_ops,
        failed_ops=failed_ops,
        warnings=[],
        errors=[],
        duration_seconds=0.0,
    )


def _metrics(*, overdue_count: int = 0, tardiness: float = 0.0, makespan: float = 2.0) -> ScheduleMetrics:
    return ScheduleMetrics(
        overdue_count=overdue_count,
        total_tardiness_hours=tardiness,
        makespan_hours=makespan,
        changeover_count=0,
        weighted_tardiness_hours=tardiness,
    )


def _result(
    op_id: int,
    *,
    batch_id: str,
    seq: int,
    machine_id: str = "MC-1",
    operator_id: str = "OP-1",
    start_offset: int,
    op_type_name: str = "cut",
) -> ScheduleResult:
    start_time = _START + timedelta(hours=start_offset)
    return ScheduleResult(
        op_id=op_id,
        op_code=f"{batch_id}-{seq}",
        batch_id=batch_id,
        seq=seq,
        machine_id=machine_id,
        operator_id=operator_id,
        start_time=start_time,
        end_time=start_time + timedelta(hours=1),
        op_type_name=op_type_name,
    )


def _score(metrics: ScheduleMetrics, *, failed_ops: int = 0) -> List[float]:
    return [float(failed_ops)] + [float(item) for item in objective_score(_OBJECTIVE, metrics)]


def _candidate(
    *,
    order: List[str],
    results: List[ScheduleResult],
    metrics: ScheduleMetrics,
    params: Optional[Dict[str, Any]] = None,
    dispatch_mode: str = "sgs",
    dispatch_rule: str = "slack",
) -> Dict[str, Any]:
    summary = _summary(total_ops=len(results), scheduled_ops=len(results), failed_ops=0)
    return {
        "results": list(results),
        "summary": summary,
        "strategy": SimpleNamespace(value="priority_first"),
        "params": dict(params or {"due_weight": 0.5, "priority_weight": 0.4}),
        "dispatch_mode": dispatch_mode,
        "dispatch_rule": dispatch_rule,
        "order": list(order),
        "metrics": metrics,
        "score": _score(metrics),
        "algo_stats": {},
    }


def _base_results() -> List[ScheduleResult]:
    return [
        _result(1, batch_id="B1", seq=10, start_offset=0),
        _result(2, batch_id="B2", seq=10, start_offset=1),
    ]


def _state() -> OptimizationSearchReportState:
    return OptimizationSearchReportState(
        algorithm_profile="multi_start_local_search",
        seed=42,
        time_budget_seconds=5,
        objective_name=_OBJECTIVE,
        started_at=1000.0,
        candidate_profile={"acceptance": "improve_only"},
    )


def test_candidate_fingerprint_is_deterministic_and_order_normalized_for_output() -> None:
    metrics = _metrics()
    first = _candidate(
        order=["B1", "B2"],
        results=list(reversed(_base_results())),
        metrics=metrics,
        params={"b": 2, "a": 1},
    )
    second = _candidate(
        order=["B1", "B2"],
        results=_base_results(),
        metrics=metrics,
        params={"a": 1, "b": 2},
    )

    first_fp = build_candidate_fingerprint(first, objective_name=_OBJECTIVE, parent_fingerprint=None, seen_output_fingerprints=set())
    second_fp = build_candidate_fingerprint(second, objective_name=_OBJECTIVE, parent_fingerprint=None, seen_output_fingerprints=set())

    assert first_fp.decision_fingerprint == second_fp.decision_fingerprint
    assert first_fp.output_fingerprint == second_fp.output_fingerprint
    assert first_fp.fingerprint_scope == OUTPUT_FINGERPRINT_SCOPE


def test_decision_and_output_fingerprint_split_collapsed_sgs_outputs() -> None:
    metrics = _metrics()
    first = _candidate(order=["B1", "B2"], results=_base_results(), metrics=metrics)
    second = _candidate(order=["B2", "B1"], results=_base_results(), metrics=metrics)

    first_fp = build_candidate_fingerprint(first, objective_name=_OBJECTIVE, parent_fingerprint=None, seen_output_fingerprints=set())
    second_fp = build_candidate_fingerprint(second, objective_name=_OBJECTIVE, parent_fingerprint=None, seen_output_fingerprints=set())

    assert first_fp.decision_fingerprint != second_fp.decision_fingerprint
    assert first_fp.output_fingerprint == second_fp.output_fingerprint


def test_report_distinct_candidates_uses_decoded_output_scope() -> None:
    metrics = _metrics()
    first = _candidate(order=["B1", "B2"], results=_base_results(), metrics=metrics)
    collapsed = _candidate(order=["B2", "B1"], results=_base_results(), metrics=metrics)
    state = _state()

    state.mark_candidate_evaluated(first, origin="multi_start")
    state.mark_candidate_accepted(first, origin="multi_start")
    state.mark_candidate_evaluated(collapsed, origin="local_search")

    report = state.finalize(runtime_ms=10, attempts=[], improvement_trace=[])
    assert report["distinct_fingerprint_scope"] == DISTINCT_FINGERPRINT_SCOPE
    assert report["distinct_fingerprint_description"] == DISTINCT_FINGERPRINT_DESCRIPTION
    assert report["evaluated_candidates"] == 2
    assert report["distinct_candidates"] == 1
    assert report["accepted_distinct_candidates"] == 1
    assert report["rejection_summary"]["same_fingerprint"] == 1
    assert report["fingerprint_events"][-1]["same_as_parent"] is True
    assert report["fingerprint_events"][-1]["same_as_seen"] is True
    assert report["improved"] is False


def test_improved_requires_fingerprint_change_score_gain_and_acceptance() -> None:
    baseline = _candidate(order=["B1", "B2"], results=_base_results(), metrics=_metrics(overdue_count=2, tardiness=4.0))

    changed_same_score = _candidate(
        order=["B3", "B4"],
        results=[
            _result(3, batch_id="B3", seq=10, start_offset=0),
            _result(4, batch_id="B4", seq=10, start_offset=1),
        ],
        metrics=_metrics(overdue_count=2, tardiness=4.0),
    )
    changed_better = _candidate(
        order=["B3", "B4"],
        results=[
            _result(3, batch_id="B3", seq=10, start_offset=0),
            _result(4, batch_id="B4", seq=10, start_offset=1),
        ],
        metrics=_metrics(overdue_count=1, tardiness=2.0),
    )

    fingerprint_only = _state()
    fingerprint_only.mark_candidate_accepted(baseline, origin="multi_start")
    fingerprint_only.mark_candidate_accepted(changed_same_score, origin="local_search")
    report = fingerprint_only.finalize(runtime_ms=10, attempts=[], improvement_trace=[])
    assert report["improvement_conditions"] == {
        "fingerprint_changed": True,
        "score_strictly_better": False,
        "acceptance": "improve_only",
        "acceptance_passed": True,
    }
    assert report["improved"] is False

    score_only = _state()
    score_only.mark_candidate_accepted(baseline, origin="multi_start")
    score_only.best_score = [0.0, 1.0]
    score_only.accepted_candidates = 2
    report = score_only.finalize(runtime_ms=10, attempts=[], improvement_trace=[])
    assert report["improvement_conditions"]["fingerprint_changed"] is False
    assert report["improvement_conditions"]["score_strictly_better"] is True
    assert report["improvement_conditions"]["acceptance_passed"] is True
    assert report["improved"] is False

    not_accepted = _state()
    not_accepted.mark_candidate_accepted(baseline, origin="multi_start")
    not_accepted_candidate_fp = build_candidate_fingerprint(
        changed_better,
        objective_name=_OBJECTIVE,
        parent_fingerprint=not_accepted.best_fingerprint,
        seen_output_fingerprints=set(),
    )
    # 这个白盒状态表示“候选看起来不同、score 也更好，但没有通过 accept 入口”。
    # 当前生产路径不会这样改 best；这条用例专门锁 finalize 的三条件，防止未来绕开 acceptance。
    not_accepted.best_fingerprint = not_accepted_candidate_fp.output_fingerprint
    not_accepted.best_candidate_fingerprint = not_accepted_candidate_fp.to_report_dict()
    not_accepted.best_score = list(changed_better["score"])
    report = not_accepted.finalize(runtime_ms=10, attempts=[], improvement_trace=[])
    assert report["improvement_conditions"] == {
        "fingerprint_changed": True,
        "score_strictly_better": True,
        "acceptance": "improve_only",
        "acceptance_passed": False,
    }
    assert report["improved"] is False

    all_conditions = _state()
    all_conditions.mark_candidate_accepted(baseline, origin="multi_start")
    all_conditions.mark_candidate_accepted(changed_better, origin="local_search")
    report = all_conditions.finalize(runtime_ms=10, attempts=[], improvement_trace=[])
    assert report["improvement_conditions"] == {
        "fingerprint_changed": True,
        "score_strictly_better": True,
        "acceptance": "improve_only",
        "acceptance_passed": True,
    }
    assert report["improved"] is True


def test_public_operation_log_and_size_guard_keep_scope_without_hash_or_internal_ids() -> None:
    baseline = _candidate(order=["B1", "B2"], results=_base_results(), metrics=_metrics(overdue_count=2, tardiness=4.0))
    better = _candidate(
        order=["B3", "B4"],
        results=[
            _result(3, batch_id="B3", seq=10, machine_id="MC-SECRET", operator_id="OP-SECRET", start_offset=0),
            _result(4, batch_id="B4", seq=10, machine_id="MC-SECRET", operator_id="OP-SECRET", start_offset=1),
        ],
        metrics=_metrics(overdue_count=1, tardiness=2.0),
    )
    state = _state()
    state.mark_candidate_accepted(baseline, origin="multi_start")
    state.mark_candidate_accepted(better, origin="local_search")
    report = state.finalize(runtime_ms=10, attempts=[], improvement_trace=[])

    public, diagnostics = project_search_report(report)
    assert public["distinct_fingerprint_scope"] == "decoded_output"
    assert public["distinct_fingerprint_description"]
    public_text = json.dumps(public, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        "decision_fingerprint",
        "output_fingerprint",
        "parent_fingerprint",
        "MC-SECRET",
        "OP-SECRET",
        '"initial_fingerprint"',
        '"best_fingerprint"',
    ):
        assert forbidden not in public_text
    assert diagnostics["best_candidate_fingerprint"]["output_fingerprint"]

    public_log_algo = operation_log_algo_summary({"algo": {"search_report": report}})
    log_text = json.dumps(public_log_algo, ensure_ascii=False, sort_keys=True)
    assert "decoded_output" in log_text
    assert "output_fingerprint" not in log_text
    assert "MC-SECRET" not in log_text

    minimal = minimal_summary_for_size_guard({"algo": {"search_report": report}}, original_size=999999, diagnostics_truncated=True)
    minimal_report = minimal["algo"]["search_report"]
    assert minimal_report["distinct_fingerprint_scope"] == "decoded_output"
    minimal_text = json.dumps(minimal_report, ensure_ascii=False, sort_keys=True)
    assert "decision_fingerprint" not in minimal_text
    assert "output_fingerprint" not in minimal_text
    assert "MC-SECRET" not in minimal_text


def test_candidate_without_results_fails_loud() -> None:
    # 候选必须带正式解码结果;缺 results 是契约违反,应明确暴露而非静默生成空指纹。
    with pytest.raises(ValidationError):
        build_candidate_fingerprint(
            {"order": ["B1"], "metrics": _metrics(), "score": _score(_metrics())},
            objective_name=_OBJECTIVE,
            parent_fingerprint=None,
            seen_output_fingerprints=set(),
        )


def test_non_finite_score_fails_loud() -> None:
    # score 进 output_fingerprint;非有限数(inf/nan)会让 hash 不可复现,必须 fail-loud。
    candidate = _candidate(order=["B1", "B2"], results=_base_results(), metrics=_metrics())
    candidate["score"] = [0.0, float("inf")]
    with pytest.raises(ValidationError):
        build_candidate_fingerprint(candidate, objective_name=_OBJECTIVE, parent_fingerprint=None, seen_output_fingerprints=set())


def test_invalid_seed_result_count_fails_loud() -> None:
    # seed_result_count 进 decision_fingerprint;非整数是契约违反,应 fail-loud 不静默兜底。
    candidate = _candidate(order=["B1", "B2"], results=_base_results(), metrics=_metrics())
    candidate["seed_result_count"] = "not-an-int"
    with pytest.raises(ValidationError):
        build_candidate_fingerprint(candidate, objective_name=_OBJECTIVE, parent_fingerprint=None, seen_output_fingerprints=set())


def test_output_signature_handles_mixed_op_id_without_crash() -> None:
    # 上游 op.id 缺失时会把 op_id 落成 0/None(见 internal_operation);签名层必须对任意 op_id 健壮,
    # 不能因正整数与 0/None 在排序键里混排而抛 TypeError。这是 B1 回归用例。
    def _row(op_id: Any) -> SimpleNamespace:
        return SimpleNamespace(
            op_id=op_id,
            op_code="c",
            batch_id="B",
            seq=1,
            machine_id="M",
            operator_id="O",
            start_time=_START,
            end_time=_START + timedelta(hours=1),
            source="",
            op_type_name="t",
        )

    metrics = _metrics()
    candidate: Dict[str, Any] = {
        "results": [_row(5), _row(0), _row(None)],
        "summary": _summary(total_ops=3, scheduled_ops=3),
        "strategy": SimpleNamespace(value="priority_first"),
        "params": {},
        "order": ["B"],
        "metrics": metrics,
        "score": _score(metrics),
    }

    first = build_candidate_fingerprint(candidate, objective_name=_OBJECTIVE, parent_fingerprint=None, seen_output_fingerprints=set())
    second = build_candidate_fingerprint(candidate, objective_name=_OBJECTIVE, parent_fingerprint=None, seen_output_fingerprints=set())
    assert first.output_fingerprint
    assert first.output_fingerprint == second.output_fingerprint  # 确定性:同输入恒同签名
