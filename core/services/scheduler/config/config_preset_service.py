from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.services.common.normalize import normalize_text

from . import config_presets
from .active_preset_service import ActivePresetService
from .config_bootstrap_service import ConfigBootstrapService
from .config_constants import (
    ACTIVE_PRESET_CUSTOM,
    ACTIVE_PRESET_REASON_PRESET_ADJUSTED,
    ACTIVE_PRESET_REASON_PRESET_DELETED,
    ACTIVE_PRESET_REASON_PRESET_MISMATCH,
    BUILTIN_PRESET_NAMES,
)
from .config_snapshot import ScheduleConfigSnapshot
from .config_uow import ConfigWriteUnitOfWork


class ConfigPresetService:
    """配置方案服务，显式依赖 UoW 和 active provenance，不反向持有 facade。"""

    def __init__(
        self,
        *,
        uow: ConfigWriteUnitOfWork,
        active_service: ActivePresetService,
        bootstrap_service: ConfigBootstrapService,
    ) -> None:
        self.uow = uow
        self.active_service = active_service
        self.bootstrap_service = bootstrap_service

    @staticmethod
    def preset_key(name: str) -> str:
        return config_presets.preset_key(name)

    @staticmethod
    def is_builtin_preset(name: str) -> bool:
        return str(name or "").strip() in BUILTIN_PRESET_NAMES

    def builtin_presets(self) -> List[Tuple[str, ScheduleConfigSnapshot, str]]:
        return self.bootstrap_service.builtin_presets()

    @staticmethod
    def snapshot_close(left: ScheduleConfigSnapshot, right: ScheduleConfigSnapshot) -> bool:
        return config_presets.snapshot_close(left, right)

    def get_snapshot_from_repo(self, *, strict_mode: bool = False) -> ScheduleConfigSnapshot:
        return config_presets.get_snapshot_from_repo(self.uow.repo, strict_mode=bool(strict_mode))

    def ensure_builtin_presets(self, *, existing_keys: Optional[set] = None) -> None:
        self.bootstrap_service.ensure_builtin_presets(existing_keys=existing_keys)

    def bootstrap_active_provenance_if_pristine(self) -> None:
        self.bootstrap_service.bootstrap_active_provenance_if_pristine()

    def list_presets(self) -> List[Dict[str, Any]]:
        prefix = self.preset_key("")
        preset_rows: Dict[str, Any] = {}
        for row in self.uow.repo.list_all():
            config_key = str(getattr(row, "config_key", "") or "")
            if not config_key.startswith(prefix):
                continue
            name = config_key[len(prefix) :].strip()
            if name:
                preset_rows[name] = row

        custom_presets = dict(preset_rows)
        presets: List[Dict[str, Any]] = []
        for name, _snapshot, description in self.builtin_presets():
            row = custom_presets.pop(name, None)
            presets.append(
                {
                    "name": name,
                    "updated_at": getattr(row, "updated_at", None),
                    "config_key": self.preset_key(name),
                    "description": getattr(row, "description", None) or description,
                }
            )
        for name in sorted(custom_presets):
            row = custom_presets[name]
            presets.append(
                {
                    "name": name,
                    "updated_at": getattr(row, "updated_at", None),
                    "config_key": getattr(row, "config_key", self.preset_key(name)),
                    "description": getattr(row, "description", None),
                }
            )
        return presets

    def _readonly_active_preset_state(self) -> Dict[str, Any]:
        rows = self.uow.repo.list_all()
        state = self.active_service.display_state_from_rows({str(row.config_key or ""): row for row in rows})
        active_preset = str(state.get("active_preset") or "").strip()
        provenance_missing = bool(state.get("provenance_missing"))
        return {
            "effective_active_preset": active_preset if active_preset and not provenance_missing else ACTIVE_PRESET_CUSTOM,
            "reason": state.get("active_preset_reason") if active_preset and not provenance_missing else None,
        }

    def _builtin_preset_payload(self, name: str) -> Optional[Dict[str, Any]]:
        for preset_name, snapshot, _description in self.builtin_presets():
            if str(preset_name or "").strip() == str(name or "").strip():
                return dict(snapshot.to_dict())
        return None

    @staticmethod
    def _is_reserved_custom_preset_name(name: str) -> bool:
        return str(name or "").strip().lower() == ACTIVE_PRESET_CUSTOM

    def validate_preset_name(self, name: Any, *, action: str) -> str:
        normalized = normalize_text(name)
        if not normalized:
            raise ValidationError("方案名称不能为空", field="方案名称")
        if len(normalized) > 50:
            raise ValidationError("方案名称过长，建议不要超过 50 个字。", field="方案名称")
        if self._is_reserved_custom_preset_name(normalized):
            raise ValidationError("“custom” 是系统保留的手动设置标记，请换个方案名称。", field="方案名称")
        if action in {"save", "delete"} and self.is_builtin_preset(normalized):
            if action == "save":
                raise ValidationError("系统自带方案不能覆盖，请换个名字另存。", field="方案名称")
            raise ValidationError("系统自带方案不能删除。", field="方案名称")
        return str(normalized)

    def _load_preset_payload(self, name: str) -> Dict[str, Any]:
        builtin_payload = self._builtin_preset_payload(name)
        if builtin_payload is not None:
            return builtin_payload
        raw = self.uow.repo.get_value(self.preset_key(name), default=None)
        return config_presets.load_preset_payload(raw, name=name)

    def try_load_preset_snapshot_for_baseline(self, name: str) -> Tuple[Optional[ScheduleConfigSnapshot], bool]:
        preset_name = str(name or "").strip()
        if not preset_name or preset_name.lower() == ACTIVE_PRESET_CUSTOM:
            return None, False
        try:
            data = self._load_preset_payload(preset_name)
        except (BusinessError, ValidationError, TypeError, ValueError):
            return None, True
        if config_presets.missing_required_preset_fields(data):
            return None, True
        try:
            return self.normalize_preset_snapshot(data), False
        except ValidationError:
            return None, True

    def save_preset(self, name: Any) -> Dict[str, Any]:
        preset_name = self.validate_preset_name(name, action="save")
        self.bootstrap_service.ensure_defaults_if_pristine()

        try:
            snapshot = self.get_snapshot_from_repo(strict_mode=True)
        except ValidationError as exc:
            readonly_state = self._readonly_active_preset_state()
            field = str(getattr(exc, "field", "") or "").strip()
            return config_presets.preset_result(
                requested_preset=preset_name,
                effective_active_preset=str(readonly_state["effective_active_preset"]),
                status="rejected",
                adjusted_fields=[],
                reason=readonly_state["reason"],
                error_field=field,
                error_fields=[field] if field else [],
                error_message=str(exc.message),
            )

        with self.uow.tx_manager.transaction():
            self.uow.repo.set(
                self.preset_key(preset_name),
                config_presets.dump_snapshot_payload(snapshot),
                description="排产配置模板（用户自定义）",
            )
            self.uow.repo.set_batch(self.active_service.active_preset_updates(preset_name))
        return config_presets.preset_result(
            requested_preset=preset_name,
            effective_active_preset=preset_name,
            status="saved",
            adjusted_fields=[],
            reason=None,
        )

    def delete_preset(self, name: Any) -> None:
        preset_name = self.validate_preset_name(name, action="delete")
        if self.uow.repo.get_value(self.preset_key(preset_name), default=None) is None:
            raise BusinessError(ErrorCode.NOT_FOUND, f"未找到方案：{preset_name}")

        active = self.active_service.get_active_preset()
        with self.uow.tx_manager.transaction():
            self.uow.repo.delete(self.preset_key(preset_name))
            if active == preset_name:
                self.uow.repo.set_batch(
                    self.active_service.active_preset_updates(
                        ACTIVE_PRESET_CUSTOM,
                        reason=ACTIVE_PRESET_REASON_PRESET_DELETED,
                    )
                )

    def normalize_preset_snapshot(self, data: Dict[str, Any]) -> ScheduleConfigSnapshot:
        return config_presets.normalize_preset_snapshot(
            data,
            base=self.bootstrap_service.default_snapshot(),
        )

    @staticmethod
    def _preset_mismatch_reason(fields: List[str]) -> str:
        sample = "、".join([str(field) for field in (fields or [])[:5]])
        return ACTIVE_PRESET_REASON_PRESET_MISMATCH if not sample else f"{ACTIVE_PRESET_REASON_PRESET_MISMATCH} 涉及字段：{sample}。"

    @staticmethod
    def _preset_adjusted_reason(fields: List[str]) -> str:
        sample = "、".join([str(field) for field in (fields or [])[:5]])
        return ACTIVE_PRESET_REASON_PRESET_ADJUSTED if not sample else f"{ACTIVE_PRESET_REASON_PRESET_ADJUSTED} 涉及字段：{sample}。"

    def apply_preset(self, name: Any) -> Dict[str, Any]:
        preset_name = self.validate_preset_name(name, action="apply")
        data = self._load_preset_payload(preset_name)

        missing_fields = config_presets.missing_required_preset_fields(data)
        if missing_fields:
            readonly_state = self._readonly_active_preset_state()
            sample = "、".join(str(field) for field in missing_fields)
            return config_presets.preset_result(
                requested_preset=preset_name,
                effective_active_preset=str(readonly_state["effective_active_preset"]),
                status="rejected",
                adjusted_fields=[],
                reason=readonly_state["reason"],
                error_field=str(missing_fields[0]),
                error_fields=list(missing_fields),
                error_message=f"方案缺少必填字段：{sample}。",
            )

        snapshot = self.normalize_preset_snapshot(data)
        payload_diff_fields = config_presets.snapshot_payload_projection_diff_fields(data, snapshot)
        config_updates = [(key, str(value), None) for key, value in snapshot.to_dict().items()]

        with self.uow.tx_manager.transaction():
            self.uow.repo.set_batch(config_updates)
            final_snapshot = config_presets.get_snapshot_from_repo(self.uow.repo, strict_mode=True)
            diff_fields = config_presets.snapshot_diff_fields(snapshot, final_snapshot)
            if diff_fields:
                combined_fields = list(dict.fromkeys(list(payload_diff_fields) + list(diff_fields)))
                reason = self._preset_mismatch_reason(combined_fields)
                self.uow.repo.set_batch(
                    self.active_service.active_preset_updates(preset_name, reason=reason)
                )
                adjusted_fields = combined_fields
                status = "adjusted"
            elif payload_diff_fields:
                reason = self._preset_adjusted_reason(payload_diff_fields)
                self.uow.repo.set_batch(
                    self.active_service.active_preset_updates(preset_name, reason=reason)
                )
                adjusted_fields = list(payload_diff_fields)
                status = "adjusted"
            else:
                self.uow.repo.set_batch(self.active_service.active_preset_updates(preset_name))
                reason = None
                adjusted_fields = []
                status = "applied"

        return config_presets.preset_result(
            requested_preset=preset_name,
            effective_active_preset=preset_name,
            status=status,
            adjusted_fields=adjusted_fields,
            reason=reason,
        )


__all__ = ["ConfigPresetService"]
