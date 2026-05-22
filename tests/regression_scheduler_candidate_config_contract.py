from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, cast

import pytest

from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.errors import ValidationError
from core.models.schedule_config_runtime_fields import list_runtime_config_fields
from core.services.scheduler.config.config_constants import CONFIG_PAGE_FIELDS, CONFIG_PAGE_WRITE_FIELDS
from core.services.scheduler.config.config_field_spec import (
    choices_for,
    coerce_config_field,
    default_for,
    list_config_fields,
)
from core.services.scheduler.config.config_presets import missing_required_preset_fields
from core.services.scheduler.config.config_service import ConfigService
from core.services.scheduler.config.config_snapshot import ScheduleConfigSnapshot, ensure_schedule_config_snapshot
from core.services.scheduler.config.config_validator import normalize_preset_snapshot
from core.services.scheduler.run import schedule_orchestrator
from core.services.scheduler.run.schedule_optimizer import OptimizationOutcome
from web.routes.domains.scheduler.scheduler_config import _collect_scheduler_config_form_payload

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


class _TxManager:
    def transaction(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _HistoryRepo:
    def allocate_next_version(self) -> int:
        return 77


class _Svc:
    logger = None

    def __init__(self) -> None:
        self.tx_manager = _TxManager()
        self.history_repo = _HistoryRepo()


def _dt(hours: int) -> datetime:
    return datetime(2026, 5, 1, 8, 0, 0) + timedelta(hours=hours)


def _base_snapshot(**overrides: Any) -> ScheduleConfigSnapshot:
    data: Dict[str, Any] = {
        "sort_strategy": "priority_first",
        "priority_weight": 0.4,
        "due_weight": 0.5,
        "ready_weight": 0.1,
        "holiday_default_efficiency": 1.0,
        "enforce_ready_default": "no",
        "prefer_primary_skill": "no",
        "dispatch_mode": "sgs",
        "dispatch_rule": "slack",
        "auto_assign_enabled": "no",
        "auto_assign_persist": "yes",
        "ortools_enabled": "no",
        "ortools_time_limit_seconds": 5,
        "algo_mode": "greedy",
        "time_budget_seconds": 30,
        "objective": "min_overdue",
        "freeze_window_enabled": "no",
        "freeze_window_days": 0,
        "graph_analysis_mode": "on",
        "graph_block_on_cycle": "no",
        "graph_critical_weight": 500,
        "graph_impact_weight": 10,
        "graph_candidate_weight_count": 5,
        "graph_selection_policy": "balanced",
        "graph_overdue_tolerance_count": 1,
        "graph_tardiness_tolerance_ratio": 0.10,
        "graph_debug_export": "no",
    }
    data.update(overrides)
    return ScheduleConfigSnapshot(**data)


def _schedule_input(cfg: ScheduleConfigSnapshot, *, run_time_budget_seconds: Any = None) -> Any:
    algo_ops = [
        SimpleNamespace(
            id=1,
            op_code="OP001",
            batch_id="B001",
            seq=10,
            source="internal",
            setup_hours=0,
            unit_hours=1,
            op_type_name="车削",
        )
    ]
    return SimpleNamespace(
        cfg=cfg,
        cal_svc=SimpleNamespace(),
        cfg_svc=SimpleNamespace(),
        run_time_budget_seconds=run_time_budget_seconds,
        algo_ops=algo_ops,
        algo_ops_to_schedule=list(algo_ops),
        downtime_map={},
        seed_results=[],
        resource_pool={"machines_by_op_type": {}, "operators_by_machine": {}, "machines_by_operator": {}},
        optimizer_seed_version=76,
        reschedulable_op_ids={1},
        reschedulable_operations=[SimpleNamespace(id=1, batch_id="B001", source="internal")],
        missing_internal_resource_op_ids=set(),
        algo_warnings=[],
        frozen_op_ids=set(),
        normalized_batch_ids=["B001"],
        start_dt_norm=_dt(0),
        end_date_norm=None,
        batches={"B001": SimpleNamespace(batch_id="B001")},
        operations=[SimpleNamespace(id=1, batch_id="B001", source="internal")],
        freeze_meta={},
        algo_input_outcome=SimpleNamespace(value=[]),
        downtime_meta={},
        resource_pool_meta={},
        readiness_gate_enabled=True,
        t0=0.0,
    )


def _selected_result() -> Any:
    return SimpleNamespace(
        op_id=1,
        op_code="OP001",
        batch_id="B001",
        seq=10,
        machine_id="M1",
        operator_id="O1",
        start_time=_dt(0),
        end_time=_dt(1),
        source="internal",
    )


def _comparison_outcome() -> SimpleNamespace:
    selected_plan = SimpleNamespace(
        results=[_selected_result()],
        summary=SimpleNamespace(success=True, total_ops=1, scheduled_ops=1, failed_ops=0, warnings=[], errors=[]),
        used_strategy=SimpleNamespace(value="priority_first"),
        used_params={"dispatch": "sgs"},
        metrics=None,
        score=(0.0,),
        best_order=["B001"],
        attempts=[],
        improvement_trace=[],
        algo_mode="greedy",
        objective_name="min_overdue",
        algo_stats={},
        time_budget_seconds=30,
        graph_analysis_public=None,
        graph_analysis_diagnostics=None,
    )
    selection = SimpleNamespace(
        selected_plan=selected_plan,
        selected_candidate_key="baseline",
        raw_score_best_key="baseline",
        baseline_best_key="baseline",
        critical_best_key="graph_w1_of_7",
        selection_policy="score_only",
        reason_code="score_only_raw_score_best",
    )
    return SimpleNamespace(
        selection=selection,
        candidates=[],
        planned_count=8,
        completed_count=8,
        failed_count=0,
        skipped_count=0,
        time_budget_reached=False,
        run_time_budget_seconds=11.0,
    )


def _summary_from_ctx(_svc: Any, *, ctx: Any):
    return [], "success", {"algo": {"candidate_comparison": ctx.candidate_comparison_public}}, "{}", 1


def test_pr7e_config_defaults_choices_and_fresh_snapshot(tmp_path: Path) -> None:
    assert default_for("graph_analysis_mode") == "on"
    assert default_for("graph_candidate_weight_count") == 5
    assert choices_for("graph_candidate_weight_count") == ("3", "5", "7")
    assert default_for("graph_selection_policy") == "balanced"
    assert choices_for("graph_selection_policy") == ("balanced", "score_only")
    assert default_for("graph_overdue_tolerance_count") == 1
    assert choices_for("graph_overdue_tolerance_count") == ("0", "1", "2")
    assert default_for("graph_tardiness_tolerance_ratio") == 0.10
    assert choices_for("graph_tardiness_tolerance_ratio") == ("0.05", "0.1", "0.2")

    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    conn = get_connection(str(db_path))
    try:
        svc = ConfigService(conn, logger=None, op_logger=None)
        svc.ensure_defaults()
        snap = svc.get_snapshot()
        assert snap.graph_analysis_mode == "on"
        assert snap.graph_candidate_weight_count == 5
        assert snap.graph_selection_policy == "balanced"
        assert snap.graph_overdue_tolerance_count == 1
        assert snap.graph_tardiness_tolerance_ratio == 0.10
    finally:
        conn.close()


def test_pr7e_numeric_choices_are_strictly_validated() -> None:
    with pytest.raises(ValidationError):
        coerce_config_field("graph_candidate_weight_count", "4", strict_mode=True, source="test")
    with pytest.raises(ValidationError):
        coerce_config_field("graph_overdue_tolerance_count", "3", strict_mode=True, source="test")
    with pytest.raises(ValidationError):
        coerce_config_field("graph_tardiness_tolerance_ratio", "0.15", strict_mode=True, source="test")

    assert coerce_config_field("graph_candidate_weight_count", "7", strict_mode=True, source="test") == 7
    assert coerce_config_field("graph_overdue_tolerance_count", "0", strict_mode=True, source="test") == 0
    assert coerce_config_field("graph_tardiness_tolerance_ratio", "0.20", strict_mode=True, source="test") == 0.20


def test_old_presets_may_omit_pr7e_fields_but_preserve_saved_values() -> None:
    base = _base_snapshot()
    old_payload = base.to_dict()
    for key in (
        "graph_candidate_weight_count",
        "graph_selection_policy",
        "graph_overdue_tolerance_count",
        "graph_tardiness_tolerance_ratio",
    ):
        old_payload.pop(key)

    assert missing_required_preset_fields(old_payload) == []
    required_missing = dict(old_payload)
    required_missing.pop("sort_strategy")
    assert "sort_strategy" in missing_required_preset_fields(required_missing)

    normalized = normalize_preset_snapshot(old_payload, base=base, strict_mode=True)
    assert normalized.graph_candidate_weight_count == 5
    assert normalized.graph_selection_policy == "balanced"
    assert normalized.graph_overdue_tolerance_count == 1
    assert normalized.graph_tardiness_tolerance_ratio == 0.10

    saved_payload = dict(old_payload)
    saved_payload.update(
        {
            "graph_candidate_weight_count": "7",
            "graph_selection_policy": "score_only",
            "graph_overdue_tolerance_count": "0",
            "graph_tardiness_tolerance_ratio": "0.2",
        }
    )
    normalized_saved = normalize_preset_snapshot(saved_payload, base=base, strict_mode=True)
    assert normalized_saved.graph_candidate_weight_count == 7
    assert normalized_saved.graph_selection_policy == "score_only"
    assert normalized_saved.graph_overdue_tolerance_count == 0
    assert normalized_saved.graph_tardiness_tolerance_ratio == 0.20


def test_graph_downstream_weight_stays_internal_candidate_parameter() -> None:
    field = "graph_downstream_weight"
    service_config_keys = {spec.key for spec in list_config_fields()}
    runtime_config_keys = {spec.key for spec in list_runtime_config_fields()}

    assert field not in CONFIG_PAGE_FIELDS
    assert field not in CONFIG_PAGE_WRITE_FIELDS
    assert field not in service_config_keys
    assert field not in runtime_config_keys
    assert _collect_scheduler_config_form_payload({field: "3"}) == {}

    external_payload = _base_snapshot().to_dict()
    external_payload[field] = 3
    normalized = ensure_schedule_config_snapshot(external_payload, strict_mode=True)
    assert normalized.graph_downstream_weight == 1

    zero_visible_payload = _base_snapshot(graph_critical_weight=0, graph_impact_weight=0).to_dict()
    normalized_zero = ensure_schedule_config_snapshot(zero_visible_payload, strict_mode=True)
    assert normalized_zero.graph_downstream_weight == 0


def test_graph_analysis_mode_controls_candidate_comparison_without_user_visible_toggle() -> None:
    assert schedule_orchestrator._candidate_comparison_enabled(_base_snapshot(graph_analysis_mode="on")) is True
    assert schedule_orchestrator._candidate_comparison_enabled(_base_snapshot(graph_analysis_mode="off")) is False
    assert schedule_orchestrator._candidate_comparison_enabled(_base_snapshot(graph_analysis_mode="report")) is False

    assert schedule_orchestrator._candidate_weight_count(_base_snapshot(graph_candidate_weight_count=7)) == 7
    assert schedule_orchestrator._candidate_selection_policy(_base_snapshot(graph_selection_policy="score_only")) == "score_only"
    assert schedule_orchestrator._candidate_overdue_tolerance_count(_base_snapshot(graph_overdue_tolerance_count=0)) == 0
    assert schedule_orchestrator._candidate_tardiness_tolerance_ratio(
        _base_snapshot(graph_tardiness_tolerance_ratio=0.20)
    ) == 0.20

    for rel_path in (
        "templates/scheduler/config.html",
        "templates/scheduler/_run_panel.html",
        "web_new_test/templates/scheduler/config.html",
    ):
        assert "candidate_comparison_enabled" not in (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    assert "run_time_budget_seconds" not in (REPO_ROOT / "templates/scheduler/config.html").read_text(encoding="utf-8")
    assert "run_time_budget_seconds" not in (REPO_ROOT / "web_new_test/templates/scheduler/config.html").read_text(encoding="utf-8")
    payload = _collect_scheduler_config_form_payload(
        {
            "graph_analysis_mode": "on",
            "graph_candidate_weight_count": "5",
            "run_time_budget_seconds": "11",
        }
    )
    assert payload == {"graph_analysis_mode": "on", "graph_candidate_weight_count": "5"}


def test_orchestrator_passes_pr7e_runtime_fields_to_default_candidate_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: Dict[str, Any] = {}
    preflight_calls: List[Any] = []

    def _fake_run_candidate_comparison(**kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return _comparison_outcome()

    cfg = _base_snapshot(
        graph_candidate_weight_count=7,
        graph_selection_policy="score_only",
        graph_overdue_tolerance_count=0,
        graph_tardiness_tolerance_ratio=0.20,
    )
    monkeypatch.setattr(schedule_orchestrator, "run_candidate_comparison", _fake_run_candidate_comparison)
    monkeypatch.setattr(
        schedule_orchestrator,
        "prepare_schedule_graph_for_dispatch",
        lambda schedule_input: preflight_calls.append(schedule_input),
    )

    outcome = schedule_orchestrator.orchestrate_schedule_run(
        _Svc(),
        schedule_input=_schedule_input(cfg, run_time_budget_seconds=11),
        simulate=False,
        strict_mode=True,
        optimize_schedule_fn=lambda **_kwargs: None,
        build_result_summary_fn=_summary_from_ctx,
    )

    assert captured["run_time_budget_seconds"] == 11
    assert captured["weight_count"] == 7
    assert captured["selection_policy"] == "score_only"
    assert captured["graph_overdue_tolerance_count"] == 0
    assert captured["graph_tardiness_tolerance_ratio"] == 0.20
    assert preflight_calls == []
    assert outcome.candidate_comparison is not None
    assert outcome.result_summary_obj["algo"]["candidate_comparison"]["planned_candidate_count"] == 8


@pytest.mark.parametrize("mode", ["off", "report"])
def test_orchestrator_keeps_off_and_report_as_single_plan_modes(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    def _unexpected_candidate_runner(**_kwargs: Any) -> None:
        raise AssertionError(f"{mode} 模式不应该运行方案对比")

    optimizer_calls: List[Dict[str, Any]] = []

    def _optimize(**kwargs: Any) -> Any:
        optimizer_calls.append(kwargs)
        return OptimizationOutcome(
            results=[_selected_result()],
            summary=SimpleNamespace(success=True, total_ops=1, scheduled_ops=1, failed_ops=0, warnings=[], errors=[]),
            used_strategy=cast(Any, SimpleNamespace(value="priority_first")),
            used_params={"dispatch": "sgs"},
            metrics=None,
            best_score=(0.0,),
            best_order=["B001"],
            attempts=[],
            improvement_trace=[],
            algo_mode="greedy",
            objective_name="min_overdue",
            algo_stats={},
            time_budget_seconds=30,
        )

    monkeypatch.setattr(schedule_orchestrator, "run_candidate_comparison", _unexpected_candidate_runner)
    outcome = schedule_orchestrator.orchestrate_schedule_run(
        _Svc(),
        schedule_input=_schedule_input(_base_snapshot(graph_analysis_mode=mode)),
        simulate=False,
        strict_mode=True,
        optimize_schedule_fn=_optimize,
        build_result_summary_fn=_summary_from_ctx,
    )

    assert outcome.candidate_comparison is None
    assert len(optimizer_calls) == 1
