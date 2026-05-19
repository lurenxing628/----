from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple

import pytest

from core.algorithms import GreedyScheduler, ScheduleResult, SortStrategy
from core.infrastructure.errors import ValidationError
from core.services.scheduler.config.config_snapshot import ScheduleConfigSnapshot
from core.services.scheduler.run.optimizer_runtime import OptimizerRuntime
from core.services.scheduler.run.schedule_graph_report import prepare_schedule_graph_for_dispatch
from core.services.scheduler.run.schedule_optimizer import OptimizationOutcome, optimize_schedule
from core.services.scheduler.schedule_orchestrator import orchestrate_schedule_run


def _make_dt(hours: int) -> datetime:
    return datetime(2026, 1, 1, 8, 0, 0) + timedelta(hours=hours)


class _TxManager:
    @contextmanager
    def transaction(self) -> Any:
        yield


class _HistoryRepo:
    def allocate_next_version(self) -> int:
        return 7


class _Svc:
    def __init__(self) -> None:
        self.logger = None
        self.tx_manager = _TxManager()
        self.history_repo = _HistoryRepo()


def _config(
    *,
    graph_analysis_mode: str = "on",
    graph_block_on_cycle: str = "no",
    graph_critical_weight: int = 500,
    graph_impact_weight: int = 10,
    graph_downstream_weight: int = 1,
    dispatch_mode: str = "sgs",
) -> ScheduleConfigSnapshot:
    return ScheduleConfigSnapshot(
        sort_strategy="priority_first",
        priority_weight=0.4,
        due_weight=0.5,
        ready_weight=0.1,
        holiday_default_efficiency=1.0,
        enforce_ready_default="no",
        prefer_primary_skill="no",
        dispatch_mode=dispatch_mode,
        dispatch_rule="slack",
        auto_assign_enabled="no",
        auto_assign_persist="yes",
        ortools_enabled="no",
        ortools_time_limit_seconds=5,
        algo_mode="greedy",
        objective="min_overdue",
        time_budget_seconds=5,
        freeze_window_enabled="no",
        freeze_window_days=0,
        graph_analysis_mode=graph_analysis_mode,
        graph_block_on_cycle=graph_block_on_cycle,
        graph_critical_weight=graph_critical_weight,
        graph_impact_weight=graph_impact_weight,
        graph_downstream_weight=graph_downstream_weight,
        graph_debug_export="no",
    )


def _op(op_id: int, batch_id: str, seq: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=op_id,
        op_code=f"OP-{batch_id}-{seq:03d}",
        batch_id=batch_id,
        seq=seq,
        source="internal",
        setup_hours=0.0,
        unit_hours=1.0,
        op_type_name="车削",
        machine_id="MC001",
        operator_id="OP001",
    )


