from __future__ import annotations

import ast
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
REFACTORED_ALGORITHM_FILES = (
    "core/algorithms/ordering.py",
    "core/algorithms/greedy/scheduler.py",
    "core/algorithms/greedy/run_context.py",
    "core/algorithms/greedy/run_state.py",
    "core/algorithms/greedy/internal_slot.py",
    "core/algorithms/greedy/internal_operation.py",
    "core/algorithms/greedy/auto_assign.py",
    "core/algorithms/greedy/seed.py",
    "core/algorithms/greedy/dispatch/batch_order.py",
    "core/algorithms/greedy/dispatch/sgs.py",
    "core/algorithms/greedy/dispatch/sgs_scoring.py",
)


def _module_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _function_span(relative_path: str, function_name: str) -> int:
    tree = ast.parse(_module_text(relative_path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            assert node.end_lineno is not None
            return int(node.end_lineno) - int(node.lineno) + 1
    raise AssertionError(f"未找到函数 {function_name} in {relative_path}")


def _line_count(relative_path: str) -> int:
    return len(_module_text(relative_path).splitlines())


def _complexity_violations(relative_paths: tuple[str, ...], *, threshold: int) -> list[str]:
    from radon.complexity import cc_visit

    violations = []
    for relative_path in relative_paths:
        for block in cc_visit(_module_text(relative_path)):
            if block.complexity > threshold:
                violations.append(f"{relative_path}:{block.lineno} {block.name} complexity={block.complexity}")
    return violations


def test_optimizer_uses_ordering_contract_instead_of_scheduler_helpers() -> None:
    text = _module_text("core/services/scheduler/run/schedule_optimizer.py")

    assert "from core.algorithms.ordering import build_batch_sort_inputs, build_normalized_batches_map" in text
    assert "from core.algorithms.greedy.scheduler import build_batch_sort_inputs" not in text
    assert "from core.algorithms.greedy.scheduler import build_normalized_batches_map" not in text


def test_scheduler_keeps_legacy_ordering_helper_export() -> None:
    from core.algorithms.greedy.scheduler import resolve_batch_sort_batch_id

    batch = SimpleNamespace(batch_id="B-FIELD")

    assert resolve_batch_sort_batch_id("", batch) == "B-FIELD"
    assert resolve_batch_sort_batch_id("B-KEY", batch) == "B-KEY"


def test_dispatch_modules_do_not_call_scheduler_private_callbacks() -> None:
    batch_order = _module_text("core/algorithms/greedy/dispatch/batch_order.py")
    sgs = _module_text("core/algorithms/greedy/dispatch/sgs.py")

    for text in (batch_order, sgs):
        assert "._schedule_internal" not in text
        assert "._schedule_external" not in text
        assert "scheduler.logger" not in text
        assert "scheduler.calendar" not in text


def test_refactored_files_and_entry_functions_stay_under_quality_gate() -> None:
    for relative_path in REFACTORED_ALGORITHM_FILES:
        assert _line_count(relative_path) < 500

    limits = {
        ("core/algorithms/greedy/scheduler.py", "schedule"): 80,
        ("core/algorithms/greedy/scheduler.py", "_schedule_internal"): 80,
        ("core/algorithms/greedy/dispatch/sgs.py", "dispatch_sgs"): 80,
        ("core/algorithms/greedy/dispatch/sgs.py", "_score_internal_candidate"): 80,
        ("core/algorithms/greedy/auto_assign.py", "auto_assign_internal_resources"): 80,
        ("core/algorithms/greedy/seed.py", "normalize_seed_results"): 80,
    }
    for (relative_path, function_name), max_lines in limits.items():
        assert _function_span(relative_path, function_name) <= max_lines


def test_refactored_algorithm_files_stay_under_complexity_threshold() -> None:
    assert _complexity_violations(REFACTORED_ALGORITHM_FILES, threshold=15) == []


class _Calendar:
    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id=None) -> datetime:
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id=None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, machine_id=None, operator_id=None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float, machine_id=None, operator_id=None) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


def _default_config() -> SimpleNamespace:
    from core.services.scheduler.config.config_field_spec import default_snapshot_values

    return SimpleNamespace(**default_snapshot_values())


def test_scheduler_schedule_still_uses_legacy_internal_callback() -> None:
    from core.algorithms.greedy.scheduler import GreedyScheduler
    from core.algorithms.types import ScheduleResult

    class CallbackScheduler(GreedyScheduler):
        def __init__(self) -> None:
            super().__init__(calendar_service=_Calendar(), config_service=_default_config())
            self.override_called = False

        def _schedule_internal(self, op, batch, batch_progress, machine_timeline, operator_timeline, base_time, errors, end_dt_exclusive, machine_downtimes=None, **kwargs):
            self.override_called = True
            return (
                ScheduleResult(
                    op_id=99,
                    op_code="OVERRIDE",
                    batch_id="B1",
                    seq=1,
                    machine_id="MX",
                    operator_id="OX",
                    start_time=base_time,
                    end_time=base_time + timedelta(hours=1),
                    source="internal",
                ),
                False,
            )

    batch = SimpleNamespace(batch_id="B1", priority="normal", due_date=None, ready_date=None, created_at=None, quantity=1)
    op = SimpleNamespace(
        id=1,
        op_code="OP1",
        batch_id="B1",
        seq=1,
        source="internal",
        machine_id="M1",
        operator_id="O1",
        setup_hours=1.0,
        unit_hours=0.0,
        op_type_name="Cut",
    )

    scheduler = CallbackScheduler()
    results, summary, _strategy, _params = scheduler.schedule(
        operations=[op],
        batches={"B1": batch},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        dispatch_mode="batch_order",
    )

    assert scheduler.override_called is True
    assert [(result.op_id, result.op_code, result.machine_id, result.operator_id) for result in results] == [(99, "OVERRIDE", "MX", "OX")]
    assert summary.scheduled_ops == 1


