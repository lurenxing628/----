from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.transaction import TransactionManager
from core.services.common.normalize import normalize_text
from data.repositories.config_repo import ConfigRepository

from . import config_presets as preset_ops
from .active_preset_service import ActivePresetService
from .config_bootstrap_service import ConfigBootstrapService
from .config_constants import (
    ACTIVE_PRESET_CUSTOM,
    ACTIVE_PRESET_KEY,
    ACTIVE_PRESET_META_KEY,
    ACTIVE_PRESET_META_REASON_HIDDEN_REPAIR,
    ACTIVE_PRESET_META_REASON_MANUAL,
    ACTIVE_PRESET_META_REASON_VISIBLE_REPAIR,
    ACTIVE_PRESET_REASON_BASELINE_DEGRADED,
    ACTIVE_PRESET_REASON_BASELINE_MISMATCH,
    ACTIVE_PRESET_REASON_CUSTOM_SELECTED,
    ACTIVE_PRESET_REASON_HIDDEN_REPAIR,
    ACTIVE_PRESET_REASON_KEY,
    ACTIVE_PRESET_REASON_MANUAL,
    ACTIVE_PRESET_REASON_PRESET_ADJUSTED,
    ACTIVE_PRESET_REASON_PRESET_DELETED,
    ACTIVE_PRESET_REASON_PRESET_MISMATCH,
    ACTIVE_PRESET_REASON_VISIBLE_REPAIR,
    BUILTIN_PRESET_DEFAULT,
    BUILTIN_PRESET_DUE_FIRST,
    BUILTIN_PRESET_IMPROVE_SLOW,
    BUILTIN_PRESET_MIN_CHANGEOVER,
    CONFIG_PAGE_FIELDS,
    CONFIG_PAGE_HIDDEN_REPAIR_FIELDS,
    CONFIG_PAGE_VISIBLE_CHANGE_FIELDS,
    CONFIG_PAGE_WRITE_FIELDS,
    DEFAULT_ALGO_MODE,
    DEFAULT_AUTO_ASSIGN_ENABLED,
    DEFAULT_AUTO_ASSIGN_PERSIST,
    DEFAULT_DISPATCH_MODE,
    DEFAULT_DISPATCH_RULE,
    DEFAULT_DUE_WEIGHT,
    DEFAULT_ENFORCE_READY_DEFAULT,
    DEFAULT_FREEZE_WINDOW_DAYS,
    DEFAULT_FREEZE_WINDOW_ENABLED,
    DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY,
    DEFAULT_OBJECTIVE,
    DEFAULT_ORTOOLS_ENABLED,
    DEFAULT_ORTOOLS_TIME_LIMIT_SECONDS,
    DEFAULT_PRIORITY_WEIGHT,
    DEFAULT_READY_WEIGHT,
    DEFAULT_SORT_STRATEGY,
    DEFAULT_TIME_BUDGET_SECONDS,
    HOLIDAY_DEFAULT_EFFICIENCY_PAGE_WARNING_TEMPLATE,
    PRESET_PREFIX,
    STRATEGY_NAME_ZH,
    VALID_ALGO_MODES,
    VALID_DISPATCH_MODES,
    VALID_DISPATCH_RULES,
    VALID_OBJECTIVES,
    VALID_STRATEGIES,
)
from .config_field_spec import get_field_spec
from .config_page_outcome import ConfigPageSaveOutcome, public_config_field_label, public_config_field_labels
from .config_page_save_service import ConfigPageSaveService
from .config_preset_service import ConfigPresetService
from .config_read_service import ConfigReadService
from .config_snapshot import ScheduleConfigSnapshot
from .config_uow import ConfigWriteUnitOfWork
from .config_weight_policy import normalize_single_weight, normalize_weight_triplet
from .config_write_service import ConfigFieldMutationService