class _Calendar:
    @staticmethod
    def adjust_to_working_time(dt: datetime, priority: Any = None, machine_id: Any = None, operator_id: Any = None) -> datetime:
        return dt

    @staticmethod
    def add_working_hours(dt: datetime, hours: float, priority: Any = None, machine_id: Any = None, operator_id: Any = None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    @staticmethod
    def get_efficiency(dt: datetime, machine_id: Any = None, operator_id: Any = None) -> float:
        return 1.0

    @staticmethod
    def add_calendar_days(dt: datetime, days: float, machine_id: Any = None, operator_id: Any = None) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


def _schedule_input(mode: str = "on") -> SimpleNamespace:
    frozen_op = _op(1, "B001", 10)
    ready_op = _op(2, "B001", 20)
    independent_op = _op(3, "B002", 10)
    algo_ops = [frozen_op, ready_op, independent_op]
    return SimpleNamespace(
        cfg=_config(graph_analysis_mode=mode),
        cal_svc=SimpleNamespace(),
        cfg_svc=SimpleNamespace(),
        readiness_gate_enabled=True,
        algo_ops=algo_ops,
        algo_ops_to_schedule=[ready_op, independent_op],
        batches={
            "B001": SimpleNamespace(batch_id="B001", quantity=1, due_date="2026-01-02", priority="normal"),
            "B002": SimpleNamespace(batch_id="B002", quantity=1, due_date="2026-01-02", priority="normal"),
        },
        start_dt_norm=datetime(2026, 1, 1, 8, 0, 0),
        end_date_norm=None,
        downtime_map={},
        seed_results=[{"op_id": 1}],
        resource_pool={"machines_by_op_type": {}, "operators_by_machine": {}, "machines_by_operator": {}},
        operations=[SimpleNamespace(id=2, batch_id="B001"), SimpleNamespace(id=3, batch_id="B002")],
        reschedulable_operations=[SimpleNamespace(id=2), SimpleNamespace(id=3)],
        reschedulable_op_ids={2, 3},
        normalized_batch_ids=["B001", "B002"],
        freeze_meta={"loaded": True},
        algo_input_outcome=SimpleNamespace(value=[]),
        downtime_meta={"load_ok": True},
        resource_pool_meta={"build_ok": True},
        algo_warnings=[],
        frozen_op_ids={1},
        t0=0.0,
        optimizer_seed_version=6,
        run_label="schedule",
        prev_version=5,
        created_by_text="tester",
        missing_internal_resource_op_ids=set(),
        run_time_budget_seconds=None,
    )


def _chain_schedule_input(
    *,
    graph_critical_weight: int = 500,
    graph_impact_weight: int = 10,
    graph_downstream_weight: int = 1,
) -> SimpleNamespace:
    a1 = _op(1, "B_A", 10)
    a2 = _op(2, "B_A", 20)
    b1 = _op(3, "B_B", 10)
    b2 = _op(4, "B_B", 20)
    b3 = _op(5, "B_B", 30)
    ops = [a1, a2, b1, b2, b3]
    return SimpleNamespace(
        cfg=_config(
            graph_critical_weight=graph_critical_weight,
            graph_impact_weight=graph_impact_weight,
            graph_downstream_weight=graph_downstream_weight,
        ),
        cal_svc=SimpleNamespace(),
        cfg_svc=SimpleNamespace(),
        readiness_gate_enabled=True,
        algo_ops=ops,
        algo_ops_to_schedule=ops,
        batches={
            "B_A": SimpleNamespace(batch_id="B_A", quantity=1, due_date="2026-01-02", priority="normal"),
            "B_B": SimpleNamespace(batch_id="B_B", quantity=1, due_date="2026-01-02", priority="normal"),
        },
        start_dt_norm=datetime(2026, 1, 1, 8, 0, 0),
        end_date_norm=None,
        downtime_map={},
        seed_results=[],
        resource_pool={"machines_by_op_type": {}, "operators_by_machine": {}, "machines_by_operator": {}},
        operations=[SimpleNamespace(id=getattr(op, "id"), batch_id=getattr(op, "batch_id")) for op in ops],
        reschedulable_operations=[SimpleNamespace(id=getattr(op, "id")) for op in ops],
        reschedulable_op_ids={1, 2, 3, 4, 5},
        normalized_batch_ids=["B_A", "B_B"],
        freeze_meta={"loaded": True},
        algo_input_outcome=SimpleNamespace(value=[]),
        downtime_meta={"load_ok": True},
        resource_pool_meta={"build_ok": True},
        algo_warnings=[],
        frozen_op_ids=set(),
        t0=0.0,
        optimizer_seed_version=6,
        run_label="schedule",
        prev_version=5,
        created_by_text="tester",
        missing_internal_resource_op_ids=set(),
        run_time_budget_seconds=None,
    )


def _optimizer_outcome() -> OptimizationOutcome:
    result = ScheduleResult(
        op_id=2,
        op_code="OP-B001-020",
        batch_id="B001",
        seq=20,
        machine_id="MC001",
        operator_id="OP001",
        start_time=_make_dt(0),
        end_time=_make_dt(1),
        source="internal",
        op_type_name="车削",
    )
    return OptimizationOutcome(
        results=[result],
        summary=SimpleNamespace(
            success=True,
            total_ops=1,
            scheduled_ops=1,
            failed_ops=0,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        ),
        used_strategy=SortStrategy.PRIORITY_FIRST,
        used_params={"dispatch": "sgs"},
        metrics=None,
        best_score=(0.0,),
        best_order=["B001"],
        attempts=[{"score": [0.0]}],
        improvement_trace=[],
        algo_mode="greedy",
        objective_name="min_overdue",
        time_budget_seconds=3,
        algo_stats={},
    )


def _summary_from_ctx(_svc: Any, *, ctx: Any) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any], str, int]:
    return [], "success", {"algo": {"graph_analysis": dict(ctx.graph_analysis_public or {})}}, "{}", 1


def _cycle_graph_payload() -> Dict[str, Any]:
    return {
        "node_count": 2,
        "edge_count": 2,
        "is_dag": False,
        "cycle_edges": [
            {"from": "op:B001:OP-B001-010:1", "to": "op:B001:OP-B001-020:2", "kind": "precedence"},
            {"from": "op:B001:OP-B001-020:2", "to": "op:B001:OP-B001-010:1", "kind": "explicit"},
        ],
        "topological_order": [],
        "critical_path": [],
        "critical_path_minutes": 0,
        "node_metrics": {},
        "warnings": [
            {
                "code": "GRAPH_HAS_CYCLE",
                "message": "工序依赖图存在循环，无法计算拓扑顺序和关键路径。",
                "data": {"cycle_edges": []},
            }
        ],
    }


def _cfg(dispatch_mode: str = "sgs") -> SimpleNamespace:
    return _config(dispatch_mode=dispatch_mode)


def _cfg_svc() -> SimpleNamespace:
    return SimpleNamespace(
        VALID_STRATEGIES=("priority_first", "weighted", "fifo", "edd"),
        VALID_DISPATCH_MODES=("batch_order", "sgs"),
        VALID_DISPATCH_RULES=("slack", "cr"),
        VALID_OBJECTIVES=("min_overdue",),
        VALID_ALGO_MODES=("greedy", "improve"),
    )


@pytest.fixture()
def cycle_graph(monkeypatch: Any) -> None:
    from core.services.scheduler.graph import analysis_service, exporter

    class FakeGraphService:
        def analyze_linear_batches(self, _nodes: Any, *, metrics_mode: str = "full") -> object:
            return object()

    monkeypatch.setattr(analysis_service, "ScheduleGraphAnalysisService", FakeGraphService)
    monkeypatch.setattr(exporter, "graph_summary_to_dict", lambda _summary: _cycle_graph_payload())


