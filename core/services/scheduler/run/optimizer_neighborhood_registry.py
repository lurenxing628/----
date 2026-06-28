from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from core.infrastructure.errors import ValidationError

from .optimizer_neighborhood_moves import (
    ALLOWED_NEIGHBORHOODS,
    BOTTLENECK_MACHINE,
    CHANGEOVER_BLOCK,
    CRITICAL_CHAIN,
    RESOURCE_ALTERNATIVE,
    TARDY_WINDOW,
    TIME_WINDOW,
    NeighborhoodMove,
    bottleneck_machine_move,
    changeover_block_move,
    critical_chain_move,
    resource_alternative_move,
    tardy_window_move,
    time_window_move,
)

NEIGHBORHOOD_REGISTRY_SCHEMA_VERSION = 1

_GENERATOR_NAMES: Tuple[str, ...] = (
    CRITICAL_CHAIN,
    TARDY_WINDOW,
    BOTTLENECK_MACHINE,
    CHANGEOVER_BLOCK,
    RESOURCE_ALTERNATIVE,
    TIME_WINDOW,
)


def validate_neighborhood_name(name: Any) -> str:
    text = str(name or "").strip().lower()
    if text not in set(ALLOWED_NEIGHBORHOODS):
        raise ValidationError(
            f"未知业务邻域“{name}”，本阶段只允许：{', '.join(ALLOWED_NEIGHBORHOODS)}。",
            field="neighborhood",
        )
    return text


def validate_neighborhoods(names: Tuple[str, ...]) -> Tuple[str, ...]:
    out: List[str] = []
    for name in names:
        text = validate_neighborhood_name(name)
        if text not in out:
            out.append(text)
    return tuple(out)


def _generators() -> Dict[str, Callable[..., NeighborhoodMove]]:
    return {
        CRITICAL_CHAIN: lambda **kwargs: critical_chain_move(kwargs["order"], kwargs["results"]),
        TARDY_WINDOW: lambda **kwargs: tardy_window_move(kwargs["order"], kwargs["results"], kwargs["batches"]),
        BOTTLENECK_MACHINE: lambda **kwargs: bottleneck_machine_move(kwargs["order"], kwargs["results"]),
        CHANGEOVER_BLOCK: lambda **kwargs: changeover_block_move(kwargs["order"], kwargs["results"]),
        RESOURCE_ALTERNATIVE: lambda **kwargs: resource_alternative_move(kwargs["order"], kwargs["resource_pool"]),
        TIME_WINDOW: lambda **kwargs: time_window_move(kwargs["order"], kwargs["results"], kwargs["batches"]),
    }


def build_neighborhood_move(
    name: str,
    *,
    order: List[str],
    results: List[Any],
    batches: Dict[str, Any],
    resource_pool: Optional[Dict[str, Any]],
    rnd: Any,
) -> NeighborhoodMove:
    key = validate_neighborhood_name(name)
    generators = _generators()
    if key not in generators:
        raise ValidationError(
            f"业务邻域“{name}”没有注册生成器。",
            field="neighborhood",
        )
    return generators[key](
        order=list(order or []),
        results=list(results or []),
        batches=batches or {},
        resource_pool=resource_pool,
        rnd=rnd,
    )


def choose_neighborhood_move(
    *,
    order: List[str],
    neighborhoods: Tuple[str, ...],
    results: List[Any],
    batches: Dict[str, Any],
    resource_pool: Optional[Dict[str, Any]],
    rnd: Any,
) -> NeighborhoodMove:
    choices = validate_neighborhoods(neighborhoods or ALLOWED_NEIGHBORHOODS)
    if not choices:
        raise ValidationError("业务邻域列表不能为空。", field="neighborhood")
    index = int(rnd.randrange(len(choices))) if len(choices) > 1 else 0
    return build_neighborhood_move(
        choices[index],
        order=order,
        results=results,
        batches=batches,
        resource_pool=resource_pool,
        rnd=rnd,
    )


def registered_neighborhoods() -> Tuple[str, ...]:
    return _GENERATOR_NAMES


__all__ = [
    "NEIGHBORHOOD_REGISTRY_SCHEMA_VERSION",
    "build_neighborhood_move",
    "choose_neighborhood_move",
    "registered_neighborhoods",
    "validate_neighborhood_name",
    "validate_neighborhoods",
]
