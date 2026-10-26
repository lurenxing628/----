from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

from core.models.objective import objective_choice_labels as _objective_choice_labels
from core.models.schedule_config_runtime_coercion import (
    coerce_config_field as coerce_runtime_value,
)
from core.models.schedule_config_runtime_fields import (
    RuntimeConfigFieldSpec,
)
from core.models.schedule_config_runtime_fields import (
    get_field_spec as runtime_field_spec,
)


@dataclass(frozen=True)
class ConfigFieldSpec:
    """Service labels decorate the common runtime field semantics."""

    key: str
    label: str
    description: str
    choice_labels: Dict[str, str] = field(default_factory=dict)
    runtime: RuntimeConfigFieldSpec = field(init=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "runtime", runtime_field_spec(self.key))

    @property
    def field_type(self):
        return self.runtime.field_type

    @property
    def default(self):
        return self.runtime.default

    @property
    def choices(self):
        return self.runtime.choices


_YES_NO_LABELS = {
    "yes": "是",
    "no": "否",
}

_OBJECTIVE_LABELS = _objective_choice_labels()
_GRAPH_ANALYSIS_MODE_LABELS = {
    "off": "关闭",
    "report": "只看分析报告",
    "on": "参与排产",
}

_FIELD_SPECS: Tuple[ConfigFieldSpec, ...] = (
    ConfigFieldSpec(
        key="sort_strategy",
        label="排产策略",
        description="当前排序策略",
        choice_labels={
            "priority_first": "优先级优先",
            "due_date_first": "交期优先",
            "weighted": "综合优先级和交期",
            "fifo": "先进先出",
        },
    ),
    ConfigFieldSpec(
        key="priority_weight",
        label="优先级权重",
        description="权重模式-优先级权重",
    ),
    ConfigFieldSpec(
        key="due_weight",
        label="交期权重",
        description="权重模式-交期权重",
    ),
    ConfigFieldSpec(
        key="ready_weight",
        label="齐套权重",
        description="权重模式-齐套权重",
    ),
    ConfigFieldSpec(
        key="holiday_default_efficiency",
        label="假期工作效率",
        description="工作日历：假期工作效率（>0；假期安排工作且效率未填时使用）",
    ),
    ConfigFieldSpec(
        key="enforce_ready_default",
        label="默认启用齐套检查",
        description="默认关闭。关闭时，齐套和齐套日期只作为显示信息；打开后，只要所选批次里有未齐套或部分齐套，本次排产会报错并停止；系统不会自动跳过这些批次继续排其它批次，齐套日期只对齐套批次作为最早开工日。",
        choice_labels=_YES_NO_LABELS,
    ),
    ConfigFieldSpec(
        key="prefer_primary_skill",
        label="优先推荐主操/高技能人员",
        description="工序补充页：是否优先推荐主操和高技能人员",
        choice_labels=_YES_NO_LABELS,
    ),
    ConfigFieldSpec(
        key="dispatch_mode",
        label="派工方式",
        description="派工方式：按批次顺序排 / 智能派工",
        choice_labels={
            "batch_order": "按批次顺序排",
            "sgs": "智能派工（系统自动挑选当前更合适的任务）",
        },
    ),
    ConfigFieldSpec(
        key="dispatch_rule",
        label="智能派工策略",
        description="智能派工策略：时间余量少的先做 / 交期更紧的先做 / 综合判断更紧急的先做",
        choice_labels={
            "slack": "时间余量少的先做",
            "cr": "交期更紧、剩余时间更吃紧的先做",
            "atc": "综合判断更紧急的先做",
        },
    ),
    ConfigFieldSpec(
        key="auto_assign_enabled",
        label="未指定设备或人员时，系统自动分配",
        description="自制工序没有填写设备或人员时，是否由系统自动补上",
        choice_labels=_YES_NO_LABELS,
    ),
    ConfigFieldSpec(
        key="auto_assign_persist",
        label="保存系统补齐的设备和人员",
        description="系统帮你补上的设备和人员，是否保存回这道工序，方便下次排产继续用",
        choice_labels=_YES_NO_LABELS,
    ),
    ConfigFieldSpec(
        key="ortools_enabled",
        label="深度优化",
        description="只在精细计算时尝试多找一个更好的起点；需要本机已安装对应的深度优化组件",
        choice_labels=_YES_NO_LABELS,
    ),
    ConfigFieldSpec(
        key="ortools_time_limit_seconds",
        label="深度优化尝试时间",
        description="深度优化最多额外尝试多少秒；只在精细计算且深度优化开启时生效",
    ),
    ConfigFieldSpec(
        key="algo_mode",
        label="计算模式",
        description="计算模式：快速计算 / 精细计算",
        choice_labels={
            "greedy": "快速计算",
            "improve": "精细计算（较慢，结果通常更好）",
        },
    ),
    ConfigFieldSpec(
        key="time_budget_seconds",
        label="找更好排法先试多久",
        description="一次共同优化的总计算预算，默认 10 秒",
    ),
    ConfigFieldSpec(
        key="objective",
        label="优化目标",
        description="优化目标：最少超期批次数 / 最少拖期小时 / 最少加权拖期小时 / 最少换型次数",
        choice_labels=dict(_OBJECTIVE_LABELS),
    ),
    ConfigFieldSpec(
        key="freeze_window_enabled",
        label="锁定近期排程",
        description="锁定近期排程：复用上一版本近期排程，减少波动",
        choice_labels=_YES_NO_LABELS,
    ),
    ConfigFieldSpec(
        key="freeze_window_days",
        label="锁定天数",
        description="锁定近期排程的天数；未开启锁定时不生效",
    ),
    ConfigFieldSpec(
        key="graph_analysis_mode",
        label="工序图分析",
        description="工序先后关系分析：关闭 / 只看分析报告 / 检查通过后参与排产",
        choice_labels=dict(_GRAPH_ANALYSIS_MODE_LABELS),
    ),
    ConfigFieldSpec(
        key="graph_block_on_cycle",
        label="工序关系互相卡住时停止排产",
        description="工序先后关系互相卡住时是否停止排产；默认不停止",
        choice_labels=_YES_NO_LABELS,
    ),
    ConfigFieldSpec(
        key="graph_critical_weight",
        label="重点工序提前权重",
        description="选择“参与排产”且工序关系可用时，影响完工时间的工序会更靠前；填 0 表示不按这项加分",
    ),
    ConfigFieldSpec(
        key="graph_impact_weight",
        label="后续影响权重",
        description="选择“参与排产”且工序关系可用时，会影响更多后续工序的当前工序会更靠前；填 0 表示不按影响范围加分",
    ),
    ConfigFieldSpec(
        key="graph_debug_export",
        label="导出工序图排查文件",
        description="是否导出工序先后关系排查文件",
        choice_labels=_YES_NO_LABELS,
    ),
)

_FIELD_SPEC_BY_KEY: Dict[str, ConfigFieldSpec] = {spec.key: spec for spec in _FIELD_SPECS}


def list_config_fields() -> Tuple[ConfigFieldSpec, ...]:
    return tuple(_FIELD_SPECS)


def get_field_spec(key: str) -> ConfigFieldSpec:
    if key not in _FIELD_SPEC_BY_KEY:
        raise KeyError(f"未定义调度配置字段：{key!r}")
    return _FIELD_SPEC_BY_KEY[key]


def choices_for(key: str) -> Tuple[str, ...]:
    spec = get_field_spec(key)
    return tuple(spec.choices)


def choice_label_map_for(key: str) -> Dict[str, str]:
    spec = get_field_spec(key)
    if spec.choice_labels:
        return dict(spec.choice_labels)
    return {value: value for value in choices_for(key)}


def coerce_config_field(key: str, value: Any, *, missing: bool = False) -> Any:
    """Strictly coerce a stored value; number errors use this page's field label."""
    return coerce_runtime_value(key, value, missing=missing, field_label=get_field_spec(key).label)