def test_legacy_direct_dispatch_keeps_empty_state_containers_in_place() -> None:
    from core.algorithms.dispatch_rules import DispatchRule
    from core.algorithms.greedy.dispatch.batch_order import dispatch_batch_order
    from core.algorithms.greedy.dispatch.sgs import dispatch_sgs
    from core.algorithms.types import ScheduleResult

    class LegacyScheduler:
        calendar = _Calendar()
        logger = SimpleNamespace(exception=lambda *args, **kwargs: None)
        _last_algo_stats = {"fallback_counts": {}, "param_fallbacks": {}, "fallback_samples": {}}

        def _schedule_internal(self, op, batch, batch_progress, machine_timeline, operator_timeline, base_time, errors, end_dt_exclusive, machine_downtimes=None, **kwargs):
            start = batch_progress.get("B1", base_time)
            end = start + timedelta(hours=1)
            machine_timeline.setdefault("M1", []).append((start, end))
            operator_timeline.setdefault("O1", []).append((start, end))
            return (
                ScheduleResult(
                    op_id=1,
                    op_code="OP1",
                    batch_id="B1",
                    seq=1,
                    machine_id="M1",
                    operator_id="O1",
                    start_time=start,
                    end_time=end,
                    source="internal",
                    op_type_name="Cut",
                ),
                False,
            )

    base_time = datetime(2026, 1, 1, 8, 0, 0)
    op = SimpleNamespace(id=1, op_code="OP1", batch_id="B1", seq=1, source="internal", machine_id="M1", operator_id="O1", setup_hours=1.0, unit_hours=0.0)
    batch = SimpleNamespace(batch_id="B1", priority="normal", quantity=1)
    for dispatch in (dispatch_batch_order, dispatch_sgs):
        batch_progress: dict = {}
        machine_timeline: dict = {}
        operator_timeline: dict = {}
        machine_busy_hours: dict = {}
        operator_busy_hours: dict = {}
        last_op_type_by_machine: dict = {}
        last_end_by_machine: dict = {}
        results: list = []
        kwargs = {}
        if dispatch is dispatch_sgs:
            kwargs = {"batch_order": {"B1": 0}, "dispatch_rule": DispatchRule.SLACK}

        scheduled_count, failed_count = dispatch(
            LegacyScheduler(),
            sorted_ops=[op],
            batches={"B1": batch},
            base_time=base_time,
            end_dt_exclusive=None,
            machine_downtimes=None,
            batch_progress=batch_progress,
            external_group_cache={},
            machine_timeline=machine_timeline,
            operator_timeline=operator_timeline,
            machine_busy_hours=machine_busy_hours,
            operator_busy_hours=operator_busy_hours,
            last_op_type_by_machine=last_op_type_by_machine,
            last_end_by_machine=last_end_by_machine,
            auto_assign_enabled=False,
            resource_pool=None,
            results=results,
            errors=[],
            blocked_batches=set(),
            scheduled_count=5,
            failed_count=2,
            **kwargs,
        )

        assert scheduled_count == 6
        assert failed_count == 2
        assert batch_progress["B1"] == base_time + timedelta(hours=1)
        assert machine_timeline["M1"]
        assert operator_timeline["O1"]
        assert machine_busy_hours["M1"] == 1.0
        assert operator_busy_hours["O1"] == 1.0
        assert last_op_type_by_machine["M1"] == "Cut"
        assert last_end_by_machine["M1"] == base_time + timedelta(hours=1)


def test_seed_identity_fields_reject_fractional_text_without_crashing() -> None:
    from core.algorithms.greedy.seed import normalize_seed_results
    from core.algorithms.types import ScheduleResult

    operations = [SimpleNamespace(id=7, op_code="OP7", batch_id="B1", seq=1)]
    base_time = datetime(2026, 1, 1, 8, 0, 0)
    stats = {"fallback_counts": {}, "param_fallbacks": {}, "fallback_samples": {}}
    seed_results = [
        ScheduleResult(
            op_id="7.5",  # type: ignore[arg-type]
            op_code="OP7",
            batch_id="B1",
            seq=1,
            machine_id="M1",
            operator_id="O1",
            start_time=base_time,
            end_time=base_time + timedelta(hours=1),
            source="internal",
        ),
        ScheduleResult(
            op_id=0,
            op_code="",
            batch_id="B1",
            seq="1.5",  # type: ignore[arg-type]
            machine_id="M1",
            operator_id="O1",
            start_time=base_time,
            end_time=base_time + timedelta(hours=1),
            source="internal",
        ),
    ]

    normalized, seed_op_ids, warnings = normalize_seed_results(seed_results=seed_results, operations=operations, algo_stats=stats)

    assert normalized == []
    assert seed_op_ids == set()
    assert stats["fallback_counts"]["seed_invalid_dropped_count"] == 2
    assert warnings and "无法匹配" in warnings[0]


