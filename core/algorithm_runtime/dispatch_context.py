from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from types import FunctionType, MethodType
from typing import Any, Dict, FrozenSet, Set, Tuple

from core.algorithm_runtime.internal_slot import require_internal_hours


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


def dispatch_callback_binding(callback: Any) -> _CallbackBinding:
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
    # The callbacks are the scheduler's own bound methods (ScheduleRunContext.from_legacy_scheduler).
    binding = _CallbackBinding(inspect.signature(callback, follow_wrapped=False), version)
    if cache_key is not None:
        if len(_CALLBACK_BINDING_CACHE) >= _CALLBACK_CACHE_LIMIT:
            _CALLBACK_BINDING_CACHE.clear()
        _CALLBACK_BINDING_CACHE[cache_key] = binding
    return binding


def check_dispatch_callback_binding(binding: _CallbackBinding, args: Tuple[Any, ...], kwargs: Dict[str, Any], *, slot: str) -> None:
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


def validate_dispatch_internal_input(call_kwargs: Dict[str, Any]) -> None:
    missing = [name for name in ("op", "batch") if name not in call_kwargs]
    if missing:
        raise DispatchContextContractError("dispatch schedule_internal missing input: " + ", ".join(missing))
    require_internal_hours(call_kwargs["op"], call_kwargs["batch"])

