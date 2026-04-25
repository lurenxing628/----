from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ActivePresetProvenanceState:
    active_value: Optional[str]
    reason_text: Optional[str]
    meta: Dict[str, Any]
    active_missing: bool
    reason_missing: bool
    completeness_status: str

    @property
    def provenance_missing(self) -> bool:
        return self.completeness_status != "complete"

    @property
    def can_preserve_baseline(self) -> bool:
        return bool(self.active_value) and not self.provenance_missing

    def to_legacy_dict(self) -> Dict[str, Any]:
        return {
            "active_preset": self.active_value,
            "active_preset_reason": self.reason_text,
            "active_preset_meta": dict(self.meta),
            "active_preset_missing": bool(self.active_missing),
            "active_preset_reason_missing": bool(self.reason_missing),
            "provenance_missing": self.provenance_missing,
            "can_preserve_baseline": self.can_preserve_baseline,
            "provenance_completeness_status": self.completeness_status,
        }


@dataclass(frozen=True)
class BaselineResolution:
    baseline_probe_failed: bool = False
    baseline_diff_fields: List[str] = field(default_factory=list)

    @property
    def drifted(self) -> bool:
        return bool(self.baseline_diff_fields)

    def to_legacy_dict(self) -> Dict[str, Any]:
        return {
            "baseline_probe_failed": bool(self.baseline_probe_failed),
            "baseline_diff_fields": list(self.baseline_diff_fields),
        }


@dataclass(frozen=True)
class RuntimeConfigHealth:
    degradation_state: str
    visible_degraded_fields: List[str] = field(default_factory=list)
    hidden_degraded_fields: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class HiddenRepairDecision:
    allowed: bool
    fields: List[str] = field(default_factory=list)
    block_reason: Optional[str] = None


@dataclass(frozen=True)
class CurrentConfigDisplayState:
    state: str
    status_label: str
    label: str
    baseline_key: Optional[str]
    baseline_label: Optional[str]
    baseline_source: Optional[str]
    is_custom: bool
    is_builtin: bool
    degraded: bool
    provenance_missing: bool
    active_preset_missing: bool
    active_preset_reason_missing: bool
    reason: str
    baseline_probe_failed: bool
    baseline_diff_fields: List[str] = field(default_factory=list)
    repair_notices: List[Dict[str, Any]] = field(default_factory=list)
    repair_notice: Dict[str, Any] = field(default_factory=dict)

    def to_legacy_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "status_label": self.status_label,
            "label": self.label,
            "baseline_key": self.baseline_key,
            "baseline_label": self.baseline_label,
            "baseline_source": self.baseline_source,
            "is_custom": bool(self.is_custom),
            "is_builtin": bool(self.is_builtin),
            "degraded": bool(self.degraded),
            "provenance_missing": bool(self.provenance_missing),
            "active_preset_missing": bool(self.active_preset_missing),
            "active_preset_reason_missing": bool(self.active_preset_reason_missing),
            "reason": self.reason,
            "baseline_probe_failed": bool(self.baseline_probe_failed),
            "baseline_diff_fields": list(self.baseline_diff_fields),
            "repair_notices": list(self.repair_notices),
            "repair_notice": dict(self.repair_notice),
        }


@dataclass(frozen=True)
class PageSaveProvenanceState:
    active_preset: Optional[str]
    active_preset_reason: Optional[str]
    active_preset_meta: Dict[str, Any]
    can_preserve_named_provenance_for_write: bool
    provenance_completeness_status: str
    current_config_state: CurrentConfigDisplayState


__all__ = [
    "ActivePresetProvenanceState",
    "BaselineResolution",
    "CurrentConfigDisplayState",
    "HiddenRepairDecision",
    "PageSaveProvenanceState",
    "RuntimeConfigHealth",
]