def test_seed_with_unknown_op_code_does_not_fall_back_to_batch_seq() -> None:
    from core.algorithms.greedy.seed import normalize_seed_results
    from core.algorithms.types import ScheduleResult

    operations = [SimpleNamespace(id=7, op_code="OP7", batch_id="B1", seq=1)]
    base_time = datetime(2026, 1, 1, 8, 0, 0)
    stats = {"fallback_counts": {}, "param_fallbacks": {}, "fallback_samples": {}}
    seed_results = [
        ScheduleResult(
            op_id=0,
            op_code="STALE_CODE",
            batch_id="B1",
            seq=1,
            machine_id="M9",
            operator_id="O9",
            start_time=base_time,
            end_time=base_time + timedelta(hours=1),
            source="internal",
        )
    ]

    normalized, seed_op_ids, warnings = normalize_seed_results(seed_results=seed_results, operations=operations, algo_stats=stats)

    assert normalized == []
    assert seed_op_ids == set()
    assert stats["fallback_counts"]["seed_invalid_dropped_count"] == 1
    assert warnings and "无法匹配" in warnings[0]


def test_seed_backfill_preserves_original_object_source_and_dynamic_attributes() -> None:
    from core.algorithms.greedy.seed import normalize_seed_results
    from core.algorithms.types import ScheduleResult

    operations = [SimpleNamespace(id=7, op_code="OP7", batch_id="B1", seq=1)]
    base_time = datetime(2026, 1, 1, 8, 0, 0)
    stats = {"fallback_counts": {}, "param_fallbacks": {}, "fallback_samples": {}}
    seed_result = ScheduleResult(
        op_id=0,
        op_code="OP7",
        batch_id="B1",
        seq=1,
        machine_id="M1",
        operator_id="O1",
        start_time=base_time,
        end_time=base_time + timedelta(hours=1),
        source="",
    )
    seed_result.extra_marker = "kept"  # type: ignore[attr-defined]

    normalized, seed_op_ids, warnings = normalize_seed_results(seed_results=[seed_result], operations=operations, algo_stats=stats)

    assert normalized == [seed_result]
    assert normalized[0] is seed_result
    assert seed_result.op_id == 7
    assert seed_op_ids == {7}
    assert seed_result.source == ""
    assert seed_result.extra_marker == "kept"  # type: ignore[attr-defined]
    assert stats["fallback_counts"]["seed_op_id_backfilled_count"] == 1
    assert warnings and "补回工序编号" in warnings[0]


def test_seed_bad_time_reasons_are_separated() -> None:
    from core.algorithms.greedy.seed import normalize_seed_results
    from core.algorithms.types import ScheduleResult

    class _IncomparableTime:
        def __gt__(self, _other):
            raise TypeError("time cannot compare")

    operations = [
        SimpleNamespace(id=7, op_code="OP7", batch_id="B1", seq=1),
        SimpleNamespace(id=8, op_code="OP8", batch_id="B1", seq=2),
    ]
    base_time = datetime(2026, 1, 1, 8, 0, 0)
    stats = {"fallback_counts": {}, "param_fallbacks": {}, "fallback_samples": {}}
    seed_results = [
        ScheduleResult(
            op_id=7,
            op_code="OP7",
            batch_id="B1",
            seq=1,
            machine_id="M1",
            operator_id="O1",
            start_time=base_time + timedelta(hours=1),
            end_time=base_time,
            source="internal",
        ),
        ScheduleResult(
            op_id=8,
            op_code="OP8",
            batch_id="B1",
            seq=2,
            machine_id="M2",
            operator_id="O2",
            start_time=_IncomparableTime(),  # type: ignore[arg-type]
            end_time=base_time + timedelta(hours=2),
            source="internal",
        ),
    ]

    normalized, seed_op_ids, warnings = normalize_seed_results(seed_results=seed_results, operations=operations, algo_stats=stats)

    fallback_counts = stats["fallback_counts"]
    assert normalized == []
    assert seed_op_ids == set()
    assert fallback_counts["seed_bad_time_order_dropped_count"] == 1
    assert fallback_counts["seed_bad_time_incomparable_dropped_count"] == 1
    assert fallback_counts["seed_bad_time_dropped_count"] == 2
    assert any("开始时间不早于结束时间" in warning for warning in warnings)
    assert any("时间无法比较" in warning for warning in warnings)


