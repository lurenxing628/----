from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from types import FunctionType, MethodType
from typing import Any, Dict, FrozenSet, Set, Tuple

from core.algorithm_runtime.algo_stats import ensure_algo_stats, increment_counter
from core.algorithm_runtime.auto_assign_contract import auto_assign_attempt_from_result
from core.algorithm_runtime.internal_slot import validate_internal_hours_for_mode


class DispatchContextContractError(TypeError):
    """Dispatch callback 缺失、签名失配或适配层输入不满足合同。"""


@dataclass
class _CallbackBinding:
    signature: inspect.Signature
    version: Tuple[Any, ...]
    shapes: Set[Tuple[int, FrozenSet[str]]] = field(default_factory=set)


_CALLBACK_BINDING_CACHE: Dict[Tuple[FunctionType, bool], _CallbackBinding] = {}
_CALLBACK_CACHE_LIMIT = 256
_CALL_SHAPE_CACHE_LIMIT = 128


def clear_dispatch_callback_binding_cache_for_tests() -> None:
    _CALLBACK_BINDING_CACHE.clear()


def _dispatch_callback_binding(callback: Any, *, slot: str) -> _CallbackBinding:
    bound = isinstance(callback, MethodType)
    function = callback.__func__ if bound else callback
    cache_key = None
    version: Tuple[Any, ...] = ()
    # Cache Python functions by identity and binding metadata; re-inspect other callables.
    # Do not retain bound instances or trust custom callable equality/hash methods.
    if isinstance(function, FunctionType):
        cache_key = (function, bound)
        version = (
            function.__code__, len(function.__defaults__ or ()),
            frozenset(function.__kwdefaults__ or ()), id(function.__dict__.get("__signature__")),
        )
        cached = _CALLBACK_BINDING_CACHE.get(cache_key)
        if cached is not None and cached.version == version:
            return cached
    try:
        signature = inspect.signature(callback, follow_wrapped=False)
    except (TypeError, ValueError) as exc:
        raise DispatchContextContractError(f"dispatch callback cannot inspect signature ({slot})") from exc
    binding = _CallbackBinding(signature, version)
    if cache_key is not None:
        if len(_CALLBACK_BINDING_CACHE) >= _CALLBACK_CACHE_LIMIT:
            _CALLBACK_BINDING_CACHE.clear()
        _CALLBACK_BINDING_CACHE[cache_key] = binding
    return binding


def check_dispatch_callback_binding(callback: Any, args: Tuple[Any, ...], kwargs: Dict[str, Any], *, slot: str) -> None:
    binding = _dispatch_callback_binding(callback, slot=slot)
    shape = (len(args), frozenset(kwargs))
    if shape in binding.shapes:
        return
    try:
        binding.signature.bind(*args, **kwargs)
    except TypeError as exc:
        # Keep callback execution outside this handler: body TypeError is business failure.
        # Do not embed bind's text here; upstream legacy wrappers match TypeError messages.
        raise DispatchContextContractError(f"dispatch callback signature mismatch ({slot})") from exc
    if len(binding.shapes) >= _CALL_SHAPE_CACHE_LIMIT:
        binding.shapes.clear()
    binding.shapes.add(shape)


def validate_dispatch_internal_input(call_kwargs: Dict[str, Any], *, strict_mode: bool) -> None:
    if not strict_mode:
        return
    missing = [name for name in ("op", "batch") if name not in call_kwargs]
    if missing:
        raise DispatchContextContractError("dispatch schedule_internal missing strict input: " + ", ".join(missing))
    validate_internal_hours_for_mode(call_kwargs["op"], call_kwargs["batch"], strict_mode=True)


class _LegacyDispatchContext:
    def __init__(self, candidate: Any) -> None:
        self._candidate = candidate
        self.calendar = getattr(candidate, "calendar", None)
        if self.calendar is None:
            self.calendar = getattr(candidate, "calendar_service", None)
        self.logger: Any = getattr(candidate, "logger", None)
        self.algo_stats = ensure_algo_stats(candidate)

    def increment(self, key: str, amount: int = 1, *, bucket: str = "fallback_counts") -> None:
        increment_counter(self.algo_stats, key, amount, bucket=bucket)

    def log_exception(self, message: str) -> None:
        try:
            self.logger.exception(message)
        except Exception:
            self.increment("dispatch_exception_log_failed_count")

    def schedule_external(self, *args: Any, **kwargs: Any):
        callback = getattr(self._candidate, "_schedule_external", None)
        if not callable(callback):
            raise DispatchContextContractError("legacy dispatch context does not provide _schedule_external")
        check_dispatch_callback_binding(callback, args, kwargs, slot="schedule_external")
        return callback(*args, **kwargs)

    def schedule_internal(self, *args: Any, **kwargs: Any):
        callback = getattr(self._candidate, "_schedule_internal", None)
        if not callable(callback):
            raise DispatchContextContractError("legacy dispatch context does not provide _schedule_internal")
        call_kwargs = dict(kwargs)
        strict_mode = bool(call_kwargs.pop("strict_mode", False))
        validate_dispatch_internal_input(call_kwargs, strict_mode=strict_mode)
        check_dispatch_callback_binding(callback, args, call_kwargs, slot="schedule_internal")
        return callback(*args, **call_kwargs)

    def auto_assign_internal_resources_attempt(self, *args: Any, **kwargs: Any):
        callback = getattr(self._candidate, "_auto_assign_internal_resources_attempt", None)
        if callable(callback):
            check_dispatch_callback_binding(callback, args, kwargs, slot="auto_assign_internal_resources_attempt")
            return auto_assign_attempt_from_result(callback(*args, **kwargs))
        callback = getattr(self._candidate, "_auto_assign_internal_resources", None)
        if callable(callback):
            check_dispatch_callback_binding(callback, args, kwargs, slot="auto_assign_internal_resources")
            return auto_assign_attempt_from_result(callback(*args, **kwargs))
        raise DispatchContextContractError("legacy dispatch context does not provide auto-assign callback")

    def auto_assign_internal_resources(self, *args: Any, **kwargs: Any):
        attempt = self.auto_assign_internal_resources_attempt(*args, **kwargs)
        if attempt.machine_id and attempt.operator_id:
            return attempt.machine_id, attempt.operator_id
        return None


def ensure_dispatch_context(candidate: Any) -> Any:
    required = ("schedule_external", "schedule_internal", "auto_assign_internal_resources_attempt", "increment", "log_exception")
    if all(callable(getattr(candidate, name, None)) for name in required):
        return candidate
    return _LegacyDispatchContext(candidate)
