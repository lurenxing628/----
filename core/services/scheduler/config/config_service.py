from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

from core.infrastructure.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.services.common.normalize import normalize_text
from core.services.common.safe_logging import safe_warning
from core.services.scheduler.degradation_messages import public_degradation_events
from data.repositories import ConfigRepository

from ..number_utils import parse_finite_float
from . import config_presets as preset_ops
from .config_field_spec import (
    MISSING_POLICY_ERROR,
    choice_label_map_for,
    choices_for,
    coerce_config_field,
    default_for,
    default_snapshot_values,
    field_label_for,
    get_field_spec,
    list_config_fields,
    page_metadata_for,
)
from .config_snapshot import ScheduleConfigSnapshot, ensure_schedule_config_snapshot

_PUBLIC_OUTCOME_HIDDEN_SNAPSHOT_FIELDS = {"auto_assign_persist"}


def _public_config_field_label(field: str) -> str:
    normalized = str(field or "").strip()
    if not normalized:
        return "隐藏配置"
    label = str(field_label_for(normalized) or "").strip()
    if label and label != normalized:
        return label
    return "隐藏配置" if "_" in normalized else (label or normalized)


def _public_config_field_labels(fields: Sequence[str]) -> List[str]:
    labels: List[str] = []
    for field_name in list(fields or []):
        label = _public_config_field_label(str(field_name or "").strip())
        if label and label not in labels:
            labels.append(label)
    return labels


def _public_config_snapshot_dict(snapshot: Optional[ScheduleConfigSnapshot]) -> Optional[Dict[str, Any]]:
    if snapshot is None:
        return None
    data = snapshot.to_dict()
    for field_name in _PUBLIC_OUTCOME_HIDDEN_SNAPSHOT_FIELDS:
        data.pop(field_name, None)
    return data


def _public_config_notice(notice: Dict[str, Any]) -> Dict[str, Any]:
    kind = str(notice.get("kind") or "").strip()
    labels = _public_config_field_labels([str(field) for field in list(notice.get("fields") or [])])
    if kind == "blocked_hidden":
        label_text = "、".join(labels or ["隐藏配置"])
        message = f"检测到后台设置“{label_text}”需要保存修复，但因来源缺失未自动修复。"
    elif kind == "hidden":
        label_text = "、".join(labels or ["隐藏配置"])
        message = f"后台设置“{label_text}”已按当前表单保存为自定义配置。"
    elif kind == "visible":
        message = "页面展示的兼容回退值已被显式保存，当前运行配置已转为自定义。"
    elif kind == "none":
        message = None
    else:
        message = "配置来源状态已更新。" if kind else None
    out: Dict[str, Any] = {"kind": kind, "message": message}
    if labels:
        out["field_labels"] = labels
    return out


