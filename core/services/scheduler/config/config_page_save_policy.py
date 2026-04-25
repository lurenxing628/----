from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

from core.infrastructure.errors import ValidationError

from .config_constants import (
    ACTIVE_PRESET_REASON_HIDDEN_REPAIR,
    ACTIVE_PRESET_REASON_VISIBLE_REPAIR,
    CONFIG_PAGE_FIELDS,
    CONFIG_PAGE_HIDDEN_REPAIR_FIELDS,
    CONFIG_PAGE_VISIBLE_CHANGE_FIELDS,
    CONFIG_PAGE_WRITE_FIELDS,
)
from .config_field_spec import field_label_for
from .config_page_write_plan import ConfigPageWritePlan
from .config_read_service import ConfigReadService
from .config_snapshot import ScheduleConfigSnapshot
from .config_weight_policy import derive_ready_weight_from_priority_due


class ConfigPageSavePolicy:
    @staticmethod
    def form_value(form_values: Any, key: str) -> Any:
        getter = getattr(form_values, "get", None)
        if callable(getter):
            return getter(key)
        if isinstance(form_values, dict):
            return form_values.get(key)
        return getattr(form_values, key, None)

    @classmethod
    def submitted_fields(cls, form_values: Any) -> set[str]:
        keys_getter = getattr(form_values, "keys", None)
        if callable(keys_getter):
            raw_keys = list(cast(Sequence[Any], keys_getter()))
        elif isinstance(form_values, dict):
            raw_keys = list(form_values.keys())
        else:
            raw_keys = []

        submitted: set[str] = set()
        allowed = set(CONFIG_PAGE_WRITE_FIELDS)
        for raw_key in raw_keys:
            key = str(raw_key or "").strip()
            if not key or key not in allowed:
                continue
            if cls.form_value(form_values, key) is None:
                continue
            submitted.add(key)
        return submitted

    @staticmethod
    def normalize_page_weights(
        priority_raw: Any,
        due_raw: Any,
        current_snapshot: ScheduleConfigSnapshot,
    ) -> Tuple[float, float, float]:
        has_priority = priority_raw is not None
        has_due = due_raw is not None
        if not has_priority and not has_due:
            return (
                float(current_snapshot.priority_weight),
                float(current_snapshot.due_weight),
                float(current_snapshot.ready_weight),
            )
        if has_priority and str(priority_raw).strip() == "":
            raise ValidationError("“优先级权重”不能为空", field="优先级权重")
        if has_due and str(due_raw).strip() == "":
            raise ValidationError("“交期权重”不能为空", field="交期权重")

        return derive_ready_weight_from_priority_due(
            priority_raw if has_priority else current_snapshot.priority_weight,
            due_raw if has_due else current_snapshot.due_weight,
        )

    @staticmethod
    def write_values(snapshot: ScheduleConfigSnapshot, *, submitted_fields: set[str]) -> Dict[str, Any]:
        values = snapshot.to_dict()
        write_fields = {key for key in CONFIG_PAGE_WRITE_FIELDS if key in submitted_fields}
        if "priority_weight" in submitted_fields or "due_weight" in submitted_fields:
            write_fields.add("ready_weight")
        return {key: values[key] for key in CONFIG_PAGE_WRITE_FIELDS if key in write_fields}

    @staticmethod
    def materialized_write_values(
        *,
        current_snapshot: ScheduleConfigSnapshot,
        write_values: Dict[str, Any],
    ) -> Dict[str, Any]:
        current_values = current_snapshot.to_dict()
        degraded_fields = set(ConfigReadService.snapshot_degraded_fields(current_snapshot))
        return {
            key: value
            for key, value in write_values.items()
            if key in degraded_fields or not ConfigReadService.values_equal(current_values.get(key), value)
        }

    @staticmethod
    def visible_changed_fields(
        *,
        current_snapshot: ScheduleConfigSnapshot,
        write_values: Dict[str, Any],
    ) -> List[str]:
        current_values = current_snapshot.to_dict()
        return [
            key
            for key in CONFIG_PAGE_VISIBLE_CHANGE_FIELDS
            if key in write_values and not ConfigReadService.values_equal(current_values.get(key), write_values.get(key))
        ]

    @staticmethod
    def visible_repair_fields(
        *,
        current_snapshot: ScheduleConfigSnapshot,
        write_values: Dict[str, Any],
    ) -> List[str]:
        current_values = current_snapshot.to_dict()
        degraded_fields = set(ConfigReadService.snapshot_degraded_fields(current_snapshot))
        repaired_fields = [
            key
            for key in CONFIG_PAGE_VISIBLE_CHANGE_FIELDS
            if key in write_values and key in degraded_fields
        ]
        weights_changed = any(
            key in write_values and not ConfigReadService.values_equal(current_values.get(key), write_values.get(key))
            for key in ("priority_weight", "due_weight")
        )
        ready_weight_repaired = "ready_weight" in degraded_fields or not ConfigReadService.values_equal(
            current_values.get("ready_weight"),
            write_values.get("ready_weight"),
        )
        if "ready_weight" in write_values and ready_weight_repaired and not weights_changed:
            repaired_fields.append("ready_weight")
        return repaired_fields

    @staticmethod
    def hidden_repair_values(
        *,
        current_snapshot: ScheduleConfigSnapshot,
        normalized_snapshot: ScheduleConfigSnapshot,
    ) -> Dict[str, Any]:
        degraded_hidden = set(ConfigReadService.snapshot_degraded_fields(current_snapshot))
        values = normalized_snapshot.to_dict()
        return {
            key: values[key]
            for key in CONFIG_PAGE_HIDDEN_REPAIR_FIELDS
            if key in degraded_hidden and key in values
        }

    @staticmethod
    def hidden_repair_reason(hidden_repaired_fields: List[str]) -> str:
        field_items: List[str] = []
        for field_name in hidden_repaired_fields:
            field_key = str(field_name).strip()
            if not field_key:
                continue
            field_label = field_label_for(field_key)
            field_items.append(f"{field_key}（{field_label}）" if field_label and field_label != field_key else field_key)
        field_list = "、".join(field_items)
        if field_list:
            return f"{ACTIVE_PRESET_REASON_HIDDEN_REPAIR} 已回写：{field_list}。"
        return ACTIVE_PRESET_REASON_HIDDEN_REPAIR

    @staticmethod
    def visible_repair_notice() -> Dict[str, Any]:
        return {
            "kind": "visible",
            "fields": [],
            "message": ACTIVE_PRESET_REASON_VISIBLE_REPAIR,
        }

    @classmethod
    def hidden_repair_notice(cls, hidden_repaired_fields: List[str]) -> Dict[str, Any]:
        return {
            "kind": "hidden",
            "fields": [str(field).strip() for field in hidden_repaired_fields if str(field).strip()],
            "message": cls.hidden_repair_reason(hidden_repaired_fields),
        }

    @staticmethod
    def blocked_hidden_repair_notice(blocked_hidden_fields: List[str], *, block_reason: Optional[str] = None) -> Dict[str, Any]:
        fields = [str(field).strip() for field in blocked_hidden_fields if str(field).strip()]
        field_list = "、".join(field_label_for(field) for field in fields)
        reason_label = {
            "blocked_baseline_drifted": "当前配置与方案已有差异",
            "blocked_baseline_unverifiable": "当前方案基线不可验证",
            "blocked_adjusted_preset": "当前方案处于调整状态",
            "blocked_custom_reason_missing": "自定义来源说明缺失",
            "blocked_provenance_missing": "来源缺失",
        }.get(str(block_reason or "").strip(), "来源缺失")
        if field_list:
            message = f"检测到隐藏配置退化，但因{reason_label}未自动修复：{field_list}。"
        else:
            message = f"检测到隐藏配置退化，但因{reason_label}未自动修复。"
        return {
            "kind": "blocked_hidden",
            "fields": fields,
            "message": message,
            "block_reason": block_reason or "blocked_provenance_missing",
        }

    @staticmethod
    def notices(*candidates: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        notices: List[Dict[str, Any]] = []
        for notice in candidates:
            if isinstance(notice, dict) and (notice.get("message") or notice.get("fields")):
                notices.append(notice)
        return notices

    @staticmethod
    def save_status(plan: ConfigPageWritePlan) -> str:
        if plan.blocked_hidden_repairs:
            return "blocked_hidden_repair"
        if plan.hidden_repaired_fields:
            return "repaired_hidden"
        if plan.updates:
            return "saved"
        return "unchanged"


__all__ = ["ConfigPageSavePolicy"]
