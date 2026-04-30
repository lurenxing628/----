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
    ),
    ConfigFieldSpec(
        key="due_weight",
        field_type="float",
        default=0.5,
        label="交期权重",
        description="权重模式-交期权重",
        min_value=0.0,
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
        description="执行排产：默认启用齐套约束（yes/no）",
        choices=_YES_NO_CHOICES,
        choice_labels=_YES_NO_LABELS,
    ),
    ConfigFieldSpec(
        key="prefer_primary_skill",
        field_type="yes_no",
        default="no",
        label="优先推荐主操/高技能人员",
        description="工序补充页：优先推荐主操/高技能人员（yes/no）",
        choices=_YES_NO_CHOICES,
        choice_labels=_YES_NO_LABELS,
    ),
    ConfigFieldSpec(
        key="dispatch_mode",
        field_type="enum",
        default="batch_order",
        label="派工方式",
        description="派工方式：batch_order/sgs（sgs=就绪集合动态派工）",
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
        description="SGS 派工规则：slack/cr/atc（仅 dispatch_mode=sgs 生效）",
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
        description="算法自动分配缺省资源（内部工序 machine/operator 未填时）",
        choices=_YES_NO_CHOICES,
        choice_labels=_YES_NO_LABELS,
    ),
    ConfigFieldSpec(
        key="auto_assign_persist",
        field_type="yes_no",
        default="yes",
        label="自动分配结果回写",
        description="排产后将自动分配的设备/人员回写到工序（内部隐藏字段）",
        choices=_YES_NO_CHOICES,
        choice_labels=_YES_NO_LABELS,
        hidden=True,
    ),
    ConfigFieldSpec(
        key="ortools_enabled",
        field_type="yes_no",
        default="no",
        label="深度优化",
        description="可选 OR-Tools 高质量模式（若环境已安装）",
        choices=_YES_NO_CHOICES,
        choice_labels=_YES_NO_LABELS,
    ),
    ConfigFieldSpec(
        key="ortools_time_limit_seconds",
        field_type="int",
        default=5,
        label="自动优化计算时间",
        description="OR-Tools 单次求解时间上限（秒；仅 ortools_enabled=yes 生效）",
        min_value=1,
    ),
    ConfigFieldSpec(
        key="algo_mode",
        field_type="enum",
        default="greedy",
        label="计算模式",
        description="算法模式：greedy/improve（improve=多起点+目标函数+时间预算）",
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
        description="算法时间预算（秒；仅 improve 模式生效；建议<=180）",
        min_value=1,
    ),
    ConfigFieldSpec(
        key="objective",
        field_type="enum",
        default="min_overdue",
        label="优化目标",
        description="目标函数：min_overdue/min_tardiness/min_weighted_tardiness/min_changeover",
        choices=tuple(_OBJECTIVE_LABELS.keys()),
        choice_labels=dict(_OBJECTIVE_LABELS),
    ),
    ConfigFieldSpec(
        key="freeze_window_enabled",
        field_type="yes_no",
        default="no",
        label="锁定近期排程",
        description="冻结窗口开关（yes/no）：复用上一版本窗口内排程",
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
        description="冻结窗口天数（>=0；仅 freeze_window_enabled=yes 生效）",
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
