from __future__ import annotations

import inspect
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from core.services.common.build_outcome import BuildOutcome


def _signature_supports_keyword_arg(signature: inspect.Signature, arg_name: str) -> bool:
    for parameter in signature.parameters.values():
        if parameter.kind == inspect.Parameter.VAR_KEYWORD:
            return True
        if parameter.name == arg_name and parameter.kind != inspect.Parameter.POSITIONAL_ONLY:
            return True
    return False


def _unsupported_keyword_args(signature: inspect.Signature, arg_names: tuple[str, ...]) -> List[str]:
    return [arg_name for arg_name in arg_names if not _signature_supports_keyword_arg(signature, arg_name)]


def _raise_keyword_contract_error(callable_name: str, *, arg_names: tuple[str, ...]) -> None:
    names = "、".join([str(arg_name).strip() for arg_name in arg_names if str(arg_name).strip()]) or "<empty>"
    raise TypeError(f"{callable_name} 必须支持关键字参数 {names}。")


def _ensure_callable_supports_keyword_args(
    callable_obj: Any,
    *,
    callable_name: str,
    arg_names: tuple[str, ...],
) -> None:
    try:
        signature = inspect.signature(callable_obj)
    except (TypeError, ValueError):
        return
    unsupported = tuple(_unsupported_keyword_args(signature, arg_names))
    if unsupported:
        _raise_keyword_contract_error(callable_name, arg_names=unsupported)


def _is_unexpected_keyword_argument_error(exc: TypeError, arg_name: str) -> bool:
    message = str(exc or "")
    return (
        f"unexpected keyword argument '{arg_name}'" in message
        or f'got an unexpected keyword argument "{arg_name}"' in message
        or f"got an unexpected keyword argument '{arg_name}'" in message
    )


def _call_build_algo_operations_fn(
    build_algo_operations_fn: Any,
    svc: Any,
    operations: List[Any],
    *,
    strict_mode: bool,
) -> Any:
    required_arg_names = ("strict_mode", "return_outcome")
    _ensure_callable_supports_keyword_args(
        build_algo_operations_fn,
        callable_name="build_algo_operations_fn",
        arg_names=required_arg_names,
    )
    try:
        return build_algo_operations_fn(
            svc,
            operations,
            strict_mode=bool(strict_mode),
            return_outcome=True,
        )
    except TypeError as exc:
        unsupported = tuple(
            arg_name for arg_name in required_arg_names if _is_unexpected_keyword_argument_error(exc, arg_name)
        )
        if unsupported:
            _raise_keyword_contract_error("build_algo_operations_fn", arg_names=unsupported)
        raise


def _build_algo_operations_outcome(
    build_algo_operations_fn: Any,
    svc: Any,
    operations: List[Any],
    *,
    strict_mode: bool,
) -> BuildOutcome[List[Any]]:
    outcome = _call_build_algo_operations_fn(
        build_algo_operations_fn,
        svc,
        operations,
        strict_mode=bool(strict_mode),
    )
    if not isinstance(outcome, BuildOutcome):
        raise TypeError("build_algo_operations_fn 在 return_outcome=True 时必须返回 BuildOutcome。")
    return outcome


def _build_freeze_window_seed_with_meta(
    build_freeze_window_seed_fn: Any,
    svc: Any,
    *,
    cfg: Any,
    prev_version: int,
    start_dt: datetime,
    operations: List[Any],
    reschedulable_operations: Optional[List[Any]],
    strict_mode: bool,
) -> tuple[Set[int], List[Dict[str, Any]], List[str], Dict[str, Any]]:
    freeze_meta: Dict[str, Any] = {}
    required_arg_names = ("cfg", "prev_version", "start_dt", "operations", "reschedulable_operations", "strict_mode", "meta")
    _ensure_callable_supports_keyword_args(
        build_freeze_window_seed_fn,
        callable_name="build_freeze_window_seed_fn",
        arg_names=required_arg_names,
    )
    try:
        result = build_freeze_window_seed_fn(
            svc,
            cfg=cfg,
            prev_version=prev_version,
            start_dt=start_dt,
            operations=operations,
            reschedulable_operations=reschedulable_operations,
            strict_mode=bool(strict_mode),
            meta=freeze_meta,
        )
    except TypeError as exc:
        unsupported = tuple(
            arg_name for arg_name in required_arg_names if _is_unexpected_keyword_argument_error(exc, arg_name)
        )
        if unsupported:
            _raise_keyword_contract_error("build_freeze_window_seed_fn", arg_names=unsupported)
        raise
    frozen_op_ids, seed_results, algo_warnings = result
    return set(frozen_op_ids or set()), list(seed_results or []), list(algo_warnings or []), freeze_meta