def _public_config_notices(notices: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [_public_config_notice(dict(notice or {})) for notice in list(notices or []) if isinstance(notice, dict)]


def _public_active_preset_reason(value: Any) -> Optional[str]:
    reason = str(value or "").strip()
    if not reason:
        return None
    if "兼容修补已回写隐藏配置项" in reason:
        return "后台设置已按当前表单保存为自定义配置。"
    if "_" in reason:
        return "配置来源状态已更新。"
    return reason


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
        return {
            "status": self.status,
            "effective_snapshot": _public_config_snapshot_dict(self.snapshot),
            "normalized_snapshot": _public_config_snapshot_dict(self.normalized_snapshot),
            "degradation_events": public_degradation_events(getattr(self.snapshot, "degradation_events", ()) or ()),
            "degradation_counters": dict(getattr(self.snapshot, "degradation_counters", {}) or {}),
            "visible_changed_field_labels": _public_config_field_labels(self.visible_changed_fields),
            "visible_repaired_field_labels": _public_config_field_labels(self.visible_repaired_fields),
            "hidden_repaired_field_labels": _public_config_field_labels(self.hidden_repaired_fields),
            "blocked_hidden_repair_labels": _public_config_field_labels(self.blocked_hidden_repairs),
            "notices": _public_config_notices(self.notices),
            "active_preset_after": self.active_preset_after,
            "active_preset_reason_after": _public_active_preset_reason(self.active_preset_reason_after),
        }


@dataclass
class _ConfigPageWritePlan:
    updates: List[Any] = field(default_factory=list)
    hidden_repaired_fields: List[str] = field(default_factory=list)
    blocked_hidden_repairs: List[str] = field(default_factory=list)
    notices: List[Dict[str, Any]] = field(default_factory=list)
    active_preset_after: Optional[str] = None
    active_preset_reason_after: Optional[str] = None


class ConfigService:
    """排产策略配置服务（ScheduleConfig）。"""

    PRESET_PREFIX = "preset."
    ACTIVE_PRESET_KEY = "active_preset"
    ACTIVE_PRESET_REASON_KEY = "active_preset_reason"
    ACTIVE_PRESET_META_KEY = "active_preset_meta"
    ACTIVE_PRESET_CUSTOM = "custom"
    ACTIVE_PRESET_META_REASON_MANUAL = "manual"
    ACTIVE_PRESET_META_REASON_VISIBLE_REPAIR = "visible_repair"
    ACTIVE_PRESET_META_REASON_HIDDEN_REPAIR = "hidden_repair"
    BUILTIN_PRESET_DEFAULT = "默认-稳定"
    BUILTIN_PRESET_DUE_FIRST = "交期优先"
    BUILTIN_PRESET_MIN_CHANGEOVER = "换型最少"
    BUILTIN_PRESET_IMPROVE_SLOW = "改进-更优(慢)"
    ACTIVE_PRESET_REASON_MANUAL = "已手工修改排产配置。"
    ACTIVE_PRESET_REASON_CUSTOM_SELECTED = "当前以手动设置为准。"
    ACTIVE_PRESET_REASON_PRESET_ADJUSTED = "方案应用时发生规范化或修补，当前运行配置与所选方案存在差异。"
    ACTIVE_PRESET_REASON_PRESET_MISMATCH = "方案写入后的实际配置与目标方案不一致，当前运行配置与所选方案存在差异。"
    ACTIVE_PRESET_REASON_PRESET_DELETED = "当前方案已删除，现有配置已保留为自定义。"
    ACTIVE_PRESET_REASON_BASELINE_MISMATCH = "当前配置与内置默认方案不一致。"
    ACTIVE_PRESET_REASON_BASELINE_DEGRADED = "历史配置存在兼容修补，已按自定义配置处理。"
    ACTIVE_PRESET_REASON_HIDDEN_REPAIR = "兼容修补已回写隐藏配置项。"
    ACTIVE_PRESET_REASON_VISIBLE_REPAIR = "页面展示的兼容回退值已被显式保存，当前运行配置已转为自定义。"

    DEFAULT_SORT_STRATEGY = str(default_for("sort_strategy"))
    DEFAULT_PRIORITY_WEIGHT = float(default_for("priority_weight"))
    DEFAULT_DUE_WEIGHT = float(default_for("due_weight"))
    DEFAULT_READY_WEIGHT = float(default_for("ready_weight"))
    DEFAULT_ENFORCE_READY_DEFAULT = str(default_for("enforce_ready_default"))
    DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY = float(default_for("holiday_default_efficiency"))
    DEFAULT_DISPATCH_MODE = str(default_for("dispatch_mode"))
    DEFAULT_DISPATCH_RULE = str(default_for("dispatch_rule"))
    DEFAULT_AUTO_ASSIGN_ENABLED = str(default_for("auto_assign_enabled"))
    DEFAULT_AUTO_ASSIGN_PERSIST = str(default_for("auto_assign_persist"))
    DEFAULT_ORTOOLS_ENABLED = str(default_for("ortools_enabled"))
    DEFAULT_ORTOOLS_TIME_LIMIT_SECONDS = int(default_for("ortools_time_limit_seconds"))
    DEFAULT_ALGO_MODE = str(default_for("algo_mode"))
    DEFAULT_TIME_BUDGET_SECONDS = int(default_for("time_budget_seconds"))
    DEFAULT_OBJECTIVE = str(default_for("objective"))
    DEFAULT_FREEZE_WINDOW_ENABLED = str(default_for("freeze_window_enabled"))
    DEFAULT_FREEZE_WINDOW_DAYS = int(default_for("freeze_window_days"))
    HOLIDAY_DEFAULT_EFFICIENCY_PAGE_WARNING_TEMPLATE = (
        "“假期工作效率”配置当前无效，页面已临时按 {value:g} 显示默认值；"
        "请先到排产参数页修复配置后再继续依赖该默认值进行操作。"
    )

    VALID_STRATEGIES = choices_for("sort_strategy")
    VALID_ALGO_MODES = choices_for("algo_mode")
    VALID_OBJECTIVES = choices_for("objective")
    VALID_DISPATCH_MODES = choices_for("dispatch_mode")
    VALID_DISPATCH_RULES = choices_for("dispatch_rule")

    STRATEGY_NAME_ZH = choice_label_map_for("sort_strategy")
    CONFIG_PAGE_FIELDS: Tuple[str, ...] = (
        "sort_strategy",
        "holiday_default_efficiency",
        "prefer_primary_skill",
        "enforce_ready_default",
        "dispatch_mode",
        "dispatch_rule",
        "auto_assign_enabled",
        "ortools_enabled",
        "ortools_time_limit_seconds",
        "algo_mode",
        "objective",
        "time_budget_seconds",
        "freeze_window_enabled",
        "freeze_window_days",
    )
    CONFIG_PAGE_WRITE_FIELDS: Tuple[str, ...] = CONFIG_PAGE_FIELDS + (
        "priority_weight",
        "due_weight",
        "ready_weight",
    )
    CONFIG_PAGE_VISIBLE_CHANGE_FIELDS: Tuple[str, ...] = CONFIG_PAGE_FIELDS + (
        "priority_weight",
        "due_weight",
    )
    CONFIG_PAGE_HIDDEN_REPAIR_FIELDS: Tuple[str, ...] = ("auto_assign_persist",)

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.tx_manager = TransactionManager(conn)
        self.repo = ConfigRepository(conn, logger=logger)

    # -------------------------
    # 工具方法
    # -------------------------
    @staticmethod
    def _normalize_text(value: Any) -> Optional[str]:
        return normalize_text(value)

    @staticmethod
    def _normalize_weight(value: Any, field: str) -> float:
        """
        权重标准化为 0~1 的小数：
        - 允许输入 0.4
        - 允许输入 40（视为百分比）
        """
        if value is None or (isinstance(value, str) and value.strip() == ""):
            raise ValidationError(f"“{field}”不能为空", field=field)
        v = float(parse_finite_float(value, field=field, allow_none=False))
        if v < 0:
            raise ValidationError(f"“{field}”不能为负数", field=field)
        if v > 1.0:
            v = v / 100.0
        if v > 1.0:
            raise ValidationError(f"“{field}”范围不合理（期望 0~1 或 0~100%）", field=field)
        return float(v)

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
        def _to_float(val: Any, field: str) -> float:
            if val is None or (isinstance(val, str) and val.strip() == ""):
                raise ValidationError(f"“{field}”不能为空", field=field)
            return float(parse_finite_float(val, field=field, allow_none=False))

        raw_pw = _to_float(priority_weight, "优先级权重")
        raw_dw = _to_float(due_weight, "交期权重")
        raw_rw = _to_float(ready_weight, "齐套权重")

        for raw, field_name in ((raw_pw, "优先级权重"), (raw_dw, "交期权重"), (raw_rw, "齐套权重")):
            if raw < 0:
                raise ValidationError(f"“{field_name}”不能为负数", field=field_name)

        percent_mode = (raw_pw > 1.0) or (raw_dw > 1.0) or (raw_rw > 1.0)
        if percent_mode:
            for raw, field in ((raw_pw, "优先级权重"), (raw_dw, "交期权重"), (raw_rw, "齐套权重")):
                if 0 < raw < 1:
                    raise ValidationError("权重输入疑似混用小数与百分比，请统一使用 0~1 或 0~100（%）。", field="权重")
                if raw > 100:
                    raise ValidationError(f"“{field}”范围不合理（期望 0~100%）", field=field)
            pw = raw_pw / 100.0
            dw = raw_dw / 100.0
            rw = raw_rw / 100.0
        else:
            pw, dw, rw = raw_pw, raw_dw, raw_rw

        for v, field in ((pw, "优先级权重"), (dw, "交期权重"), (rw, "齐套权重")):
            if v > 1.0:
                raise ValidationError(f"“{field}”范围不合理（期望 0~1 或 0~100%）", field=field)

        total = float(pw + dw + rw)
        if require_sum_1 and abs(total - 1.0) > 1e-6:
            raise ValidationError("权重总和应为 1（或 100%）", field="权重")

        return float(pw), float(dw), float(rw)

    def _field_description(self, key: str) -> str:
        return get_field_spec(key).description

    def _registered_updates(self, values: Dict[str, Any]) -> List[Tuple[str, str, str]]:
        updates: List[Tuple[str, str, str]] = []
        for key, value in values.items():
            updates.append((key, str(value), self._field_description(key)))
        return updates

    def _get_raw_value(self, config_key: str, default: Any = None) -> Any:
        return self.repo.get_value(str(config_key), default=None if default is None else str(default))

    def _bootstrap_registered_defaults(self, *, existing_keys: Optional[set] = None) -> set:
        existing = set(existing_keys) if existing_keys is not None else {c.config_key for c in self.repo.list_all()}
        to_set: List[Tuple[str, str, str]] = []
        for spec in list_config_fields():
            if spec.key in existing:
                continue
            to_set.append((spec.key, str(spec.default), spec.description))

        if not to_set:
            return existing
        with self.tx_manager.transaction():
            for k, v, d in to_set:
                self.repo.set(k, v, description=d)
        existing.update(k for k, _v, _d in to_set)
        return existing

    def ensure_defaults(self) -> None:
        """
        确保默认配置与内置模板已落库（缺失则写入，不覆盖用户已有配置）。
        """
        if self._is_pristine_store():
            existing = self._bootstrap_registered_defaults(existing_keys=set())
            self._ensure_builtin_presets(existing_keys=existing)
            preset_ops.bootstrap_active_provenance_if_pristine(self)
            return
        existing = self._bootstrap_registered_defaults()
        self._ensure_builtin_presets(existing_keys=existing)

    def _is_pristine_store(self) -> bool:
        return int(self.repo.count_all() or 0) == 0

    def _ensure_defaults_if_pristine(self) -> bool:
        if not self._is_pristine_store():
            return False
        self.ensure_defaults()
        return True

    # -------------------------
    # 配置模板/方案（Preset）
    # -------------------------
    @classmethod
    def _preset_key(cls, name: str) -> str:
        return f"{cls.PRESET_PREFIX}{name}"

    @classmethod
    def _is_builtin_preset(cls, name: str) -> bool:
        return name in (
            cls.BUILTIN_PRESET_DEFAULT,
            cls.BUILTIN_PRESET_DUE_FIRST,
            cls.BUILTIN_PRESET_MIN_CHANGEOVER,
            cls.BUILTIN_PRESET_IMPROVE_SLOW,
        )

    def _default_snapshot(self) -> ScheduleConfigSnapshot:
        defaults = default_snapshot_values()
        return ScheduleConfigSnapshot(
            sort_strategy=str(defaults["sort_strategy"]),
            priority_weight=float(defaults["priority_weight"]),
            due_weight=float(defaults["due_weight"]),
            ready_weight=float(defaults["ready_weight"]),
            holiday_default_efficiency=float(defaults["holiday_default_efficiency"]),
            enforce_ready_default=str(defaults["enforce_ready_default"]),
            prefer_primary_skill=str(defaults["prefer_primary_skill"]),
            dispatch_mode=str(defaults["dispatch_mode"]),
            dispatch_rule=str(defaults["dispatch_rule"]),
            auto_assign_enabled=str(defaults["auto_assign_enabled"]),
            auto_assign_persist=str(defaults["auto_assign_persist"]),
            ortools_enabled=str(defaults["ortools_enabled"]),
            ortools_time_limit_seconds=int(defaults["ortools_time_limit_seconds"]),
            algo_mode=str(defaults["algo_mode"]),
            time_budget_seconds=int(defaults["time_budget_seconds"]),
            objective=str(defaults["objective"]),
            freeze_window_enabled=str(defaults["freeze_window_enabled"]),
            freeze_window_days=int(defaults["freeze_window_days"]),
        )

    def _builtin_presets(self) -> List[Tuple[str, ScheduleConfigSnapshot, str]]:
        return preset_ops.builtin_presets(self)

    @staticmethod
    def _snapshot_close(a: ScheduleConfigSnapshot, b: ScheduleConfigSnapshot) -> bool:
        return preset_ops.snapshot_close(a, b)

    def _ensure_builtin_presets(self, existing_keys: Optional[set] = None) -> None:
        preset_ops.ensure_builtin_presets(self, existing_keys=existing_keys)

    def _get_snapshot_from_repo(self, *, strict_mode: bool = False) -> ScheduleConfigSnapshot:
        return preset_ops.get_snapshot_from_repo(self, strict_mode=bool(strict_mode))

    def _list_config_rows(self, *, readonly: bool = True) -> List[Any]:
        if not bool(readonly):
            self.ensure_defaults()
        return list(self.repo.list_all())

    @classmethod
    def _extract_repair_fields(cls, reason: str) -> List[str]:
        marker = "已回写："
        if marker not in reason:
            return []
        suffix = str(reason.split(marker, 1)[1] or "").strip().rstrip("。")
        fields: List[str] = []
        for raw_field in suffix.split("、"):
            field = raw_field.strip()
            if "（" in field:
                field = field.split("（", 1)[0].strip()
            if "(" in field:
                field = field.split("(", 1)[0].strip()
            if field:
                fields.append(field)
        return fields

    @classmethod
    def _repair_notice_from_reason(cls, reason: str) -> Dict[str, Any]:
        if cls.ACTIVE_PRESET_REASON_HIDDEN_REPAIR in reason:
            return {
                "kind": "hidden",
                "fields": cls._extract_repair_fields(reason),
                "message": reason or cls.ACTIVE_PRESET_REASON_HIDDEN_REPAIR,
            }
        if cls.ACTIVE_PRESET_REASON_VISIBLE_REPAIR in reason:
            return {
                "kind": "visible",
                "fields": [],
                "message": reason or cls.ACTIVE_PRESET_REASON_VISIBLE_REPAIR,
            }
        return {"kind": "none", "fields": [], "message": None}

    @classmethod
    def _normalize_repair_notice(cls, notice: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(notice, dict):
            return None
        kind = str(notice.get("kind") or "").strip().lower()
        if kind not in {"visible", "hidden"}:
            return None
        fields: List[str] = []
        raw_fields = notice.get("fields")
        if isinstance(raw_fields, (list, tuple)):
            for raw_field in raw_fields:
                field = str(raw_field or "").strip()
                if field and field not in fields:
                    fields.append(field)
        message = str(notice.get("message") or "").strip()
        return {
            "kind": kind,
            "fields": fields,
            "message": message or None,
        }

    @classmethod
    def _active_preset_meta_payload(
        cls,
        *,
        reason_code: Optional[str],
        repair_notices: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        normalized_reason_code = str(reason_code or "").strip().lower() or None
        if normalized_reason_code not in {
            cls.ACTIVE_PRESET_META_REASON_MANUAL,
            cls.ACTIVE_PRESET_META_REASON_VISIBLE_REPAIR,
            cls.ACTIVE_PRESET_META_REASON_HIDDEN_REPAIR,
        }:
            normalized_reason_code = None
        notices: List[Dict[str, Any]] = []
        for raw_notice in repair_notices or []:
            notice = cls._normalize_repair_notice(raw_notice)
            if notice is not None:
                notices.append(notice)
        return {
            "reason_code": normalized_reason_code,
            "repair_notices": notices,
        }

    @classmethod
    def _legacy_active_preset_meta_from_reason(cls, reason: Optional[str]) -> Dict[str, Any]:
        reason_text = str(reason or "").strip()
        if not reason_text:
            return cls._active_preset_meta_payload(reason_code=None, repair_notices=[])
        if cls.ACTIVE_PRESET_REASON_HIDDEN_REPAIR in reason_text:
            return cls._active_preset_meta_payload(
                reason_code=cls.ACTIVE_PRESET_META_REASON_HIDDEN_REPAIR,
                repair_notices=[cls._repair_notice_from_reason(reason_text)],
            )
        if cls.ACTIVE_PRESET_REASON_VISIBLE_REPAIR in reason_text:
            return cls._active_preset_meta_payload(
                reason_code=cls.ACTIVE_PRESET_META_REASON_VISIBLE_REPAIR,
                repair_notices=[cls._repair_notice_from_reason(reason_text)],
            )
        if reason_text == cls.ACTIVE_PRESET_REASON_MANUAL:
            return cls._active_preset_meta_payload(
                reason_code=cls.ACTIVE_PRESET_META_REASON_MANUAL,
                repair_notices=[],
            )
        return cls._active_preset_meta_payload(reason_code=None, repair_notices=[])

    @classmethod
    def _active_preset_meta_from_value(
        cls,
        value: Any,
        *,
        reason_fallback: Optional[str] = None,
    ) -> Dict[str, Any]:
        data: Any = value
        if isinstance(data, str):
            text = str(data or "").strip()
            if text:
                try:
                    data = json.loads(text)
                except Exception:
                    data = None
            else:
                data = None
        if not isinstance(data, dict):
            data = {}
        meta = cls._active_preset_meta_payload(
            reason_code=data.get("reason_code"),
            repair_notices=data.get("repair_notices"),
        )
        if meta["reason_code"] is None and not meta["repair_notices"]:
            legacy = cls._legacy_active_preset_meta_from_reason(reason_fallback)
            if legacy["reason_code"] is not None or legacy["repair_notices"]:
                return legacy
        return meta

    @classmethod
    def _active_preset_meta_parse_warning(cls, value: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(value, str):
            return None
        text = str(value or "").strip()
        if not text:
            return None
        try:
            json.loads(text)
        except Exception:
            return {
                "field": cls.ACTIVE_PRESET_META_KEY,
                "message": "active_preset_meta 不是有效 JSON，已按历史来源信息继续显示。",
            }
        return None

    @classmethod
    def _serialize_active_preset_meta(cls, meta: Optional[Dict[str, Any]]) -> str:
        payload = cls._active_preset_meta_payload(
            reason_code=(meta or {}).get("reason_code"),
            repair_notices=(meta or {}).get("repair_notices"),
        )
        if payload["reason_code"] is None and not payload["repair_notices"]:
            return ""
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @classmethod
    def _compat_repair_notice(
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
        return cls._repair_notice_from_reason(str(reason_fallback or "").strip())

    @classmethod
    def _reason_in(cls, reason: str, *candidates: str) -> bool:
        return any(candidate and candidate in reason for candidate in candidates)

    def _builtin_preset_names(self) -> set[str]:
        return {
            str(name or "").strip()
            for name, _snapshot, _description in self._builtin_presets()
            if str(name or "").strip()
        }

    @staticmethod
    def _row_config_text(row: Optional[Any]) -> Optional[str]:
        text = str(getattr(row, "config_value", "") or "").strip()
        return text or None

    @staticmethod
    def _config_page_values_equal(left: Any, right: Any) -> bool:
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return abs(float(left) - float(right)) <= 1e-9
        return left == right

    def _try_load_preset_baseline_snapshot(self, active_text: str) -> Tuple[Optional[ScheduleConfigSnapshot], bool]:
        return preset_ops.try_load_preset_snapshot_for_baseline(self, active_text)

    def _active_preset_baseline_probe_state(
        self,
        *,
        current_snapshot: ScheduleConfigSnapshot,
        active_text: str,
        provenance_missing: bool,
    ) -> Dict[str, Any]:
        if provenance_missing or not active_text or active_text.lower() == self.ACTIVE_PRESET_CUSTOM:
            return {
                "baseline_probe_failed": False,
                "baseline_diff_fields": [],
            }
        baseline_snapshot, baseline_probe_failed = self._try_load_preset_baseline_snapshot(active_text)
        if baseline_snapshot is None:
            return {
                "baseline_probe_failed": bool(baseline_probe_failed),
                "baseline_diff_fields": [],
            }
        return {
            "baseline_probe_failed": False,
            "baseline_diff_fields": preset_ops.snapshot_diff_fields(current_snapshot, baseline_snapshot),
        }

    def _resolve_current_config_baseline(
        self,
        *,
        active_text: str,
        builtin_names: set[str],
        provenance_missing: bool,
    ) -> Dict[str, Any]:
        is_custom = active_text.lower() == self.ACTIVE_PRESET_CUSTOM if active_text else False
        baseline_key = active_text or None
        if provenance_missing:
            if active_text and not is_custom:
                return {
                    "baseline_key": baseline_key,
                    "baseline_label": active_text,
                    "baseline_source": "builtin" if active_text in builtin_names else "named",
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
            "baseline_source": "builtin" if active_text in builtin_names else "named",
            "is_custom": False,
        }

    @staticmethod
    def _current_config_missing_provenance_descriptor(baseline_label: str) -> Tuple[str, str, str]:
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

    @classmethod
    def _current_config_manual_reason(cls, reason: str) -> bool:
        return cls._reason_in(
            reason,
            cls.ACTIVE_PRESET_REASON_MANUAL,
            cls.ACTIVE_PRESET_REASON_CUSTOM_SELECTED,
            cls.ACTIVE_PRESET_REASON_PRESET_DELETED,
            cls.ACTIVE_PRESET_REASON_BASELINE_MISMATCH,
            cls.ACTIVE_PRESET_REASON_BASELINE_DEGRADED,
            cls.ACTIVE_PRESET_REASON_VISIBLE_REPAIR,
        )

    def _resolve_current_config_descriptor(
        self,
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
            return self._current_config_missing_provenance_descriptor(baseline_label)
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
                reason or f"当前运行配置与“{baseline_label}”存在差异。",
            )
        if self._reason_in(reason, self.ACTIVE_PRESET_REASON_PRESET_ADJUSTED, self.ACTIVE_PRESET_REASON_PRESET_MISMATCH):
            return (
                "adjusted",
                "与方案有差异",
                reason or f"当前运行配置与“{baseline_label}”存在差异。",
            )
        if degraded:
            if is_custom:
                return (
                    "degraded",
                    "存在兼容修补",
                    "当前运行配置存在兼容修补，但仍以手动设置为准；请保存后修复。",
                )
            return (
                "degraded",
                "存在兼容修补",
                f"当前运行配置存在兼容修补，不能视为与“{baseline_label}”完全一致；请保存后修复。",
            )
        if is_custom or self._current_config_manual_reason(reason):
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

    def _collect_preset_rows(self, rows: List[Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        by_key = {str(row.config_key or ""): row for row in rows}
        preset_rows: Dict[str, Any] = {}
        for row in rows:
            config_key = str(row.config_key or "")
            if not config_key.startswith(self.PRESET_PREFIX):
                continue
            name = config_key[len(self.PRESET_PREFIX) :].strip()
            if name:
                preset_rows[name] = row
        return by_key, preset_rows

    def _build_preset_entries(self, preset_rows: Dict[str, Any]) -> List[Dict[str, Any]]:
        custom_presets = dict(preset_rows)
        presets: List[Dict[str, Any]] = []
        for name, _snapshot, description in self._builtin_presets():
            row = custom_presets.pop(name, None)
            presets.append(
                {
                    "name": name,
                    "updated_at": getattr(row, "updated_at", None),
                    "config_key": self._preset_key(name),
                    "description": getattr(row, "description", None) or description,
                }
            )
        for name in sorted(custom_presets):
            row = custom_presets[name]
            presets.append(
                {
                    "name": name,
                    "updated_at": getattr(row, "updated_at", None),
                    "config_key": getattr(row, "config_key", self._preset_key(name)),
                    "description": getattr(row, "description", None),
                }
            )
        return presets

    def _active_preset_display_state_from_rows(self, by_key: Dict[str, Any]) -> Dict[str, Any]:
        active_row = by_key.get(self.ACTIVE_PRESET_KEY)
        active_reason_row = by_key.get(self.ACTIVE_PRESET_REASON_KEY)
        active_preset = self._row_config_text(active_row)
        active_preset_reason = self._row_config_text(active_reason_row)
        active_meta_row = by_key.get(self.ACTIVE_PRESET_META_KEY)
        active_preset_meta = self._active_preset_meta_from_value(
            self._row_config_text(active_meta_row),
            reason_fallback=active_preset_reason,
        )
        return self._active_preset_provenance_state(
            active_preset=active_preset,
            active_preset_reason=active_preset_reason,
            active_preset_meta=active_preset_meta,
            active_preset_missing=bool(active_row is None or active_preset is None),
            active_preset_reason_missing=bool(active_reason_row is None),
        )

    @classmethod
    def _active_preset_provenance_state(
        cls,
        *,
        active_preset: Optional[str],
        active_preset_reason: Optional[str],
        active_preset_meta: Optional[Dict[str, Any]],
        active_preset_missing: bool,
        active_preset_reason_missing: bool,
    ) -> Dict[str, Any]:
        active_text = str(active_preset or "").strip() or None
        reason_text = str(active_preset_reason or "").strip() or None
        meta = cls._active_preset_meta_from_value(active_preset_meta, reason_fallback=reason_text)
        custom_reason_missing = bool(
            active_text and active_text.lower() == cls.ACTIVE_PRESET_CUSTOM and not reason_text
        )
        provenance_missing = bool(
            active_preset_missing
            or active_preset_reason_missing
            or not active_text
            or custom_reason_missing
        )
        return {
            "active_preset": active_text,
            "active_preset_reason": reason_text,
            "active_preset_meta": meta,
            "active_preset_missing": bool(active_preset_missing),
            "active_preset_reason_missing": bool(active_preset_reason_missing),
            "provenance_missing": bool(provenance_missing),
            "can_preserve_baseline": bool(active_text) and not provenance_missing,
        }

    def _build_current_config_state(
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
    ) -> Dict[str, Any]:
        active_text = str(active_preset or "").strip()
        reason = str(active_preset_reason or "").strip()
        builtin_names = self._builtin_preset_names()
        baseline = self._resolve_current_config_baseline(
            active_text=active_text,
            builtin_names=builtin_names,
            provenance_missing=bool(provenance_missing),
        )
        resolved_baseline_diff_fields = list(baseline_diff_fields or [])
        resolved_baseline_probe_failed = bool(baseline_probe_failed) and not bool(baseline.get("is_custom"))
        baseline_drifted = bool(resolved_baseline_diff_fields) and not bool(baseline.get("is_custom"))
        degraded = bool(tuple(getattr(current_snapshot, "degradation_events", ()) or ())) or bool(provenance_missing)
        meta = self._active_preset_meta_from_value(active_preset_meta, reason_fallback=reason)
        raw_repair_notices = list(meta.get("repair_notices") or [])
        raw_repair_notice = self._compat_repair_notice(raw_repair_notices, reason_fallback=reason)
        repair_notices = _public_config_notices(raw_repair_notices)
        repair_notice = _public_config_notice(raw_repair_notice)
        state, status_label, label = self._resolve_current_config_descriptor(
            provenance_missing=bool(provenance_missing),
            degraded=degraded,
            baseline_probe_failed=resolved_baseline_probe_failed,
            baseline_drifted=baseline_drifted,
            is_custom=bool(baseline.get("is_custom")),
            baseline_label=str(baseline.get("baseline_label") or ""),
            reason=reason,
            repair_notice=repair_notice,
        )

        return {
            "state": state,
            "status_label": status_label,
            "label": label,
            "baseline_key": baseline.get("baseline_key"),
            "baseline_label": baseline.get("baseline_label"),
            "baseline_source": baseline.get("baseline_source"),
            "is_custom": bool(baseline.get("is_custom")),
            "is_builtin": bool((not bool(provenance_missing)) and (not bool(baseline.get("is_custom"))) and active_text in builtin_names),
            "degraded": bool(degraded),
            "provenance_missing": bool(provenance_missing),
            "active_preset_missing": bool(active_preset_missing),
            "active_preset_reason_missing": bool(active_preset_reason_missing),
            "reason": _public_active_preset_reason(reason),
            "baseline_probe_failed": resolved_baseline_probe_failed,
            "baseline_diff_fields": resolved_baseline_diff_fields,
            "repair_notices": repair_notices,
            "repair_notice": repair_notice,
        }

    def get_active_preset(self) -> Optional[str]:
        raw = self.repo.get_value(self.ACTIVE_PRESET_KEY, default=None)
        v = str(raw).strip() if raw is not None else ""
        return v if v else None

    def get_active_preset_reason(self) -> Optional[str]:
        raw = self.repo.get_value(self.ACTIVE_PRESET_REASON_KEY, default=None)
        v = str(raw).strip() if raw is not None else ""
        return v if v else None

    def get_active_preset_meta(self) -> Dict[str, Any]:
        raw = self.repo.get_value(self.ACTIVE_PRESET_META_KEY, default=None)
        return self._active_preset_meta_from_value(raw, reason_fallback=self.get_active_preset_reason())

    def get_preset_display_state(
        self,
        *,
        readonly: bool = True,
        current_snapshot: Optional[ScheduleConfigSnapshot] = None,
    ) -> Dict[str, Any]:
        rows = self._list_config_rows(readonly=bool(readonly))
        by_key, preset_rows = self._collect_preset_rows(rows)
        preset_state = self._active_preset_display_state_from_rows(by_key)
        snapshot = current_snapshot if current_snapshot is not None else self._get_snapshot_from_repo(strict_mode=False)
        baseline_probe_state = self._active_preset_baseline_probe_state(
            current_snapshot=snapshot,
            active_text=str(preset_state.get("active_preset") or "").strip(),
            provenance_missing=bool(preset_state.get("provenance_missing")),
        )
        baseline_probe_failed = bool(baseline_probe_state.get("baseline_probe_failed"))
        baseline_diff_fields = list(baseline_probe_state.get("baseline_diff_fields") or [])
        if baseline_probe_failed or baseline_diff_fields:
            preset_state = {
                **preset_state,
                "can_preserve_baseline": False,
            }
        active_preset_reason = str(preset_state.get("active_preset_reason") or "").strip()
        can_preserve_named_provenance_for_write = bool(
            preset_state.get("active_preset")
        ) and not bool(preset_state.get("provenance_missing")) and not baseline_probe_failed and not baseline_diff_fields and not self._reason_in(
            active_preset_reason,
            self.ACTIVE_PRESET_REASON_PRESET_ADJUSTED,
            self.ACTIVE_PRESET_REASON_PRESET_MISMATCH,
        )
        current_config_state = self._build_current_config_state(
            current_snapshot=snapshot,
            active_preset=preset_state["active_preset"],
            active_preset_reason=active_preset_reason,
            active_preset_meta=preset_state.get("active_preset_meta"),
            active_preset_missing=bool(preset_state["active_preset_missing"]),
            active_preset_reason_missing=bool(preset_state["active_preset_reason_missing"]),
            provenance_missing=bool(preset_state["provenance_missing"]),
            baseline_diff_fields=baseline_diff_fields,
            baseline_probe_failed=baseline_probe_failed,
        )
        return {
            "presets": self._build_preset_entries(preset_rows),
            **preset_state,
            "current_config_state": current_config_state,
            "can_preserve_named_provenance_for_write": can_preserve_named_provenance_for_write,
            "readonly": bool(readonly),
        }

    def _active_preset_update(self, name: Optional[str]) -> Tuple[str, str, str]:
        v = ("" if name is None else str(name)).strip()
        return (
            self.ACTIVE_PRESET_KEY,
            v if v else self.ACTIVE_PRESET_CUSTOM,
            "当前启用排产配置模板",
        )

    def _active_preset_reason_update(self, reason: Optional[str]) -> Tuple[str, str, str]:
        v = ("" if reason is None else str(reason)).strip()
        return (
            self.ACTIVE_PRESET_REASON_KEY,
            v,
            "当前启用排产配置模板的状态说明",
        )

    def _active_preset_meta_update(self, meta: Optional[Dict[str, Any]] = None) -> Tuple[str, str, str]:
        return (
            self.ACTIVE_PRESET_META_KEY,
            self._serialize_active_preset_meta(meta),
            "当前启用排产配置模板的结构化来源记录",
        )

    def _active_preset_updates(
        self,
        name: Optional[str],
        reason: Optional[str] = None,
        *,
        meta: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[str, str, str]]:
        resolved_meta = meta
        if resolved_meta is None:
            resolved_meta = self._legacy_active_preset_meta_from_reason(reason)
        return [
            self._active_preset_update(name),
            self._active_preset_reason_update(reason),
            self._active_preset_meta_update(resolved_meta),
        ]

    def _set_active_preset(self, name: Optional[str], *, reason: Optional[str] = None) -> None:
        with self.tx_manager.transaction():
            self.repo.set_batch(self._active_preset_updates(name, reason=reason))

    def mark_active_preset_custom(self, reason: Optional[str] = None) -> None:
        self._set_active_preset(
            self.ACTIVE_PRESET_CUSTOM,
            reason=(self.ACTIVE_PRESET_REASON_CUSTOM_SELECTED if reason is None else reason),
        )

    def list_presets(self) -> List[Dict[str, Any]]:
        return preset_ops.list_presets(self)

    def save_preset(self, name: Any) -> Dict[str, Any]:
        return preset_ops.save_preset(self, name)

    def delete_preset(self, name: Any) -> None:
        preset_ops.delete_preset(self, name)

    def _normalize_preset_snapshot(self, data: Dict[str, Any]) -> ScheduleConfigSnapshot:
        return preset_ops.normalize_preset_snapshot(self, data)

    def apply_preset(self, name: Any) -> Dict[str, Any]:
        return preset_ops.apply_preset(self, name)

    def get(self, config_key: str) -> Any:
        return self.repo.get_value(str(config_key), default=None)

    def _get_registered_field_value(self, key: str, *, strict_mode: bool, source: str) -> Any:
        if not bool(strict_mode):
            return getattr(self.get_snapshot(strict_mode=False), key)

        self._ensure_defaults_if_pristine()
        raw_value = self._get_raw_value(key)
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
            self._get_registered_field_value(
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
        safe_warning(logger if logger is not None else self.logger, f"{consumer}读取假期工作效率配置失败，暂按默认值展示：{value:g}")
        return value, True, self.HOLIDAY_DEFAULT_EFFICIENCY_PAGE_WARNING_TEMPLATE.format(value=value)

    # -------------------------
    # 查询
    # -------------------------
    def get_available_strategies(self) -> List[Dict[str, str]]:
        labels = choice_label_map_for("sort_strategy")
        return [{"key": key, "name": labels.get(key, key)} for key in choices_for("sort_strategy")]

    def get_snapshot(self, *, strict_mode: bool = False) -> ScheduleConfigSnapshot:
        if not bool(strict_mode):
            self._ensure_defaults_if_pristine()
        return self._get_snapshot_from_repo(strict_mode=bool(strict_mode))

    @staticmethod
    def get_page_metadata(keys: List[str]) -> Dict[str, Any]:
        return page_metadata_for(keys)

    @staticmethod
    def get_field_label(key: str) -> str:
        return field_label_for(key)

    @staticmethod
    def get_choice_labels(key: str) -> Dict[str, str]:
        return choice_label_map_for(key)

    # -------------------------
    # 更新
    # -------------------------
    @staticmethod
    def _config_page_value(form_values: Any, key: str) -> Any:
        getter = getattr(form_values, "get", None)
        if callable(getter):
            return getter(key)
        if isinstance(form_values, dict):
            return form_values.get(key)
        return getattr(form_values, key, None)

    @classmethod
    def _config_page_submitted_fields(cls, form_values: Any) -> set[str]:
        keys_getter = getattr(form_values, "keys", None)
        if callable(keys_getter):
            raw_keys = list(cast(Sequence[Any], keys_getter()))
        elif isinstance(form_values, dict):
            raw_keys = list(form_values.keys())
        else:
            raw_keys = []

        submitted_fields: set[str] = set()
        allowed_fields = set(cls.CONFIG_PAGE_WRITE_FIELDS)
        for raw_key in raw_keys:
            key = str(raw_key or "").strip()
            if not key or key not in allowed_fields:
                continue
            if cls._config_page_value(form_values, key) is None:
                continue
            submitted_fields.add(key)
        return submitted_fields

    def _normalize_config_page_weights(
        self,
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

        raw_pw = parse_finite_float(
            priority_raw if has_priority else current_snapshot.priority_weight,
            field="优先级权重",
            allow_none=False,
        )
        raw_dw = parse_finite_float(
            due_raw if has_due else current_snapshot.due_weight,
            field="交期权重",
            allow_none=False,
        )
        if raw_pw < 0 or raw_dw < 0:
            raise ValidationError("权重不能为负数", field="权重")

        percent_mode = float(raw_pw) > 1.0 or float(raw_dw) > 1.0
        raw_total = float(raw_pw) + float(raw_dw)
        raw_ready = (100.0 - raw_total) if percent_mode else (1.0 - raw_total)
        if raw_ready < -1e-9:
            raise ValidationError("优先级权重 + 交期权重 之和不能超过 1（或 100%）。", field="权重")
        return self._normalize_weights_triplet(
            raw_pw,
            raw_dw,
            max(0.0, float(raw_ready)),
            require_sum_1=True,
        )

    def _normalize_config_page_payload(
        self,
        form_values: Any,
        *,
        current_snapshot: ScheduleConfigSnapshot,
        submitted_fields: set[str],
    ) -> ScheduleConfigSnapshot:
        payload = current_snapshot.to_dict()
        for key in self.CONFIG_PAGE_FIELDS:
            if key not in submitted_fields:
                continue
            raw_value = self._config_page_value(form_values, key)
            payload[key] = raw_value

        priority_raw = self._config_page_value(form_values, "priority_weight") if "priority_weight" in submitted_fields else None
        due_raw = self._config_page_value(form_values, "due_weight") if "due_weight" in submitted_fields else None
        priority_weight, due_weight, ready_weight = self._normalize_config_page_weights(
            priority_raw,
            due_raw,
            current_snapshot,
        )
        payload["priority_weight"] = float(priority_weight)
        payload["due_weight"] = float(due_weight)
        payload["ready_weight"] = float(ready_weight)

        return ensure_schedule_config_snapshot(
            payload,
            strict_mode=True,
            source="scheduler.config_service.save_page_config",
        )

    def _config_page_write_values(
        self,
        snapshot: ScheduleConfigSnapshot,
        *,
        submitted_fields: set[str],
    ) -> Dict[str, Any]:
        values = snapshot.to_dict()
        write_fields = {key for key in self.CONFIG_PAGE_WRITE_FIELDS if key in submitted_fields}
        if "priority_weight" in submitted_fields or "due_weight" in submitted_fields:
            write_fields.add("ready_weight")
        return {key: values[key] for key in self.CONFIG_PAGE_WRITE_FIELDS if key in write_fields}

    @classmethod
    def _config_page_materialized_write_values(
        cls,
        *,
        current_snapshot: ScheduleConfigSnapshot,
        write_values: Dict[str, Any],
    ) -> Dict[str, Any]:
        current_values = current_snapshot.to_dict()
        degraded_fields = set(cls._snapshot_degraded_fields(current_snapshot))
        return {
            key: value
            for key, value in write_values.items()
            if key in degraded_fields or not cls._config_page_values_equal(current_values.get(key), value)
        }

    def _config_page_visible_changed_fields(
        self,
        *,
        current_snapshot: ScheduleConfigSnapshot,
        write_values: Dict[str, Any],
    ) -> List[str]:
        current_values = current_snapshot.to_dict()
        changed_fields: List[str] = []
        for key in self.CONFIG_PAGE_VISIBLE_CHANGE_FIELDS:
            if key in write_values and not self._config_page_values_equal(current_values.get(key), write_values.get(key)):
                changed_fields.append(key)
        return changed_fields

    @staticmethod
    def _snapshot_degraded_fields(snapshot: ScheduleConfigSnapshot) -> List[str]:
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

    @classmethod
    def _config_page_visible_repair_fields(
        cls,
        *,
        current_snapshot: ScheduleConfigSnapshot,
        write_values: Dict[str, Any],
    ) -> List[str]:
        current_values = current_snapshot.to_dict()
        degraded_fields = set(cls._snapshot_degraded_fields(current_snapshot))
        repaired_fields = [
            key
            for key in cls.CONFIG_PAGE_VISIBLE_CHANGE_FIELDS
            if key in write_values and key in degraded_fields
        ]
        weights_changed = any(
            key in write_values and not cls._config_page_values_equal(current_values.get(key), write_values.get(key))
            for key in ("priority_weight", "due_weight")
        )
        ready_weight_repaired = "ready_weight" in degraded_fields or not cls._config_page_values_equal(
            current_values.get("ready_weight"),
            write_values.get("ready_weight"),
        )
        if (
            "ready_weight" in write_values
            and ready_weight_repaired
            and not weights_changed
        ):
            repaired_fields.append("ready_weight")
        return repaired_fields

    @classmethod
    def _config_page_hidden_repair_values(
        cls,
        *,
        current_snapshot: ScheduleConfigSnapshot,
        normalized_snapshot: ScheduleConfigSnapshot,
    ) -> Dict[str, Any]:
        degraded_hidden_fields = set(cls._snapshot_degraded_fields(current_snapshot))
        values = normalized_snapshot.to_dict()
        repair_values: Dict[str, Any] = {}
        for key in cls.CONFIG_PAGE_HIDDEN_REPAIR_FIELDS:
            if key in degraded_hidden_fields and key in values:
                repair_values[key] = values[key]
        return repair_values

    @classmethod
    def _config_page_hidden_repair_reason(cls, hidden_repaired_fields: List[str]) -> str:
        field_items: List[str] = []
        for field_name in hidden_repaired_fields:
            field_key = str(field_name).strip()
            if not field_key:
                continue
            field_label = field_label_for(field_key)
            if field_label and field_label != field_key:
                field_items.append(f"{field_key}（{field_label}）")
            else:
                field_items.append(field_key)
        field_list = "、".join(field_items)
        if field_list:
            return f"{cls.ACTIVE_PRESET_REASON_HIDDEN_REPAIR} 已回写：{field_list}。"
        return cls.ACTIVE_PRESET_REASON_HIDDEN_REPAIR

    @classmethod
    def _config_page_visible_repair_notice(cls) -> Dict[str, Any]:
        return {
            "kind": "visible",
            "fields": [],
            "message": cls.ACTIVE_PRESET_REASON_VISIBLE_REPAIR,
        }

    @classmethod
    def _config_page_hidden_repair_notice(cls, hidden_repaired_fields: List[str]) -> Dict[str, Any]:
        return {
            "kind": "hidden",
            "fields": [str(field).strip() for field in hidden_repaired_fields if str(field).strip()],
            "message": cls._config_page_hidden_repair_reason(hidden_repaired_fields),
        }

    @classmethod
    def _config_page_blocked_hidden_repair_notice(cls, blocked_hidden_fields: List[str]) -> Dict[str, Any]:
        fields = [str(field).strip() for field in blocked_hidden_fields if str(field).strip()]
        field_list = "\u3001".join(field_label_for(field) for field in fields)
        if field_list:
            message = f"\u68c0\u6d4b\u5230\u9690\u85cf\u914d\u7f6e\u9000\u5316\uff0c\u4f46\u56e0\u6765\u6e90\u7f3a\u5931\u672a\u81ea\u52a8\u4fee\u590d\uff1a{field_list}\u3002"
        else:
            message = "\u68c0\u6d4b\u5230\u9690\u85cf\u914d\u7f6e\u9000\u5316\uff0c\u4f46\u56e0\u6765\u6e90\u7f3a\u5931\u672a\u81ea\u52a8\u4fee\u590d\u3002"
        return {
            "kind": "blocked_hidden",
            "fields": fields,
            "message": message,
        }

    def _config_page_current_provenance_state(
        self,
        *,
        current_snapshot: ScheduleConfigSnapshot,
    ) -> Dict[str, Any]:
        preset_display_state = self.get_preset_display_state(readonly=True, current_snapshot=current_snapshot)
        return {
            "active_preset": preset_display_state.get("active_preset"),
            "active_preset_reason": preset_display_state.get("active_preset_reason"),
            "active_preset_meta": preset_display_state.get("active_preset_meta"),
            "can_preserve_baseline": bool(preset_display_state.get("can_preserve_baseline")),
            "can_preserve_named_provenance_for_write": bool(
                preset_display_state.get("can_preserve_named_provenance_for_write")
            ),
        }

    @staticmethod
    def _config_page_notices(*candidates: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        notices: List[Dict[str, Any]] = []
        for notice in candidates:
            if isinstance(notice, dict) and (notice.get("message") or notice.get("fields")):
                notices.append(notice)
        return notices

    def _config_page_initial_write_plan(
        self,
        *,
        write_values: Dict[str, Any],
        current_active_preset: Optional[str],
        current_active_preset_reason: Optional[str],
        hidden_repaired_fields: List[str],
    ) -> Tuple[_ConfigPageWritePlan, Optional[Dict[str, Any]], Optional[str]]:
        hidden_repair_notice = (
            self._config_page_hidden_repair_notice(hidden_repaired_fields) if hidden_repaired_fields else None
        )
        hidden_repair_reason = hidden_repair_notice["message"] if hidden_repair_notice is not None else None
        plan = _ConfigPageWritePlan(
            updates=self._registered_updates(write_values),
            hidden_repaired_fields=list(hidden_repaired_fields),
            notices=self._config_page_notices(hidden_repair_notice),
            active_preset_after=current_active_preset,
            active_preset_reason_after=current_active_preset_reason,
        )
        return plan, hidden_repair_notice, hidden_repair_reason

    def _config_page_apply_visible_change_plan(
        self,
        *,
        plan: _ConfigPageWritePlan,
        hidden_repair_notice: Optional[Dict[str, Any]],
    ) -> None:
        repair_notices = [hidden_repair_notice] if hidden_repair_notice is not None else []
        plan.updates.extend(
            self._active_preset_updates(
                self.ACTIVE_PRESET_CUSTOM,
                reason=self.ACTIVE_PRESET_REASON_MANUAL,
                meta=self._active_preset_meta_payload(
                    reason_code=self.ACTIVE_PRESET_META_REASON_MANUAL,
                    repair_notices=repair_notices,
                ),
            )
        )
        plan.active_preset_after = self.ACTIVE_PRESET_CUSTOM
        plan.active_preset_reason_after = self.ACTIVE_PRESET_REASON_MANUAL

    def _config_page_apply_visible_repair_plan(
        self,
        *,
        plan: _ConfigPageWritePlan,
        hidden_repair_notice: Optional[Dict[str, Any]],
    ) -> None:
        repair_notices = [self._config_page_visible_repair_notice()]
        if hidden_repair_notice is not None:
            repair_notices.append(hidden_repair_notice)
        plan.updates.extend(
            self._active_preset_updates(
                self.ACTIVE_PRESET_CUSTOM,
                reason=self.ACTIVE_PRESET_REASON_VISIBLE_REPAIR,
                meta=self._active_preset_meta_payload(
                    reason_code=self.ACTIVE_PRESET_META_REASON_VISIBLE_REPAIR,
                    repair_notices=repair_notices,
                ),
            )
        )
        plan.active_preset_after = self.ACTIVE_PRESET_CUSTOM
        plan.active_preset_reason_after = self.ACTIVE_PRESET_REASON_VISIBLE_REPAIR

    def _config_page_apply_hidden_repair_plan(
        self,
        *,
        plan: _ConfigPageWritePlan,
        current_active_preset: str,
        current_active_preset_reason: Optional[str],
        current_active_preset_meta: Optional[Dict[str, Any]],
        hidden_repair_reason: Optional[str],
        hidden_repair_notice: Optional[Dict[str, Any]],
    ) -> None:
        current_reason = str(current_active_preset_reason or "").strip()
        preserved_named_reason = self._reason_in(
            current_reason,
            self.ACTIVE_PRESET_REASON_PRESET_ADJUSTED,
            self.ACTIVE_PRESET_REASON_PRESET_MISMATCH,
        )
        preserved_custom_reason = current_active_preset == self.ACTIVE_PRESET_CUSTOM and bool(current_reason)
        if preserved_named_reason or preserved_custom_reason:
            current_meta = self._active_preset_meta_from_value(
                current_active_preset_meta,
                reason_fallback=current_active_preset_reason,
            )
            repair_notices = list(current_meta.get("repair_notices") or [])
            if hidden_repair_notice is not None:
                repair_notices.append(hidden_repair_notice)
            reason_after = current_reason or None
            hidden_meta = self._active_preset_meta_payload(
                reason_code=current_meta.get("reason_code"),
                repair_notices=repair_notices,
            )
        else:
            reason_after = hidden_repair_reason
            hidden_meta = self._active_preset_meta_payload(
                reason_code=self.ACTIVE_PRESET_META_REASON_HIDDEN_REPAIR,
                repair_notices=[hidden_repair_notice] if hidden_repair_notice is not None else [],
            )
        plan.updates.extend(
            self._active_preset_updates(
                current_active_preset,
                reason=reason_after,
                meta=hidden_meta,
            )
        )
        plan.active_preset_after = current_active_preset
        plan.active_preset_reason_after = reason_after

    def _config_page_blocked_hidden_write_plan(
        self,
        *,
        write_values: Dict[str, Any],
        current_active_preset: Optional[str],
        current_active_preset_reason: Optional[str],
        hidden_repaired_fields: List[str],
    ) -> _ConfigPageWritePlan:
        blocked_hidden_repairs = list(hidden_repaired_fields)
        blocked_hidden_notice = self._config_page_blocked_hidden_repair_notice(blocked_hidden_repairs)
        blocked_write_values = dict(write_values)
        for key in blocked_hidden_repairs:
            blocked_write_values.pop(key, None)
        return _ConfigPageWritePlan(
            updates=self._registered_updates(blocked_write_values),
            hidden_repaired_fields=[],
            blocked_hidden_repairs=blocked_hidden_repairs,
            notices=self._config_page_notices(blocked_hidden_notice),
            active_preset_after=current_active_preset,
            active_preset_reason_after=current_active_preset_reason,
        )

    def _config_page_build_write_plan(
        self,
        *,
        write_values: Dict[str, Any],
        visible_changed_fields: List[str],
        visible_repaired_fields: List[str],
        hidden_repaired_fields: List[str],
        current_active_preset: Optional[str],
        current_active_preset_reason: Optional[str],
        current_active_preset_meta: Optional[Dict[str, Any]],
        can_preserve_named_provenance_for_write: bool,
    ) -> _ConfigPageWritePlan:
        blocked_hidden_repairs: List[str] = []
        blocked_hidden_notice: Optional[Dict[str, Any]] = None
        if hidden_repaired_fields and not (
            current_active_preset and can_preserve_named_provenance_for_write
        ):
            blocked_hidden_repairs = list(hidden_repaired_fields)
            blocked_hidden_notice = self._config_page_blocked_hidden_repair_notice(blocked_hidden_repairs)
            write_values = dict(write_values)
            for key in blocked_hidden_repairs:
                write_values.pop(key, None)
            hidden_repaired_fields = []

        plan, hidden_repair_notice, hidden_repair_reason = self._config_page_initial_write_plan(
            write_values=write_values,
            current_active_preset=current_active_preset,
            current_active_preset_reason=current_active_preset_reason,
            hidden_repaired_fields=hidden_repaired_fields,
        )
        if blocked_hidden_repairs:
            plan.blocked_hidden_repairs = list(blocked_hidden_repairs)
            plan.notices = self._config_page_notices(*plan.notices, blocked_hidden_notice)
        if visible_changed_fields:
            self._config_page_apply_visible_change_plan(
                plan=plan,
                hidden_repair_notice=hidden_repair_notice,
            )
            return plan
        if visible_repaired_fields:
            self._config_page_apply_visible_repair_plan(
                plan=plan,
                hidden_repair_notice=hidden_repair_notice,
            )
            return plan
        if not hidden_repaired_fields:
            return plan
        if current_active_preset and can_preserve_named_provenance_for_write:
            self._config_page_apply_hidden_repair_plan(
                plan=plan,
                current_active_preset=current_active_preset,
                current_active_preset_reason=current_active_preset_reason,
                current_active_preset_meta=current_active_preset_meta,
                hidden_repair_reason=hidden_repair_reason,
                hidden_repair_notice=hidden_repair_notice,
            )
            return plan
        return self._config_page_blocked_hidden_write_plan(
            write_values=write_values,
            current_active_preset=current_active_preset,
            current_active_preset_reason=current_active_preset_reason,
            hidden_repaired_fields=hidden_repaired_fields,
        )

    @staticmethod
    def _config_page_save_status(plan: _ConfigPageWritePlan) -> str:
        if plan.blocked_hidden_repairs:
            return "blocked_hidden_repair"
        if plan.hidden_repaired_fields:
            return "repaired_hidden"
        if plan.updates:
            return "saved"
        return "unchanged"

    def _config_page_raw_persisted_state(self) -> Tuple[Dict[str, Any], List[str]]:
        rows = self.repo.list_all()
        by_key = {str(getattr(row, "config_key", "") or ""): row for row in rows}
        keys = [spec.key for spec in list_config_fields()]
        keys.extend([self.ACTIVE_PRESET_KEY, self.ACTIVE_PRESET_REASON_KEY, self.ACTIVE_PRESET_META_KEY])
        raw_values: Dict[str, Any] = {}
        missing: List[str] = []
        seen = set()
        for key in keys:
            if key in seen:
                continue
            seen.add(key)
            row = by_key.get(key)
            if row is None:
                missing.append(key)
                continue
            raw_values[key] = getattr(row, "config_value", None)
        return raw_values, missing

    def save_page_config(self, form_values: Any) -> ConfigPageSaveOutcome:
        self._ensure_defaults_if_pristine()
        active_meta_raw = self.repo.get_value(self.ACTIVE_PRESET_META_KEY, default=None)
        meta_parse_warning = self._active_preset_meta_parse_warning(active_meta_raw)
        if meta_parse_warning:
            safe_warning(self.logger, str(meta_parse_warning["message"]))
        current_snapshot = self.get_snapshot(strict_mode=False)
        provenance_state = self._config_page_current_provenance_state(
            current_snapshot=current_snapshot,
        )
        current_active_preset = str(provenance_state.get("active_preset") or "").strip() or None
        current_active_preset_reason = str(provenance_state.get("active_preset_reason") or "").strip() or None
        current_active_preset_meta = provenance_state.get("active_preset_meta")
        submitted_fields = self._config_page_submitted_fields(form_values)
        normalized_snapshot = self._normalize_config_page_payload(
            form_values,
            current_snapshot=current_snapshot,
            submitted_fields=submitted_fields,
        )
        write_values = self._config_page_write_values(normalized_snapshot, submitted_fields=submitted_fields)
        visible_changed_fields = self._config_page_visible_changed_fields(
            current_snapshot=current_snapshot,
            write_values=write_values,
        )
        visible_repaired_fields = self._config_page_visible_repair_fields(
            current_snapshot=current_snapshot,
            write_values=write_values,
        )
        hidden_repair_values = self._config_page_hidden_repair_values(
            current_snapshot=current_snapshot,
            normalized_snapshot=normalized_snapshot,
        )
        hidden_repaired_fields = list(hidden_repair_values.keys())
        write_values.update(hidden_repair_values)
        materialized_write_values = self._config_page_materialized_write_values(
            current_snapshot=current_snapshot,
            write_values=write_values,
        )
        plan = self._config_page_build_write_plan(
            write_values=materialized_write_values,
            visible_changed_fields=visible_changed_fields,
            visible_repaired_fields=visible_repaired_fields,
            hidden_repaired_fields=hidden_repaired_fields,
            current_active_preset=current_active_preset,
            current_active_preset_reason=current_active_preset_reason,
            current_active_preset_meta=current_active_preset_meta,
            can_preserve_named_provenance_for_write=bool(
                provenance_state.get("can_preserve_named_provenance_for_write")
            ),
        )
        if plan.updates:
            with self.tx_manager.transaction():
                self.repo.set_batch(plan.updates)
        post_save_snapshot = self.get_snapshot(strict_mode=False)
        raw_persisted_values, raw_missing_fields = self._config_page_raw_persisted_state()
        return ConfigPageSaveOutcome(
            snapshot=post_save_snapshot,
            status=self._config_page_save_status(plan),
            normalized_snapshot=normalized_snapshot,
            raw_persisted_values=raw_persisted_values,
            raw_missing_fields=raw_missing_fields,
            meta_parse_warnings=[meta_parse_warning] if meta_parse_warning else [],
            visible_changed_fields=list(visible_changed_fields),
            visible_repaired_fields=list(visible_repaired_fields),
            hidden_repaired_fields=list(plan.hidden_repaired_fields),
            blocked_hidden_repairs=list(plan.blocked_hidden_repairs),
            notices=list(plan.notices),
            active_preset_after=plan.active_preset_after,
            active_preset_reason_after=plan.active_preset_reason_after,
        )

    def set_strategy(self, sort_strategy: Any) -> None:
        v = str(
            coerce_config_field(
                "sort_strategy",
                sort_strategy,
                strict_mode=True,
                source="scheduler.config_service.set_strategy",
            )
        )
        with self.tx_manager.transaction():
            self.repo.set("sort_strategy", v, description=self._field_description("sort_strategy"))
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def set_weights(self, priority_weight: Any, due_weight: Any, ready_weight: Any, require_sum_1: bool = True) -> None:
        pw, dw, rw = self._normalize_weights_triplet(
            priority_weight,
            due_weight,
            ready_weight,
            require_sum_1=require_sum_1,
        )

        with self.tx_manager.transaction():
            self.repo.set("priority_weight", str(pw), description=self._field_description("priority_weight"))
            self.repo.set("due_weight", str(dw), description=self._field_description("due_weight"))
            self.repo.set("ready_weight", str(rw), description=self._field_description("ready_weight"))
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def restore_default(self) -> None:
        updates = self._registered_updates(default_snapshot_values())
        updates.extend(self._active_preset_updates(self.BUILTIN_PRESET_DEFAULT))
        with self.tx_manager.transaction():
            self.repo.set_batch(updates)

    def set_dispatch(self, dispatch_mode: Any, dispatch_rule: Any) -> None:
        dm = str(
            coerce_config_field(
                "dispatch_mode",
                dispatch_mode,
                strict_mode=True,
                source="scheduler.config_service.set_dispatch",
            )
        )
        dr = str(
            coerce_config_field(
                "dispatch_rule",
                dispatch_rule,
                strict_mode=True,
                source="scheduler.config_service.set_dispatch",
            )
        )

        with self.tx_manager.transaction():
            self.repo.set("dispatch_mode", dm, description=self._field_description("dispatch_mode"))
            self.repo.set("dispatch_rule", dr, description=self._field_description("dispatch_rule"))
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def set_auto_assign_enabled(self, value: Any) -> None:
        yes_no = str(
            coerce_config_field(
                "auto_assign_enabled",
                value,
                strict_mode=True,
                source="scheduler.config_service.set_auto_assign_enabled",
            )
        )
        with self.tx_manager.transaction():
            self.repo.set("auto_assign_enabled", yes_no, description=self._field_description("auto_assign_enabled"))
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def set_ortools(self, enabled: Any, time_limit_seconds: Any) -> None:
        en_yesno = str(
            coerce_config_field(
                "ortools_enabled",
                enabled,
                strict_mode=True,
                source="scheduler.config_service.set_ortools",
            )
        )
        tl = int(
            coerce_config_field(
                "ortools_time_limit_seconds",
                time_limit_seconds,
                strict_mode=True,
                source="scheduler.config_service.set_ortools",
            )
        )
        with self.tx_manager.transaction():
            self.repo.set("ortools_enabled", en_yesno, description=self._field_description("ortools_enabled"))
            self.repo.set("ortools_time_limit_seconds", str(tl), description=self._field_description("ortools_time_limit_seconds"))
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def set_prefer_primary_skill(self, value: Any) -> None:
        yes_no = str(
            coerce_config_field(
                "prefer_primary_skill",
                value,
                strict_mode=True,
                source="scheduler.config_service.set_prefer_primary_skill",
            )
        )
        with self.tx_manager.transaction():
            self.repo.set("prefer_primary_skill", yes_no, description=self._field_description("prefer_primary_skill"))
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def set_enforce_ready_default(self, value: Any) -> None:
        yes_no = str(
            coerce_config_field(
                "enforce_ready_default",
                value,
                strict_mode=True,
                source="scheduler.config_service.set_enforce_ready_default",
            )
        )
        with self.tx_manager.transaction():
            self.repo.set("enforce_ready_default", yes_no, description=self._field_description("enforce_ready_default"))
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def set_holiday_default_efficiency(self, value: Any) -> None:
        if value is None or str(value).strip() == "":
            raise ValidationError("假期工作效率不能为空。", field="假期工作效率")
        v = float(
            coerce_config_field(
                "holiday_default_efficiency",
                value,
                strict_mode=True,
                source="scheduler.config_service.set_holiday_default_efficiency",
            )
        )
        with self.tx_manager.transaction():
            self.repo.set(
                "holiday_default_efficiency",
                str(float(v)),
                description=self._field_description("holiday_default_efficiency"),
            )
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def set_algo_mode(self, value: Any) -> None:
        v = str(
            coerce_config_field(
                "algo_mode",
                value,
                strict_mode=True,
                source="scheduler.config_service.set_algo_mode",
            )
        )
        with self.tx_manager.transaction():
            self.repo.set("algo_mode", v, description=self._field_description("algo_mode"))
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def set_time_budget_seconds(self, value: Any) -> None:
        if value is None or str(value).strip() == "":
            raise ValidationError("计算时间上限不能为空。", field="计算时间上限")
        v = int(
            coerce_config_field(
                "time_budget_seconds",
                value,
                strict_mode=True,
                source="scheduler.config_service.set_time_budget_seconds",
            )
        )
        with self.tx_manager.transaction():
            self.repo.set("time_budget_seconds", str(v), description=self._field_description("time_budget_seconds"))
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def set_objective(self, value: Any) -> None:
        v = str(
            coerce_config_field(
                "objective",
                value,
                strict_mode=True,
                source="scheduler.config_service.set_objective",
            )
        )
        with self.tx_manager.transaction():
            self.repo.set("objective", v, description=self._field_description("objective"))
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def set_freeze_window(self, enabled: Any, days: Any) -> None:
        en_yesno = str(
            coerce_config_field(
                "freeze_window_enabled",
                enabled,
                strict_mode=True,
                source="scheduler.config_service.set_freeze_window",
            )
        )
        d = int(
            coerce_config_field(
                "freeze_window_days",
                days,
                strict_mode=True,
                source="scheduler.config_service.set_freeze_window",
            )
        )
        with self.tx_manager.transaction():
            self.repo.set("freeze_window_enabled", en_yesno, description=self._field_description("freeze_window_enabled"))
            self.repo.set("freeze_window_days", str(d), description=self._field_description("freeze_window_days"))
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )
