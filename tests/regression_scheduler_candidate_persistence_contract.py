from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.schedule_candidate_persistence import persist_candidate_comparison
from core.services.scheduler.run.schedule_candidate_runner import CandidateComparisonOutcome, CandidatePlan
from core.services.scheduler.run.schedule_candidate_selection import CandidateSelectionResult
from core.services.scheduler.run.schedule_candidate_summary import candidate_comparison_public_summary
from core.services.scheduler.run.schedule_persistence import (
    build_validated_schedule_payload,
    persist_schedule_run_with_candidates,
)
from core.services.scheduler.schedule_service import ScheduleService

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema.sql"


class _OpLogger:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def info(self, **kwargs: Any) -> None:
        self.calls.append(dict(kwargs))


class _FailingSelectionRepo:
    def __init__(self, repo: Any) -> None:
        self._repo = repo

    def create_candidates(self, candidates: Any) -> Dict[str, int]:
        return self._repo.create_candidates(candidates)

    def bulk_create_candidate_rows(self, rows: Any) -> int:
        return self._repo.bulk_create_candidate_rows(rows)

    def create_selection(self, selection: Any) -> Any:
        raise RuntimeError("selection write failed")


def _connect_fresh_schema(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


def _dt(hours: int) -> datetime:
    return datetime(2026, 5, 1, 8, 0, 0) + timedelta(hours=hours)


def _result(op_id: int, machine_id: str, operator_id: str, start_hour: int) -> SimpleNamespace:
    return SimpleNamespace(
        op_id=op_id,
        op_code=f"OP{op_id}",
        batch_id="B1",
        seq=op_id,
        machine_id=machine_id,
        operator_id=operator_id,
        start_time=_dt(start_hour),
        end_time=_dt(start_hour + 1),
        source="internal",
    )


def _seed_schedule_context(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        INSERT INTO Machines(machine_id, name)
        VALUES ('M-ADOPTED', '正式设备'), ('M-BASELINE', '基线设备');

        INSERT INTO Operators(operator_id, name)
        VALUES ('O-ADOPTED', '正式人员'), ('O-BASELINE', '基线人员');

        INSERT INTO Parts(part_no, part_name)
        VALUES ('P001', '零件一');

        INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, status)
        VALUES ('B1', 'P001', '零件一', 1, '2026-05-02', 'normal', 'pending');

        INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
        VALUES (10, 'OP10', 'B1', 'piece-a', 10, '车削', 'internal', 'pending');
        """
    )
    conn.commit()


def _candidate(
    key: str,
    kind: str,
    *,
    sequence: int,
    op_id: int = 10,
    machine_id: str,
    operator_id: str,
    score: Any,
) -> CandidatePlan:
    return CandidatePlan(
        sequence=sequence,
        candidate_key=key,
        kind=kind,
        label=key,
        status="completed",
        score=tuple(score),
        graph_critical_weight=500 if kind == "critical_chain" else 0,
        graph_impact_weight=10 if kind == "critical_chain" else 0,
        graph_downstream_weight=1 if kind == "critical_chain" else 0,
        results=[_result(op_id, machine_id, operator_id, sequence * 2)],
        summary=SimpleNamespace(total_ops=1, scheduled_ops=1, failed_ops=0, warnings=[], errors=[]),
        metrics=SimpleNamespace(
            overdue_count=int(score[1]),
            total_tardiness_hours=float(score[2]),
            weighted_tardiness_hours=float(score[2]),
            makespan_hours=1.0,
            changeover_count=0,
        ),
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={"dispatch": "sgs"},
        best_order=["B1"],
        attempts=[{"score": list(score)}],
        improvement_trace=[{"score": list(score)}],
        algo_mode="greedy",
        objective_name="min_overdue",
        algo_stats={"small": True},
        time_budget_seconds=20,
        sort_strategy="priority_first",
        dispatch_mode="sgs",
        dispatch_rule="cr",
        objective="min_overdue",
    )


def _comparison(*, baseline_op_id: int = 10, adopted_op_id: int = 10) -> CandidateComparisonOutcome:
    baseline = _candidate(
        "baseline",
        "baseline",
        sequence=0,
        op_id=baseline_op_id,
        machine_id="M-BASELINE",
        operator_id="O-BASELINE",
        score=(0, 1, 2.0),
    )
    adopted = _candidate(
        "graph_w1_of_3",
        "critical_chain",
        sequence=1,
        op_id=adopted_op_id,
        machine_id="M-ADOPTED",
        operator_id="O-ADOPTED",
        score=(0, 0, 1.0),
    )
    selection = CandidateSelectionResult(
        selected_candidate_key=adopted.candidate_key,
        selected_kind=adopted.kind,
        selection_policy="balanced",
        reason_code="balanced_critical_health_better",
        raw_score_best_key=adopted.candidate_key,
        baseline_best_key=baseline.candidate_key,
        critical_best_key=adopted.candidate_key,
        critical_health_best_key=adopted.candidate_key,
        selected_score=adopted.score or (),
        selected_plan=adopted,
    )
    return CandidateComparisonOutcome(
        candidates=[baseline, adopted],
        selection=selection,
        planned_count=2,
        completed_count=2,
        failed_count=0,
        skipped_count=0,
        time_budget_reached=False,
        selection_policy="balanced",
        run_time_budget_seconds=20.0,
        skipped_candidate_labels=[],
        baseline_missing_or_failed=False,
    )


def _comparison_with_selection(**overrides: Any) -> CandidateComparisonOutcome:
    comparison = _comparison()
    selection = replace(comparison.selection, **overrides)
    return replace(comparison, selection=selection)


def _persist_once(conn: sqlite3.Connection, *, op_logger: _OpLogger) -> None:
    svc = ScheduleService(conn, logger=None, op_logger=op_logger)
    comparison = _comparison()
    adopted = comparison.selection.selected_plan
    payload = build_validated_schedule_payload(list(adopted.results), allowed_op_ids={10})
    result_summary_obj = {"algo": {"candidate_comparison": candidate_comparison_public_summary(comparison)}}
    persist_schedule_run_with_candidates(
        svc,
        cfg=SimpleNamespace(auto_assign_persist="no"),
        version=7,
        validated_schedule_payload=payload,
        summary=adopted.summary,
        used_strategy=adopted.used_strategy,
        used_params=adopted.used_params,
        batches={"B1": SimpleNamespace(batch_id="B1", status="pending")},
        reschedulable_operations=[SimpleNamespace(id=10, batch_id="B1", source="internal", status="pending")],
        normalized_batch_ids=["B1"],
        created_by="pytest",
        simulate=True,
        frozen_op_ids=set(),
        result_status="simulated",
        result_summary_json=json.dumps(result_summary_obj, ensure_ascii=False),
        result_summary_obj=result_summary_obj,
        missing_internal_resource_op_ids=set(),
        overdue_items=[],
        time_cost_ms=12,
        candidate_comparison=comparison,
    )


def test_schedule_candidate_history_and_rows_are_written_in_one_successful_run(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    op_logger = _OpLogger()
    try:
        _seed_schedule_context(conn)
        _persist_once(conn, op_logger=op_logger)

        assert conn.execute("SELECT COUNT(*) FROM Schedule WHERE version = 7").fetchone()[0] == 1
        assert conn.execute("SELECT machine_id FROM Schedule WHERE version = 7").fetchone()[0] == "M-ADOPTED"
        assert conn.execute("SELECT COUNT(*) FROM ScheduleHistory WHERE version = 7").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM ScheduleCandidate WHERE version = 7").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM ScheduleCandidateRows WHERE version = 7").fetchone()[0] == 1

        selections = {
            row["role"]: row["source_table"]
            for row in conn.execute("SELECT role, source_table FROM ScheduleCandidateSelection WHERE version = 7")
        }
        assert selections == {
            "adopted": "schedule",
            "baseline_best": "candidate_rows",
            "critical_best": "schedule",
        }
        detail_flags = {
            row["candidate_key"]: row["detail_saved"]
            for row in conn.execute("SELECT candidate_key, detail_saved FROM ScheduleCandidate WHERE version = 7")
        }
        assert detail_flags == {"baseline": "yes", "graph_w1_of_3": "no"}

        assert len(op_logger.calls) == 1
        log_candidate_summary = op_logger.calls[0]["detail"]["algo"]["candidate_comparison"]
        assert "candidates" not in log_candidate_summary
        assert log_candidate_summary["adopted_candidate_key"] == "graph_w1_of_3"
    finally:
        conn.close()


def test_candidate_persistence_failure_rolls_back_schedule_history_and_candidates(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    op_logger = _OpLogger()
    try:
        _seed_schedule_context(conn)
        svc = ScheduleService(conn, logger=None, op_logger=op_logger)
        svc.candidate_repo = _FailingSelectionRepo(svc.candidate_repo)  # type: ignore[assignment]
        comparison = _comparison()
        adopted = comparison.selection.selected_plan
        payload = build_validated_schedule_payload(list(adopted.results), allowed_op_ids={10})
        try:
            persist_schedule_run_with_candidates(
                svc,
                cfg=SimpleNamespace(auto_assign_persist="no"),
                version=8,
                validated_schedule_payload=payload,
                summary=adopted.summary,
                used_strategy=adopted.used_strategy,
                used_params=adopted.used_params,
                batches={"B1": SimpleNamespace(batch_id="B1", status="pending")},
                reschedulable_operations=[SimpleNamespace(id=10, batch_id="B1", source="internal", status="pending")],
                normalized_batch_ids=["B1"],
                created_by="pytest",
                simulate=True,
                frozen_op_ids=set(),
                result_status="simulated",
                result_summary_json="{}",
                result_summary_obj={"algo": {"candidate_comparison": candidate_comparison_public_summary(comparison)}},
                missing_internal_resource_op_ids=set(),
                overdue_items=[],
                time_cost_ms=12,
                candidate_comparison=comparison,
            )
        except RuntimeError as exc:
            assert "selection write failed" in str(exc)
        else:
            raise AssertionError("candidate selection failure must abort persistence")

        assert conn.execute("SELECT COUNT(*) FROM Schedule WHERE version = 8").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM ScheduleHistory WHERE version = 8").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM ScheduleCandidate WHERE version = 8").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM ScheduleCandidateRows WHERE version = 8").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM ScheduleCandidateSelection WHERE version = 8").fetchone()[0] == 0
        assert op_logger.calls == []
    finally:
        conn.close()


def test_candidate_detail_rows_reject_out_of_scope_op_id_and_rollback(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    op_logger = _OpLogger()
    try:
        _seed_schedule_context(conn)
        svc = ScheduleService(conn, logger=None, op_logger=op_logger)
        comparison = _comparison(baseline_op_id=999)
        adopted = comparison.selection.selected_plan
        payload = build_validated_schedule_payload(list(adopted.results), allowed_op_ids={10})

        with pytest.raises(ValidationError) as exc_info:
            persist_schedule_run_with_candidates(
                svc,
                cfg=SimpleNamespace(auto_assign_persist="no"),
                version=11,
                validated_schedule_payload=payload,
                summary=adopted.summary,
                used_strategy=adopted.used_strategy,
                used_params=adopted.used_params,
                batches={"B1": SimpleNamespace(batch_id="B1", status="pending")},
                reschedulable_operations=[SimpleNamespace(id=10, batch_id="B1", source="internal", status="pending")],
                normalized_batch_ids=["B1"],
                created_by="pytest",
                simulate=True,
                frozen_op_ids=set(),
                result_status="simulated",
                result_summary_json="{}",
                result_summary_obj={"algo": {"candidate_comparison": candidate_comparison_public_summary(comparison)}},
                missing_internal_resource_op_ids=set(),
                overdue_items=[],
                time_cost_ms=12,
                candidate_comparison=comparison,
            )

        assert exc_info.value.field == "candidate_rows"
        assert "超出本次可重排范围" in str(exc_info.value)
        assert conn.execute("SELECT COUNT(*) FROM Schedule WHERE version = 11").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM ScheduleHistory WHERE version = 11").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM ScheduleCandidate WHERE version = 11").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM ScheduleCandidateRows WHERE version = 11").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM ScheduleCandidateSelection WHERE version = 11").fetchone()[0] == 0
        assert op_logger.calls == []
    finally:
        conn.close()


def test_candidate_persistence_rejects_missing_selected_candidate_key(tmp_path: Path) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        _seed_schedule_context(conn)
        svc = ScheduleService(conn, logger=None, op_logger=_OpLogger())
        comparison = _comparison_with_selection(selected_candidate_key="missing_candidate")

        with pytest.raises(ValidationError) as exc_info:
            persist_candidate_comparison(
                svc,
                version=9,
                candidate_comparison=comparison,
                frozen_op_ids=set(),
                allowed_op_ids={10},
            )

        assert exc_info.value.field == "candidate_selection"
        assert "指向不存在的方案编号" in str(exc_info.value)
    finally:
        conn.close()


@pytest.mark.parametrize(
    "selection_override",
    [
        {"baseline_best_key": "missing_baseline"},
        {"critical_best_key": "missing_critical"},
    ],
)
def test_candidate_persistence_rejects_missing_best_role_candidate_key(
    tmp_path: Path,
    selection_override: Dict[str, Any],
) -> None:
    conn = _connect_fresh_schema(tmp_path)
    try:
        _seed_schedule_context(conn)
        svc = ScheduleService(conn, logger=None, op_logger=_OpLogger())
        comparison = _comparison_with_selection(**selection_override)

        with pytest.raises(ValidationError) as exc_info:
            persist_candidate_comparison(
                svc,
                version=10,
                candidate_comparison=comparison,
                frozen_op_ids=set(),
                allowed_op_ids={10},
            )

        assert exc_info.value.field == "candidate_selection"
        assert "指向不存在的方案编号" in str(exc_info.value)
    finally:
        conn.close()