def test_on_dag_prepares_plain_graph_ready_context_before_optimizer() -> None:
    captured: Dict[str, Any] = {}

    def _optimize(**kwargs: Any) -> OptimizationOutcome:
        captured["graph_ready_context"] = kwargs.get("graph_ready_context")
        return _optimizer_outcome()

    outcome = orchestrate_schedule_run(
        _Svc(),
        schedule_input=_schedule_input("on"),  # type: ignore[arg-type]
        simulate=True,
        strict_mode=True,
        optimize_schedule_fn=_optimize,
        build_result_summary_fn=_summary_from_ctx,
    )

    context = captured["graph_ready_context"]
    assert isinstance(context, dict)
    assert set(context["schedulable_op_ids"]) == {2, 3}
    assert set(context["fixed_op_ids"]) == {1}
    assert context["predecessor_op_ids_by_op_id"][2] == {1}
    assert context["predecessor_op_ids_by_op_id"][3] == set()
    assert context["score_enabled"] is True
    assert set(context["graph_priority_key_by_op_id"]) == {2, 3}
    assert "graph" not in context
    assert outcome.result_summary_obj["algo"]["graph_analysis"]["status"] == "available"
    assert outcome.result_summary_obj["algo"]["graph_analysis"]["effective_mode"] == "graph_ready_queue"
    assert outcome.result_summary_obj["algo"]["graph_analysis"]["ready_queue_enabled"] is True
    assert outcome.result_summary_obj["algo"]["graph_analysis"]["score_enabled"] is True
    assert outcome.result_summary_obj["algo"]["graph_analysis"]["score_metric_status"] == "available"
    assert outcome.validated_schedule_payload.scheduled_op_ids == {2}
    assert [row.op_id for row in outcome.validated_schedule_payload.schedule_rows] == [2]


def test_on_dag_score_context_uses_single_full_metrics_pass(monkeypatch: Any) -> None:
    from core.services.scheduler.graph.analysis_service import ScheduleGraphAnalysisService

    calls: List[str] = []
    original = ScheduleGraphAnalysisService.analyze_linear_batches

    def _wrapped(self: Any, nodes: Any, *, metrics_mode: str = "full") -> Any:
        calls.append(metrics_mode)
        return original(self, nodes, metrics_mode=metrics_mode)

    monkeypatch.setattr(ScheduleGraphAnalysisService, "analyze_linear_batches", _wrapped)

    preparation = prepare_schedule_graph_for_dispatch(_schedule_input("on"))  # type: ignore[arg-type]

    assert calls == ["full"]
    assert preparation.graph_ready_context is not None
    assert preparation.graph_ready_context["score_enabled"] is True
    assert preparation.graph_analysis_public is not None
    assert preparation.graph_analysis_public["score_enabled"] is True
    assert preparation.graph_analysis_diagnostics is not None
    assert preparation.graph_analysis_diagnostics["node_metrics_status"] == "available"
    assert "graph_score_sample" in preparation.graph_analysis_diagnostics


def test_on_dag_zero_graph_weights_keep_ready_queue_but_disable_scoring(monkeypatch: Any) -> None:
    from core.services.scheduler.graph.analysis_service import ScheduleGraphAnalysisService

    calls: List[str] = []
    original = ScheduleGraphAnalysisService.analyze_linear_batches

    def _wrapped(self: Any, nodes: Any, *, metrics_mode: str = "full") -> Any:
        calls.append(metrics_mode)
        return original(self, nodes, metrics_mode=metrics_mode)

    schedule_input = _schedule_input("on")
    schedule_input.cfg.graph_critical_weight = 0
    schedule_input.cfg.graph_impact_weight = 0
    schedule_input.cfg.graph_downstream_weight = 0
    monkeypatch.setattr(ScheduleGraphAnalysisService, "analyze_linear_batches", _wrapped)

    preparation = prepare_schedule_graph_for_dispatch(schedule_input)  # type: ignore[arg-type]

    assert calls == ["basic"]
    assert preparation.graph_ready_context is not None
    assert preparation.graph_ready_context["score_enabled"] is False
    assert "graph_priority_key_by_op_id" not in preparation.graph_ready_context
    assert preparation.graph_analysis_public is not None
    assert preparation.graph_analysis_public["ready_queue_enabled"] is True
    assert preparation.graph_analysis_public["score_enabled"] is False
    assert preparation.graph_analysis_public["score_metric_status"] == "disabled"
    assert preparation.graph_analysis_public["score_disabled_reason"] == "score_weights_zero"
    assert preparation.graph_analysis_diagnostics is not None
    assert preparation.graph_analysis_diagnostics["node_metrics_status"] == "skipped_basic_report"


def test_on_dag_bad_ready_edge_endpoint_reports_graph_input_contract_error(monkeypatch: Any) -> None:
    from core.services.scheduler.graph import precedence_builder
    from core.services.scheduler.graph.types import OperationGraphEdge

    def _bad_edges(nodes: Any) -> List[OperationGraphEdge]:
        return [OperationGraphEdge(from_node_id="unknown-node", to_node_id=str(nodes[0].node_id))]

    monkeypatch.setattr(precedence_builder, "build_linear_edges_by_batch", _bad_edges)

    with pytest.raises(ValidationError) as exc_info:
        prepare_schedule_graph_for_dispatch(_schedule_input("on"))  # type: ignore[arg-type]

    assert exc_info.value.field == "graph_input_contract_error"
    details = exc_info.value.details
    assert details is not None
    assert details["reason"] == "graph_input_contract_error"
    assert details["status"] == "input_error"
    assert "工序图增强无法启用" in str(exc_info.value)


