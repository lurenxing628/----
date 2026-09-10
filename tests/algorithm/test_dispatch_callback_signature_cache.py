from __future__ import annotations

import gc
import inspect
import weakref
from functools import partial, wraps
from typing import Any

import pytest

import core.algorithm_runtime.dispatch_context as contract
from core.algorithm_runtime.dispatch_context import (
    DispatchContextContractError,
    check_dispatch_callback_binding,
    clear_dispatch_callback_binding_cache_for_tests,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_dispatch_callback_binding_cache_for_tests()
    yield
    clear_dispatch_callback_binding_cache_for_tests()


def _check(callback, *args, **kwargs):
    check_dispatch_callback_binding(callback, args, kwargs, slot="test_slot")


@pytest.mark.parametrize("callback,args,kwargs", [
    (lambda **kwargs: None, (), {"extra": 1}),
    (lambda *, op: None, (), {"op": 1}),
    (lambda op: None, (1,), {}),
    (lambda op, /: None, (1,), {}),
    (lambda *args, **kwargs: None, (1, 2), {"op": 1}),
    (partial(lambda op, *, batch: None, 1), (), {"batch": 2}),
    (len, ([1],), {}),
])
def test_legal_call_shapes_bind_without_execution(callback, args, kwargs):
    check_dispatch_callback_binding(callback, args, kwargs, slot="test_slot")


@pytest.mark.parametrize("args,kwargs", [((), {}), ((), {"unexpected": 1}), ((1, 2), {}), ((1,), {"op": 2})])
def test_binding_errors_keep_slot_and_original_cause(args, kwargs):
    with pytest.raises(DispatchContextContractError, match="test_slot") as exc:
        check_dispatch_callback_binding(lambda op: None, args, kwargs, slot="test_slot")
    assert type(exc.value.__cause__) is TypeError
    assert str(exc.value.__cause__)


def test_cache_separates_positional_count_and_keyword_names():
    def callback(op, *, batch):
        pytest.fail("bind must not execute the body")

    _check(callback, 1, batch=2)
    _check(callback, op=1, batch=2)
    for args, kwargs in [((), {"batch": 2}), ((1, 2), {"batch": 2}), ((1,), {"op": 2, "batch": 3})]:
        with pytest.raises(DispatchContextContractError):
            check_dispatch_callback_binding(callback, args, kwargs, slot="test_slot")


def test_bound_methods_share_signature_and_shape_cache_without_retaining_instances(monkeypatch):
    class Candidate:
        def callback(self, *, op, batch=None):
            return op

    counts = {"signature": 0, "bind": 0}
    original_signature, original_bind = inspect.signature, inspect.Signature.bind

    def signature(*args, **kwargs):
        counts["signature"] += 1
        return original_signature(*args, **kwargs)

    def bind(self, *args, **kwargs):
        counts["bind"] += 1
        return original_bind(self, *args, **kwargs)

    monkeypatch.setattr(contract.inspect, "signature", signature)
    monkeypatch.setattr(inspect.Signature, "bind", bind)
    candidate = Candidate()
    ref = weakref.ref(candidate)
    _check(candidate.callback, op=1)
    _check(Candidate().callback, op=2)
    _check(candidate.callback, op=3, batch=4)
    assert counts == {"signature": 1, "bind": 2}
    del candidate
    gc.collect()
    assert ref() is None
    clear_dispatch_callback_binding_cache_for_tests()
    _check(Candidate().callback, op=5)
    assert counts == {"signature": 2, "bind": 3}


@pytest.mark.parametrize("bound_first", [True, False])
def test_bound_and_unbound_same_function_do_not_share_signature(bound_first):
    class Candidate:
        def callback(self, *, op):
            return op

    bound, unbound = Candidate().callback, Candidate.callback
    if bound_first:
        _check(bound, op=1)
    else:
        _check(unbound, Candidate(), op=1)
    with pytest.raises(DispatchContextContractError):
        _check(unbound, op=1)
    _check(bound, op=1)
    _check(unbound, Candidate(), op=1)


def test_callable_instances_are_inspected_without_hash_or_equality_cache(monkeypatch):
    class Callable:
        __hash__: Any = None

        def __call__(self, *, op):
            pytest.fail("must not execute")

    original = inspect.signature
    calls = []

    def signature(*args, **kwargs):
        calls.append(args[0])
        return original(*args, **kwargs)

    monkeypatch.setattr(contract.inspect, "signature", signature)
    callback = Callable()
    _check(callback, op=1)
    _check(callback, op=2)
    assert len(calls) == 2
    with pytest.raises(DispatchContextContractError):
        _check(callback, batch=2)


def test_partial_keyword_mutation_is_rechecked():
    callback = partial(lambda *, op: None, op=1)
    _check(callback)
    callback.keywords.clear()
    with pytest.raises(DispatchContextContractError):
        _check(callback)


@pytest.mark.parametrize("metadata", ["code", "defaults", "kwdefaults", "signature"])
def test_function_signature_metadata_mutation_invalidates_cache(metadata):
    def default_callback(op=None):
        return op

    callback: Any = default_callback
    if metadata == "kwdefaults":
        callback = lambda *, op=None: op
    _check(callback)
    if metadata == "code":
        callback.__code__ = (lambda op, batch: op).__code__
    elif metadata == "defaults":
        callback.__defaults__ = None
    elif metadata == "kwdefaults":
        callback.__kwdefaults__.clear()
    else:
        callback.__signature__ = inspect.Signature([inspect.Parameter("batch", inspect.Parameter.KEYWORD_ONLY)])
    with pytest.raises(DispatchContextContractError):
        _check(callback)


def test_wrapped_callable_checks_actual_wrapper_binding():
    def wrapped(*, removed):
        return removed

    @wraps(wrapped)
    def wrapper(**kwargs):
        return kwargs

    _check(wrapper, op=1)
    assert wrapper(op=1) == {"op": 1}


@pytest.mark.parametrize("exception_type", [TypeError, ValueError])
def test_uninspectable_signature_fails_closed_with_cause(monkeypatch, exception_type):
    def signature(*args, **kwargs):
        raise exception_type("unexpected keyword argument 'strict_mode'")

    monkeypatch.setattr(contract.inspect, "signature", signature)
    with pytest.raises(DispatchContextContractError, match="cannot inspect signature") as exc:
        _check(lambda **kwargs: None)
    assert type(exc.value.__cause__) is exception_type
    assert "unexpected keyword argument" not in str(exc.value)


def test_function_and_shape_cache_sizes_are_bounded(monkeypatch):
    monkeypatch.setattr(contract, "_CALLBACK_CACHE_LIMIT", 2)
    monkeypatch.setattr(contract, "_CALL_SHAPE_CACHE_LIMIT", 2)
    callbacks = [lambda **kwargs: None for _ in range(4)]
    for callback in callbacks:
        _check(callback)
    assert len(contract._CALLBACK_BINDING_CACHE) <= 2
    for name in ("one", "two", "three", "four"):
        _check(callbacks[-1], **{name: 1})
    assert all(len(binding.shapes) <= 2 for binding in contract._CALLBACK_BINDING_CACHE.values())