def test_auto_assign_empty_machine_pool_records_single_root_cause() -> None:
    from core.algorithms.greedy.auto_assign import auto_assign_internal_resources

    base_time = datetime(2026, 1, 1, 8, 0, 0)
    stats = {"fallback_counts": {}, "param_fallbacks": {}, "fallback_samples": {}}
    op = SimpleNamespace(id=1, op_code="OP1", batch_id="B1", op_type_id="OT1", machine_id="", operator_id="", setup_hours=1.0, unit_hours=0.0, op_type_name="Cut")
    batch = SimpleNamespace(batch_id="B1", priority="normal", quantity=1)

    chosen = auto_assign_internal_resources(
        calendar=_Calendar(),
        algo_stats=stats,
        op=op,
        batch=batch,
        batch_progress={"B1": base_time},
        machine_timeline={},
        operator_timeline={},
        base_time=base_time,
        end_dt_exclusive=None,
        machine_downtimes={},
        resource_pool={"machines_by_op_type": {"OT1": []}, "operators_by_machine": {}, "machines_by_operator": {}, "pair_rank": {}},
        last_op_type_by_machine={},
        machine_busy_hours={},
        operator_busy_hours={},
    )

    assert chosen is None
    assert stats["fallback_counts"] == {"auto_assign_missing_machine_pool_count": 1}


def test_auto_assign_fixed_operator_requires_declared_op_type_pool() -> None:
    from core.algorithms.greedy.auto_assign import auto_assign_internal_resources

    base_time = datetime(2026, 1, 1, 8, 0, 0)
    stats = {"fallback_counts": {}, "param_fallbacks": {}, "fallback_samples": {}}
    op = SimpleNamespace(
        id=1,
        op_code="OP1",
        batch_id="B1",
        op_type_id="OT_OK",
        machine_id="",
        operator_id="O1",
        setup_hours=1.0,
        unit_hours=0.0,
        op_type_name="Cut",
    )
    batch = SimpleNamespace(batch_id="B1", priority="normal", quantity=1)

    chosen = auto_assign_internal_resources(
        calendar=_Calendar(),
        algo_stats=stats,
        op=op,
        batch=batch,
        batch_progress={"B1": base_time},
        machine_timeline={},
        operator_timeline={},
        base_time=base_time,
        end_dt_exclusive=None,
        machine_downtimes={},
        resource_pool={
            "machines_by_op_type": {"OT_OTHER": ["M_BAD"]},
            "operators_by_machine": {"M_BAD": ["O1"]},
            "machines_by_operator": {"O1": ["M_BAD"]},
            "pair_rank": {},
        },
        last_op_type_by_machine={},
        machine_busy_hours={},
        operator_busy_hours={},
    )

    assert chosen is None
    assert stats["fallback_counts"] == {"auto_assign_missing_machine_pool_count": 1}


def test_auto_assign_fixed_machine_uses_declared_machine_when_op_type_pool_is_unknown() -> None:
    from core.algorithms.greedy.auto_assign import auto_assign_internal_resources

    base_time = datetime(2026, 1, 1, 8, 0, 0)
    stats = {"fallback_counts": {}, "param_fallbacks": {}, "fallback_samples": {}}
    op = SimpleNamespace(
        id=1,
        op_code="OP1",
        batch_id="B1",
        op_type_id="OT_UNKNOWN",
        machine_id="M_FIXED",
        operator_id="",
        setup_hours=1.0,
        unit_hours=0.0,
        op_type_name="Cut",
    )
    batch = SimpleNamespace(batch_id="B1", priority="normal", quantity=1)

    chosen = auto_assign_internal_resources(
        calendar=_Calendar(),
        algo_stats=stats,
        op=op,
        batch=batch,
        batch_progress={"B1": base_time},
        machine_timeline={},
        operator_timeline={},
        base_time=base_time,
        end_dt_exclusive=None,
        machine_downtimes={},
        resource_pool={
            "machines_by_op_type": {},
            "operators_by_machine": {"M_FIXED": ["O1"]},
            "machines_by_operator": {},
            "pair_rank": {},
        },
        last_op_type_by_machine={},
        machine_busy_hours={},
        operator_busy_hours={},
    )

    assert chosen == ("M_FIXED", "O1")
    assert stats["fallback_counts"] == {}


def test_auto_assign_fixed_machine_respects_declared_op_type_pool() -> None:
    from core.algorithms.greedy.auto_assign import auto_assign_internal_resources

    base_time = datetime(2026, 1, 1, 8, 0, 0)
    stats = {"fallback_counts": {}, "param_fallbacks": {}, "fallback_samples": {}}
    op = SimpleNamespace(
        id=1,
        op_code="OP1",
        batch_id="B1",
        op_type_id="OT_OK",
        machine_id="M_FIXED",
        operator_id="",
        setup_hours=1.0,
        unit_hours=0.0,
        op_type_name="Cut",
    )
    batch = SimpleNamespace(batch_id="B1", priority="normal", quantity=1)

    chosen = auto_assign_internal_resources(
        calendar=_Calendar(),
        algo_stats=stats,
        op=op,
        batch=batch,
        batch_progress={"B1": base_time},
        machine_timeline={},
        operator_timeline={},
        base_time=base_time,
        end_dt_exclusive=None,
        machine_downtimes={},
        resource_pool={
            "machines_by_op_type": {"OT_OK": ["M_OTHER"]},
            "operators_by_machine": {"M_FIXED": ["O1"], "M_OTHER": ["O2"]},
            "machines_by_operator": {},
            "pair_rank": {},
        },
        last_op_type_by_machine={},
        machine_busy_hours={},
        operator_busy_hours={},
    )

    assert chosen is None
    assert stats["fallback_counts"] == {"auto_assign_no_machine_candidate_count": 1}


