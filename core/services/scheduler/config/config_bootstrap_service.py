from __future__ import annotations

from typing import List, Optional, Tuple

from core.services.common.safe_logging import safe_warning

from . import config_presets
from .active_preset_service import ActivePresetService
from .config_constants import (
    ACTIVE_PRESET_CUSTOM,
    ACTIVE_PRESET_REASON_BASELINE_DEGRADED,
    ACTIVE_PRESET_REASON_BASELINE_MISMATCH,
    BUILTIN_PRESET_NAMES,
)
from .config_field_spec import default_snapshot_values, list_config_fields
from .config_snapshot import ScheduleConfigSnapshot
from .config_uow import ConfigWriteUnitOfWork


class ConfigBootstrapService:
    """配置默认值与空库启动服务，不回调 ConfigService facade。"""

    def __init__(
        self,
        *,
        uow: ConfigWriteUnitOfWork,
        active_service: ActivePresetService,
    ) -> None:
        self.uow = uow
        self.active_service = active_service

    @staticmethod
    def default_snapshot() -> ScheduleConfigSnapshot:
        return ScheduleConfigSnapshot(**default_snapshot_values())

    def builtin_presets(self) -> List[Tuple[str, ScheduleConfigSnapshot, str]]:
        return config_presets.builtin_presets(self.default_snapshot())

    def is_pristine_store(self) -> bool:
        return int(self.uow.repo.count_all() or 0) == 0

    def bootstrap_registered_defaults(self, *, existing_keys: Optional[set] = None) -> set:
        existing = set(existing_keys) if existing_keys is not None else {c.config_key for c in self.uow.repo.list_all()}
        to_set: List[Tuple[str, str, str]] = []
        for spec in list_config_fields():
            if spec.key not in existing:
                to_set.append((spec.key, str(spec.default), spec.description))
        if not to_set:
            return existing
        with self.uow.tx_manager.transaction():
            self.uow.repo.set_batch(to_set)
        existing.update(key for key, _value, _description in to_set)
        return existing

    def ensure_builtin_presets(self, *, existing_keys: Optional[set] = None) -> None:
        keys = existing_keys if existing_keys is not None else {c.config_key for c in self.uow.repo.list_all()}
        presets_to_create: List[Tuple[str, str, str]] = []
        for name, snap, desc in self.builtin_presets():
            key = config_presets.preset_key(name)
            if key in keys:
                continue
            presets_to_create.append(
                (
                    key,
                    config_presets.dump_snapshot_payload(snap),
                    f"排产配置模板：{desc}",
                )
            )

        if not presets_to_create:
            return

        with self.uow.tx_manager.transaction():
            for key, value, description in presets_to_create:
                self.uow.repo.set(key, value, description=description)

    def bootstrap_active_provenance_if_pristine(self) -> None:
        active_value = None
        active_reason = None
        try:
            current = config_presets.get_snapshot_from_repo(self.uow.repo)
            default_snapshot = self.default_snapshot()
            if getattr(current, "degradation_counters", None):
                active_value = ACTIVE_PRESET_CUSTOM
                active_reason = ACTIVE_PRESET_REASON_BASELINE_DEGRADED
            elif config_presets.snapshot_close(current, default_snapshot):
                active_value = BUILTIN_PRESET_NAMES[0]
                active_reason = None
            else:
                active_value = ACTIVE_PRESET_CUSTOM
                active_reason = ACTIVE_PRESET_REASON_BASELINE_MISMATCH
        except Exception as exc:
            active_value = ACTIVE_PRESET_CUSTOM
            active_reason = f"{ACTIVE_PRESET_REASON_BASELINE_DEGRADED} 原因：{type(exc).__name__}"
            safe_warning(
                self.uow.logger,
                f"初始化 active_preset 基线探测失败，已标记为 degraded：{exc}",
            )

        with self.uow.tx_manager.transaction():
            self.uow.repo.set_batch(self.active_service.active_preset_updates(active_value, reason=active_reason))

    def ensure_defaults(self) -> None:
        if self.is_pristine_store():
            existing = self.bootstrap_registered_defaults(existing_keys=set())
            self.ensure_builtin_presets(existing_keys=existing)
            self.bootstrap_active_provenance_if_pristine()
            return
        existing = self.bootstrap_registered_defaults()
        self.ensure_builtin_presets(existing_keys=existing)

    def ensure_defaults_if_pristine(self) -> bool:
        if not self.is_pristine_store():
            return False
        self.ensure_defaults()
        return True


__all__ = ["ConfigBootstrapService"]
