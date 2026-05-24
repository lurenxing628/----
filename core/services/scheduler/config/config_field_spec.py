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
_GRAPH_ANALYSIS_MODE_LABELS = {
    "off": "关闭",
    "report": "只看分析报告",
    "on": "参与排产",
}
_GRAPH_CANDIDATE_WEIGHT_COUNT_LABELS = {"3": "3 档（更快）", "5": "5 档（默认）", "7": "7 档（更细）"}
_GRAPH_SELECTION_POLICY_LABELS = {"balanced": "综合看交期和整体分数", "score_only": "只看整体分数"}
_GRAPH_OVERDUE_TOLERANCE_COUNT_LABELS = {"0": "0 批", "1": "1 批（默认）", "2": "2 批"}
_GRAPH_TARDINESS_TOLERANCE_RATIO_LABELS = {"0.05": "5%", "0.1": "10%（默认）", "0.2": "20%"}

_FIELD_LABEL_ALIASES = {
    "preset_name": "方案名称",
    "preset": "方案数据",
}


def _choice_pairs(choice_labels: Dict[str, str]) -> Tuple[Dict[str, str], ...]:
    return tuple({"value": key, "label": value} for key, value in choice_labels.items())


def _candidate_option_spec(
    key: str,
    field_type: str,
    default: Any,
    label: str,
    description: str,
    choices: Tuple[str, ...],
    choice_labels: Dict[str, str],
    hint: str,
) -> ConfigFieldSpec:
    return ConfigFieldSpec(
        key=key,
        field_type=field_type,
        default=default,
        label=label,
        description=description,
        choices=choices,
        choice_labels=dict(choice_labels),
        page_metadata=ConfigFieldPageMetadata(key=key, label=label, hint=hint, choices=_choice_pairs(choice_labels)),
    )


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
        description="工作日历：假期工作效率（>0；假期安排工作且效率未填时使用）",
        min_value=0.0,
        min_inclusive=False,
    ),
    ConfigFieldSpec(
        key="enforce_ready_default",
        field_type="yes_no",
        default="no",
        label="默认启用齐套检查",
        description="默认关闭。关闭时，齐套和齐套日期只作为显示信息；打开后，只要所选批次里有未齐套或部分齐套，本次排产会报错并停止；系统不会自动跳过这些批次继续排其它批次，齐套日期只对齐套批次作为最早开工日。",
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
        label="找更好排法先试多久",
        description="精细计算会在这段时间里多试排法，建议不超过 180 秒",
        min_value=1,
        page_metadata=ConfigFieldPageMetadata(
            key="time_budget_seconds",
            label="找更好排法先试多久",
            hint="精细计算时，系统会在这段时间里多试排法。时间到了以后不再开始新的排法；已经开始算的会算完。填的是秒数，例如 20。",
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
    ConfigFieldSpec(
        key="graph_analysis_mode",
        field_type="enum",
        default="on",
        label="工序图分析",
        description="工序先后关系分析：关闭 / 只看分析报告 / 检查通过后参与排产",
        choices=("off", "report", "on"),
        choice_labels=dict(_GRAPH_ANALYSIS_MODE_LABELS),
        page_metadata=ConfigFieldPageMetadata(
            key="graph_analysis_mode",
            label="工序图分析",
            hint="默认选择“参与排产”。这样每次排产都会先排普通方案，再试几档重点工序优先方案，最后自动采用更合适的一版。",
            choices=_choice_pairs(_GRAPH_ANALYSIS_MODE_LABELS),
        ),
    ),
    ConfigFieldSpec(
        key="graph_block_on_cycle",
        field_type="yes_no",
        default="no",
        label="工序关系互相卡住时停止排产",
        description="工序先后关系互相卡住时是否停止排产；默认不停止",
        choices=_YES_NO_CHOICES,
        choice_labels=_YES_NO_LABELS,
        page_metadata=ConfigFieldPageMetadata(
            key="graph_block_on_cycle",
            label="工序关系互相卡住时停止排产",
            hint="一般保持关闭。打开后，如果发现工序先后关系互相卡住，本次排产会直接停下，让你先修资料；关闭时会在结果里提醒问题，排产继续走可用的方案。",
        ),
    ),
    ConfigFieldSpec(
        key="graph_critical_weight",
        field_type="int",
        default=500,
        label="重点工序提前权重",
        description="选择“参与排产”且工序关系可用时，影响完工时间的工序会更靠前；填 0 表示不按这项加分",
        min_value=0,
        page_metadata=ConfigFieldPageMetadata(
            key="graph_critical_weight",
            label="重点工序提前权重",
            hint="选择“参与排产”且工序关系可用时生效。数值越大，越影响完工时间的工序越容易提前；填 0 表示不使用这项加分。",
        ),
    ),
    ConfigFieldSpec(
        key="graph_impact_weight",
        field_type="int",
        default=10,
        label="后续影响权重",
        description="选择“参与排产”且工序关系可用时，会影响更多后续工序的当前工序会更靠前；填 0 表示不按影响范围加分",
        min_value=0,
        page_metadata=ConfigFieldPageMetadata(
            key="graph_impact_weight",
            label="后续影响权重",
            hint="选择“参与排产”且工序关系可用时生效。数值越大，后面牵着更多工序的当前工序越容易提前；填 0 表示不使用这项加分。",
        ),
    ),
    _candidate_option_spec("graph_candidate_weight_count", "int", 5, "重点工序方案档数", "参与排产时，系统额外尝试几档重点工序优先方案", ("3", "5", "7"), _GRAPH_CANDIDATE_WEIGHT_COUNT_LABELS, "默认 5 档。档数越多，系统会多试几种排法，结果更容易挑细一点，但也会多花一点时间。"),
    _candidate_option_spec("graph_selection_policy", "enum", "balanced", "最终方案选择方式", "系统自动挑最终采用方案时使用的规则", ("balanced", "score_only"), _GRAPH_SELECTION_POLICY_LABELS, "默认综合判断。综合判断会先避免明显拖期更多的方案，再看整体排产分数；只看整体分数则完全按分数最高的方案来选。"),
    _candidate_option_spec("graph_overdue_tolerance_count", "int", 1, "允许多超期批次数", "综合选择方案时，最多允许比当前最好方案多几个超期批次", ("0", "1", "2"), _GRAPH_OVERDUE_TOLERANCE_COUNT_LABELS, "默认 1 批。综合判断时，如果一个方案让超期批次数多太多，系统不会只因为分数高就采用它。"),
    _candidate_option_spec("graph_tardiness_tolerance_ratio", "float", 0.10, "允许多拖期比例", "综合选择方案时，最多允许比当前最好方案多出的拖期比例", ("0.05", "0.1", "0.2"), _GRAPH_TARDINESS_TOLERANCE_RATIO_LABELS, "默认 10%。综合判断时，如果一个方案拖期时间多太多，系统不会只因为分数高就采用它。"),
    ConfigFieldSpec(
        key="graph_debug_export",
        field_type="yes_no",
        default="no",
        label="导出工序图排查文件",
        description="是否导出工序先后关系排查文件",
        choices=_YES_NO_CHOICES,
        choice_labels=_YES_NO_LABELS,
        page_metadata=ConfigFieldPageMetadata(
            key="graph_debug_export",
            label="导出工序图排查文件",
            hint="默认关闭。一般调度员不用打开；需要排查工序前后关系问题时，再由维护人员开启。",
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