def test_auto_assign_existing_pair_rank_must_be_integer() -> None:
    from core.algorithms.greedy.auto_assign import auto_assign_internal_resources
    from core.infrastructure.errors import ValidationError

    base_time = datetime(2026, 1, 1, 8, 0, 0)
    stats = {"fallback_counts": {}, "param_fallbacks": {}, "fallback_samples": {}}
    op = SimpleNamespace(
        id=1,
        op_code="OP1",
        batch_id="B1",
        op_type_id="OT_OK",
        machine_id="",
        operator_id="",
        setup_hours=1.0,
        unit_hours=0.0,
        op_type_name="Cut",
    )
    batch = SimpleNamespace(batch_id="B1", priority="normal", quantity=1)

    with pytest.raises(ValidationError) as exc_info:
        auto_assign_internal_resources(
            calendar=_Calendar(),
            algo_stats=stats,
            op=op,
            batch=batch,
            batch_progress={"B1": base_time},
            machine_timeline={},
            operator_timeline={},
            base_time=base_time,
            end_dt_exclusive=None,
            machine_downtimes={},
            resource_pool={
                "machines_by_op_type": {"OT_OK": ["M1"]},
                "operators_by_machine": {"M1": ["O1"]},
                "machines_by_operator": {},
                "pair_rank": {("O1", "M1"): "not-an-int"},
            },
            last_op_type_by_machine={},
            machine_busy_hours={},
            operator_busy_hours={},
        )

    assert exc_info.value.field == "pair_rank"


def test_sgs_scoring_hook_sync_does_not_leak_monkeypatch() -> None:
    from unittest import mock

    import core.algorithms.greedy.dispatch.sgs as sgs
    import core.algorithms.greedy.dispatch.sgs_scoring as scoring
    from core.algorithms.dispatch_rules import DispatchRule
    from core.algorithms.greedy.run_state import ScheduleRunState

    original = scoring.estimate_internal_slot
    base_time = datetime(2026, 1, 1, 8, 0, 0)

    def fake_estimator(*args, **kwargs):
        assert scoring.estimate_internal_slot is original
        return SimpleNamespace(
            start_time=base_time,
            end_time=base_time + timedelta(hours=1),
            total_hours=1.0,
            changeover_penalty=0,
            blocked_by_window=False,
            abort_after_hit=False,
        )

    fake_estimator_mock = mock.Mock(name="fake_estimator", side_effect=fake_estimator)
    op = SimpleNamespace(id=1, op_code="OP1", batch_id="B1", seq=1, source="internal", machine_id="M1", operator_id="O1", setup_hours=1.0, unit_hours=0.0)
    batch = SimpleNamespace(batch_id="B1", priority="normal", due_date=None, quantity=1)
    context = SimpleNamespace(calendar=_Calendar(), increment=lambda *args, **kwargs: None)

    with mock.patch.object(sgs, "estimate_internal_slot", fake_estimator_mock):
        sgs._score_internal_candidate(
            ctx=context,
            state=ScheduleRunState(base_time=base_time),
            op=op,
            batch=batch,
            batch_id="B1",
            batch_order={"B1": 0},
            dispatch_rule=DispatchRule.SLACK,
            end_dt_exclusive=None,
            machine_downtimes=None,
            auto_assign_enabled=False,
            resource_pool=None,
            avg_proc_hours=1.0,
            strict_mode=False,
        )
        fake_estimator_mock.assert_called_once()

    assert scoring.estimate_internal_slot is original


def test_dispatch_sgs_main_loop_uses_legacy_scoring_wrapper() -> None:
    from unittest import mock

    import core.algorithms.greedy.dispatch.sgs as sgs
    from core.algorithms.dispatch_rules import DispatchRule
    from core.algorithms.types import ScheduleResult

    class LegacyScheduler:
        calendar = _Calendar()
        logger = SimpleNamespace(exception=lambda *args, **kwargs: None)
        _last_algo_stats = {"fallback_counts": {}, "param_fallbacks": {}, "fallback_samples": {}}

        def _schedule_internal(self, op, batch, batch_progress, machine_timeline, operator_timeline, base_time, errors, end_dt_exclusive, machine_downtimes=None, **kwargs):
            return (
                ScheduleResult(
                    op_id=1,
                    op_code="OP1",
                    batch_id="B1",
                    seq=1,
                    machine_id="M1",
                    operator_id="O1",
                    start_time=base_time,
                    end_time=base_time + timedelta(hours=1),
                    source="internal",
                ),
                False,
            )

    op = SimpleNamespace(id=1, op_code="OP1", batch_id="B1", seq=1, source="internal")
    batch = SimpleNamespace(batch_id="B1", priority="normal", due_date=None, quantity=1)
    wrapper = mock.Mock(return_value=(0.0,))

    with mock.patch.object(sgs, "_score_internal_candidate", wrapper):
        scheduled_count, failed_count = sgs.dispatch_sgs(
            LegacyScheduler(),
            sorted_ops=[op],
            batches={"B1": batch},
            batch_order={"B1": 0},
            dispatch_rule=DispatchRule.SLACK,
            base_time=datetime(2026, 1, 1, 8, 0, 0),
            end_dt_exclusive=None,
            machine_downtimes=None,
            auto_assign_enabled=False,
            resource_pool=None,
        )

    assert (scheduled_count, failed_count) == (1, 0)
    wrapper.assert_called_once()


