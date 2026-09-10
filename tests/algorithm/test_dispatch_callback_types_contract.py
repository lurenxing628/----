"""Runtime and annotation contracts for typed dispatch callbacks."""

from __future__ import annotations

import ast
import inspect
import textwrap
from datetime import datetime
from types import SimpleNamespace
from typing import get_args, get_type_hints

import pytest

from core.algorithm_runtime.dispatch_callback_types import (
    AutoAssignAttemptCallback,
    AutoAssignCallback,
    ExternalScheduleCallback,
    InternalScheduleCallback,
)
from core.algorithm_runtime.dispatch_context import DispatchContextContractError, ensure_dispatch_context
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithms.greedy.auto_assign import auto_assign_internal_resources, auto_assign_internal_resources_attempt
from core.algorithms.greedy.dispatch.batch_order import _schedule_op
from core.algorithms.greedy.dispatch.sgs_scoring import _auto_assign_attempt_for_scoring
from core.algorithms.greedy.external_groups import schedule_external
from core.algorithms.greedy.internal_operation import _resolve_internal_resources, schedule_internal_operation
from core.algorithms.greedy.run_context import ScheduleRunContext
from core.algorithms.greedy.scheduler import GreedyScheduler

_INTERNAL = {
    "op", "batch", "batch_progress", "machine_timeline", "operator_timeline", "base_time", "errors",
    "end_dt_exclusive", "machine_downtimes", "auto_assign_enabled", "resource_pool",
    "last_op_type_by_machine", "machine_busy_hours", "operator_busy_hours",
}
_EXTERNAL = {"op", "batch", "batch_progress", "external_group_cache", "base_time", "errors", "end_dt_exclusive", "strict_mode"}
_AUTO_ASSIGN = (_INTERNAL - {"errors", "auto_assign_enabled"}) | {"probe_only"}


def _tree(function):
    return ast.parse(textwrap.dedent(inspect.getsource(function)))


def _call_keyword_names(function, name):
    calls = [
        node for node in ast.walk(_tree(function))
        if isinstance(node, ast.Call)
        and ((isinstance(node.func, ast.Attribute) and node.func.attr == name)
             or (isinstance(node.func, ast.Name) and node.func.id == name))
    ]
    assert len(calls) == 1
    assert all(kw.arg is not None for kw in calls[0].keywords)
    return {kw.arg for kw in calls[0].keywords}


@pytest.mark.parametrize("protocol,field,expected", [
    (InternalScheduleCallback, "internal_callback", _INTERNAL),
    (ExternalScheduleCallback, "external_callback", _EXTERNAL),
    (AutoAssignCallback, "auto_assign_callback", _AUTO_ASSIGN),
    (AutoAssignAttemptCallback, "auto_assign_attempt_callback", _AUTO_ASSIGN),
])
def test_callback_protocol_fields_match_frozen_keyword_contract(protocol, field, expected):
    parameters = dict(inspect.signature(protocol.__call__).parameters)
    del parameters["self"]
    assert set(parameters) == expected
    assert all(p.kind == inspect.Parameter.KEYWORD_ONLY for p in parameters.values())
    assert protocol in get_args(get_type_hints(ScheduleRunContext)[field])


def test_dispatch_keywords_protocols_scheduler_and_fallbacks_agree():
    assert _call_keyword_names(_schedule_op, "schedule_internal") == _INTERNAL | {"strict_mode"}
    assert _call_keyword_names(_schedule_op, "schedule_external") == _EXTERNAL
    scheduler = object.__new__(GreedyScheduler)
    for names, callback in [(_INTERNAL, scheduler._schedule_internal), (_EXTERNAL, scheduler._schedule_external)]:
        inspect.signature(callback).bind(**dict.fromkeys(names))
    internal = inspect.signature(scheduler._schedule_internal)
    assert set(internal.parameters) == _INTERNAL | {"strict_mode"}
    assert internal.parameters["strict_mode"].default is False
    assert set(inspect.signature(scheduler._schedule_external).parameters) == _EXTERNAL
    inspect.signature(schedule_internal_operation).bind(
        **dict.fromkeys(_INTERNAL), calendar=None, algo_stats={}, auto_assign_resources=None, strict_mode=True,
    )
    inspect.signature(schedule_external).bind(object(), **dict.fromkeys(_EXTERNAL))


def test_auto_assign_probe_and_commit_keywords_match_both_scheduler_callbacks():
    assignments = [
        node.value for node in ast.walk(_tree(_auto_assign_attempt_for_scoring))
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "kwargs" for target in node.targets)
    ]
    assert len(assignments) == 1 and isinstance(assignments[0], ast.Dict)
    keys = assignments[0].keys
    assert all(isinstance(key, ast.Constant) for key in keys)
    assert {key.value for key in keys if isinstance(key, ast.Constant)} == _AUTO_ASSIGN
    assert _call_keyword_names(_resolve_internal_resources, "auto_assign_resources") == _AUTO_ASSIGN - {"probe_only"}
    scheduler = object.__new__(GreedyScheduler)
    for callback in [scheduler._auto_assign_internal_resources, scheduler._auto_assign_internal_resources_attempt]:
        signature = inspect.signature(callback)
        assert set(signature.parameters) == _AUTO_ASSIGN
        assert signature.parameters["probe_only"].default is False
        signature.bind(**dict.fromkeys(_AUTO_ASSIGN))
        signature.bind(**dict.fromkeys(_AUTO_ASSIGN - {"probe_only"}))
    for fallback in [auto_assign_internal_resources, auto_assign_internal_resources_attempt]:
        inspect.signature(fallback).bind(**dict.fromkeys(_AUTO_ASSIGN), calendar=None, algo_stats={})


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("attempt_slot", [False, True])
def test_auto_assign_probe_and_commit_preserve_exact_keys(legacy, attempt_slot):
    calls = []

    def callback(**kwargs):
        calls.append(kwargs)
        return "M1", "O1"

    name = "_auto_assign_internal_resources" + ("_attempt" if attempt_slot else "")
    candidate = SimpleNamespace(**{name: callback})
    context = ensure_dispatch_context(candidate) if legacy else ScheduleRunContext.from_legacy_scheduler(candidate)
    state = ScheduleRunState(base_time=datetime(2026, 1, 1))
    attempt = _auto_assign_attempt_for_scoring(
        context, state=state, op=object(), batch=object(), end_dt_exclusive=None, machine_downtimes=None, resource_pool={},
    )
    assert (attempt.machine_id, attempt.operator_id) == ("M1", "O1")
    assert set(calls[0]) == _AUTO_ASSIGN and calls[0]["probe_only"] is True
    commit_kwargs = dict(calls[0])
    commit_kwargs.pop("probe_only")
    assert context.auto_assign_internal_resources(**commit_kwargs) == ("M1", "O1")
    assert calls[1] == commit_kwargs


@pytest.mark.parametrize("legacy", [False, True])
def test_scoring_probe_signature_drift_fails_loud(legacy):
    candidate = SimpleNamespace(_auto_assign_internal_resources_attempt=lambda *, removed: None)
    context = ensure_dispatch_context(candidate) if legacy else ScheduleRunContext.from_legacy_scheduler(candidate)
    with pytest.raises(DispatchContextContractError, match="auto_assign_internal_resources_attempt"):
        _auto_assign_attempt_for_scoring(
            context, state=ScheduleRunState(base_time=datetime(2026, 1, 1)), op=object(), batch=object(),
            end_dt_exclusive=None, machine_downtimes=None, resource_pool={},
        )
