"""候选方案成功持久化与失败回滚。"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from core.infrastructure.database import ensure_schema, get_connection
from core.models.objective import best_score_schema
from core.models.workbench_plan_scope import PlanCatalogScope
from core.services.scheduler.run.schedule_candidate_runner import CandidateComparisonOutcome, CandidatePlan
from core.services.scheduler.run.schedule_candidate_selection import (
    BusinessObjectiveSelectionResult,
)
from core.services.scheduler.run.schedule_candidate_summary import candidate_comparison_public_summary
from core.services.scheduler.run.schedule_persistence import (
    build_validated_schedule_payload,
    persist_schedule_run_with_candidates,
)
from core.services.scheduler.schedule_plan_query_service import SchedulePlanQueryService
from core.services.scheduler.schedule_service import ScheduleService
from core.services.scheduler.summary import schedule_summary, summary_size_guard, summary_size_guard_fields
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from tests._support.paths import REPO_ROOT
from tests.workbench.legacy_run_archive_support import stored_legacy_selection
from tests.workbench.run_candidate_support import candidate_case

SCHEMA_PATH = REPO_ROOT / "schema.sql"


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
    selection = stored_legacy_selection({
        "selected_candidate_key": "graph_w1_of_3", "selected_kind": "critical_chain",
        "selection_policy": "balanced", "reason_code": "balanced_critical_health_better",
        "raw_score_best_key": "graph_w1_of_3", "baseline_best_key": "baseline",
        "critical_best_key": "graph_w1_of_3", "critical_health_best_key": "graph_w1_of_3",
        "selected_score": [0, 0, 1.0], "selection_policy_version": "candidate-selection-v1",
        "overdue_tolerance_count": None, "tardiness_tolerance_ratio": None,
    }, adopted)
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
    saved = comparison.selection.to_dict()
    selected_plan = overrides.pop("selected_plan", comparison.selection.selected_plan)
    selection = stored_legacy_selection({**saved, **overrides}, selected_plan)
    return replace(comparison, selection=selection)


def _business_comparison() -> CandidateComparisonOutcome:
    targets = ("min_overdue", "min_tardiness", "min_changeover")
    scope = {"scheduled_operation_ids": [10], "complete_batch_ids": ["B1"], "objective_scope": "full_candidate",
             "components_known": True, "is_complete": True}
    candidates = []
    for original, key, label, objective, metrics in (
        (_comparison().candidates[0], "business-first", "拖期更轻代表方案", "min_tardiness",
         {"failed_ops": 0, "overdue_count": 1, "total_tardiness_hours": 1, "weighted_tardiness_hours": 1,
          "makespan_hours": 1, "changeover_count": 3}),
        (_comparison().candidates[1], "business-selected", "交期优先代表方案", "min_overdue",
         {"failed_ops": 0, "overdue_count": 0, "total_tardiness_hours": 2, "weighted_tardiness_hours": 2,
          "makespan_hours": 1, "changeover_count": 0}),
    ):
        evaluations = {target: {"score": [metrics[item["key"]] for item in best_score_schema(target)],
            "field_order": [item["key"] for item in best_score_schema(target)], "scoring_scope": scope} for target in targets}
        candidates.append(replace(original, candidate_key=key, kind="business_objective", label=label,
            generation_policy_version="unified_search_v1", objective=objective, objective_name=objective,
            representative_objectives=["min_tardiness"] if objective == "min_tardiness" else ["min_overdue", "min_changeover"],
            evaluations=evaluations, score=tuple(evaluations[objective]["score"]), metrics=SimpleNamespace(**metrics),
            graph_critical_weight=None, graph_impact_weight=None, graph_downstream_weight=None))
    selected = candidates[1]
    selection = BusinessObjectiveSelectionResult(selected_candidate_key=selected.candidate_key, selected_plan=selected,
        primary_objective="min_overdue", target_objectives=targets,
        objective_winners={"min_overdue": selected.candidate_key, "min_tardiness": candidates[0].candidate_key,
                           "min_changeover": selected.candidate_key},
        objective_winner_reasons={target: None for target in targets},
        objective_field_order={target: [item["key"] for item in best_score_schema(target)] for target in targets},
        selected_score=selected.score, scoring_scope=scope, reason_code="primary_objective_best", evidence_state="available")
    return CandidateComparisonOutcome(candidates=candidates, selection=selection, planned_count=2, completed_count=2,
        failed_count=0, skipped_count=0, time_budget_reached=False, selection_policy="business_objectives_v1",
        run_time_budget_seconds=20.0, skipped_candidate_labels=[], baseline_missing_or_failed=False,
        generation_policy_version="unified_search_v1", primary_objective="min_overdue", target_objectives=list(targets))


def _persist_once(conn: sqlite3.Connection, *, op_logger: _OpLogger, comparison=None, version=7, simulate=True) -> None:
    svc = ScheduleService(conn, logger=None, op_logger=op_logger)
    comparison = _comparison() if comparison is None else comparison
    adopted = comparison.selection.selected_plan
    payload = build_validated_schedule_payload(list(adopted.results), allowed_op_ids={10})
    result_summary_obj = {"algo": {"candidate_comparison": candidate_comparison_public_summary(comparison)}}
    persist_schedule_run_with_candidates(
        svc,
        cfg=SimpleNamespace(auto_assign_persist="no"),
        version=version,
        validated_schedule_payload=payload,
        summary=adopted.summary,
        used_strategy=adopted.used_strategy,
        used_params=adopted.used_params,
        batches={"B1": SimpleNamespace(batch_id="B1", status="pending")},
        reschedulable_operations=[SimpleNamespace(id=10, batch_id="B1", source="internal", status="pending")],
        normalized_batch_ids=["B1"],
        created_by="pytest",
        simulate=simulate,
        frozen_op_ids=set(),
        result_status="simulated" if simulate else "success",
        result_summary_json=json.dumps(result_summary_obj, ensure_ascii=False),
        result_summary_obj=result_summary_obj,
        missing_internal_resource_op_ids=set(),
        overdue_items=[],
        time_cost_ms=12,
        candidate_comparison=comparison,
    )


def test_schedule_candidate_history_and_rows_are_written_in_one_successful_run(tmp_path: Path, monkeypatch, record_property) -> None:
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
        assert "adopted_candidate_key" not in log_candidate_summary
        assert "candidate_key" not in str(log_candidate_summary)
        _persist_once(conn, op_logger=op_logger, comparison=_business_comparison(), version=9, simulate=False)
        assert conn.execute("SELECT COUNT(*) FROM Schedule WHERE version=9").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM ScheduleCandidate WHERE version=9 AND candidate_kind='business_objective'").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM ScheduleCandidateRows WHERE version=9").fetchone()[0] == 1
        roles = {row["role"]: (row["candidate_id"], row["source_table"]) for row in conn.execute(
            "SELECT role,candidate_id,source_table FROM ScheduleCandidateSelection WHERE version=9")}
        query = SchedulePlanQueryService(conn)
        assert [option.role for option in query.list_plan_roles(9)] == ["adopted", "min_overdue", "min_tardiness", "min_changeover"]
        assert roles["adopted"] == roles["min_overdue"] == roles["min_changeover"]
        assert roles["adopted"][1] == "schedule" and roles["min_tardiness"][1] == "candidate_rows"
        adopted_resolution = query.resolve_existing_plan(9, "adopted")
        assert adopted_resolution.plan_identity.can_dispatch is True
        assert adopted_resolution.plan_identity.can_write_feedback is True
        for role in ("min_overdue", "min_tardiness", "min_changeover"):
            resolved = query.resolve_existing_plan(9, role)
            assert resolved.status == "resolved_comparison" and resolved.selected_role == role
            assert resolved.plan_identity.can_dispatch is resolved.plan_identity.can_write_feedback is False
        workbench = WorkbenchPlanQueryService(conn)
        with workbench.read_snapshot():
            catalog, _ = workbench.catalog_page(PlanCatalogScope())
        new_plans = [row for row in catalog["plans"] if row["version"] == 9]
        assert len(new_plans) == 4 and all(row["capabilities"]["view"] for row in new_plans)
        assert {row["display_name"] for row in new_plans if row["kind"] == "candidate"} == {
            "交期优先代表方案", "拖期更轻代表方案", "切换更少代表方案"}
    finally:
        conn.close()

    native_path = tmp_path / "native-summary"
    native_path.mkdir()
    fixture = candidate_case.__wrapped__(native_path)
    case = next(fixture)
    try:
        case.config(time_budget_seconds=2, graph_analysis_mode="off", algo_mode="greedy")
        captured = []
        original_guard = schedule_summary.apply_summary_size_guard

        def capture_guard(summary):
            original = json.dumps(summary, ensure_ascii=False)
            display = original_guard(summary)
            captured.append((original, display))
            return display

        monkeypatch.setattr(summary_size_guard, "SUMMARY_SIZE_LIMIT_BYTES", 512)
        monkeypatch.setattr(summary_size_guard_fields, "SUMMARY_SIZE_LIMIT_BYTES", 512)
        monkeypatch.setattr(schedule_summary, "apply_summary_size_guard", capture_guard)
        result = ScheduleService(case.conn).run_schedule(
            ["B1"], start_dt=datetime(2026, 9, 9, 8), end_date="2026-09-25", simulate=False,
            created_by="pytest-native-summary", run_time_budget_seconds=2)
        assert result["result_persisted"] is True and not case.conn.in_transaction
        assert len(captured) == 1
        original_text, display = captured[0]
        original = json.loads(original_text)
        assert display["summary_truncated"] is True
        assert summary_size_guard_fields.summary_size_bytes(display) <= 512
        comparison = original["algo"]["candidate_comparison"]
        assert comparison["generation_policy_version"] == "unified_search_v1"
        assert comparison["selection"]["selected_candidate_key"]
        assert comparison["candidates"] and comparison["unified_process"]["events"]
        saved_text = case.conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=?", (result["version"],)).fetchone()[0]
        assert saved_text == original_text
        saved_comparison = json.loads(saved_text)["algo"]["candidate_comparison"]
        for field in ("selection", "candidates", "unified_process"):
            assert saved_comparison[field] == comparison[field]
        assert display.get("algo", {}).get("candidate_comparison") != comparison
        record_property("native_summary_size_guard", json.dumps({
            "threshold_bytes": 512, "original_bytes": len(original_text.encode("utf-8")),
            "display_bytes": summary_size_guard_fields.summary_size_bytes(display), "display_truncated": True,
            "candidate_count": len(comparison["candidates"]), "process_event_count": len(comparison["unified_process"]["events"]),
            "complete_history_text_equal": True}, ensure_ascii=False))
    finally:
        try:
            next(fixture)
        except StopIteration:
            pass


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
        original = tuple(conn.iterdump())
        comparison = _business_comparison()
        adopted = comparison.selection.selected_plan
        payload = build_validated_schedule_payload(list(adopted.results), allowed_op_ids={10})
        try:
            persist_schedule_run_with_candidates(
                svc, cfg=SimpleNamespace(auto_assign_persist="no"), version=9, validated_schedule_payload=payload,
                summary=adopted.summary, used_strategy=adopted.used_strategy, used_params=adopted.used_params,
                batches={"B1": SimpleNamespace(batch_id="B1", status="pending")},
                reschedulable_operations=[SimpleNamespace(id=10, batch_id="B1", source="internal", status="pending")],
                normalized_batch_ids=["B1"], created_by="pytest", simulate=False, frozen_op_ids=set(),
                result_status="success", result_summary_json="{}", result_summary_obj={},
                missing_internal_resource_op_ids=set(), overdue_items=[], time_cost_ms=12, candidate_comparison=comparison)
        except RuntimeError as exc:
            assert "selection write failed" in str(exc)
        else:
            raise AssertionError("business selection failure must abort persistence")
        assert tuple(conn.iterdump()) == original
        assert op_logger.calls == []
    finally:
        conn.close()