def test_on_cycle_block_no_uses_real_optimizer_sgs_override(cycle_graph: None) -> None:
    calls: Dict[str, Any] = {}
    schedule_input = _schedule_input("on")
    schedule_input.cfg = _cfg(dispatch_mode="batch_order")
    schedule_input.cfg.graph_block_on_cycle = "no"
    schedule_input.cfg_svc = _cfg_svc()
    schedule_input.seed_results = [
        {
            "op_id": 1,
            "op_code": "OP-B001-010",
            "batch_id": "B001",
            "seq": 10,
            "machine_id": "MC001",
            "operator_id": "OP001",
            "start_time": _make_dt(-1),
            "end_time": _make_dt(0),
            "source": "internal",
            "op_type_name": "车削",
        }
    ]

    class Scheduler:
        _last_algo_stats = {"fallback_counts": {}, "param_fallbacks": {}}

        def schedule(self, **kwargs: Any) -> Tuple[List[Any], Any, Any, Dict[str, Any]]:
            calls["scheduler_graph_ready_context"] = kwargs.get("graph_ready_context")
            calls["scheduler_dispatch_mode"] = kwargs.get("dispatch_mode")
            summary = SimpleNamespace(success=True, total_ops=1, scheduled_ops=1, failed_ops=0, warnings=[], errors=[])
            return [_optimizer_outcome().results[0]], summary, kwargs.get("strategy"), dict(kwargs.get("strategy_params") or {})

    def _keep_best(**kwargs: Any) -> Any:
        if "dispatch_modes" in kwargs:
            calls["multi_start_dispatch_modes"] = list(kwargs.get("dispatch_modes") or [])
        if "dispatch_mode_cfg" in kwargs:
            calls.setdefault("dispatch_mode_cfg_values", []).append(kwargs.get("dispatch_mode_cfg"))
        return kwargs.get("best")

    runtime = OptimizerRuntime(
        scheduler_factory=lambda **_kwargs: Scheduler(),
        clock=lambda: 1000.0,
        rng_factory=lambda _seed: None,
        run_ortools_warmstart=_keep_best,
        run_multi_start=_keep_best,
        run_local_search=_keep_best,
    )

    outcome = orchestrate_schedule_run(
        _Svc(),
        schedule_input=schedule_input,  # type: ignore[arg-type]
        simulate=True,
        strict_mode=True,
        optimize_schedule_fn=lambda **kwargs: optimize_schedule(**kwargs, _runtime=runtime),
        build_result_summary_fn=_summary_from_ctx,
    )

    graph_analysis = outcome.result_summary_obj["algo"]["graph_analysis"]
    assert graph_analysis["effective_mode"] == "sgs_without_graph_ready_queue"
    assert graph_analysis["ready_queue_enabled"] is False
    assert graph_analysis["graph_enhancement_disabled_reason"] == "schedule_graph_cycle"
    assert graph_analysis["score_enabled"] is False
    assert graph_analysis["score_metric_status"] == "disabled"
    assert graph_analysis["score_disabled_reason"] == "schedule_graph_cycle"
    assert calls["scheduler_graph_ready_context"] is None
    assert calls["scheduler_dispatch_mode"] == "sgs"
    assert calls["multi_start_dispatch_modes"] == ["sgs"]
    assert calls["dispatch_mode_cfg_values"] == ["batch_order", "batch_order"] + ["sgs"] * 10


def test_report_mode_does_not_prepare_graph_ready_context() -> None:
    preparation = prepare_schedule_graph_for_dispatch(_schedule_input("report"))  # type: ignore[arg-type]

    assert preparation.graph_analysis_public is not None
    assert preparation.graph_ready_context is None
    assert preparation.graph_dispatch_mode_override is None


def test_optimizer_passes_graph_ready_context_to_runtime_steps_and_fallback_scheduler() -> None:
    calls: Dict[str, Any] = {}
    graph_ready_context = {"enabled": True, "schedulable_op_ids": {2}}

    class Scheduler:
        _last_algo_stats = {"fallback_counts": {}, "param_fallbacks": {}}

        def schedule(self, **kwargs: Any) -> Tuple[List[Any], Any, Any, Dict[str, Any]]:
            calls["scheduler_graph_ready_context"] = kwargs.get("graph_ready_context")
            calls["scheduler_dispatch_mode"] = kwargs.get("dispatch_mode")
            summary = SimpleNamespace(success=True, total_ops=0, scheduled_ops=0, failed_ops=0, warnings=[], errors=[])
            return [], summary, kwargs.get("strategy"), dict(kwargs.get("strategy_params") or {})

    def _step(name: str):
        def _inner(**kwargs: Any) -> Any:
            calls[name] = kwargs.get("graph_ready_context")
            if name == "multi_start":
                calls["multi_start_dispatch_modes"] = list(kwargs.get("dispatch_modes") or [])
            if name in ("ortools", "local_search"):
                calls[f"{name}_dispatch_mode"] = kwargs.get("dispatch_mode_cfg")
            return kwargs.get("best")

        return _inner

    runtime = OptimizerRuntime(
        scheduler_factory=lambda **_kwargs: Scheduler(),
        clock=lambda: 1000.0,
        rng_factory=lambda _seed: None,
        run_ortools_warmstart=_step("ortools"),
        run_multi_start=_step("multi_start"),
        run_local_search=_step("local_search"),
    )

    optimize_schedule(
        calendar_service=SimpleNamespace(),
        cfg_svc=_cfg_svc(),
        cfg=_cfg(dispatch_mode="batch_order"),
        algo_ops_to_schedule=[],
        batches={},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        end_date=None,
        downtime_map={},
        seed_results=[],
        resource_pool=None,
        version=1,
        logger=None,
        strict_mode=True,
        graph_ready_context=graph_ready_context,
        _runtime=runtime,
    )

    assert calls["ortools"] is graph_ready_context
    assert calls["multi_start"] is graph_ready_context
    assert calls["local_search"] is graph_ready_context
    assert calls["scheduler_graph_ready_context"] is graph_ready_context
    assert calls["ortools_dispatch_mode"] == "sgs"
    assert calls["multi_start_dispatch_modes"] == ["sgs"]
    assert calls["local_search_dispatch_mode"] == "sgs"
    assert calls["scheduler_dispatch_mode"] == "sgs"


