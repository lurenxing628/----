from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from . import active_preset_provenance
from .active_preset_state import ActivePresetProvenanceState
from .config_constants import (
    ACTIVE_PRESET_CUSTOM,
    ACTIVE_PRESET_KEY,
    ACTIVE_PRESET_META_KEY,
    ACTIVE_PRESET_META_REASON_HIDDEN_REPAIR,
    ACTIVE_PRESET_META_REASON_MANUAL,
    ACTIVE_PRESET_META_REASON_VISIBLE_REPAIR,
    ACTIVE_PRESET_REASON_CUSTOM_SELECTED,
    ACTIVE_PRESET_REASON_HIDDEN_REPAIR,
    ACTIVE_PRESET_REASON_KEY,
    ACTIVE_PRESET_REASON_MANUAL,
    ACTIVE_PRESET_REASON_VISIBLE_REPAIR,
)
from .config_uow import ConfigWriteUnitOfWork


class ActivePresetService:
    def __init__(self, uow: ConfigWriteUnitOfWork) -> None:
        self.uow = uow

    @staticmethod
    def row_config_text(row: Optional[Any]) -> Optional[str]:
        text = str(getattr(row, "config_value", "") or "").strip()
        return text or None

    @staticmethod
    def extract_repair_fields(reason: str) -> List[str]:
        return active_preset_provenance.extract_repair_fields(reason)

    @staticmethod
    def repair_notice_from_reason(reason: str) -> Dict[str, Any]:
        return active_preset_provenance.repair_notice_from_reason(
            reason,
            hidden_repair_reason=ACTIVE_PRESET_REASON_HIDDEN_REPAIR,
            visible_repair_reason=ACTIVE_PRESET_REASON_VISIBLE_REPAIR,
        )

    @staticmethod
    def normalize_repair_notice(notice: Any) -> Optional[Dict[str, Any]]:
        return active_preset_provenance.normalize_repair_notice(notice)

    @staticmethod
    def meta_reason_codes() -> Tuple[str, str, str]:
        return (
            ACTIVE_PRESET_META_REASON_MANUAL,
            ACTIVE_PRESET_META_REASON_VISIBLE_REPAIR,
            ACTIVE_PRESET_META_REASON_HIDDEN_REPAIR,
        )

    @classmethod
    def meta_payload(
        cls,
        *,
        reason_code: Optional[str],
        repair_notices: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        return active_preset_provenance.active_preset_meta_payload(
            reason_code=reason_code,
            repair_notices=repair_notices,
            valid_reason_codes=cls.meta_reason_codes(),
        )

    @classmethod
    def legacy_meta_from_reason(cls, reason: Optional[str]) -> Dict[str, Any]:
        reason_text = str(reason or "").strip()
        if not reason_text:
            return cls.meta_payload(reason_code=None, repair_notices=[])
        if ACTIVE_PRESET_REASON_HIDDEN_REPAIR in reason_text:
            return cls.meta_payload(
                reason_code=ACTIVE_PRESET_META_REASON_HIDDEN_REPAIR,
                repair_notices=[cls.repair_notice_from_reason(reason_text)],
            )
        if ACTIVE_PRESET_REASON_VISIBLE_REPAIR in reason_text:
            return cls.meta_payload(
                reason_code=ACTIVE_PRESET_META_REASON_VISIBLE_REPAIR,
                repair_notices=[cls.repair_notice_from_reason(reason_text)],
            )
        if reason_text == ACTIVE_PRESET_REASON_MANUAL:
            return cls.meta_payload(
                reason_code=ACTIVE_PRESET_META_REASON_MANUAL,
                repair_notices=[],
            )
        return cls.meta_payload(reason_code=None, repair_notices=[])

    @classmethod
    def meta_from_value(
        cls,
        value: Any,
        *,
        reason_fallback: Optional[str] = None,
    ) -> Dict[str, Any]:
        return active_preset_provenance.parse_active_preset_meta(
            value,
            reason_fallback=reason_fallback,
            valid_reason_codes=cls.meta_reason_codes(),
            legacy_meta_from_reason=cls.legacy_meta_from_reason,
        )

    @staticmethod
    def meta_parse_warning(value: Any) -> Optional[Dict[str, Any]]:
        return active_preset_provenance.active_preset_meta_parse_warning(
            value,
            field=ACTIVE_PRESET_META_KEY,
        )

    @classmethod
    def serialize_meta(cls, meta: Optional[Dict[str, Any]]) -> str:
        return active_preset_provenance.serialize_active_preset_meta(
            meta,
            valid_reason_codes=cls.meta_reason_codes(),
        )

    @classmethod
    def compat_repair_notice(
        cls,
        repair_notices: List[Dict[str, Any]],
        *,
        reason_fallback: Optional[str] = None,
    ) -> Dict[str, Any]:
        for kind in ("visible", "hidden"):
            for notice in repair_notices:
                if str(notice.get("kind") or "").strip().lower() != kind:
                    continue
                return {
                    "kind": kind,
                    "fields": list(notice.get("fields") or []),
                    "message": notice.get("message"),
                }
        return cls.repair_notice_from_reason(str(reason_fallback or "").strip())

    def provenance_state_from_rows(self, by_key: Dict[str, Any]) -> ActivePresetProvenanceState:
        active_row = by_key.get(ACTIVE_PRESET_KEY)
        reason_row = by_key.get(ACTIVE_PRESET_REASON_KEY)
        meta_row = by_key.get(ACTIVE_PRESET_META_KEY)
        active_preset = self.row_config_text(active_row)
        active_reason = self.row_config_text(reason_row)
        active_meta = self.meta_from_value(
            self.row_config_text(meta_row),
            reason_fallback=active_reason,
        )
        return self.provenance_state(
            active_preset=active_preset,
            active_preset_reason=active_reason,
            active_preset_meta=active_meta,
            active_preset_missing=bool(active_row is None),
            active_preset_reason_missing=bool(reason_row is None),
        )

    def display_state_from_rows(self, by_key: Dict[str, Any]) -> Dict[str, Any]:
        return self.provenance_state_from_rows(by_key).to_legacy_dict()

    @classmethod
    def provenance_state(
        cls,
        *,
        active_preset: Optional[str],
        active_preset_reason: Optional[str],
        active_preset_meta: Optional[Dict[str, Any]],
        active_preset_missing: bool,
        active_preset_reason_missing: bool,
    ) -> ActivePresetProvenanceState:
        active_text = str(active_preset or "").strip() or None
        reason_text = str(active_preset_reason or "").strip() or None
        meta = cls.meta_from_value(active_preset_meta, reason_fallback=reason_text)
        if active_preset_missing:
            completeness = "missing_active_row"
        elif not active_text:
            completeness = "active_blank"
        elif active_preset_reason_missing:
            completeness = "missing_reason_row"
        elif active_text.lower() == ACTIVE_PRESET_CUSTOM and not reason_text:
            completeness = "custom_reason_blank"
        else:
            completeness = "complete"
        return ActivePresetProvenanceState(
            active_value=active_text,
            reason_text=reason_text,
            meta=meta,
            active_missing=bool(active_preset_missing),
            reason_missing=bool(active_preset_reason_missing),
            completeness_status=completeness,
        )

    @staticmethod
    def active_preset_update(name: Optional[str]) -> Tuple[str, str, str]:
        value = ("" if name is None else str(name)).strip()
        return (
            ACTIVE_PRESET_KEY,
            value if value else ACTIVE_PRESET_CUSTOM,
            "当前启用排产配置模板",
        )

    @staticmethod
    def active_preset_reason_update(reason: Optional[str]) -> Tuple[str, str, str]:
        value = ("" if reason is None else str(reason)).strip()
        return (
            ACTIVE_PRESET_REASON_KEY,
            value,
            "当前启用排产配置模板的状态说明",
        )

    @classmethod
    def active_preset_meta_update(cls, meta: Optional[Dict[str, Any]] = None) -> Tuple[str, str, str]:
        return (
            ACTIVE_PRESET_META_KEY,
            cls.serialize_meta(meta),
            "当前启用排产配置模板的结构化来源记录",
        )

    @classmethod
    def active_preset_updates(
        cls,
        name: Optional[str],
        reason: Optional[str] = None,
        *,
        meta: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, str, str]]:
        resolved_meta = meta
        if resolved_meta is None:
            resolved_meta = cls.legacy_meta_from_reason(reason)
        return [
            cls.active_preset_update(name),
            cls.active_preset_reason_update(reason),
            cls.active_preset_meta_update(resolved_meta),
        ]

    def set_active_preset(self, name: Optional[str], *, reason: Optional[str] = None) -> None:
        with self.uow.tx_manager.transaction():
            self.uow.repo.set_batch(self.active_preset_updates(name, reason=reason))

    def mark_custom(self, reason: Optional[str] = None) -> None:
        self.set_active_preset(
            ACTIVE_PRESET_CUSTOM,
            reason=(ACTIVE_PRESET_REASON_CUSTOM_SELECTED if reason is None else reason),
        )

    def get_active_preset(self) -> Optional[str]:
        raw = self.uow.repo.get_value(ACTIVE_PRESET_KEY, default=None)
        value = str(raw).strip() if raw is not None else ""
        return value if value else None

    def get_active_preset_reason(self) -> Optional[str]:
        raw = self.uow.repo.get_value(ACTIVE_PRESET_REASON_KEY, default=None)
        value = str(raw).strip() if raw is not None else ""
        return value if value else None

    def get_active_preset_meta(self) -> Dict[str, Any]:
        raw = self.uow.repo.get_value(ACTIVE_PRESET_META_KEY, default=None)
        return self.meta_from_value(raw, reason_fallback=self.get_active_preset_reason())


__all__ = ["ActivePresetService"]
