from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Optional

from core.algorithm_contracts.date_parsers import due_exclusive
from core.algorithm_contracts.dispatch_rules import DispatchRuleSpec, parse_dispatch_rule_token
from core.algorithm_contracts.sort_strategies import WeightedParams
from core.models.enums import SortStrategy, YesNo


def used_params_record(
    *, strategy: SortStrategy, weights: Optional[WeightedParams], graph_ready_profile: Optional[Dict[str, Any]],
    dispatch_mode: str, dispatch_rule: str, auto_assign_enabled: bool,
) -> Dict[str, Any]:
    """The public record of the parameters a decode used (``used_params``), built only at its exits.

    The weighted strategy records its weights and no graph-ready profile; any other strategy records the
    profile it decoded under, if any. The decode record keeps the profile it was given; a published plan
    passes the profile's public projection.
    """
    record: Dict[str, Any] = {} if weights is None else weights.public_dict()
    if strategy != SortStrategy.WEIGHTED and graph_ready_profile is not None:
        record["graph_ready_profile"] = graph_ready_profile
    record["dispatch_mode"] = dispatch_mode
    record["dispatch_rule"] = dispatch_rule
    record["auto_assign_enabled"] = YesNo.YES.value if auto_assign_enabled else YesNo.NO.value
    return record


@dataclass(frozen=True)
class ScheduleParams:
    base_time: datetime
    end_dt_exclusive: datetime
    strategy: SortStrategy
    # Set exactly for the weighted strategy.
    weights: Optional[WeightedParams]
    graph_ready_profile: Optional[Dict[str, Any]]
    dispatch_mode_key: str
    dispatch_rule_spec: DispatchRuleSpec
    # Recorded in used_params; the decode itself reads its pool's ``enabled`` (the same value, resolved from it).
    auto_assign_enabled: bool

    @property
    def used_params(self) -> Dict[str, Any]:
        return used_params_record(
            strategy=self.strategy, weights=self.weights, graph_ready_profile=self.graph_ready_profile,
            dispatch_mode=self.dispatch_mode_key, dispatch_rule=self.dispatch_rule_spec.token,
            auto_assign_enabled=self.auto_assign_enabled,
        )


def resolve_schedule_params(
    *,
    auto_assign_enabled: bool,
    strategy: SortStrategy,
    strategy_params: Optional[WeightedParams],
    graph_ready_profile: Optional[Dict[str, Any]],
    start_dt: datetime,
    end_date: date,
    dispatch_mode: str,
    dispatch_rule: str,
) -> ScheduleParams:
    """One decode request's parameters; every value is an optimizer-owned choice, not configuration input."""
    return ScheduleParams(
        base_time=start_dt,
        # 9999-12-31 is the "no deadline" sentinel; due_exclusive maps it to datetime.max instead of overflowing.
        end_dt_exclusive=due_exclusive(end_date),
        strategy=strategy,
        weights=strategy_params,
        graph_ready_profile=graph_ready_profile,
        dispatch_mode_key=dispatch_mode,
        # The optimizer searches ATC k ladder tokens besides the three configured rules; one syntax, one parser.
        dispatch_rule_spec=parse_dispatch_rule_token(dispatch_rule),
        auto_assign_enabled=auto_assign_enabled,
    )