class ConfigService:
    """排产策略配置服务稳定 facade。"""

    PRESET_PREFIX = PRESET_PREFIX
    ACTIVE_PRESET_KEY = ACTIVE_PRESET_KEY
    ACTIVE_PRESET_REASON_KEY = ACTIVE_PRESET_REASON_KEY
    ACTIVE_PRESET_META_KEY = ACTIVE_PRESET_META_KEY
    ACTIVE_PRESET_CUSTOM = ACTIVE_PRESET_CUSTOM
    ACTIVE_PRESET_META_REASON_MANUAL = ACTIVE_PRESET_META_REASON_MANUAL
    ACTIVE_PRESET_META_REASON_VISIBLE_REPAIR = ACTIVE_PRESET_META_REASON_VISIBLE_REPAIR
    ACTIVE_PRESET_META_REASON_HIDDEN_REPAIR = ACTIVE_PRESET_META_REASON_HIDDEN_REPAIR
    BUILTIN_PRESET_DEFAULT = BUILTIN_PRESET_DEFAULT
    BUILTIN_PRESET_DUE_FIRST = BUILTIN_PRESET_DUE_FIRST
    BUILTIN_PRESET_MIN_CHANGEOVER = BUILTIN_PRESET_MIN_CHANGEOVER
    BUILTIN_PRESET_IMPROVE_SLOW = BUILTIN_PRESET_IMPROVE_SLOW
    ACTIVE_PRESET_REASON_MANUAL = ACTIVE_PRESET_REASON_MANUAL
    ACTIVE_PRESET_REASON_CUSTOM_SELECTED = ACTIVE_PRESET_REASON_CUSTOM_SELECTED
    ACTIVE_PRESET_REASON_PRESET_ADJUSTED = ACTIVE_PRESET_REASON_PRESET_ADJUSTED
    ACTIVE_PRESET_REASON_PRESET_MISMATCH = ACTIVE_PRESET_REASON_PRESET_MISMATCH
    ACTIVE_PRESET_REASON_PRESET_DELETED = ACTIVE_PRESET_REASON_PRESET_DELETED
    ACTIVE_PRESET_REASON_BASELINE_MISMATCH = ACTIVE_PRESET_REASON_BASELINE_MISMATCH
    ACTIVE_PRESET_REASON_BASELINE_DEGRADED = ACTIVE_PRESET_REASON_BASELINE_DEGRADED
    ACTIVE_PRESET_REASON_HIDDEN_REPAIR = ACTIVE_PRESET_REASON_HIDDEN_REPAIR
    ACTIVE_PRESET_REASON_VISIBLE_REPAIR = ACTIVE_PRESET_REASON_VISIBLE_REPAIR

    DEFAULT_SORT_STRATEGY = DEFAULT_SORT_STRATEGY
    DEFAULT_PRIORITY_WEIGHT = DEFAULT_PRIORITY_WEIGHT
    DEFAULT_DUE_WEIGHT = DEFAULT_DUE_WEIGHT
    DEFAULT_READY_WEIGHT = DEFAULT_READY_WEIGHT
    DEFAULT_ENFORCE_READY_DEFAULT = DEFAULT_ENFORCE_READY_DEFAULT
    DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY = DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY
    DEFAULT_DISPATCH_MODE = DEFAULT_DISPATCH_MODE
    DEFAULT_DISPATCH_RULE = DEFAULT_DISPATCH_RULE
    DEFAULT_AUTO_ASSIGN_ENABLED = DEFAULT_AUTO_ASSIGN_ENABLED
    DEFAULT_AUTO_ASSIGN_PERSIST = DEFAULT_AUTO_ASSIGN_PERSIST
    DEFAULT_ORTOOLS_ENABLED = DEFAULT_ORTOOLS_ENABLED
    DEFAULT_ORTOOLS_TIME_LIMIT_SECONDS = DEFAULT_ORTOOLS_TIME_LIMIT_SECONDS
    DEFAULT_ALGO_MODE = DEFAULT_ALGO_MODE
    DEFAULT_TIME_BUDGET_SECONDS = DEFAULT_TIME_BUDGET_SECONDS
    DEFAULT_OBJECTIVE = DEFAULT_OBJECTIVE
    DEFAULT_FREEZE_WINDOW_ENABLED = DEFAULT_FREEZE_WINDOW_ENABLED
    DEFAULT_FREEZE_WINDOW_DAYS = DEFAULT_FREEZE_WINDOW_DAYS
    HOLIDAY_DEFAULT_EFFICIENCY_PAGE_WARNING_TEMPLATE = HOLIDAY_DEFAULT_EFFICIENCY_PAGE_WARNING_TEMPLATE

    VALID_STRATEGIES = VALID_STRATEGIES
    VALID_ALGO_MODES = VALID_ALGO_MODES
    VALID_OBJECTIVES = VALID_OBJECTIVES
    VALID_DISPATCH_MODES = VALID_DISPATCH_MODES
    VALID_DISPATCH_RULES = VALID_DISPATCH_RULES
    STRATEGY_NAME_ZH = STRATEGY_NAME_ZH
    CONFIG_PAGE_FIELDS = CONFIG_PAGE_FIELDS
    CONFIG_PAGE_WRITE_FIELDS = CONFIG_PAGE_WRITE_FIELDS
    CONFIG_PAGE_VISIBLE_CHANGE_FIELDS = CONFIG_PAGE_VISIBLE_CHANGE_FIELDS
    CONFIG_PAGE_HIDDEN_REPAIR_FIELDS = CONFIG_PAGE_HIDDEN_REPAIR_FIELDS

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)
        self.repo = ConfigRepository(conn, logger=logger)
        self.uow = ConfigWriteUnitOfWork(self.repo, self.tx_manager, logger=logger, op_logger=op_logger)
        self.active_preset_service = ActivePresetService(self.uow)
        self.bootstrap_service = ConfigBootstrapService(
            uow=self.uow,
            active_service=self.active_preset_service,
        )
        self.preset_service = ConfigPresetService(
            uow=self.uow,
            active_service=self.active_preset_service,
            bootstrap_service=self.bootstrap_service,
        )
        self.read_service = ConfigReadService(
            uow=self.uow,
            active_service=self.active_preset_service,
            preset_service=self.preset_service,
            bootstrap_service=self.bootstrap_service,
        )
        self.mutation_service = ConfigFieldMutationService(
            uow=self.uow,
            active_service=self.active_preset_service,
        )
        self.page_save_service = ConfigPageSaveService(
            uow=self.uow,
            active_service=self.active_preset_service,
            read_service=self.read_service,
            mutation_service=self.mutation_service,
            bootstrap_service=self.bootstrap_service,
        )

    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        return normalize_text(value)

    @staticmethod
    def _normalize_weight(value: Any, field: str) -> float:
        return normalize_single_weight(value, field=field)

    @staticmethod
    def normalize_weight(value: Any, field: str) -> float:
        return ConfigService._normalize_weight(value, field=field)

    @staticmethod
    def _normalize_weights_triplet(
        priority_weight: Any,
        due_weight: Any,
        ready_weight: Any,
        *,
        require_sum_1: bool = True,
    ) -> Tuple[float, float, float]:
        return normalize_weight_triplet(
            priority_weight,
            due_weight,
            ready_weight,
            require_sum_1=require_sum_1,
        )

    @staticmethod
    def _field_description(key: str) -> str:
        return get_field_spec(key).description

    @classmethod
    def _registered_updates(cls, values: Dict[str, Any]) -> List[Tuple[str, str, str]]:
        return ConfigFieldMutationService.registered_updates(values)

    def _get_raw_value(self, config_key: str, default: Any = None) -> Any:
        return self.repo.get_value(str(config_key), default=None if default is None else str(default))

    def _bootstrap_registered_defaults(self, *, existing_keys: Optional[set] = None) -> set:
        return self.bootstrap_service.bootstrap_registered_defaults(existing_keys=existing_keys)

    def ensure_defaults(self) -> None:
        self.bootstrap_service.ensure_defaults()

    def _is_pristine_store(self) -> bool:
        return self.bootstrap_service.is_pristine_store()

    def _ensure_defaults_if_pristine(self) -> bool:
        return self.bootstrap_service.ensure_defaults_if_pristine()

    @classmethod
    def _preset_key(cls, name: str) -> str:
        return preset_ops.preset_key(name)

    @classmethod
    def _is_builtin_preset(cls, name: str) -> bool:
        return str(name or "").strip() in {
            cls.BUILTIN_PRESET_DEFAULT,
            cls.BUILTIN_PRESET_DUE_FIRST,
            cls.BUILTIN_PRESET_MIN_CHANGEOVER,
            cls.BUILTIN_PRESET_IMPROVE_SLOW,
        }

    @staticmethod
    def _default_snapshot() -> ScheduleConfigSnapshot:
        return ConfigBootstrapService.default_snapshot()

    def _builtin_presets(self) -> List[Tuple[str, ScheduleConfigSnapshot, str]]:
        return self.preset_service.builtin_presets()

    @staticmethod
    def _snapshot_close(a: ScheduleConfigSnapshot, b: ScheduleConfigSnapshot) -> bool:
        return preset_ops.snapshot_close(a, b)

    def _ensure_builtin_presets(self, existing_keys: Optional[set] = None) -> None:
        self.bootstrap_service.ensure_builtin_presets(existing_keys=existing_keys)

    def _get_snapshot_from_repo(self, *, strict_mode: bool = False) -> ScheduleConfigSnapshot:
        return self.preset_service.get_snapshot_from_repo(strict_mode=bool(strict_mode))

    @classmethod
    def _extract_repair_fields(cls, reason: str) -> List[str]:
        return ActivePresetService.extract_repair_fields(reason)

    @classmethod
    def _repair_notice_from_reason(cls, reason: str) -> Dict[str, Any]:
        return ActivePresetService.repair_notice_from_reason(reason)

    @classmethod
    def _normalize_repair_notice(cls, notice: Any) -> Optional[Dict[str, Any]]:
        return ActivePresetService.normalize_repair_notice(notice)

    @classmethod
    def _active_preset_meta_reason_codes(cls) -> Tuple[str, str, str]:
        return ActivePresetService.meta_reason_codes()

    @classmethod
    def _active_preset_meta_payload(
        cls,
        *,
        reason_code: Optional[str],
        repair_notices: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        return ActivePresetService.meta_payload(reason_code=reason_code, repair_notices=repair_notices)

    @classmethod
    def _legacy_active_preset_meta_from_reason(cls, reason: Optional[str]) -> Dict[str, Any]:
        return ActivePresetService.legacy_meta_from_reason(reason)

    @classmethod
    def _active_preset_meta_from_value(
        cls,
        value: Any,
        *,
        reason_fallback: Optional[str] = None,
    ) -> Dict[str, Any]:
        return ActivePresetService.meta_from_value(value, reason_fallback=reason_fallback)

    @classmethod
    def _active_preset_meta_parse_warning(cls, value: Any) -> Optional[Dict[str, Any]]:
        return ActivePresetService.meta_parse_warning(value)

    @classmethod
    def _serialize_active_preset_meta(cls, meta: Optional[Dict[str, Any]]) -> str:
        return ActivePresetService.serialize_meta(meta)

    @classmethod
    def _reason_in(cls, reason: str, *candidates: str) -> bool:
        return ConfigReadService.reason_in(reason, *candidates)

    def _active_preset_updates(
        self,
        name: Optional[str],
        reason: Optional[str] = None,
        *,
        meta: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, str, str]]:
        return self.active_preset_service.active_preset_updates(name, reason=reason, meta=meta)

    def _set_active_preset(self, name: Optional[str], *, reason: Optional[str] = None) -> None:
        self.active_preset_service.set_active_preset(name, reason=reason)

    def mark_active_preset_custom(self, reason: Optional[str] = None) -> None:
        self.active_preset_service.mark_custom(reason=reason)

    def get_active_preset(self) -> Optional[str]:
        return self.active_preset_service.get_active_preset()

    def get_active_preset_reason(self) -> Optional[str]:
        return self.active_preset_service.get_active_preset_reason()

    def get_active_preset_meta(self) -> Dict[str, Any]:
        return self.active_preset_service.get_active_preset_meta()

    def get_preset_display_state(
        self,
        *,
        readonly: bool = True,
        current_snapshot: Optional[ScheduleConfigSnapshot] = None,
    ) -> Dict[str, Any]:
        return self.read_service.get_preset_display_state(readonly=readonly, current_snapshot=current_snapshot)

    def list_presets(self) -> List[Dict[str, Any]]:
        return self.read_service.list_presets()

    def save_preset(self, name: Any) -> Dict[str, Any]:
        return self.preset_service.save_preset(name)

    def delete_preset(self, name: Any) -> None:
        self.preset_service.delete_preset(name)

    def _normalize_preset_snapshot(self, data: Dict[str, Any]) -> ScheduleConfigSnapshot:
        return self.preset_service.normalize_preset_snapshot(data)

    def apply_preset(self, name: Any) -> Dict[str, Any]:
        return self.preset_service.apply_preset(name)

    def get(self, config_key: str) -> Any:
        return self.read_service.get(config_key)

    def _get_registered_field_value(self, key: str, *, strict_mode: bool, source: str) -> Any:
        return self.read_service.get_registered_field_value(key, strict_mode=strict_mode, source=source)

    def get_holiday_default_efficiency(self, *, strict_mode: bool = True) -> float:
        return self.read_service.get_holiday_default_efficiency(strict_mode=strict_mode)

    def get_holiday_default_efficiency_display_state(
        self,
        *,
        consumer: str = "页面",
        logger: Any = None,
    ) -> Tuple[float, bool, Optional[str]]:
        return self.read_service.get_holiday_default_efficiency_display_state(consumer=consumer, logger=logger)

    def get_available_strategies(self) -> List[Dict[str, str]]:
        return self.read_service.get_available_strategies()

    def get_snapshot(self, *, strict_mode: bool = False) -> ScheduleConfigSnapshot:
        return self.read_service.get_snapshot(strict_mode=strict_mode)

    @staticmethod
    def get_page_metadata(keys: List[str]) -> Dict[str, Any]:
        return ConfigReadService.get_page_metadata(keys)

    @staticmethod
    def get_field_label(key: str) -> str:
        return ConfigReadService.get_field_label(key)

    @staticmethod
    def get_choice_labels(key: str) -> Dict[str, str]:
        return ConfigReadService.get_choice_labels(key)

    @staticmethod
    def public_config_field_label(field: str) -> str:
        return public_config_field_label(field)

    @staticmethod
    def public_config_field_labels(fields: List[str]) -> List[str]:
        return public_config_field_labels(fields)

    def save_page_config(self, form_values: Any) -> ConfigPageSaveOutcome:
        return self.page_save_service.save_page_config(form_values)

    def set_strategy(self, sort_strategy: Any) -> None:
        self.mutation_service.set_strategy(sort_strategy)

    def set_weights(self, priority_weight: Any, due_weight: Any, ready_weight: Any, require_sum_1: bool = True) -> None:
        self.mutation_service.set_weights(priority_weight, due_weight, ready_weight, require_sum_1=require_sum_1)

    def restore_default(self) -> None:
        self.mutation_service.restore_default()

    def set_dispatch(self, dispatch_mode: Any, dispatch_rule: Any) -> None:
        self.mutation_service.set_dispatch(dispatch_mode, dispatch_rule)

    def set_auto_assign_enabled(self, value: Any) -> None:
        self.mutation_service.set_auto_assign_enabled(value)

    def set_ortools(self, enabled: Any, time_limit_seconds: Any) -> None:
        self.mutation_service.set_ortools(enabled, time_limit_seconds)

    def set_prefer_primary_skill(self, value: Any) -> None:
        self.mutation_service.set_prefer_primary_skill(value)

    def set_enforce_ready_default(self, value: Any) -> None:
        self.mutation_service.set_enforce_ready_default(value)

    def set_holiday_default_efficiency(self, value: Any) -> None:
        self.mutation_service.set_holiday_default_efficiency(value)

    def set_algo_mode(self, value: Any) -> None:
        self.mutation_service.set_algo_mode(value)

    def set_time_budget_seconds(self, value: Any) -> None:
        self.mutation_service.set_time_budget_seconds(value)

    def set_objective(self, value: Any) -> None:
        self.mutation_service.set_objective(value)

    def set_freeze_window(self, enabled: Any, days: Any) -> None:
        self.mutation_service.set_freeze_window(enabled, days)


__all__ = ["ConfigService"]
