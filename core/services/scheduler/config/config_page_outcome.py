from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from core.models.scheduler_degradation_messages import public_degradation_events

from .config_field_spec import field_label_for, has_config_field
from .config_snapshot import ScheduleConfigSnapshot

PUBLIC_OUTCOME_HIDDEN_SNAPSHOT_FIELDS = {"auto_assign_persist"}
PUBLIC_FIELD_LABEL_OVERRIDES = {
    "active_preset_meta": "方案来源记录",
    "auto_assign_persist": "自动分配结果回写",
    "preset": "方案数据",
    "preset_name": "方案名称",
}
PUBLIC_HIDDEN_BLOCK_REASON_LABELS = {
    "blocked_adjusted_preset": "当前方案处于调整状态",
    "blocked_baseline_drifted": "当前配置与方案已有差异",
    "blocked_baseline_unverifiable": "当前方案基线不可验证",
    "blocked_custom_reason_missing": "自定义来源说明缺失",
    "blocked_provenance_missing": "来源缺失",
}
PUBLIC_STATUS_LABELS = {
    "blocked_hidden_repair": "部分配置未自动修复",
    "repaired_hidden": "后台设置已修复",
    "saved": "配置已保存",
    "unchanged": "配置未变化",
}


def public_config_field_label(field: str) -> str:
    normalized = str(field or "").strip()
    if not normalized:
        return "隐藏配置"
    if normalized in PUBLIC_FIELD_LABEL_OVERRIDES:
        return PUBLIC_FIELD_LABEL_OVERRIDES[normalized]
    if has_config_field(normalized):
        label = str(field_label_for(normalized) or "").strip()
        return label if label and label != normalized else "配置字段"
    return "隐藏配置"


def public_config_field_labels(fields: Sequence[str]) -> List[str]:
    labels: List[str] = []
    for field_name in list(fields or []):
        label = public_config_field_label(str(field_name or "").strip())
        if label and label not in labels:
            labels.append(label)
    return labels


def public_hidden_block_reason_label(reason: Any) -> Optional[str]:
    text = str(reason or "").strip()
    if not text:
        return None
    return PUBLIC_HIDDEN_BLOCK_REASON_LABELS.get(text, "配置来源状态不可自动保留")


def public_config_notice(notice: Dict[str, Any]) -> Dict[str, Any]:
    kind = str(notice.get("kind") or "").strip()
    labels = public_config_field_labels([str(field) for field in list(notice.get("fields") or [])])
    if kind == "blocked_hidden":
        label_text = "、".join(labels or ["隐藏配置"])
        reason_label = public_hidden_block_reason_label(notice.get("block_reason")) or "来源缺失"
        message = f"检测到后台设置“{label_text}”需要保存修复，但因{reason_label}未自动修复。"
    elif kind == "hidden":
        label_text = "、".join(labels or ["隐藏配置"])
        message = f"后台设置“{label_text}”已按当前表单值回写。"
    elif kind == "visible":
        message = "页面展示的兼容回退值已被显式保存，当前运行配置已转为自定义。"
    elif kind == "none":
        message = None
    else:
        message = "配置来源状态已更新。" if kind else None
    out: Dict[str, Any] = {"kind": kind, "message": message}
    if labels:
        out["field_labels"] = labels
    reason_label = public_hidden_block_reason_label(notice.get("block_reason"))
    if reason_label:
        out["block_reason_label"] = reason_label
    return out


