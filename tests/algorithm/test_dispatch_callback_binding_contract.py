from __future__ import annotations

import inspect
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, cast

import pytest

import core.algorithms.greedy.run_context as run_context
from core.algorithm_contracts.dispatch_rules import DispatchRule
from core.algorithm_runtime.dispatch_context import DispatchContextContractError, ensure_dispatch_context
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithms.greedy.dispatch.batch_order import dispatch_batch_order
from core.algorithms.greedy.dispatch.sgs import dispatch_sgs
from core.algorithms.greedy.run_context import ScheduleRunContext
from core.services.scheduler.run.schedule_signature_support import (
    clear_strict_mode_support_cache_for_tests,
    schedule_with_optional_strict_mode,
)


def _context(callback, *, legacy, source="internal"):
    calendar = SimpleNamespace(
        adjust_to_working_time=lambda start, **kwargs: start,
        add_working_hours=lambda start, hours, **kwargs: start + timedelta(hours=hours),
        add_calendar_days=lambda start, days: start + timedelta(days=days),
        get_efficiency=lambda *args, **kwargs: 1.0,
    )
    candidate = SimpleNamespace(calendar=calendar, logger=None)
    setattr(candidate, "_schedule_" + source, callback)
    return ensure_dispatch_context(candidate) if legacy else ScheduleRunContext.from_legacy_scheduler(candidate)


def _dispatch(context, *, mode, source):
    start = datetime(2026, 1, 1, 8)
    state = ScheduleRunState(base_time=start)
    op = SimpleNamespace(
        id=1, op_id=1, seq=1, op_code="OP-1", batch_id="B1", source=source,
        machine_id="M1", operator_id="O1", setup_hours=1, unit_hours=0, ext_days=1,
    )
    kwargs: Dict[str, Any] = dict(
        sorted_ops=[op], batches={"B1": SimpleNamespace(batch_id="B1", quantity=1, priority="normal", due_date=None)},
        base_time=start, end_dt_exclusive=None, machine_downtimes=None, state=state,
        auto_assign_enabled=False, resource_pool=None,
    )
    if mode == "sgs":
        return state, lambda: dispatch_sgs(context, batch_order={"B1": 0}, dispatch_rule=DispatchRule.CR, **kwargs)
    return state, lambda: dispatch_batch_order(context, **kwargs)


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("mode", ["batch_order", "sgs"])
@pytest.mark.parametrize("source", ["internal", "external"])
def test_signature_drift_aborts_dispatch_without_business_failure(legacy, mode, source):
    def callback(*, removed_parameter):
        pytest.fail("invalid callback must not run")

    context = _context(callback, legacy=legacy, source=source)
    state, dispatch = _dispatch(context, mode=mode, source=source)
    with pytest.raises(DispatchContextContractError, match="schedule_" + source):
        dispatch()
    assert state.failed_count == 0
    assert state.failure_details == []
    assert state.blocked_batches == set()


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("mode", ["batch_order", "sgs"])
@pytest.mark.parametrize("source", ["internal", "external"])
def test_callback_body_type_error_keeps_business_failure_classification(legacy, mode, source):
    calls = []

    def callback(**kwargs):
        calls.append(kwargs)
        raise TypeError("callback body failed")

    context = _context(callback, legacy=legacy, source=source)
    state, dispatch = _dispatch(context, mode=mode, source=source)
    assert dispatch() == (0, 1)
    assert len(calls) == 1
    assert state.failure_details[0]["code"] == "dispatch_operation_exception"


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("missing", ["op", "batch"])
def test_strict_adapter_missing_input_is_contract_error(legacy, missing):
    context = _context(lambda **kwargs: pytest.fail("must validate first"), legacy=legacy)
    kwargs = {"op": SimpleNamespace(setup_hours=1, unit_hours=0), "batch": SimpleNamespace(quantity=1)}
    del kwargs[missing]
    with pytest.raises(DispatchContextContractError, match=missing):
        context.schedule_internal(strict_mode=True, **kwargs)


@pytest.mark.parametrize("legacy", [False, True])
def test_uninspectable_callback_is_rejected_only_when_used(legacy):
    class OpaqueCallback:
        __signature__ = "not a signature"

        def __call__(self, **kwargs):
            pytest.fail("opaque callback must not bypass validation")

    context = _context(OpaqueCallback(), legacy=legacy)
    with pytest.raises(DispatchContextContractError, match="schedule_internal"):
        context.schedule_internal()


@pytest.mark.parametrize("legacy", [False, True])
def test_internal_strict_pop_and_external_strict_forwarding_preserve_actual_kwargs(legacy):
    calls = []

    def internal(*, op, batch):
        calls.append({"op": op, "batch": batch})
        return None, False

    op, batch = SimpleNamespace(setup_hours=1, unit_hours=0), SimpleNamespace(quantity=1)
    context = _context(internal, legacy=legacy)
    assert context.schedule_internal(op=op, batch=batch, strict_mode=True) == (None, False)
    assert calls == [{"op": op, "batch": batch}]
    external = _context(lambda **kwargs: kwargs, legacy=legacy, source="external")
    assert external.schedule_external(op=op, strict_mode=True) == {"op": op, "strict_mode": True}