def test_run_context_enforces_strict_internal_input_before_legacy_callback() -> None:
    from core.algorithms.greedy.run_context import ScheduleRunContext
    from core.algorithms.types import ScheduleResult
    from core.infrastructure.errors import ValidationError

    called = False
    base_time = datetime(2026, 1, 1, 8, 0, 0)

    def legacy_callback(**kwargs):
        nonlocal called
        called = True
        return (
            ScheduleResult(
                op_id=1,
                op_code="SHOULD_NOT_RUN",
                batch_id="B1",
                seq=1,
                machine_id="M1",
                operator_id="O1",
                start_time=base_time,
                end_time=base_time + timedelta(hours=1),
                source="internal",
            ),
            False,
        )

    ctx = ScheduleRunContext(calendar=_Calendar(), logger=None, algo_stats={}, internal_callback=legacy_callback)
    op = SimpleNamespace(id=1, op_code="OP1", batch_id="B1", seq=1, setup_hours=float("inf"), unit_hours=0.0)
    batch = SimpleNamespace(batch_id="B1", priority="normal", quantity=1)

    with pytest.raises(ValidationError) as exc_info:
        ctx.schedule_internal(
            op=op,
            batch=batch,
            batch_progress={"B1": base_time},
            machine_timeline={},
            operator_timeline={},
            base_time=base_time,
            errors=[],
            end_dt_exclusive=None,
            machine_downtimes=None,
            auto_assign_enabled=False,
            resource_pool=None,
            last_op_type_by_machine={},
            machine_busy_hours={},
            operator_busy_hours={},
            strict_mode=True,
        )

    assert exc_info.value.field == "setup_hours"
    assert called is False


def test_run_context_strict_mode_does_not_break_legacy_internal_callback_signature() -> None:
    from core.algorithms.greedy.run_context import ScheduleRunContext
    from core.algorithms.types import ScheduleResult

    base_time = datetime(2026, 1, 1, 8, 0, 0)

    def legacy_callback(
        *,
        op,
        batch,
        batch_progress,
        machine_timeline,
        operator_timeline,
        base_time,
        errors,
        end_dt_exclusive,
        machine_downtimes=None,
        auto_assign_enabled=False,
        resource_pool=None,
        last_op_type_by_machine=None,
        machine_busy_hours=None,
        operator_busy_hours=None,
    ):
        return (
            ScheduleResult(
                op_id=1,
                op_code=getattr(op, "op_code", "OP1"),
                batch_id=getattr(batch, "batch_id", "B1"),
                seq=1,
                machine_id="M1",
                operator_id="O1",
                start_time=base_time,
                end_time=base_time + timedelta(hours=1),
                source="internal",
            ),
            False,
        )

    ctx = ScheduleRunContext(calendar=_Calendar(), logger=None, algo_stats={}, internal_callback=legacy_callback)
    result, blocked = ctx.schedule_internal(
        op=SimpleNamespace(id=1, op_code="OP1", batch_id="B1", seq=1, setup_hours=1.0, unit_hours=0.0),
        batch=SimpleNamespace(batch_id="B1", priority="normal", quantity=1),
        batch_progress={"B1": base_time},
        machine_timeline={},
        operator_timeline={},
        base_time=base_time,
        errors=[],
        end_dt_exclusive=None,
        machine_downtimes=None,
        auto_assign_enabled=False,
        resource_pool=None,
        last_op_type_by_machine={},
        machine_busy_hours={},
        operator_busy_hours={},
        strict_mode=True,
    )

    assert blocked is False
    assert result and result.op_code == "OP1"


def test_sgs_external_scoring_does_not_double_count_defaulted_days() -> None:
    from core.algorithms.dispatch_rules import DispatchRule
    from core.algorithms.greedy.dispatch.sgs import dispatch_sgs
    from core.algorithms.greedy.run_context import ScheduleRunContext

    stats = {"fallback_counts": {}, "param_fallbacks": {}, "fallback_samples": {}}
    ctx = ScheduleRunContext(calendar=_Calendar(), logger=None, algo_stats=stats)
    op = SimpleNamespace(id=11, op_code="EXT-001", batch_id="B_EXT", seq=10, source="external", ext_days=None)
    batch = SimpleNamespace(batch_id="B_EXT", priority="normal", due_date="2099-12-31", quantity=1)

    scheduled_count, failed_count = dispatch_sgs(
        ctx,
        sorted_ops=[op],
        batches={"B_EXT": batch},
        batch_order={"B_EXT": 0},
        dispatch_rule=DispatchRule.SLACK,
        base_time=datetime(2026, 4, 2, 8, 0, 0),
        end_dt_exclusive=None,
        machine_downtimes=None,
        auto_assign_enabled=False,
        resource_pool=None,
        strict_mode=False,
    )

    assert (scheduled_count, failed_count) == (1, 0)
    assert stats["fallback_counts"]["legacy_external_days_defaulted_count"] == 1


