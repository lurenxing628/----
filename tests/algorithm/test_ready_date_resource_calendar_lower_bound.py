"""Readiness is a date lower bound; actual resources decide working time."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.algorithms.greedy.scheduler import GreedyScheduler
from core.infrastructure.errors import BusinessError, ErrorCode
from core.services.scheduler.calendar_service import CalendarService
from core.services.scheduler.config.config_field_spec import default_snapshot_values


def _calendar(conn, *, personal=False, urgent_only=False):
    conn.execute("INSERT INTO Operators (operator_id, name) VALUES ('O1', 'Operator')")
    calendar = CalendarService(conn)
    if urgent_only:
        calendar.upsert("2026-09-06", day_type="workday", shift_start="08:00", shift_hours=8,
                        efficiency=1, allow_normal="no", allow_urgent="yes")
    if personal:
        calendar.upsert_operator_calendar(
            "O1", "2026-09-06", day_type="workday", shift_start="08:00", shift_hours=8,
            efficiency=1, allow_normal="no" if urgent_only else "yes", allow_urgent="yes",
        )
    return calendar


def _batch(*, priority="normal", ready_date="2026-09-06"):
    return SimpleNamespace(batch_id="B1", priority=priority, ready_date=ready_date,
                           ready_status="yes", due_date=None, created_at=None, quantity=1)


def _operation(*, source="internal", merge_mode="separate", op_id=1):
    return SimpleNamespace(
        id=op_id, op_code=f"B1-{op_id}", batch_id="B1", seq=op_id, source=source,
        machine_id="M1" if source == "internal" else None,
        operator_id="O1" if source == "internal" else None,
        setup_hours=0.0, unit_hours=1.0, op_type_id="OT1", op_type_name="Turning",
        ext_days=1.0, ext_merge_mode=merge_mode, ext_group_id="G1", ext_group_total_days=1.0,
    )


def _schedule(calendar, *, operations=None, batch=None, start_dt=datetime(2026, 9, 4, 8), config_overrides=None, **kwargs):
    config = default_snapshot_values()
    config.update(config_overrides or {})
    scheduler = GreedyScheduler(calendar_service=calendar, config_service=SimpleNamespace(**config))
    return scheduler.schedule(
        operations=[_operation()] if operations is None else operations,
        batches={"B1": batch or _batch()}, start_dt=start_dt, **kwargs,
    )


@pytest.mark.parametrize("dispatch_mode", ["batch_order", "sgs"])
@pytest.mark.parametrize("strict_mode", [False, True])
@pytest.mark.parametrize("priority", ["normal", "urgent", "critical"])
@pytest.mark.parametrize("personal", [False, True])
def test_sunday_readiness_respects_actual_operator_calendar(schema_conn, dispatch_mode, strict_mode, priority, personal):
    calendar = _calendar(schema_conn, personal=personal)
    results, summary, _, _ = _schedule(
        calendar, batch=_batch(priority=priority), readiness_gate_enabled=True,
        dispatch_mode=dispatch_mode, strict_mode=strict_mode,
    )
    expected = datetime(2026, 9, 6 if personal else 7, 8)
    assert summary.failed_ops == 0, summary.errors
    assert len(results) == 1
    assert results[0].start_time == expected
    assert results[0].end_time == expected + timedelta(hours=1)


@pytest.mark.parametrize("dispatch_mode", ["batch_order", "sgs"])
@pytest.mark.parametrize("personal", [False, True])
@pytest.mark.parametrize("priority,expected_day", [("normal", 7), ("urgent", 6), ("critical", 6)])
def test_readiness_keeps_normal_and_urgent_permissions(schema_conn, dispatch_mode, personal, priority, expected_day):
    calendar = _calendar(schema_conn, personal=personal, urgent_only=True)
    results, summary, _, _ = _schedule(
        calendar, batch=_batch(priority=priority), readiness_gate_enabled=True, dispatch_mode=dispatch_mode,
    )
    assert summary.failed_ops == 0, summary.errors
    assert results[0].start_time == datetime(2026, 9, expected_day, 8)


@pytest.mark.parametrize("dispatch_mode", ["batch_order", "sgs"])
@pytest.mark.parametrize("strict_mode", [False, True])
def test_auto_assign_uses_personal_calendar_after_readiness(schema_conn, dispatch_mode, strict_mode):
    calendar = _calendar(schema_conn, personal=True)
    op = _operation()
    op.machine_id = ""
    op.operator_id = ""
    pool = {
        "machines_by_op_type": {"OT1": ["M1"]},
        "operators_by_machine": {"M1": ["O1"]},
        "machines_by_operator": {"O1": ["M1"]}, "pair_rank": {},
    }
    results, summary, _, _ = _schedule(
        calendar, operations=[op], config_overrides={"auto_assign_enabled": "yes"},
        resource_pool=pool, readiness_gate_enabled=True,
        dispatch_mode=dispatch_mode, strict_mode=strict_mode,
    )
    assert summary.failed_ops == 0, summary.errors
    assert len(results) == 1
    assert (results[0].machine_id, results[0].operator_id) == ("M1", "O1")
    assert results[0].start_time == datetime(2026, 9, 6, 8)
    assert results[0].end_time == datetime(2026, 9, 6, 9)


@pytest.mark.parametrize("dispatch_mode", ["batch_order", "sgs"])
@pytest.mark.parametrize("strict_mode", [False, True])
@pytest.mark.parametrize("auto_assign", [False, True])
def test_personal_shift_survives_global_calendar_search_limit(schema_conn, monkeypatch, dispatch_mode, strict_mode, auto_assign):
    calendar = _calendar(schema_conn, personal=True)
    ready = datetime(2026, 9, 6)
    schema_conn.executemany(
        """INSERT INTO WorkCalendar
        (date, day_type, shift_hours, efficiency, allow_normal, allow_urgent)
        VALUES (?, 'holiday', 0, 1, 'no', 'no')""",
        [((ready + timedelta(days=offset)).date().isoformat(),) for offset in range(3661)],
    )
    with pytest.raises(BusinessError) as error:
        calendar.adjust_to_working_time(ready, priority="normal")
    assert error.value.code == ErrorCode.CALENDAR_ERROR
    assert calendar.adjust_to_working_time(ready, priority="normal", operator_id="O1") == ready.replace(hour=8)

    calls = []
    adjust = calendar.adjust_to_working_time

    def observed(dt, priority=None, machine_id=None, operator_id=None):
        calls.append(operator_id)
        return adjust(dt, priority=priority, machine_id=machine_id, operator_id=operator_id)

    monkeypatch.setattr(calendar, "adjust_to_working_time", observed)
    op = _operation()
    if auto_assign:
        op.machine_id = ""
        op.operator_id = ""
    pool = {
        "machines_by_op_type": {"OT1": ["M1"]},
        "operators_by_machine": {"M1": ["O1"]},
        "machines_by_operator": {"O1": ["M1"]}, "pair_rank": {},
    }
    results, summary, _, _ = _schedule(
        calendar, operations=[op], resource_pool=pool,
        config_overrides={"auto_assign_enabled": "yes" if auto_assign else "no"},
        dispatch_mode=dispatch_mode, strict_mode=strict_mode, readiness_gate_enabled=True,
    )
    assert summary.success, summary
    assert len(results) == 1
    assert (results[0].machine_id, results[0].operator_id) == ("M1", "O1")
    assert results[0].start_time == ready.replace(hour=8)
    assert results[0].end_time == ready.replace(hour=9)
    assert calls and all(operator_id == "O1" for operator_id in calls)


@pytest.mark.parametrize("dispatch_mode", ["batch_order", "sgs"])
@pytest.mark.parametrize("merge_mode", ["separate", "merged"])
@pytest.mark.parametrize("strict_mode", [False, True])
def test_external_readiness_uses_natural_days_not_global_workdays(schema_conn, dispatch_mode, merge_mode, strict_mode):
    calendar = _calendar(schema_conn)
    operations = [_operation(source="external", merge_mode=merge_mode, op_id=n) for n in (1, 2)]
    results, summary, _, _ = _schedule(
        calendar, operations=operations, readiness_gate_enabled=True,
        dispatch_mode=dispatch_mode, strict_mode=strict_mode,
    )
    assert summary.failed_ops == 0, summary.errors
    assert len(results) == 2
    assert results[0].start_time == datetime(2026, 9, 6)
    assert results[0].end_time == datetime(2026, 9, 7)
    assert results[1].start_time == (results[0].start_time if merge_mode == "merged" else results[0].end_time)
    assert results[1].end_time == results[1].start_time + timedelta(days=1)


@pytest.mark.parametrize("source", ["internal", "external"])
@pytest.mark.parametrize("ready_date", [None, "2026-09-04", "2026-09-06"])
def test_readiness_never_moves_before_run_start(schema_conn, source, ready_date):
    calendar = _calendar(schema_conn, personal=True)
    start = datetime(2026, 9, 6, 10, 30)
    results, summary, _, _ = _schedule(
        calendar, operations=[_operation(source=source)], batch=_batch(ready_date=ready_date),
        start_dt=start, readiness_gate_enabled=True,
    )
    assert summary.failed_ops == 0, summary.errors
    assert results[0].start_time == start


@pytest.mark.parametrize("source", ["internal", "external"])
def test_disabled_readiness_gate_ignores_future_ready_date(schema_conn, source):
    calendar = _calendar(schema_conn)
    start = datetime(2026, 9, 4, 8)
    results, summary, _, _ = _schedule(
        calendar, operations=[_operation(source=source)], start_dt=start, readiness_gate_enabled=False,
    )
    assert summary.failed_ops == 0, summary.errors
    assert results[0].start_time == start


@pytest.mark.parametrize("strict_mode", [False, True])
@pytest.mark.parametrize("empty_work", [False, True])
def test_readiness_does_not_query_global_calendar(schema_conn, monkeypatch, strict_mode, empty_work):
    calendar = _calendar(schema_conn)
    calls = []
    adjust = calendar.adjust_to_working_time

    def resource_only(dt, priority=None, machine_id=None, operator_id=None):
        calls.append(operator_id)
        assert operator_id == "O1", "Readiness must not search the global calendar"
        return adjust(dt, priority=priority, machine_id=machine_id, operator_id=operator_id)

    monkeypatch.setattr(calendar, "adjust_to_working_time", resource_only)
    results, summary, _, _ = _schedule(
        calendar, operations=[] if empty_work else [_operation()],
        readiness_gate_enabled=True, strict_mode=strict_mode,
    )
    assert summary.success, summary
    assert len(results) == (0 if empty_work else 1)
    assert bool(calls) is not empty_work
    assert all(operator_id == "O1" for operator_id in calls)


@pytest.mark.parametrize("strict_mode", [False, True])
def test_actual_resource_calendar_error_remains_visible(schema_conn, monkeypatch, caplog, strict_mode):
    calendar = _calendar(schema_conn)
    calls = []

    def unavailable(dt, priority=None, machine_id=None, operator_id=None):
        calls.append((dt, operator_id))
        raise RuntimeError("calendar unavailable")

    monkeypatch.setattr(calendar, "adjust_to_working_time", unavailable)
    results, summary, _, _ = _schedule(calendar, readiness_gate_enabled=True, strict_mode=strict_mode)
    assert not summary.success
    assert summary.failed_ops == 1
    assert summary.scheduled_ops == 0
    assert [detail["code"] for detail in summary.failure_details] == ["dispatch_operation_exception"]
    assert not any(result.start_time for result in results)
    assert "calendar unavailable" in caplog.text
    assert calls == [(datetime(2026, 9, 6), "O1")]