def test_optimizer_dispatch_override_uses_sgs_without_graph_ready_context() -> None:
    calls: Dict[str, Any] = {}

    class Scheduler:
        _last_algo_stats = {"fallback_counts": {}, "param_fallbacks": {}}

        def schedule(self, **kwargs: Any) -> Tuple[List[Any], Any, Any, Dict[str, Any]]:
            calls["scheduler_graph_ready_context"] = kwargs.get("graph_ready_context")
            calls["scheduler_dispatch_mode"] = kwargs.get("dispatch_mode")
            summary = SimpleNamespace(success=True, total_ops=0, scheduled_ops=0, failed_ops=0, warnings=[], errors=[])
            return [], summary, kwargs.get("strategy"), dict(kwargs.get("strategy_params") or {})

    def _step(name: str):
        def _inner(**kwargs: Any) -> Any:
            calls[name] = kwargs.get("graph_ready_context")
            if name == "multi_start":
                calls["multi_start_dispatch_modes"] = list(kwargs.get("dispatch_modes") or [])
            if name in ("ortools", "local_search"):
                calls[f"{name}_dispatch_mode"] = kwargs.get("dispatch_mode_cfg")
            return kwargs.get("best")

        return _inner

    runtime = OptimizerRuntime(
        scheduler_factory=lambda **_kwargs: Scheduler(),
        clock=lambda: 1000.0,
        rng_factory=lambda _seed: None,
        run_ortools_warmstart=_step("ortools"),
        run_multi_start=_step("multi_start"),
        run_local_search=_step("local_search"),
    )

    optimize_schedule(
        calendar_service=SimpleNamespace(),
        cfg_svc=_cfg_svc(),
        cfg=_cfg(dispatch_mode="batch_order"),
        algo_ops_to_schedule=[],
        batches={},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        end_date=None,
        downtime_map={},
        seed_results=[],
        resource_pool=None,
        version=1,
        logger=None,
        strict_mode=True,
        graph_ready_context=None,
        graph_dispatch_mode_override="sgs",
        _runtime=runtime,
    )

    assert calls["ortools"] is None
    assert calls["multi_start"] is None
    assert calls["local_search"] is None
    assert calls["scheduler_graph_ready_context"] is None
    assert calls["ortools_dispatch_mode"] == "sgs"
    assert calls["multi_start_dispatch_modes"] == ["sgs"]
    assert calls["local_search_dispatch_mode"] == "sgs"
    assert calls["scheduler_dispatch_mode"] == "sgs"


def test_optimizer_rejects_unknown_graph_dispatch_override() -> None:
    with pytest.raises(ValidationError) as exc_info:
        optimize_schedule(
            calendar_service=SimpleNamespace(),
            cfg_svc=_cfg_svc(),
            cfg=_cfg(dispatch_mode="batch_order"),
            algo_ops_to_schedule=[],
            batches={},
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            end_date=None,
            downtime_map={},
            seed_results=[],
            resource_pool=None,
            version=1,
            logger=None,
            strict_mode=True,
            graph_ready_context=None,
            graph_dispatch_mode_override="batch_order",
        )

    assert exc_info.value.field == "graph_dispatch_mode_override"


def test_greedy_scheduler_rejects_graph_ready_context_without_sgs_dispatch_mode() -> None:
    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": {1},
        "fixed_op_ids": set(),
        "predecessor_op_ids_by_op_id": {1: set()},
        "successor_op_ids_by_op_id": {1: set()},
        "sort_key_by_op_id": {1: (0, 10, 1)},
    }

    with pytest.raises(ValidationError) as exc_info:
        GreedyScheduler(_Calendar()).schedule(
            operations=[_op(1, "B1", 10)],
            batches={"B1": SimpleNamespace(batch_id="B1", quantity=1, due_date="2026-01-02", priority="normal")},
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            dispatch_mode="batch_order",
            graph_ready_context=graph_ready_context,
        )

    assert exc_info.value.field == "graph_ready_context"
    assert "SGS" in exc_info.value.message


def test_sgs_uses_graph_ready_context_as_candidate_qualification() -> None:
    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    batches = {
        "B1": SimpleNamespace(batch_id="B1", quantity=1, due_date="2026-01-02", priority="normal"),
        "B2": SimpleNamespace(batch_id="B2", quantity=1, due_date="2026-01-02", priority="normal"),
    }
    operations = [_op(1, "B1", 10), _op(2, "B2", 10)]
    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": {1, 2},
        "fixed_op_ids": set(),
        "predecessor_op_ids_by_op_id": {1: set(), 2: {1}},
        "successor_op_ids_by_op_id": {1: {2}, 2: set()},
        "sort_key_by_op_id": {1: (1, 10, 1), 2: (0, 10, 2)},
    }

    baseline_results, baseline_summary, _strategy, _params = GreedyScheduler(_Calendar()).schedule(
        operations=operations,
        batches=batches,
        start_dt=start_dt,
        dispatch_mode="sgs",
        dispatch_rule="slack",
        batch_order_override=["B2", "B1"],
    )
    graph_results, graph_summary, _strategy, _params = GreedyScheduler(_Calendar()).schedule(
        operations=operations,
        batches=batches,
        start_dt=start_dt,
        dispatch_mode="sgs",
        dispatch_rule="slack",
        batch_order_override=["B2", "B1"],
        graph_ready_context=graph_ready_context,
    )

    assert baseline_summary.failed_ops == 0
    assert graph_summary.failed_ops == 0
    assert [result.op_id for result in baseline_results] == [2, 1]
    assert [result.op_id for result in graph_results] == [1, 2]


