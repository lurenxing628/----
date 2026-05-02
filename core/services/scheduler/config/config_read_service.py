from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import ValidationError
from core.services.common.safe_logging import safe_warning

from . import config_presets as preset_ops
from .active_preset_service import ActivePresetService
from .active_preset_state import BaselineResolution, CurrentConfigDisplayState, PageSaveProvenanceState
from .config_bootstrap_service import ConfigBootstrapService
from .config_constants import (
    ACTIVE_PRESET_CUSTOM,
    ACTIVE_PRESET_META_KEY,
    ACTIVE_PRESET_REASON_BASELINE_DEGRADED,
    ACTIVE_PRESET_REASON_BASELINE_MISMATCH,
    ACTIVE_PRESET_REASON_CUSTOM_SELECTED,
    ACTIVE_PRESET_REASON_HIDDEN_REPAIR,
    ACTIVE_PRESET_REASON_MANUAL,
    ACTIVE_PRESET_REASON_PRESET_ADJUSTED,
    ACTIVE_PRESET_REASON_PRESET_DELETED,
    ACTIVE_PRESET_REASON_PRESET_MISMATCH,
    ACTIVE_PRESET_REASON_VISIBLE_REPAIR,
    BUILTIN_PRESET_NAMES,
    CONFIG_PAGE_HIDDEN_REPAIR_FIELDS,
    HOLIDAY_DEFAULT_EFFICIENCY_PAGE_WARNING_TEMPLATE,
)
from .config_field_spec import (
    MISSING_POLICY_ERROR,
    choice_label_map_for,
    choices_for,
    coerce_config_field,
    default_snapshot_values,
    field_label_for,
    list_config_fields,
    page_metadata_for,
)
from .config_page_outcome import (
    public_active_preset_reason,
    public_adjusted_reason_label,
    public_config_notice,
    public_config_notices,
)
from .config_preset_service import ConfigPresetService
from .config_snapshot import ScheduleConfigSnapshot
from .config_uow import ConfigWriteUnitOfWork


