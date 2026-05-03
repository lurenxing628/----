from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.models.objective import objective_choice_labels as _objective_choice_labels
from core.shared.degradation import DegradationCollector

MISSING_POLICY_ERROR = "error"
MISSING_POLICY_FALLBACK_WITH_DEGRADATION = "fallback_with_degradation"
MISSING_POLICY_INHERIT_LEGACY_OMISSION = "inherit_legacy_omission"


@dataclass(frozen=True)
class ConfigFieldPageMetadata:
    key: str
    label: str
    hint: str = ""
    unit: str = ""
    choices: Tuple[Dict[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ConfigFieldSpec:
    key: str
    field_type: str
    default: Any
    label: str
    description: str
    allow_blank: bool = False
    min_value: Optional[float] = None
    min_inclusive: bool = True
    choices: Tuple[str, ...] = field(default_factory=tuple)
    choice_labels: Dict[str, str] = field(default_factory=dict)
    page_metadata: Optional[ConfigFieldPageMetadata] = None
    hidden: bool = False


_YES_NO_LABELS = {
    "yes": "是",
    "no": "否",
}

_YES_NO_CHOICES = tuple(_YES_NO_LABELS.keys())
_OBJECTIVE_LABELS = _objective_choice_labels()

_FIELD_LABEL_ALIASES = {
    "preset_name": "方案名称",
    "preset": "方案数据",
}


def _choice_pairs(choice_labels: Dict[str, str]) -> Tuple[Dict[str, str], ...]:
    return tuple({"value": key, "label": value} for key, value in choice_labels.items())


_FIELD_SPECS: Tuple[ConfigFieldSpec, ...] = (
    ConfigFieldSpec(
        key="sort_strategy",
        field_type="enum",
        default="priority_first",
        label="排产策略",
        description="当前排序策略",
        choices=("priority_first", "due_date_first", "weighted", "fifo"),
        choice_labels={
            "priority_first": "优先级优先",
            "due_date_first": "交期优先",
            "weighted": "综合优先级和交期",
            "fifo": "先进先出",
        },
    ),
    ConfigFieldSpec(
        key="priority_weight",
        field_type="float",
        default=0.4,
        label="优先级权重",
        description="权重模式-优先级权重",
        min_value=0.0,
        page_metadata=ConfigFieldPageMetadata(
            key="priority_weight",
            label="优先级权重",
            hint="可以填 0 到 1 的小数；也可以填百分比，比如 40 表示 40%。数值越大，越优先照顾急件和特急件。",
        ),
    ),
    ConfigFieldSpec(
        key="due_weight",
        field_type="float",
        default=0.5,
        label="交期权重",
        description="权重模式-交期权重",
        min_value=0.0,
        page_metadata=ConfigFieldPageMetadata(
            key="due_weight",
            label="交期权重",
            hint="可以填 0 到 1 的小数；也可以填百分比，比如 50 表示 50%。数值越大，越优先照顾交期更近的批次。",
        ),
    ),
    ConfigFieldSpec(
        key="ready_weight",
        field_type="float",
        default=0.1,
        label="齐套权重",
        description="权重模式-齐套权重",
        min_value=0.0,
    ),
    ConfigFieldSpec(
        key="holiday_default_efficiency",
        field_type="float",
        default=0.8,
        label="假期工作效率",
        description="工作日历：假期默认效率（>0；假期安排工作且效率未填时使用）",
        min_value=0.0,
        min_inclusive=False,
    ),
    ConfigFieldSpec(
        key="enforce_ready_default",
        field_type="yes_no",
        default="no",
        label="排产前检查物料是否齐套",
        description="执行排产：默认是否检查齐套",
        choices=_YES_NO_CHOICES,
        choice_labels=_YES_NO_LABELS,
    ),
    ConfigFieldSpec(
        key="prefer_primary_skill",
        field_type="yes_no",
        default="no",
        label="优先推荐主操/高技能人员",
        description="工序补充页：是否优先推荐主操和高技能人员",
        choices=_YES_NO_CHOICES,
        choice_labels=_YES_NO_LABELS,
    ),
    ConfigFieldSpec(
        key="dispatch_mode",
        field_type="enum",
        default="batch_order",
        label="派工方式",
        description="派工方式：按批次顺序排 / 智能派工",
        choices=("batch_order", "sgs"),
        choice_labels={
            "batch_order": "按批次顺序排",
            "sgs": "智能派工（系统自动挑选当前更合适的任务）",
        },
        page_metadata=ConfigFieldPageMetadata(
            key="dispatch_mode",
            label="派工方式",
            choices=_choice_pairs(
                {
                    "batch_order": "按批次顺序排",
                    "sgs": "智能派工（系统自动挑选当前更合适的任务）",
                }
            ),
        ),
    ),
    ConfigFieldSpec(
        key="dispatch_rule",
        field_type="enum",
        default="slack",
        label="智能派工策略",
        description="智能派工策略：时间余量少的先做 / 交期更紧的先做 / 综合判断更紧急的先做",
        choices=("slack", "cr", "atc"),
        choice_labels={
            "slack": "时间余量少的先做",
            "cr": "交期更紧、剩余时间更吃紧的先做",
            "atc": "综合判断更紧急的先做",
        },
        page_metadata=ConfigFieldPageMetadata(
            key="dispatch_rule",
            label="智能派工策略",
            hint="仅智能派工时生效",
            choices=_choice_pairs(
                {
                    "slack": "时间余量少的先做",
                    "cr": "交期更紧、剩余时间更吃紧的先做",
                    "atc": "综合判断更紧急的先做",
                }
            ),
        ),
    ),
    ConfigFieldSpec(
        key="auto_assign_enabled",
        field_type="yes_no",
        default="no",
        label="未指定设备或人员时，系统自动分配",
        description="自制工序没有填写设备或人员时，是否由系统自动补上",
        choices=_YES_NO_CHOICES,
        choice_labels=_YES_NO_LABELS,
    ),
    ConfigFieldSpec(
        key="auto_assign_persist",
        field_type="yes_no",
        default="yes",
        label="保存系统补齐的设备和人员",
        description="系统帮你补上的设备和人员，是否保存回这道工序，方便下次排产继续用",
        choices=_YES_NO_CHOICES,
        choice_labels=_YES_NO_LABELS,
        hidden=True,
    ),
    ConfigFieldSpec(
        key="ortools_enabled",
        field_type="yes_no",
        default="no",
        label="深度优化",
        description="只在精细计算时尝试多找一个更好的起点；需要本机已安装对应的深度优化组件",
        choices=_YES_NO_CHOICES,
        choice_labels=_YES_NO_LABELS,
        page_metadata=ConfigFieldPageMetadata(
            key="ortools_enabled",
            label="深度优化",
            hint="只在精细计算时生效；系统会多花几秒尝试找更好的排法，优化目标就是当前页面选择的目标。",
        ),
    ),
    ConfigFieldSpec(
        key="ortools_time_limit_seconds",
        field_type="int",
        default=5,
        label="深度优化尝试时间",
        description="深度优化最多额外尝试多少秒；只在精细计算且深度优化开启时生效",
        min_value=1,
        page_metadata=ConfigFieldPageMetadata(
            key="ortools_time_limit_seconds",
            label="深度优化尝试时间",
            hint="最多多试几秒。不保证每次一定更好，但超过这个时间就会停下。",
            unit="秒",
        ),
    ),
    ConfigFieldSpec(
        key="algo_mode",
        field_type="enum",
        default="greedy",
        label="计算模式",
        description="计算模式：快速计算 / 精细计算",
        choices=("greedy", "improve"),
        choice_labels={
            "greedy": "快速计算",
            "improve": "精细计算（较慢，结果通常更好）",
        },
        page_metadata=ConfigFieldPageMetadata(
            key="algo_mode",
            label="计算模式",
            choices=_choice_pairs(
                {
                    "greedy": "快速计算",
                    "improve": "精细计算（较慢，结果通常更好）",
                }
            ),
        ),
    ),
    ConfigFieldSpec(
        key="time_budget_seconds",
        field_type="int",
        default=20,
        label="计算时间上限",
        description="精细计算最多尝试多少秒，建议不超过 180 秒",
        min_value=1,
        page_metadata=ConfigFieldPageMetadata(
            key="time_budget_seconds",
            label="计算时间上限",
            hint="精细计算时，系统最多在这段时间内尝试更多排法。填的是秒数，例如 20 表示最多算 20 秒。",
            unit="秒",
        ),
    ),
    ConfigFieldSpec(
        key="objective",
        field_type="enum",
        default="min_overdue",
        label="优化目标",
        description="优化目标：最少超期批次数 / 最少拖期小时 / 最少加权拖期小时 / 最少换型次数",
        choices=tuple(_OBJECTIVE_LABELS.keys()),
        choice_labels=dict(_OBJECTIVE_LABELS),
    ),
    ConfigFieldSpec(
        key="freeze_window_enabled",
        field_type="yes_no",
        default="no",
        label="锁定近期排程",
        description="锁定近期排程：复用上一版本近期排程，减少波动",
        choices=_YES_NO_CHOICES,
        choice_labels=_YES_NO_LABELS,
        page_metadata=ConfigFieldPageMetadata(
            key="freeze_window_enabled",
            label="锁定近期排程",
            hint="指定天数内的排程保持不变，不重新计算",
        ),
    ),
    ConfigFieldSpec(
        key="freeze_window_days",
        field_type="int",
        default=0,
        label="锁定天数",
        description="锁定近期排程的天数；未开启锁定时不生效",
        min_value=0,
        page_metadata=ConfigFieldPageMetadata(
            key="freeze_window_days",
            label="锁定天数",
            unit="天",
        ),
    ),
)

_FIELD_SPEC_BY_KEY: Dict[str, ConfigFieldSpec] = {spec.key: spec for spec in _FIELD_SPECS}
_UNSET = object()


def list_config_fields() -> Tuple[ConfigFieldSpec, ...]:
    return tuple(_FIELD_SPECS)


def has_config_field(key: str) -> bool:
    return str(key or "").strip() in _FIELD_SPEC_BY_KEY


def get_field_spec(key: str) -> ConfigFieldSpec:
    normalized_key = str(key or "").strip()
    if not normalized_key or normalized_key not in _FIELD_SPEC_BY_KEY:
        raise KeyError(f"未定义调度配置字段：{key!r}")
    return _FIELD_SPEC_BY_KEY[normalized_key]


def default_for(key: str) -> Any:
    return get_field_spec(key).default


def choices_for(key: str) -> Tuple[str, ...]:
    spec = get_field_spec(key)
    return tuple(spec.choices)


def field_label_for(key: str) -> str:
    normalized_key = str(key or "").strip()
    if normalized_key in _FIELD_SPEC_BY_KEY:
        return _FIELD_SPEC_BY_KEY[normalized_key].label
    return _FIELD_LABEL_ALIASES.get(normalized_key, normalized_key)


def choice_label_map_for(key: str) -> Dict[str, str]:
    spec = get_field_spec(key)
    if spec.choice_labels:
        return dict(spec.choice_labels)
    return {value: value for value in choices_for(key)}


def page_metadata_for(keys: List[str]) -> Dict[str, ConfigFieldPageMetadata]:
    out: Dict[str, ConfigFieldPageMetadata] = {}
    for key in list(keys or []):
        spec = get_field_spec(key)
        metadata = spec.page_metadata
        if metadata is None:
            metadata = ConfigFieldPageMetadata(
                key=spec.key,
                label=spec.label,
                choices=_choice_pairs(choice_label_map_for(spec.key)),
            )
        out[spec.key] = metadata
    return out


def normalize_text_field(key: str, value: Any) -> str:
    from .config_field_coercion import normalize_text_field as _normalize_text_field

    return _normalize_text_field(key, value)


def coerce_config_field(
    key: str,
    value: Any,
    *,
    strict_mode: bool,
    source: str,
    collector: Optional[DegradationCollector] = None,
    missing: bool = False,
    fallback: Any = _UNSET,
    missing_policy: str = MISSING_POLICY_FALLBACK_WITH_DEGRADATION,
) -> Any:
    from .config_field_coercion import coerce_config_field as _coerce_config_field

    kwargs = {
        "strict_mode": strict_mode,
        "source": source,
        "collector": collector,
        "missing": missing,
        "missing_policy": missing_policy,
    }
    if fallback is not _UNSET:
        kwargs["fallback"] = fallback
    return _coerce_config_field(key, value, **kwargs)


def default_snapshot_values() -> Dict[str, Any]:
    return {spec.key: spec.default for spec in list_config_fields()}