def test_sgs_strict_external_scoring_rejects_blank_ext_days_before_defaulting() -> None:
    from core.algorithms.greedy.dispatch.sgs_scoring import _external_candidate_window
    from core.algorithms.greedy.run_context import ScheduleRunContext
    from core.algorithms.greedy.run_state import ScheduleRunState
    from core.infrastructure.errors import ValidationError

    ctx = ScheduleRunContext(calendar=_Calendar(), logger=None, algo_stats={})
    state = ScheduleRunState(base_time=datetime(2026, 4, 2, 8, 0, 0))
    op = SimpleNamespace(id=11, op_code="EXT-001", batch_id="B_EXT", seq=10, source="external", ext_days="   ")

    with pytest.raises(ValidationError) as exc_info:
        _external_candidate_window(ctx, state, op=op, batch_id="B_EXT", prev_end=state.base_time, strict_mode=True)

    assert exc_info.value.field == "ext_days"


def test_sgs_strict_external_scoring_rejects_blank_merged_total_days() -> None:
    from core.algorithms.greedy.dispatch.sgs_scoring import _external_candidate_window
    from core.algorithms.greedy.run_context import ScheduleRunContext
    from core.algorithms.greedy.run_state import ScheduleRunState
    from core.algorithms.value_domains import MERGED
    from core.infrastructure.errors import ValidationError

    ctx = ScheduleRunContext(calendar=_Calendar(), logger=None, algo_stats={})
    state = ScheduleRunState(base_time=datetime(2026, 4, 2, 8, 0, 0))
    op = SimpleNamespace(
        id=11,
        op_code="EXT-001",
        batch_id="B_EXT",
        seq=10,
        source="external",
        ext_days=None,
        ext_merge_mode=MERGED,
        ext_group_id="G1",
        ext_group_total_days="   ",
    )

    with pytest.raises(ValidationError) as exc_info:
        _external_candidate_window(ctx, state, op=op, batch_id="B_EXT", prev_end=state.base_time, strict_mode=True)

    assert exc_info.value.field == "ext_group_total_days"


def test_sgs_strict_merged_external_group_allows_blank_member_ext_days_when_total_days_is_valid() -> None:
    from core.algorithms.dispatch_rules import DispatchRule
    from core.algorithms.greedy.dispatch.sgs import dispatch_sgs
    from core.algorithms.greedy.run_context import ScheduleRunContext
    from core.algorithms.value_domains import MERGED

    ctx = ScheduleRunContext(calendar=_Calendar(), logger=None, algo_stats={})
    op = SimpleNamespace(
        id=11,
        op_code="EXT-001",
        batch_id="B_EXT",
        seq=10,
        source="external",
        ext_days=None,
        ext_merge_mode=MERGED,
        ext_group_id="G1",
        ext_group_total_days=2.0,
    )
    batch = SimpleNamespace(batch_id="B_EXT", priority="normal", due_date="2099-12-31", quantity=1)

    scheduled_count, failed_count = dispatch_sgs(
        ctx,
        sorted_ops=[op],
        batches={"B_EXT": batch},
        batch_order={"B_EXT": 0},
        dispatch_rule=DispatchRule.SLACK,
        base_time=datetime(2026, 4, 2, 8, 0, 0),
        end_dt_exclusive=None,
        machine_downtimes=None,
        auto_assign_enabled=False,
        resource_pool=None,
        strict_mode=True,
    )

    assert (scheduled_count, failed_count) == (1, 0)
    assert "legacy_external_days_defaulted_count" not in (ctx.algo_stats.get("fallback_counts") or {})


def test_dispatch_sgs_rejects_invalid_sequence_identity() -> None:
    from core.algorithms.dispatch_rules import DispatchRule
    from core.algorithms.greedy.dispatch.sgs import dispatch_sgs
    from core.algorithms.greedy.run_context import ScheduleRunContext
    from core.infrastructure.errors import ValidationError

    ctx = ScheduleRunContext(calendar=_Calendar(), logger=None, algo_stats={})
    op = SimpleNamespace(id=1, op_code="OP1", batch_id="B1", seq="bad-seq", source="internal")
    batch = SimpleNamespace(batch_id="B1", priority="normal", due_date=None, quantity=1)

    with pytest.raises(ValidationError) as exc_info:
        dispatch_sgs(
            ctx,
            sorted_ops=[op],
            batches={"B1": batch},
            batch_order={"B1": 0},
            dispatch_rule=DispatchRule.SLACK,
            base_time=datetime(2026, 1, 1, 8, 0, 0),
            end_dt_exclusive=None,
            machine_downtimes=None,
            auto_assign_enabled=False,
            resource_pool=None,
        )

    assert exc_info.value.field == "seq"


