from __future__ import annotations

from typing import Tuple

from .config_field_spec import choice_label_map_for, choices_for, default_for

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
BUILTIN_PRESET_NAMES = (
    BUILTIN_PRESET_DEFAULT,
    BUILTIN_PRESET_DUE_FIRST,
    BUILTIN_PRESET_MIN_CHANGEOVER,
    BUILTIN_PRESET_IMPROVE_SLOW,
)

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

HOLIDAY_DEFAULT_EFFICIENCY_PAGE_WARNING_TEMPLATE = (
    "“假期工作效率”配置当前无效，页面已临时按 {value:g} 显示默认值；"
    "请先到排产参数页修复配置后再继续依赖该默认值进行操作。"
)

__all__ = [
    "ACTIVE_PRESET_CUSTOM",
    "ACTIVE_PRESET_KEY",
    "ACTIVE_PRESET_META_KEY",
    "ACTIVE_PRESET_META_REASON_HIDDEN_REPAIR",
    "ACTIVE_PRESET_META_REASON_MANUAL",
    "ACTIVE_PRESET_META_REASON_VISIBLE_REPAIR",
    "ACTIVE_PRESET_REASON_BASELINE_DEGRADED",
    "ACTIVE_PRESET_REASON_BASELINE_MISMATCH",
    "ACTIVE_PRESET_REASON_CUSTOM_SELECTED",
    "ACTIVE_PRESET_REASON_HIDDEN_REPAIR",
    "ACTIVE_PRESET_REASON_MANUAL",
    "ACTIVE_PRESET_REASON_PRESET_ADJUSTED",
    "ACTIVE_PRESET_REASON_PRESET_DELETED",
    "ACTIVE_PRESET_REASON_PRESET_MISMATCH",
    "ACTIVE_PRESET_REASON_VISIBLE_REPAIR",
    "ACTIVE_PRESET_REASON_KEY",
    "BUILTIN_PRESET_DEFAULT",
    "BUILTIN_PRESET_DUE_FIRST",
    "BUILTIN_PRESET_IMPROVE_SLOW",
    "BUILTIN_PRESET_MIN_CHANGEOVER",
    "BUILTIN_PRESET_NAMES",
    "CONFIG_PAGE_FIELDS",
    "CONFIG_PAGE_HIDDEN_REPAIR_FIELDS",
    "CONFIG_PAGE_VISIBLE_CHANGE_FIELDS",
    "CONFIG_PAGE_WRITE_FIELDS",
    "HOLIDAY_DEFAULT_EFFICIENCY_PAGE_WARNING_TEMPLATE",
    "PRESET_PREFIX",
]
