"""守护 compute_metrics 的公开字段契约：对含逾期/外协/非法 due/无 due 的排产结果，逐项校验 to_dict 输出的 overdue_count、total_tardiness_hours、makespan、changeover_count、加权拖期、机台/人员利用率与负载 CV、invalid_due/unscheduled 计数及样本，并验证 objective_score('min_weighted_tardiness') 得出预期四元组。"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from core.algorithms import ScheduleResult
from core.algorithms.evaluation import compute_metrics, objective_score


def _result(
    *,
    op_id: int,
    batch_id: str,
    source: str,
    machine_id: str,
    operator_id: str,
    op_type_name: str,
    start_time: datetime,
    end_time: datetime,
) -> ScheduleResult:
    return ScheduleResult(
        op_id=op_id,
        op_code=f"OP{op_id}",
        batch_id=batch_id,
        seq=op_id,
        source=source,
        machine_id=machine_id,
        operator_id=operator_id,
        op_type_name=op_type_name,
        start_time=start_time,
        end_time=end_time,
    )


def test_compute_metrics_contract_preserves_public_fields_and_objective_score() -> None:
    batches = {
        "B_LATE": SimpleNamespace(batch_id="B_LATE", priority="Urgent", due_date="2026-01-01"),
        "B_OK": SimpleNamespace(batch_id="B_OK", priority="normal", due_date="2026-01-03"),
        "B_EXT": SimpleNamespace(batch_id="B_EXT", priority="normal", due_date="2026-01-03"),
        "B_INVALID": SimpleNamespace(batch_id="B_INVALID", priority="normal", due_date="not-a-date"),
        "B_NODUE": SimpleNamespace(batch_id="B_NODUE", priority="normal", due_date=None),
    }
    results = [
        _result(
            op_id=1,
            batch_id="B_LATE",
            source="internal",
            machine_id="M1",
            operator_id="O1",
            op_type_name="车削",
            start_time=datetime(2026, 1, 1, 8, 0, 0),
            end_time=datetime(2026, 1, 2, 6, 0, 0),
        ),
        _result(
            op_id=2,
            batch_id="B_OK",
            source="internal",
            machine_id="M1",
            operator_id="O1",
            op_type_name="",
            start_time=datetime(2026, 1, 2, 6, 0, 0),
            end_time=datetime(2026, 1, 2, 7, 0, 0),
        ),
        _result(
            op_id=3,
            batch_id="B_OK",
            source="internal",
            machine_id="M1",
            operator_id="O1",
            op_type_name="铣削",
            start_time=datetime(2026, 1, 2, 7, 0, 0),
            end_time=datetime(2026, 1, 2, 9, 0, 0),
        ),
        _result(
            op_id=4,
            batch_id="B_EXT",
            source="external",
            machine_id="EXT_M",
            operator_id="EXT_O",
            op_type_name="外协",
            start_time=datetime(2026, 1, 1, 9, 0, 0),
            end_time=datetime(2026, 1, 1, 12, 0, 0),
        ),
    ]

    metrics = compute_metrics(results, batches)
    assert metrics.to_dict() == {
        "overdue_count": 1,
        "total_tardiness_hours": 6.0,
        "makespan_hours": 25.0,
        "changeover_count": 1,
        "weighted_tardiness_hours": 12.0,
        "makespan_internal_hours": 25.0,
        "machine_used_count": 1,
        "operator_used_count": 1,
        "machine_busy_hours_total": 25.0,
        "operator_busy_hours_total": 25.0,
        "machine_util_avg": 1.0,
        "operator_util_avg": 1.0,
        "machine_load_cv": 0.0,
        "operator_load_cv": 0.0,
        "internal_horizon_hours": 25.0,
        "util_defined": True,
        "invalid_due_count": 1,
        "unscheduled_batch_count": 2,
        "invalid_due_batch_ids_sample": ["B_INVALID"],
        "unscheduled_batch_ids_sample": ["B_INVALID(not-a-date)", "B_NODUE"],
    }
    assert objective_score("min_weighted_tardiness", metrics) == (12.0, 6.0, 25.0, 1.0)