def test_dispatch_sgs_rejects_invalid_internal_hours_during_scoring_in_non_strict_mode() -> None:
    from core.algorithms.dispatch_rules import DispatchRule
    from core.algorithms.greedy.dispatch.sgs import dispatch_sgs
    from core.algorithms.greedy.run_context import ScheduleRunContext
    from core.infrastructure.errors import ValidationError

    ctx = ScheduleRunContext(calendar=_Calendar(), logger=None, algo_stats={})
    op = SimpleNamespace(
        id=1,
        op_code="OP1",
        batch_id="B1",
        seq=1,
        source="internal",
        machine_id="M1",
        operator_id="O1",
        setup_hours=float("inf"),
        unit_hours=0.0,
    )
    batch = SimpleNamespace(batch_id="B1", priority="normal", due_date=None, quantity=1)

    with pytest.raises(ValidationError) as exc_info:
        dispatch_sgs(
            ctx,
            sorted_ops=[op],
            batches={"B1": batch},
            batch_order={"B1": 0},
            dispatch_rule=DispatchRule.SLACK,
            base_time=datetime(2026, 1, 1, 8, 0, 0),
            end_dt_exclusive=None,
            machine_downtimes=None,
            auto_assign_enabled=False,
            resource_pool=None,
            strict_mode=False,
        )

    assert exc_info.value.field == "setup_hours"


def test_dispatch_sgs_rejects_malformed_auto_assign_probe_result() -> None:
    from core.algorithms.dispatch_rules import DispatchRule
    from core.algorithms.greedy.dispatch.sgs import dispatch_sgs
    from core.algorithms.greedy.run_context import ScheduleRunContext

    base_time = datetime(2026, 1, 1, 8, 0, 0)

    def bad_probe(**_kwargs):
        return ("M1",)

    ctx = ScheduleRunContext(calendar=_Calendar(), logger=None, algo_stats={}, auto_assign_callback=bad_probe)
    op = SimpleNamespace(
        id=1,
        op_code="OP1",
        batch_id="B1",
        seq=1,
        source="internal",
        machine_id="",
        operator_id="",
        setup_hours=1.0,
        unit_hours=0.0,
    )
    batch = SimpleNamespace(batch_id="B1", priority="normal", due_date=None, quantity=1)

    with pytest.raises(TypeError, match="auto_assign probe result is not a pair"):
        dispatch_sgs(
            ctx,
            sorted_ops=[op],
            batches={"B1": batch},
            batch_order={"B1": 0},
            dispatch_rule=DispatchRule.SLACK,
            base_time=base_time,
            end_dt_exclusive=None,
            machine_downtimes=None,
            auto_assign_enabled=True,
            resource_pool={},
        )


def test_dispatch_sgs_propagates_validation_error_from_legacy_internal_callback() -> None:
    from core.algorithms.dispatch_rules import DispatchRule
    from core.algorithms.greedy.dispatch.sgs import dispatch_sgs
    from core.infrastructure.errors import ValidationError

    class LegacyScheduler:
        calendar = _Calendar()
        logger = SimpleNamespace(exception=lambda *args, **kwargs: None)
        _last_algo_stats = {"fallback_counts": {}, "param_fallbacks": {}, "fallback_samples": {}}

        def _schedule_internal(self, **kwargs):
            raise ValidationError("legacy strict failure", field="subclass_field")

    op = SimpleNamespace(
        id=1,
        op_code="OP1",
        batch_id="B1",
        seq=1,
        source="internal",
        machine_id="M1",
        operator_id="O1",
        setup_hours=1.0,
        unit_hours=0.0,
    )
    batch = SimpleNamespace(batch_id="B1", priority="normal", due_date=None, quantity=1)

    with pytest.raises(ValidationError) as exc_info:
        dispatch_sgs(
            LegacyScheduler(),
            sorted_ops=[op],
            batches={"B1": batch},
            batch_order={"B1": 0},
            dispatch_rule=DispatchRule.SLACK,
            base_time=datetime(2026, 1, 1, 8, 0, 0),
            end_dt_exclusive=None,
            machine_downtimes=None,
            auto_assign_enabled=False,
            resource_pool=None,
        )

    assert exc_info.value.field == "subclass_field"


@pytest.mark.parametrize("dispatch_mode", ["batch_order", "sgs"])
def test_strict_internal_nonfinite_hours_rejected_in_all_dispatch_modes(dispatch_mode: str) -> None:
    from core.algorithms.greedy.scheduler import GreedyScheduler
    from core.infrastructure.errors import ValidationError

    scheduler = GreedyScheduler(calendar_service=_Calendar(), config_service=_default_config())
    batch = SimpleNamespace(batch_id="B1", priority="normal", due_date=None, ready_date=None, created_at=None, quantity=1)
    op = SimpleNamespace(
        id=1,
        op_code="OP1",
        batch_id="B1",
        seq=1,
        source="internal",
        machine_id="M1",
        operator_id="O1",
        setup_hours=float("inf"),
        unit_hours=0.0,
        op_type_name="Cut",
    )

    with pytest.raises(ValidationError) as exc_info:
        scheduler.schedule(
            operations=[op],
            batches={"B1": batch},
            start_dt=datetime(2026, 1, 1, 8, 0, 0),
            dispatch_mode=dispatch_mode,
            strict_mode=True,
        )

    assert exc_info.value.field == "setup_hours"
