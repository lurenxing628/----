from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

from core.infrastructure.errors import ValidationError

from .active_preset_service import ActivePresetService
from .config_constants import (
    ACTIVE_PRESET_CUSTOM,
    ACTIVE_PRESET_REASON_MANUAL,
    BUILTIN_PRESET_DEFAULT,
)
from .config_field_spec import coerce_config_field, default_snapshot_values, get_field_spec
from .config_uow import ConfigWriteUnitOfWork
from .config_weight_policy import normalize_weight_triplet


class ConfigFieldMutationService:
    def __init__(
        self,
        *,
        uow: ConfigWriteUnitOfWork,
        active_service: ActivePresetService,
    ) -> None:
        self.uow = uow
        self.active_service = active_service

    @staticmethod
    def field_description(key: str) -> str:
        return get_field_spec(key).description

    @classmethod
    def registered_updates(cls, values: Dict[str, Any]) -> List[Tuple[str, str, str]]:
        return [(key, str(value), cls.field_description(key)) for key, value in values.items()]

    def _mark_custom_updates(self) -> List[Tuple[str, str, str]]:
        return self.active_service.active_preset_updates(
            ACTIVE_PRESET_CUSTOM,
            reason=ACTIVE_PRESET_REASON_MANUAL,
        )

    def set_fields_mark_custom(self, updates: Iterable[Tuple[str, Any]]) -> None:
        rows = [(key, str(value), self.field_description(key)) for key, value in updates]
        rows.extend(self._mark_custom_updates())
        with self.uow.tx_manager.transaction():
            self.uow.repo.set_batch(rows)

    def restore_default(self) -> None:
        updates = self.registered_updates(default_snapshot_values())
        updates.extend(self.active_service.active_preset_updates(BUILTIN_PRESET_DEFAULT))
        with self.uow.tx_manager.transaction():
            self.uow.repo.set_batch(updates)

    def set_strategy(self, sort_strategy: Any) -> None:
        value = str(
            coerce_config_field(
                "sort_strategy",
                sort_strategy,
                strict_mode=True,
                source="scheduler.config_service.set_strategy",
            )
        )
        self.set_fields_mark_custom([("sort_strategy", value)])

    def set_weights(self, priority_weight: Any, due_weight: Any, ready_weight: Any, require_sum_1: bool = True) -> None:
        priority, due, ready = normalize_weight_triplet(
            priority_weight,
            due_weight,
            ready_weight,
            require_sum_1=require_sum_1,
        )
        self.set_fields_mark_custom(
            [
                ("priority_weight", priority),
                ("due_weight", due),
                ("ready_weight", ready),
            ]
        )

    def set_dispatch(self, dispatch_mode: Any, dispatch_rule: Any) -> None:
        mode = str(
            coerce_config_field(
                "dispatch_mode",
                dispatch_mode,
                strict_mode=True,
                source="scheduler.config_service.set_dispatch",
            )
        )
        rule = str(
            coerce_config_field(
                "dispatch_rule",
                dispatch_rule,
                strict_mode=True,
                source="scheduler.config_service.set_dispatch",
            )
        )
        self.set_fields_mark_custom([("dispatch_mode", mode), ("dispatch_rule", rule)])

    def set_yes_no_field(self, field: str, value: Any, *, source: str) -> None:
        yes_no = str(
            coerce_config_field(
                field,
                value,
                strict_mode=True,
                source=source,
            )
        )
        self.set_fields_mark_custom([(field, yes_no)])

    def set_auto_assign_enabled(self, value: Any) -> None:
        self.set_yes_no_field(
            "auto_assign_enabled",
            value,
            source="scheduler.config_service.set_auto_assign_enabled",
        )

    def set_prefer_primary_skill(self, value: Any) -> None:
        self.set_yes_no_field(
            "prefer_primary_skill",
            value,
            source="scheduler.config_service.set_prefer_primary_skill",
        )

    def set_enforce_ready_default(self, value: Any) -> None:
        self.set_yes_no_field(
            "enforce_ready_default",
            value,
            source="scheduler.config_service.set_enforce_ready_default",
        )

    def set_algo_mode(self, value: Any) -> None:
        mode = str(
            coerce_config_field(
                "algo_mode",
                value,
                strict_mode=True,
                source="scheduler.config_service.set_algo_mode",
            )
        )
        self.set_fields_mark_custom([("algo_mode", mode)])

    def set_objective(self, value: Any) -> None:
        objective = str(
            coerce_config_field(
                "objective",
                value,
                strict_mode=True,
                source="scheduler.config_service.set_objective",
            )
        )
        self.set_fields_mark_custom([("objective", objective)])

    def set_ortools(self, enabled: Any, time_limit_seconds: Any) -> None:
        enabled_value = str(
            coerce_config_field(
                "ortools_enabled",
                enabled,
                strict_mode=True,
                source="scheduler.config_service.set_ortools",
            )
        )
        time_limit = int(
            coerce_config_field(
                "ortools_time_limit_seconds",
                time_limit_seconds,
                strict_mode=True,
                source="scheduler.config_service.set_ortools",
            )
        )
        self.set_fields_mark_custom(
            [
                ("ortools_enabled", enabled_value),
                ("ortools_time_limit_seconds", time_limit),
            ]
        )

    def set_holiday_default_efficiency(self, value: Any) -> None:
        if value is None or str(value).strip() == "":
            raise ValidationError("假期工作效率不能为空。", field="假期工作效率")
        efficiency = float(
            coerce_config_field(
                "holiday_default_efficiency",
                value,
                strict_mode=True,
                source="scheduler.config_service.set_holiday_default_efficiency",
            )
        )
        self.set_fields_mark_custom([("holiday_default_efficiency", float(efficiency))])

    def set_time_budget_seconds(self, value: Any) -> None:
        if value is None or str(value).strip() == "":
            raise ValidationError("计算时间上限不能为空。", field="计算时间上限")
        seconds = int(
            coerce_config_field(
                "time_budget_seconds",
                value,
                strict_mode=True,
                source="scheduler.config_service.set_time_budget_seconds",
            )
        )
        self.set_fields_mark_custom([("time_budget_seconds", seconds)])

    def set_freeze_window(self, enabled: Any, days: Any) -> None:
        enabled_value = str(
            coerce_config_field(
                "freeze_window_enabled",
                enabled,
                strict_mode=True,
                source="scheduler.config_service.set_freeze_window",
            )
        )
        days_value = int(
            coerce_config_field(
                "freeze_window_days",
                days,
                strict_mode=True,
                source="scheduler.config_service.set_freeze_window",
            )
        )
        self.set_fields_mark_custom(
            [
                ("freeze_window_enabled", enabled_value),
                ("freeze_window_days", days_value),
            ]
        )


__all__ = ["ConfigFieldMutationService"]