def test_on_dag_graph_score_makes_longer_critical_chain_candidate_first() -> None:
    schedule_input = _chain_schedule_input()
    preparation = prepare_schedule_graph_for_dispatch(schedule_input)  # type: ignore[arg-type]

    baseline_results, baseline_summary, _strategy, _params = GreedyScheduler(_Calendar()).schedule(
        operations=schedule_input.algo_ops_to_schedule,
        batches=schedule_input.batches,
        start_dt=schedule_input.start_dt_norm,
        dispatch_mode="sgs",
        dispatch_rule="slack",
        batch_order_override=["B_A", "B_B"],
    )
    graph_results, graph_summary, _strategy, _params = GreedyScheduler(_Calendar()).schedule(
        operations=schedule_input.algo_ops_to_schedule,
        batches=schedule_input.batches,
        start_dt=schedule_input.start_dt_norm,
        dispatch_mode="sgs",
        dispatch_rule="slack",
        batch_order_override=["B_A", "B_B"],
        graph_ready_context=preparation.graph_ready_context,
    )

    assert baseline_summary.failed_ops == 0
    assert graph_summary.failed_ops == 0
    assert baseline_results[0].op_id == 1
    assert graph_results[0].op_id == 3
    assert preparation.graph_ready_context is not None
    assert preparation.graph_ready_context["graph_priority_key_by_op_id"][3] < preparation.graph_ready_context["graph_priority_key_by_op_id"][1]


@pytest.mark.parametrize(
    ("graph_priority_key_by_op_id", "expected_first_op_id"),
    [
        ({1: (0.0, 1_000_000_000.0), 2: (-500.0, 0.0)}, 2),
        ({1: (-10.0, 1_000_000_000.0), 2: (-30.0, 1_000_000_000.0)}, 2),
        ({1: (-20.0, 1_000_000_000.0), 2: (-120.0, 1_000_000_000.0)}, 2),
    ],
)
@pytest.mark.parametrize("dispatch_rule", ["slack", "cr", "atc"])
def test_sgs_graph_score_component_orders_ready_candidates_without_reversing_dispatch_rules(
    graph_priority_key_by_op_id: Dict[int, Tuple[float, ...]],
    expected_first_op_id: int,
    dispatch_rule: str,
) -> None:
    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": {1, 2},
        "fixed_op_ids": set(),
        "predecessor_op_ids_by_op_id": {1: set(), 2: set()},
        "successor_op_ids_by_op_id": {1: set(), 2: set()},
        "sort_key_by_op_id": {1: (0, 10, 1), 2: (1, 10, 2)},
        "score_enabled": True,
        "graph_priority_key_by_op_id": graph_priority_key_by_op_id,
    }

    results, summary, _strategy, _params = GreedyScheduler(_Calendar()).schedule(
        operations=[_op(1, "B1", 10), _op(2, "B2", 10)],
        batches={
            "B1": SimpleNamespace(batch_id="B1", quantity=1, due_date="2026-01-02", priority="normal"),
            "B2": SimpleNamespace(batch_id="B2", quantity=1, due_date="2026-01-02", priority="normal"),
        },
        start_dt=start_dt,
        dispatch_mode="sgs",
        dispatch_rule=dispatch_rule,
        batch_order_override=["B1", "B2"],
        graph_ready_context=graph_ready_context,
    )

    assert summary.failed_ops == 0
    assert results[0].op_id == expected_first_op_id


def test_sgs_graph_score_missing_candidate_key_is_contract_error() -> None:
    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": {1, 2},
        "fixed_op_ids": set(),
        "predecessor_op_ids_by_op_id": {1: set(), 2: set()},
        "successor_op_ids_by_op_id": {1: set(), 2: set()},
        "sort_key_by_op_id": {1: (0, 10, 1), 2: (1, 10, 2)},
        "score_enabled": True,
        "graph_priority_key_by_op_id": {1: (0.0, 0.0)},
    }

    with pytest.raises(ValidationError) as exc_info:
        GreedyScheduler(_Calendar()).schedule(
            operations=[_op(1, "B1", 10), _op(2, "B2", 10)],
            batches={
                "B1": SimpleNamespace(batch_id="B1", quantity=1, due_date="2026-01-02", priority="normal"),
                "B2": SimpleNamespace(batch_id="B2", quantity=1, due_date="2026-01-02", priority="normal"),
            },
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            dispatch_mode="sgs",
            dispatch_rule="slack",
            graph_ready_context=graph_ready_context,
        )

    assert exc_info.value.field == "graph_ready_context"
    assert "评分 key" in exc_info.value.message


def test_sgs_graph_ready_context_treats_seed_as_fixed_predecessor_without_rescheduling_it() -> None:
    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    seed = ScheduleResult(
        op_id=1,
        op_code="OP-B1-010",
        batch_id="B1",
        seq=10,
        machine_id="MC001",
        operator_id="OP001",
        start_time=start_dt,
        end_time=start_dt + timedelta(hours=1),
        source="internal",
        op_type_name="车削",
    )
    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": {2},
        "fixed_op_ids": {1},
        "predecessor_op_ids_by_op_id": {1: set(), 2: {1}},
        "successor_op_ids_by_op_id": {1: {2}, 2: set()},
        "sort_key_by_op_id": {2: (0, 20, 2)},
    }

    results, summary, _strategy, _params = GreedyScheduler(_Calendar()).schedule(
        operations=[_op(2, "B1", 20)],
        batches={"B1": SimpleNamespace(batch_id="B1", quantity=1, due_date="2026-01-02", priority="normal")},
        start_dt=start_dt,
        dispatch_mode="sgs",
        dispatch_rule="slack",
        seed_results=[seed],
        graph_ready_context=graph_ready_context,
    )

    assert summary.failed_ops == 0
    assert [result.op_id for result in results] == [1, 2]
    assert [result.op_id for result in results].count(1) == 1