def public_config_notices(notices: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [public_config_notice(dict(notice or {})) for notice in list(notices or []) if isinstance(notice, dict)]


def public_active_preset_reason(value: Any) -> Optional[str]:
    reason = str(value or "").strip()
    if not reason:
        return None
    if "涉及字段：" in reason:
        return public_adjusted_reason_label(reason)
    if "兼容修补已回写隐藏配置项" in reason:
        return "后台设置已按当前表单值回写。"
    if "_" in reason:
        return "配置来源状态已更新。"
    return reason


def public_adjusted_reason_label(reason: str) -> str:
    text = str(reason or "").strip()
    if not text:
        return text
    marker = "涉及字段："
    if marker not in text:
        return public_active_preset_reason(text) or "配置来源状态已更新。"
    prefix, suffix = text.split(marker, 1)
    raw_fields = str(suffix or "").strip().rstrip("。")
    labels = public_config_field_labels([field.strip() for field in raw_fields.split("、") if field.strip()])
    if not labels:
        return public_active_preset_reason(prefix) or "配置来源状态已更新。"
    return f"{prefix.strip()} 涉及字段：{'、'.join(labels)}。".strip()


def public_config_snapshot_dict(snapshot: Optional[ScheduleConfigSnapshot]) -> Optional[Dict[str, Any]]:
    if snapshot is None:
        return None
    data = snapshot.to_dict()
    for field_name in PUBLIC_OUTCOME_HIDDEN_SNAPSHOT_FIELDS:
        data.pop(field_name, None)
    return data


def public_degradation_counters(events: Sequence[Any]) -> Dict[str, int]:
    return {
        str(event.get("code")): int(event.get("count") or 0)
        for event in public_degradation_events(events)
        if isinstance(event, dict) and str(event.get("code") or "").strip()
    }


def public_save_status_label(status: Any) -> str:
    text = str(status or "").strip()
    return PUBLIC_STATUS_LABELS.get(text, "配置状态已更新")


def public_repair_status(outcome: ConfigPageSaveOutcome) -> str:
    if outcome.blocked_hidden_repairs:
        return "blocked_hidden"
    if outcome.hidden_repaired_fields:
        return "hidden_repaired"
    if outcome.visible_repaired_fields:
        return "visible_repaired"
    return "none"


def public_hidden_block_reason_from_notices(notices: Sequence[Dict[str, Any]]) -> Optional[str]:
    for notice in notices:
        if not isinstance(notice, dict):
            continue
        if str(notice.get("kind") or "").strip() != "blocked_hidden":
            continue
        label = public_hidden_block_reason_label(notice.get("block_reason"))
        if label:
            return label
    return None


@dataclass
class ConfigPageSaveOutcome:
    snapshot: ScheduleConfigSnapshot
    visible_changed_fields: List[str] = field(default_factory=list)
    visible_repaired_fields: List[str] = field(default_factory=list)
    hidden_repaired_fields: List[str] = field(default_factory=list)
    blocked_hidden_repairs: List[str] = field(default_factory=list)
    notices: List[Dict[str, Any]] = field(default_factory=list)
    active_preset_after: Optional[str] = None
    active_preset_reason_after: Optional[str] = None
    status: str = "saved"
    normalized_snapshot: Optional[ScheduleConfigSnapshot] = None
    raw_persisted_values: Dict[str, Any] = field(default_factory=dict)
    raw_missing_fields: List[str] = field(default_factory=list)
    meta_parse_warnings: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def effective_snapshot(self) -> ScheduleConfigSnapshot:
        return self.snapshot

    def __getattr__(self, item: str) -> Any:
        return getattr(self.snapshot, item)

    def to_dict(self) -> Dict[str, Any]:
        return self.to_effective_snapshot_dict()

    def to_snapshot_dict(self) -> Dict[str, Any]:
        return self.to_effective_snapshot_dict()

    def to_effective_snapshot_dict(self) -> Dict[str, Any]:
        return self.snapshot.to_dict()

    def raw_effective_mismatches(self) -> List[Dict[str, Any]]:
        effective = self.snapshot.to_dict()
        mismatches: List[Dict[str, Any]] = []
        for field_name, raw_value in sorted(dict(self.raw_persisted_values).items()):
            if field_name not in effective:
                continue
            effective_value = effective.get(field_name)
            if str(raw_value) == str(effective_value):
                continue
            mismatches.append(
                {
                    "field": field_name,
                    "effective_value": effective_value,
                    "raw_value": raw_value,
                }
            )
        return mismatches

    def to_outcome_dict(self) -> Dict[str, Any]:
        """内部诊断载荷；包含 raw persisted values，不作为 Web/API 公共 DTO。"""
        return {
            "status": self.status,
            "effective_snapshot": self.snapshot.to_dict(),
            "normalized_snapshot": self.normalized_snapshot.to_dict() if self.normalized_snapshot else None,
            "raw_persisted_values": dict(self.raw_persisted_values),
            "raw_effective_mismatches": self.raw_effective_mismatches(),
            "raw_missing_fields": list(self.raw_missing_fields),
            "degradation_events": list(getattr(self.snapshot, "degradation_events", ()) or ()),
            "degradation_counters": dict(getattr(self.snapshot, "degradation_counters", {}) or {}),
            "visible_changed_fields": list(self.visible_changed_fields),
            "visible_repaired_fields": list(self.visible_repaired_fields),
            "hidden_repaired_fields": list(self.hidden_repaired_fields),
            "blocked_hidden_repairs": list(self.blocked_hidden_repairs),
            "notices": list(self.notices),
            "meta_parse_warnings": list(self.meta_parse_warnings),
            "active_preset_after": self.active_preset_after,
            "active_preset_reason_after": self.active_preset_reason_after,
        }

    def to_public_outcome_dict(self) -> Dict[str, Any]:
        raw_events = list(getattr(self.snapshot, "degradation_events", ()) or ())
        return {
            "status": self.status,
            "public_status_label": public_save_status_label(self.status),
            "repair_status": public_repair_status(self),
            "hidden_block_reason_label": public_hidden_block_reason_from_notices(self.notices),
            "effective_snapshot": public_config_snapshot_dict(self.snapshot),
            "normalized_snapshot": public_config_snapshot_dict(self.normalized_snapshot),
            "degradation_events": public_degradation_events(raw_events),
            "degradation_counters": public_degradation_counters(raw_events),
            "visible_changed_field_labels": public_config_field_labels(self.visible_changed_fields),
            "visible_repaired_field_labels": public_config_field_labels(self.visible_repaired_fields),
            "hidden_repaired_field_labels": public_config_field_labels(self.hidden_repaired_fields),
            "blocked_hidden_repair_labels": public_config_field_labels(self.blocked_hidden_repairs),
            "notices": public_config_notices(self.notices),
            "active_preset_after": self.active_preset_after,
            "active_preset_reason_after": public_active_preset_reason(self.active_preset_reason_after),
        }


__all__ = [
    "ConfigPageSaveOutcome",
    "public_active_preset_reason",
    "public_adjusted_reason_label",
    "public_config_field_label",
    "public_config_field_labels",
    "public_config_notice",
    "public_config_notices",
    "public_hidden_block_reason_label",
    "public_repair_status",
    "public_save_status_label",
]