@pytest.mark.parametrize("legacy", [False, True])
def test_positional_adapter_calls_still_work_outside_strict_mode(legacy):
    sentinel = object()
    context = _context(lambda op, /: op, legacy=legacy)
    assert context.schedule_internal(sentinel) is sentinel
    with pytest.raises(DispatchContextContractError, match="op, batch"):
        context.schedule_internal(sentinel, strict_mode=True)


@pytest.mark.parametrize("method", [
    "schedule_internal", "schedule_external", "auto_assign_internal_resources", "auto_assign_internal_resources_attempt",
])
@pytest.mark.parametrize("extra", [False, True])
def test_canonical_fallback_binding_is_checked(method, extra):
    context = ScheduleRunContext(calendar=None, logger=None, algo_stats={})
    kwargs = {}
    if extra:
        fallback = {
            "schedule_internal": run_context.schedule_internal_operation,
            "schedule_external": run_context.schedule_external,
            "auto_assign_internal_resources": run_context.auto_assign_internal_resources_attempt,
            "auto_assign_internal_resources_attempt": run_context.auto_assign_internal_resources_attempt,
        }[method]
        kwargs = dict.fromkeys(set(inspect.signature(fallback).parameters) - {
            "scheduler", "calendar", "algo_stats", "auto_assign_resources", "strict_mode",
        })
        kwargs["extra"] = None
    with pytest.raises(DispatchContextContractError, match="fallback") as exc:
        getattr(context, method)(**kwargs)
    if extra:
        assert "unexpected keyword argument 'extra'" in str(exc.value.__cause__)


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("attempt_slot", [False, True])
@pytest.mark.parametrize("method", ["auto_assign_internal_resources", "auto_assign_internal_resources_attempt"])
def test_auto_assign_signature_drift_is_contract_error(legacy, attempt_slot, method):
    callback = lambda *, removed: None
    name = "_auto_assign_internal_resources" + ("_attempt" if attempt_slot else "")
    candidate = SimpleNamespace(**{name: callback})
    context = ensure_dispatch_context(candidate) if legacy else ScheduleRunContext.from_legacy_scheduler(candidate)
    with pytest.raises(DispatchContextContractError, match="auto_assign_internal_resources"):
        getattr(context, method)(probe_only=True)


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("attempt_slot", [False, True])
def test_auto_assign_body_type_error_is_not_reclassified(legacy, attempt_slot):
    error = TypeError("callback body failure")

    def callback(**kwargs):
        raise error

    name = "_auto_assign_internal_resources" + ("_attempt" if attempt_slot else "")
    candidate = SimpleNamespace(**{name: callback})
    context = ensure_dispatch_context(candidate) if legacy else ScheduleRunContext.from_legacy_scheduler(candidate)
    with pytest.raises(TypeError) as exc:
        context.auto_assign_internal_resources_attempt(probe_only=True)
    assert exc.value is error


@pytest.mark.parametrize("legacy", [False, True])
def test_unused_missing_capabilities_do_not_prevent_valid_callback(legacy):
    context = _context(lambda **kwargs: (None, False), legacy=legacy, source="external")
    assert context.schedule_external() == (None, False)


@pytest.mark.parametrize("legacy", [False, True])
def test_callback_replacement_invalidates_warm_binding(legacy):
    candidate = SimpleNamespace(_schedule_internal=lambda **kwargs: (None, False))
    context = ensure_dispatch_context(candidate) if legacy else ScheduleRunContext.from_legacy_scheduler(candidate)
    assert context.schedule_internal(op=1) == (None, False)
    callback = lambda *, required: None
    if legacy:
        candidate._schedule_internal = callback
    else:
        context.internal_callback = cast(Any, callback)
    with pytest.raises(DispatchContextContractError):
        context.schedule_internal(op=1)


@pytest.mark.parametrize("unknown_signature", [False, True])
@pytest.mark.parametrize("source", ["internal", "external"])
def test_upstream_schedule_wrapper_never_retries_contract_error(monkeypatch, unknown_signature, source):
    import core.services.scheduler.run.schedule_signature_support as support

    context = _context(lambda *, op: None, legacy=False, source=source)

    class Scheduler:
        def __init__(self):
            self.calls = 0

        def schedule(self, *, strict_mode=False, **kwargs):
            self.calls += 1
            return getattr(context, "schedule_" + source)(op=1, strict_mode=False, readiness_gate_enabled=False)

    scheduler = Scheduler()
    clear_strict_mode_support_cache_for_tests()
    if unknown_signature:
        original = support.inspect.signature

        def signature(callback, **kwargs):
            if getattr(callback, "__self__", None) is scheduler:
                raise ValueError("opaque schedule")
            return original(callback, **kwargs)

        monkeypatch.setattr(support.inspect, "signature", signature)
    with pytest.raises(DispatchContextContractError, match="schedule_" + source) as exc:
        schedule_with_optional_strict_mode(scheduler, strict_mode=True, readiness_gate_enabled=False)
    assert type(exc.value.__cause__) is TypeError
    assert scheduler.calls == 1
    clear_strict_mode_support_cache_for_tests()