def test_sgs_graph_ready_context_does_not_release_successor_after_blocked_failure() -> None:
    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    blocking_op = _op(1, "B1", 10)
    blocking_op.setup_hours = 48.0
    successor_op = _op(2, "B2", 10)
    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": {1, 2},
        "fixed_op_ids": set(),
        "predecessor_op_ids_by_op_id": {1: set(), 2: {1}},
        "successor_op_ids_by_op_id": {1: {2}, 2: set()},
        "sort_key_by_op_id": {1: (0, 10, 1), 2: (1, 10, 2)},
    }

    results, summary, _strategy, _params = GreedyScheduler(_Calendar()).schedule(
        operations=[blocking_op, successor_op],
        batches={
            "B1": SimpleNamespace(batch_id="B1", quantity=1, due_date="2026-01-02", priority="normal"),
            "B2": SimpleNamespace(batch_id="B2", quantity=1, due_date="2026-01-02", priority="normal"),
        },
        start_dt=start_dt,
        end_date="2026-01-01",
        dispatch_mode="sgs",
        dispatch_rule="slack",
        graph_ready_context=graph_ready_context,
    )

    assert results == []
    assert summary.failed_ops == 2
    assert any("OP-B2-010" in error and "OP-B1-010" in error and "本次跳过" in error for error in summary.errors)


def test_sgs_graph_ready_context_uses_normalized_successor_map_for_blocking() -> None:
    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    blocking_op = _op(1, "B1", 10)
    blocking_op.setup_hours = 48.0
    successor_op = _op(2, "B2", 10)
    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": {1, 2},
        "fixed_op_ids": set(),
        "predecessor_op_ids_by_op_id": {"1": set(), "2": {"1"}},
        "successor_op_ids_by_op_id": {"1": {"2"}, "2": set()},
        "sort_key_by_op_id": {1: (0, 10, 1), 2: (1, 10, 2)},
    }

    results, summary, _strategy, _params = GreedyScheduler(_Calendar()).schedule(
        operations=[blocking_op, successor_op],
        batches={
            "B1": SimpleNamespace(batch_id="B1", quantity=1, due_date="2026-01-02", priority="normal"),
            "B2": SimpleNamespace(batch_id="B2", quantity=1, due_date="2026-01-02", priority="normal"),
        },
        start_dt=start_dt,
        end_date="2026-01-01",
        dispatch_mode="sgs",
        dispatch_rule="slack",
        graph_ready_context=graph_ready_context,
    )

    assert results == []
    assert summary.failed_ops == 2
    assert any("OP-B2-010" in error and "OP-B1-010" in error and "本次跳过" in error for error in summary.errors)


@pytest.mark.parametrize("field", ["schedulable_op_ids", "fixed_op_ids"])
def test_sgs_graph_ready_context_rejects_graph_like_op_id_collections(field: str) -> None:
    class GraphLike:
        def nodes(self) -> List[int]:
            return [1]

        def edges(self) -> List[Tuple[int, int]]:
            return []

    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": {1},
        "fixed_op_ids": set(),
        "predecessor_op_ids_by_op_id": {1: set()},
        "successor_op_ids_by_op_id": {1: set()},
        "sort_key_by_op_id": {1: (0, 10, 1)},
    }
    graph_ready_context[field] = GraphLike()

    with pytest.raises(ValidationError) as exc_info:
        GreedyScheduler(_Calendar()).schedule(
            operations=[_op(1, "B1", 10)],
            batches={"B1": SimpleNamespace(batch_id="B1", quantity=1, due_date="2026-01-02", priority="normal")},
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            dispatch_mode="sgs",
            dispatch_rule="slack",
            graph_ready_context=graph_ready_context,
        )

    assert exc_info.value.field == "graph_ready_context"
    assert field in exc_info.value.message
    assert "不能传图对象" in exc_info.value.message


@pytest.mark.parametrize(
    ("field", "op_id"),
    [
        ("predecessor_op_ids_by_op_id", 2),
        ("successor_op_ids_by_op_id", 1),
    ],
)
def test_sgs_graph_ready_context_rejects_graph_like_link_collections(field: str, op_id: int) -> None:
    class GraphLike:
        nodes = (1, 2)
        edges = ()

        def __iter__(self):
            return iter(self.nodes)

    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": {1, 2},
        "fixed_op_ids": set(),
        "predecessor_op_ids_by_op_id": {1: set(), 2: {1}},
        "successor_op_ids_by_op_id": {1: {2}, 2: set()},
        "sort_key_by_op_id": {1: (0, 10, 1), 2: (0, 20, 2)},
    }
    graph_ready_context[field] = dict(graph_ready_context[field])
    graph_ready_context[field][op_id] = GraphLike()

    with pytest.raises(ValidationError) as exc_info:
        GreedyScheduler(_Calendar()).schedule(
            operations=[_op(1, "B1", 10), _op(2, "B1", 20)],
            batches={"B1": SimpleNamespace(batch_id="B1", quantity=1, due_date="2026-01-02", priority="normal")},
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            dispatch_mode="sgs",
            dispatch_rule="slack",
            graph_ready_context=graph_ready_context,
        )

    assert exc_info.value.field == "graph_ready_context"
    assert field in exc_info.value.message
    assert "不能传图对象" in exc_info.value.message


@pytest.mark.parametrize("raw_sort_key", ["1", True])
def test_sgs_graph_ready_context_keeps_sort_key_op_id_keys_strict(raw_sort_key: Any) -> None:
    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": {1},
        "fixed_op_ids": set(),
        "predecessor_op_ids_by_op_id": {1: set()},
        "successor_op_ids_by_op_id": {1: set()},
        "sort_key_by_op_id": {raw_sort_key: (0, 10, 1)},
    }

    with pytest.raises(ValidationError) as exc_info:
        GreedyScheduler(_Calendar()).schedule(
            operations=[_op(1, "B1", 10)],
            batches={"B1": SimpleNamespace(batch_id="B1", quantity=1, due_date="2026-01-02", priority="normal")},
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            dispatch_mode="sgs",
            dispatch_rule="slack",
            graph_ready_context=graph_ready_context,
        )

    assert exc_info.value.field == "graph_ready_context"
    assert "sort_key_by_op_id" in exc_info.value.message
    assert "正整数 op_id" in exc_info.value.message