class ConfigReadService:
    def __init__(
        self,
        *,
        uow: ConfigWriteUnitOfWork,
        active_service: ActivePresetService,
        preset_service: ConfigPresetService,
        bootstrap_service: ConfigBootstrapService,
    ) -> None:
        self.uow = uow
        self.active_service = active_service
        self.preset_service = preset_service
        self.bootstrap_service = bootstrap_service

    @staticmethod
    def values_equal(left: Any, right: Any) -> bool:
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return abs(float(left) - float(right)) <= 1e-9
        return left == right

    def get(self, config_key: str) -> Any:
        return self.uow.repo.get_value(str(config_key), default=None)

    def get_snapshot(self, *, strict_mode: bool = False) -> ScheduleConfigSnapshot:
        if not bool(strict_mode):
            self.bootstrap_service.ensure_defaults_if_pristine()
        return self.preset_service.get_snapshot_from_repo(strict_mode=bool(strict_mode))

    def get_registered_field_value(self, key: str, *, strict_mode: bool, source: str) -> Any:
        if not bool(strict_mode):
            return getattr(self.get_snapshot(strict_mode=False), key)

        self.bootstrap_service.ensure_defaults_if_pristine()
        raw_value = self.uow.repo.get_value(str(key), default=None)
        return coerce_config_field(
            key,
            raw_value,
            strict_mode=True,
            source=source,
            missing=(raw_value is None),
            missing_policy=MISSING_POLICY_ERROR,
        )

    def get_holiday_default_efficiency(self, *, strict_mode: bool = True) -> float:
        return float(
            self.get_registered_field_value(
                "holiday_default_efficiency",
                strict_mode=bool(strict_mode),
                source="scheduler.config_service.get_holiday_default_efficiency",
            )
        )

    def get_holiday_default_efficiency_display_state(
        self,
        *,
        consumer: str = "页面",
        logger: Any = None,
    ) -> Tuple[float, bool, Optional[str]]:
        snapshot = self.get_snapshot(strict_mode=False)
        value = float(snapshot.holiday_default_efficiency)
        degraded = any(
            isinstance(event, dict) and str((event or {}).get("field") or "").strip() == "holiday_default_efficiency"
            for event in (snapshot.degradation_events or ())
        )
        if not degraded:
            return value, False, None
        safe_warning(logger if logger is not None else self.uow.logger, f"{consumer}读取假期工作效率配置失败，页面先按默认值展示：{value:g}")
        return value, True, HOLIDAY_DEFAULT_EFFICIENCY_PAGE_WARNING_TEMPLATE.format(value=value)

    @staticmethod
    def get_available_strategies() -> List[Dict[str, str]]:
        labels = choice_label_map_for("sort_strategy")
        return [{"key": key, "name": labels.get(key, key)} for key in choices_for("sort_strategy")]

    @staticmethod
    def get_page_metadata(keys: List[str]) -> Dict[str, Any]:
        return page_metadata_for(keys)

    @staticmethod
    def get_field_label(key: str) -> str:
        return field_label_for(key)

    @staticmethod
    def get_choice_labels(key: str) -> Dict[str, str]:
        return choice_label_map_for(key)

    def list_config_rows(self, *, readonly: bool = True) -> List[Any]:
        if not bool(readonly):
            self.bootstrap_service.ensure_defaults()
        return list(self.uow.repo.list_all())

    @staticmethod
    def collect_preset_rows(rows: List[Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        by_key = {str(row.config_key or ""): row for row in rows}
        preset_rows: Dict[str, Any] = {}
        for row in rows:
            config_key = str(row.config_key or "")
            if not config_key.startswith(preset_ops.preset_key("")):
                continue
            name = config_key[len(preset_ops.preset_key("")) :].strip()
            if name:
                preset_rows[name] = row
        return by_key, preset_rows

    def build_preset_entries(self, preset_rows: Dict[str, Any]) -> List[Dict[str, Any]]:
        custom_presets = dict(preset_rows)
        presets: List[Dict[str, Any]] = []
        for name, _snapshot, description in self.preset_service.builtin_presets():
            row = custom_presets.pop(name, None)
            presets.append(
                {
                    "name": name,
                    "updated_at": getattr(row, "updated_at", None),
                    "config_key": self.preset_service.preset_key(name),
                    "description": getattr(row, "description", None) or description,
                }
            )
        for name in sorted(custom_presets):
            row = custom_presets[name]
            presets.append(
                {
                    "name": name,
                    "updated_at": getattr(row, "updated_at", None),
                    "config_key": getattr(row, "config_key", self.preset_service.preset_key(name)),
                    "description": getattr(row, "description", None),
                }
            )
        return presets

    def baseline_probe_state(
        self,
        *,
        current_snapshot: ScheduleConfigSnapshot,
        active_text: str,
        provenance_missing: bool,
    ) -> BaselineResolution:
        if provenance_missing or not active_text or active_text.lower() == ACTIVE_PRESET_CUSTOM:
            return BaselineResolution()
        baseline_snapshot, baseline_probe_failed = self.preset_service.try_load_preset_snapshot_for_baseline(active_text)
        if baseline_snapshot is None:
            return BaselineResolution(baseline_probe_failed=bool(baseline_probe_failed))
        return BaselineResolution(
            baseline_probe_failed=False,
            baseline_diff_fields=preset_ops.snapshot_diff_fields(current_snapshot, baseline_snapshot),
        )

    @staticmethod
    def resolve_current_config_baseline(
        *,
        active_text: str,
        provenance_missing: bool,
    ) -> Dict[str, Any]:
        is_custom = active_text.lower() == ACTIVE_PRESET_CUSTOM if active_text else False
        baseline_key = active_text or None
        if provenance_missing:
            if active_text and not is_custom:
                return {
                    "baseline_key": baseline_key,
                    "baseline_label": active_text,
                    "baseline_source": "builtin" if active_text in BUILTIN_PRESET_NAMES else "named",
                    "is_custom": False,
                }
            return {
                "baseline_key": baseline_key,
                "baseline_label": "基线未记录",
                "baseline_source": "unknown",
                "is_custom": bool(is_custom),
            }
        if is_custom:
            return {
                "baseline_key": baseline_key,
                "baseline_label": "自定义",
                "baseline_source": "custom",
                "is_custom": True,
            }
        return {
            "baseline_key": baseline_key,
            "baseline_label": active_text,
            "baseline_source": "builtin" if active_text in BUILTIN_PRESET_NAMES else "named",
            "is_custom": False,
        }

    @staticmethod
    def missing_provenance_descriptor(baseline_label: str) -> Tuple[str, str, str]:
        if baseline_label and baseline_label != "基线未记录":
            return (
                "degraded",
                "基线记录不完整",
                f"当前运行配置已知基线“{baseline_label}”，但缺少 provenance 记录；无法确认是否完全一致。",
            )
        return (
            "degraded",
            "基线未记录",
            "当前运行配置缺少基线记录，无法确认与任何方案的一致性；请显式保存或重新应用方案。",
        )

    @staticmethod
    def reason_in(reason: str, *candidates: str) -> bool:
        return any(candidate and candidate in reason for candidate in candidates)

    @classmethod
    def current_config_manual_reason(cls, reason: str) -> bool:
        return cls.reason_in(
            reason,
            ACTIVE_PRESET_REASON_MANUAL,
            ACTIVE_PRESET_REASON_CUSTOM_SELECTED,
            ACTIVE_PRESET_REASON_PRESET_DELETED,
            ACTIVE_PRESET_REASON_BASELINE_MISMATCH,
            ACTIVE_PRESET_REASON_BASELINE_DEGRADED,
            ACTIVE_PRESET_REASON_VISIBLE_REPAIR,
        )

    @classmethod
    def resolve_current_config_descriptor(
        cls,
        *,
        provenance_missing: bool,
        degraded: bool,
        baseline_probe_failed: bool,
        baseline_drifted: bool,
        is_custom: bool,
        baseline_label: str,
        reason: str,
        repair_notice: Dict[str, Any],
    ) -> Tuple[str, str, str]:
        if provenance_missing:
            return cls.missing_provenance_descriptor(baseline_label)
        if baseline_probe_failed:
            return (
                "adjusted",
                "基线不可验证",
                f"当前运行配置引用的方案“{baseline_label}”已不可读取，无法确认是否完全一致。",
            )
        if baseline_drifted:
            return (
                "adjusted",
                "与方案有差异",
                public_adjusted_reason_label(reason) or f"当前运行配置与“{baseline_label}”存在差异。",
            )
        if cls.reason_in(reason, ACTIVE_PRESET_REASON_PRESET_ADJUSTED, ACTIVE_PRESET_REASON_PRESET_MISMATCH):
            return (
                "adjusted",
                "与方案有差异",
                public_adjusted_reason_label(reason) or f"当前运行配置与“{baseline_label}”存在差异。",
            )
        if degraded:
            if is_custom:
                return (
                    "degraded",
                    "需要复核",
                    "当前运行配置有需要复核的设置，但仍以手动设置为准；请检查后保存一次。",
                )
            return (
                "degraded",
                "需要复核",
                f"当前运行配置有需要复核的设置，不能视为与“{baseline_label}”完全一致；请检查后保存一次。",
            )
        if is_custom or cls.current_config_manual_reason(reason):
            return (
                "custom",
                "手动设置",
                reason or "当前运行配置以手动设置为准。",
            )
        label = f"当前运行配置与“{baseline_label}”一致。"
        repair_message = str(repair_notice.get("message") or "").strip()
        if repair_notice.get("kind") == "hidden" and repair_message:
            label = f"{label} {repair_message}".strip()
        return "exact", "与方案一致", label

    def build_current_config_state(
        self,
        *,
        current_snapshot: ScheduleConfigSnapshot,
        active_preset: Optional[str],
        active_preset_reason: Optional[str],
        active_preset_meta: Optional[Dict[str, Any]],
        active_preset_missing: bool,
        active_preset_reason_missing: bool,
        provenance_missing: bool,
        baseline_diff_fields: Optional[List[str]] = None,
        baseline_probe_failed: bool = False,
    ) -> CurrentConfigDisplayState:
        active_text = str(active_preset or "").strip()
        reason = str(active_preset_reason or "").strip()
        baseline = self.resolve_current_config_baseline(
            active_text=active_text,
            provenance_missing=bool(provenance_missing),
        )
        resolved_diff_fields = list(baseline_diff_fields or [])
        resolved_probe_failed = bool(baseline_probe_failed) and not bool(baseline.get("is_custom"))
        baseline_drifted = bool(resolved_diff_fields) and not bool(baseline.get("is_custom"))
        degraded = bool(tuple(getattr(current_snapshot, "degradation_events", ()) or ())) or bool(provenance_missing)
        meta = self.active_service.meta_from_value(active_preset_meta, reason_fallback=reason)
        raw_notices = list(meta.get("repair_notices") or [])
        raw_notice = self.active_service.compat_repair_notice(raw_notices, reason_fallback=reason)
        repair_notices = public_config_notices(raw_notices)
        repair_notice = public_config_notice(raw_notice)
        state, status_label, label = self.resolve_current_config_descriptor(
            provenance_missing=bool(provenance_missing),
            degraded=degraded,
            baseline_probe_failed=resolved_probe_failed,
            baseline_drifted=baseline_drifted,
            is_custom=bool(baseline.get("is_custom")),
            baseline_label=str(baseline.get("baseline_label") or ""),
            reason=reason,
            repair_notice=repair_notice,
        )

        return CurrentConfigDisplayState(
            state=state,
            status_label=status_label,
            label=label,
            baseline_key=baseline.get("baseline_key"),
            baseline_label=baseline.get("baseline_label"),
            baseline_source=baseline.get("baseline_source"),
            is_custom=bool(baseline.get("is_custom")),
            is_builtin=bool(
                (not bool(provenance_missing))
                and (not bool(baseline.get("is_custom")))
                and active_text in BUILTIN_PRESET_NAMES
            ),
            degraded=bool(degraded),
            provenance_missing=bool(provenance_missing),
            active_preset_missing=bool(active_preset_missing),
            active_preset_reason_missing=bool(active_preset_reason_missing),
            reason=public_active_preset_reason(reason) or "",
            baseline_probe_failed=resolved_probe_failed,
            baseline_diff_fields=resolved_diff_fields,
            repair_notices=repair_notices,
            repair_notice=repair_notice,
        )

    def get_preset_display_state(
        self,
        *,
        readonly: bool = True,
        current_snapshot: Optional[ScheduleConfigSnapshot] = None,
    ) -> Dict[str, Any]:
        rows = self.list_config_rows(readonly=bool(readonly))
        by_key, preset_rows = self.collect_preset_rows(rows)
        provenance_state = self.active_service.provenance_state_from_rows(by_key)
        snapshot = current_snapshot if current_snapshot is not None else self.preset_service.get_snapshot_from_repo(strict_mode=False)
        baseline = self.baseline_probe_state(
            current_snapshot=snapshot,
            active_text=str(provenance_state.active_value or "").strip(),
            provenance_missing=provenance_state.provenance_missing,
        )
        baseline_probe_failed = bool(baseline.baseline_probe_failed)
        baseline_diff_fields = list(baseline.baseline_diff_fields)
        preset_state = provenance_state.to_legacy_dict()
        if baseline_probe_failed or baseline_diff_fields:
            preset_state = {
                **preset_state,
                "can_preserve_baseline": False,
            }
        active_reason = str(provenance_state.reason_text or "").strip()
        can_preserve_named_provenance_for_write = bool(
            provenance_state.active_value
        ) and not provenance_state.provenance_missing and not baseline_probe_failed and not baseline_diff_fields and not self.reason_in(
            active_reason,
            ACTIVE_PRESET_REASON_PRESET_ADJUSTED,
            ACTIVE_PRESET_REASON_PRESET_MISMATCH,
        )
        current_config_state = self.build_current_config_state(
            current_snapshot=snapshot,
            active_preset=provenance_state.active_value,
            active_preset_reason=active_reason,
            active_preset_meta=provenance_state.meta,
            active_preset_missing=provenance_state.active_missing,
            active_preset_reason_missing=provenance_state.reason_missing,
            provenance_missing=provenance_state.provenance_missing,
            baseline_diff_fields=baseline_diff_fields,
            baseline_probe_failed=baseline_probe_failed,
        )
        return {
            "presets": self.build_preset_entries(preset_rows),
            **preset_state,
            "current_config_state": current_config_state.to_legacy_dict(),
            "can_preserve_named_provenance_for_write": can_preserve_named_provenance_for_write,
            "readonly": bool(readonly),
        }

    def get_page_save_provenance_state(
        self,
        *,
        current_snapshot: ScheduleConfigSnapshot,
    ) -> PageSaveProvenanceState:
        rows = self.list_config_rows(readonly=True)
        by_key, _preset_rows = self.collect_preset_rows(rows)
        provenance_state = self.active_service.provenance_state_from_rows(by_key)
        baseline = self.baseline_probe_state(
            current_snapshot=current_snapshot,
            active_text=str(provenance_state.active_value or "").strip(),
            provenance_missing=provenance_state.provenance_missing,
        )
        baseline_probe_failed = bool(baseline.baseline_probe_failed)
        baseline_diff_fields = list(baseline.baseline_diff_fields)
        active_reason = str(provenance_state.reason_text or "").strip()
        can_preserve_named_provenance_for_write = bool(
            provenance_state.active_value
        ) and not provenance_state.provenance_missing and not baseline_probe_failed and not baseline_diff_fields and not self.reason_in(
            active_reason,
            ACTIVE_PRESET_REASON_PRESET_ADJUSTED,
            ACTIVE_PRESET_REASON_PRESET_MISMATCH,
        )
        return PageSaveProvenanceState(
            active_preset=provenance_state.active_value,
            active_preset_reason=active_reason or None,
            active_preset_meta=dict(provenance_state.meta),
            can_preserve_named_provenance_for_write=can_preserve_named_provenance_for_write,
            provenance_completeness_status=str(provenance_state.completeness_status or ""),
            current_config_state=self.build_current_config_state(
                current_snapshot=current_snapshot,
                active_preset=provenance_state.active_value,
                active_preset_reason=active_reason,
                active_preset_meta=provenance_state.meta,
                active_preset_missing=provenance_state.active_missing,
                active_preset_reason_missing=provenance_state.reason_missing,
                provenance_missing=provenance_state.provenance_missing,
                baseline_diff_fields=baseline_diff_fields,
                baseline_probe_failed=baseline_probe_failed,
            ),
        )

    def list_presets(self) -> List[Dict[str, Any]]:
        state = self.get_preset_display_state(readonly=True)
        return list(state.get("presets") or [])

    @staticmethod
    def snapshot_degraded_fields(snapshot: ScheduleConfigSnapshot) -> List[str]:
        degraded_fields: List[str] = []
        seen: set[str] = set()
        for event in (getattr(snapshot, "degradation_events", ()) or ()):
            if not isinstance(event, dict):
                continue
            field = str((event or {}).get("field") or "").strip()
            if not field or field in seen:
                continue
            seen.add(field)
            degraded_fields.append(field)
        return degraded_fields

    @staticmethod
    def hidden_degraded_fields(snapshot: ScheduleConfigSnapshot) -> List[str]:
        hidden = set(CONFIG_PAGE_HIDDEN_REPAIR_FIELDS)
        return [field for field in ConfigReadService.snapshot_degraded_fields(snapshot) if field in hidden]


__all__ = ["ConfigReadService"]