@pytest.mark.parametrize("raw_sort_key_value", ["bad", 1.9, True])
def test_sgs_graph_ready_context_keeps_sort_key_values_strict(raw_sort_key_value: Any) -> None:
    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": {1},
        "fixed_op_ids": set(),
        "predecessor_op_ids_by_op_id": {1: set()},
        "successor_op_ids_by_op_id": {1: set()},
        "sort_key_by_op_id": {1: (0, 10, raw_sort_key_value)},
    }

    with pytest.raises(ValidationError) as exc_info:
        GreedyScheduler(_Calendar()).schedule(
            operations=[_op(1, "B1", 10)],
            batches={"B1": SimpleNamespace(batch_id="B1", quantity=1, due_date="2026-01-02", priority="normal")},
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            dispatch_mode="sgs",
            dispatch_rule="slack",
            graph_ready_context=graph_ready_context,
        )

    assert exc_info.value.field == "graph_ready_context"
    assert "排序 key 必须只包含整数" in exc_info.value.message


def test_sgs_graph_ready_context_accepts_integer_text_sort_key_values() -> None:
    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": {1},
        "fixed_op_ids": set(),
        "predecessor_op_ids_by_op_id": {1: set()},
        "successor_op_ids_by_op_id": {1: set()},
        "sort_key_by_op_id": {1: (0, "10", 1)},
    }

    results, summary, _strategy, _params = GreedyScheduler(_Calendar()).schedule(
        operations=[_op(1, "B1", 10)],
        batches={"B1": SimpleNamespace(batch_id="B1", quantity=1, due_date="2026-01-02", priority="normal")},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        dispatch_mode="sgs",
        dispatch_rule="slack",
        graph_ready_context=graph_ready_context,
    )

    assert summary.failed_ops == 0
    assert [result.op_id for result in results] == [1]


def test_sgs_graph_ready_context_does_not_double_count_same_batch_blocked_successor() -> None:
    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    blocking_op = _op(1, "B1", 10)
    blocking_op.setup_hours = 48.0
    successor_op = _op(2, "B1", 20)
    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": {1, 2},
        "fixed_op_ids": set(),
        "predecessor_op_ids_by_op_id": {1: set(), 2: {1}},
        "successor_op_ids_by_op_id": {1: {2}, 2: set()},
        "sort_key_by_op_id": {1: (0, 10, 1), 2: (0, 20, 2)},
    }

    results, summary, _strategy, _params = GreedyScheduler(_Calendar()).schedule(
        operations=[blocking_op, successor_op],
        batches={"B1": SimpleNamespace(batch_id="B1", quantity=1, due_date="2026-01-02", priority="normal")},
        start_dt=start_dt,
        end_date="2026-01-01",
        dispatch_mode="sgs",
        dispatch_rule="slack",
        graph_ready_context=graph_ready_context,
    )

    assert results == []
    assert summary.failed_ops == 2
    assert any("OP-B1-020" in error and "OP-B1-010" in error and "本次跳过" in error for error in summary.errors)


def test_sgs_graph_ready_context_exits_when_remaining_ready_ops_are_batch_blocked() -> None:
    start_dt = datetime(2026, 1, 1, 8, 0, 0)
    blocking_op = _op(1, "B1", 10)
    blocking_op.setup_hours = 48.0
    independent_same_batch_op = _op(2, "B1", 20)
    independent_same_batch_op.setup_hours = 48.0
    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": {1, 2},
        "fixed_op_ids": set(),
        "predecessor_op_ids_by_op_id": {1: set(), 2: set()},
        "successor_op_ids_by_op_id": {1: set(), 2: set()},
        "sort_key_by_op_id": {1: (0, 10, 1), 2: (0, 20, 2)},
    }

    results, summary, _strategy, _params = GreedyScheduler(_Calendar()).schedule(
        operations=[blocking_op, independent_same_batch_op],
        batches={"B1": SimpleNamespace(batch_id="B1", quantity=1, due_date="2026-01-02", priority="normal")},
        start_dt=start_dt,
        end_date="2026-01-01",
        dispatch_mode="sgs",
        dispatch_rule="slack",
        graph_ready_context=graph_ready_context,
    )

    assert results == []
    assert summary.failed_ops == 2


def test_sgs_graph_ready_context_rejects_mismatched_successor_map() -> None:
    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": {1, 2},
        "fixed_op_ids": set(),
        "predecessor_op_ids_by_op_id": {1: set(), 2: set()},
        "successor_op_ids_by_op_id": {1: {2}, 2: set()},
        "sort_key_by_op_id": {1: (0, 10, 1), 2: (1, 10, 2)},
    }

    with pytest.raises(ValidationError) as exc_info:
        GreedyScheduler(_Calendar()).schedule(
            operations=[_op(1, "B1", 10), _op(2, "B2", 10)],
            batches={
                "B1": SimpleNamespace(batch_id="B1", quantity=1, due_date="2026-01-02", priority="normal"),
                "B2": SimpleNamespace(batch_id="B2", quantity=1, due_date="2026-01-02", priority="normal"),
            },
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            dispatch_mode="sgs",
            dispatch_rule="slack",
            graph_ready_context=graph_ready_context,
        )

    assert exc_info.value.field == "graph_ready_context"
    assert "后继 2" in exc_info.value.message
