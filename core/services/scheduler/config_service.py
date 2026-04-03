from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.services.common.normalize import normalize_text
from data.repositories import ConfigRepository

from . import config_presets as preset_ops
from .config_snapshot import ScheduleConfigSnapshot, build_schedule_config_snapshot
from .config_validator import normalize_preset_snapshot
from .number_utils import parse_finite_float, parse_finite_int


class ConfigService:
    """排产策略配置服务（ScheduleConfig）。"""

    PRESET_PREFIX = "preset."
    ACTIVE_PRESET_KEY = "active_preset"
    ACTIVE_PRESET_REASON_KEY = "active_preset_reason"
    ACTIVE_PRESET_CUSTOM = "custom"
    BUILTIN_PRESET_DEFAULT = "默认-稳定"
    BUILTIN_PRESET_DUE_FIRST = "交期优先"
    BUILTIN_PRESET_MIN_CHANGEOVER = "换型最少"
    BUILTIN_PRESET_IMPROVE_SLOW = "改进-更优(慢)"
    ACTIVE_PRESET_REASON_MANUAL = "已手工修改排产配置。"
    ACTIVE_PRESET_REASON_CUSTOM_SELECTED = "当前以手动设置为准。"
    ACTIVE_PRESET_REASON_PRESET_ADJUSTED = "方案应用时发生规范化或修补，当前配置已切换为自定义。"
    ACTIVE_PRESET_REASON_PRESET_MISMATCH = "方案写入后的实际配置与目标方案不一致，当前配置已切换为自定义。"
    ACTIVE_PRESET_REASON_PRESET_DELETED = "当前方案已删除，现有配置已保留为自定义。"
    ACTIVE_PRESET_REASON_BASELINE_MISMATCH = "当前配置与内置默认方案不一致。"
    ACTIVE_PRESET_REASON_BASELINE_DEGRADED = "历史配置存在兼容修补，已按自定义配置处理。"

    # 开发文档默认值（weighted 模式）
    DEFAULT_SORT_STRATEGY = "priority_first"
    DEFAULT_PRIORITY_WEIGHT = 0.4
    DEFAULT_DUE_WEIGHT = 0.5
    DEFAULT_READY_WEIGHT = 0.1
    DEFAULT_ENFORCE_READY_DEFAULT = "no"  # yes/no：执行排产时默认是否启用“齐套约束”
    # 工作日历：假期默认效率（假期安排工作且效率未填时使用）
    DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY = 0.8

    # 派工方式（V1.2）：默认保持 V1 行为（batch_order）
    DEFAULT_DISPATCH_MODE = "batch_order"  # batch_order/sgs
    DEFAULT_DISPATCH_RULE = "slack"  # slack/cr/atc（仅 sgs 生效）
    DEFAULT_AUTO_ASSIGN_ENABLED = "no"  # yes/no
    DEFAULT_ORTOOLS_ENABLED = "no"  # yes/no
    DEFAULT_ORTOOLS_TIME_LIMIT_SECONDS = 5  # seconds

    # 算法增强（V1.1：默认关闭“改进模式”）
    DEFAULT_ALGO_MODE = "greedy"  # greedy/improve
    DEFAULT_TIME_BUDGET_SECONDS = 20  # 用户可自由设置（建议 <=180）
    DEFAULT_OBJECTIVE = "min_overdue"
    DEFAULT_FREEZE_WINDOW_ENABLED = "no"
    DEFAULT_FREEZE_WINDOW_DAYS = 0

    VALID_STRATEGIES = ("priority_first", "due_date_first", "weighted", "fifo")
    VALID_ALGO_MODES = ("greedy", "improve")
    VALID_OBJECTIVES = ("min_overdue", "min_tardiness", "min_weighted_tardiness", "min_changeover")
    VALID_DISPATCH_MODES = ("batch_order", "sgs")
    VALID_DISPATCH_RULES = ("slack", "cr", "atc")

    STRATEGY_NAME_ZH = {
        "priority_first": "优先级优先",
        "due_date_first": "交期优先",
        "weighted": "综合优先级和交期",
        "fifo": "先进先出",
    }

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
        # 防御：避免 1000% 这种输入
        if v > 1.0:
            raise ValidationError(f"“{field}”范围不合理（期望 0~1 或 0~100%）", field=field)
        return float(v)

    @staticmethod
    def normalize_weight(value: Any, field: str) -> float:
        """
        公共方法：权重归一化为 0~1 的小数（兼容 0~100% 输入）。

        说明：路由层/视图层不应调用私有方法 `_normalize_weight`。
        """
        return ConfigService._normalize_weight(value, field=field)

    @staticmethod
    def _normalize_weights_triplet(
        priority_weight: Any,
        due_weight: Any,
        ready_weight: Any,
        *,
        require_sum_1: bool = True,
    ) -> Tuple[float, float, float]:
        """
        统一归一化三项权重，避免“单项>1当百分比”导致的混用歧义。

        规则：
        - 若任一原始输入 >1，则视为百分比模式（0~100），三项都按 /100 处理（因此 1 表示 1%）。
        - 否则视为小数模式（0~1），三项直接使用（1 表示 100%）。
        - 百分比模式下禁止出现 (0,1) 的非整数小数（如 0.5/50），避免歧义混用。
        """

        def _to_float(val: Any, field: str) -> float:
            if val is None or (isinstance(val, str) and val.strip() == ""):
                raise ValidationError(f"“{field}”不能为空", field=field)
            return float(parse_finite_float(val, field=field, allow_none=False))

        raw_pw = _to_float(priority_weight, "优先级权重")
        raw_dw = _to_float(due_weight, "交期权重")
        raw_rw = _to_float(ready_weight, "齐套权重")

        for raw, field in ((raw_pw, "优先级权重"), (raw_dw, "交期权重"), (raw_rw, "齐套权重")):
            if raw < 0:
                raise ValidationError(f"“{field}”不能为负数", field=field)

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

    def ensure_defaults(self) -> None:
        """
        确保默认配置已落库（缺失则写入，不覆盖用户已有配置）。
        """
        existing = {c.config_key for c in self.repo.list_all()}
        to_set: List[Tuple[str, str, str]] = []
        if "sort_strategy" not in existing:
            to_set.append(("sort_strategy", self.DEFAULT_SORT_STRATEGY, "当前排序策略"))
        if "priority_weight" not in existing:
            to_set.append(("priority_weight", str(self.DEFAULT_PRIORITY_WEIGHT), "权重模式-优先级权重"))
        if "due_weight" not in existing:
            to_set.append(("due_weight", str(self.DEFAULT_DUE_WEIGHT), "权重模式-交期权重"))
        if "ready_weight" not in existing:
            to_set.append(("ready_weight", str(self.DEFAULT_READY_WEIGHT), "权重模式-齐套权重"))
        if "holiday_default_efficiency" not in existing:
            to_set.append(
                (
                    "holiday_default_efficiency",
                    str(self.DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY),
                    "工作日历：假期默认效率（>0；假期安排工作且效率未填时使用）",
                )
            )
        if "enforce_ready_default" not in existing:
            to_set.append(("enforce_ready_default", str(self.DEFAULT_ENFORCE_READY_DEFAULT), "执行排产：默认启用齐套约束（yes/no）"))
        if "prefer_primary_skill" not in existing:
            to_set.append(("prefer_primary_skill", "no", "工序补充页：优先推荐主操/高技能人员（yes/no）"))
        if "dispatch_mode" not in existing:
            to_set.append(("dispatch_mode", self.DEFAULT_DISPATCH_MODE, "派工方式：batch_order/sgs（sgs=就绪集合动态派工）"))
        if "dispatch_rule" not in existing:
            to_set.append(("dispatch_rule", self.DEFAULT_DISPATCH_RULE, "SGS 派工规则：slack/cr/atc（仅 dispatch_mode=sgs 生效）"))
        if "auto_assign_enabled" not in existing:
            to_set.append(("auto_assign_enabled", self.DEFAULT_AUTO_ASSIGN_ENABLED, "算法自动分配缺省资源（内部工序 machine/operator 未填时）"))
        if "ortools_enabled" not in existing:
            to_set.append(("ortools_enabled", self.DEFAULT_ORTOOLS_ENABLED, "可选 OR-Tools 高质量模式（若环境已安装）"))
        if "ortools_time_limit_seconds" not in existing:
            to_set.append(("ortools_time_limit_seconds", str(self.DEFAULT_ORTOOLS_TIME_LIMIT_SECONDS), "OR-Tools 单次求解时间上限（秒；仅 ortools_enabled=yes 生效）"))
        if "algo_mode" not in existing:
            to_set.append(("algo_mode", self.DEFAULT_ALGO_MODE, "算法模式：greedy/improve（improve=多起点+目标函数+时间预算）"))
        if "time_budget_seconds" not in existing:
            to_set.append(("time_budget_seconds", str(self.DEFAULT_TIME_BUDGET_SECONDS), "算法时间预算（秒；仅 improve 模式生效；建议<=180）"))
        if "objective" not in existing:
            to_set.append(("objective", self.DEFAULT_OBJECTIVE, "目标函数：min_overdue/min_tardiness/min_weighted_tardiness/min_changeover"))
        if "freeze_window_enabled" not in existing:
            to_set.append(("freeze_window_enabled", self.DEFAULT_FREEZE_WINDOW_ENABLED, "冻结窗口开关（yes/no）：复用上一版本窗口内排程"))
        if "freeze_window_days" not in existing:
            to_set.append(("freeze_window_days", str(self.DEFAULT_FREEZE_WINDOW_DAYS), "冻结窗口天数（>=0；仅 freeze_window_enabled=yes 生效）"))

        if not to_set:
            # 即使基础键都存在，也要确保内置模板/active_preset 存在（不覆盖用户配置）
            self._ensure_builtin_presets(existing_keys=existing)
            return
        with self.tx_manager.transaction():
            for k, v, d in to_set:
                self.repo.set(k, v, description=d)

        # 基础键补齐后再补齐内置模板（避免模板引用缺失的配置键）
        self._ensure_builtin_presets(existing_keys=existing)

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
        return ScheduleConfigSnapshot(
            sort_strategy=self.DEFAULT_SORT_STRATEGY,
            priority_weight=float(self.DEFAULT_PRIORITY_WEIGHT),
            due_weight=float(self.DEFAULT_DUE_WEIGHT),
            ready_weight=float(self.DEFAULT_READY_WEIGHT),
            holiday_default_efficiency=float(self.DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY),
            enforce_ready_default=str(self.DEFAULT_ENFORCE_READY_DEFAULT),
            prefer_primary_skill="no",
            dispatch_mode=self.DEFAULT_DISPATCH_MODE,
            dispatch_rule=self.DEFAULT_DISPATCH_RULE,
            auto_assign_enabled=self.DEFAULT_AUTO_ASSIGN_ENABLED,
            ortools_enabled=self.DEFAULT_ORTOOLS_ENABLED,
            ortools_time_limit_seconds=int(self.DEFAULT_ORTOOLS_TIME_LIMIT_SECONDS),
            algo_mode=self.DEFAULT_ALGO_MODE,
            time_budget_seconds=int(self.DEFAULT_TIME_BUDGET_SECONDS),
            objective=self.DEFAULT_OBJECTIVE,
            freeze_window_enabled=self.DEFAULT_FREEZE_WINDOW_ENABLED,
            freeze_window_days=int(self.DEFAULT_FREEZE_WINDOW_DAYS),
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

    def get_active_preset(self) -> Optional[str]:
        self.ensure_defaults()
        raw = self.repo.get_value(self.ACTIVE_PRESET_KEY, default=None)
        v = str(raw).strip() if raw is not None else ""
        return v if v else None

    def get_active_preset_reason(self) -> Optional[str]:
        self.ensure_defaults()
        raw = self.repo.get_value(self.ACTIVE_PRESET_REASON_KEY, default=None)
        v = str(raw).strip() if raw is not None else ""
        return v if v else None

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

    def _active_preset_updates(self, name: Optional[str], reason: Optional[str] = None) -> List[Tuple[str, str, str]]:
        return [
            self._active_preset_update(name),
            self._active_preset_reason_update(reason),
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

    def save_preset(self, name: Any) -> str:
        return preset_ops.save_preset(self, name)

    def delete_preset(self, name: Any) -> None:
        preset_ops.delete_preset(self, name)

    def _normalize_preset_snapshot(self, data: Dict[str, Any]) -> ScheduleConfigSnapshot:
        return preset_ops.normalize_preset_snapshot(self, data)

    def apply_preset(self, name: Any) -> str:
        return preset_ops.apply_preset(self, name)


    def get(self, config_key: str, default: Any = None) -> Any:
        """
        读取配置值（算法层会用到）。

        说明：
        - 会先 ensure_defaults，避免关键键缺失
        - 返回类型保持为字符串或 default（调用方可自行 float/int 转换）
        """
        self.ensure_defaults()
        return self.repo.get_value(str(config_key), default=str(default) if default is not None else None)

    def get_holiday_default_efficiency(self) -> float:
        raw = self.get(
            "holiday_default_efficiency",
            default=self.DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY,
        )
        v = float(parse_finite_float(raw, field="假期工作效率", allow_none=False))
        if v <= 0:
            raise ValidationError("假期工作效率必须大于 0。", field="假期工作效率")
        return float(v)

    # -------------------------
    # 查询
    # -------------------------
    def get_available_strategies(self) -> List[Dict[str, str]]:
        return [{"key": k, "name": self.STRATEGY_NAME_ZH.get(k, k)} for k in self.VALID_STRATEGIES]

    def get_snapshot(self, *, strict_mode: bool = False) -> ScheduleConfigSnapshot:
        self.ensure_defaults()
        return self._get_snapshot_from_repo(strict_mode=bool(strict_mode))

    # -------------------------
    # 更新
    # -------------------------
    def set_strategy(self, sort_strategy: Any) -> None:
        v = self._normalize_text(sort_strategy)
        if not v:
            raise ValidationError("“排产策略”不能为空", field="排产策略")
        if v not in self.VALID_STRATEGIES:
            raise ValidationError("排产策略不正确，请重新选择。", field="排产策略")
        with self.tx_manager.transaction():
            self.repo.set("sort_strategy", v, description="当前排序策略")
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
            self.repo.set("priority_weight", str(pw), description="权重模式-优先级权重")
            self.repo.set("due_weight", str(dw), description="权重模式-交期权重")
            self.repo.set("ready_weight", str(rw), description="权重模式-齐套权重")
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def restore_default(self) -> None:
        updates = [
            ("sort_strategy", self.DEFAULT_SORT_STRATEGY, "当前排序策略"),
            ("priority_weight", str(self.DEFAULT_PRIORITY_WEIGHT), "权重模式-优先级权重"),
            ("due_weight", str(self.DEFAULT_DUE_WEIGHT), "权重模式-交期权重"),
            ("ready_weight", str(self.DEFAULT_READY_WEIGHT), "权重模式-齐套权重"),
            (
                "holiday_default_efficiency",
                str(self.DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY),
                "工作日历：假期默认效率（>0；假期安排工作且效率未填时使用）",
            ),
            (
                "enforce_ready_default",
                str(self.DEFAULT_ENFORCE_READY_DEFAULT),
                "执行排产：默认启用齐套约束（yes/no）",
            ),
            ("prefer_primary_skill", "no", "工序补充页：优先推荐主操/高技能人员（yes/no）"),
            ("dispatch_mode", self.DEFAULT_DISPATCH_MODE, "派工方式：batch_order/sgs（sgs=就绪集合动态派工）"),
            ("dispatch_rule", self.DEFAULT_DISPATCH_RULE, "SGS 派工规则：slack/cr/atc（仅 dispatch_mode=sgs 生效）"),
            ("auto_assign_enabled", self.DEFAULT_AUTO_ASSIGN_ENABLED, "算法自动分配缺省资源（内部工序 machine/operator 未填时）"),
            ("ortools_enabled", self.DEFAULT_ORTOOLS_ENABLED, "可选 OR-Tools 高质量模式（若环境已安装）"),
            ("ortools_time_limit_seconds", str(self.DEFAULT_ORTOOLS_TIME_LIMIT_SECONDS), "OR-Tools 单次求解时间上限（秒；仅 ortools_enabled=yes 生效）"),
            ("algo_mode", self.DEFAULT_ALGO_MODE, "算法模式：greedy/improve（improve=多起点+目标函数+时间预算）"),
            ("time_budget_seconds", str(self.DEFAULT_TIME_BUDGET_SECONDS), "算法时间预算（秒；仅 improve 模式生效；建议<=180）"),
            ("objective", self.DEFAULT_OBJECTIVE, "目标函数：min_overdue/min_tardiness/min_weighted_tardiness/min_changeover"),
            ("freeze_window_enabled", self.DEFAULT_FREEZE_WINDOW_ENABLED, "冻结窗口开关（yes/no）：复用上一版本窗口内排程"),
            ("freeze_window_days", str(self.DEFAULT_FREEZE_WINDOW_DAYS), "冻结窗口天数（>=0；仅 freeze_window_enabled=yes 生效）"),
            *self._active_preset_updates(self.BUILTIN_PRESET_DEFAULT),
        ]
        with self.tx_manager.transaction():
            self.repo.set_batch(updates)

    def set_dispatch(self, dispatch_mode: Any, dispatch_rule: Any) -> None:
        dm = str(dispatch_mode or "").strip().lower()
        if not dm:
            dm = self.DEFAULT_DISPATCH_MODE
        if dm not in self.VALID_DISPATCH_MODES:
            raise ValidationError("派工方式不正确，请选择：按批次顺序排 或 智能派工。", field="派工方式")

        dr = str(dispatch_rule or "").strip().lower()
        if not dr:
            dr = self.DEFAULT_DISPATCH_RULE
        if dr not in self.VALID_DISPATCH_RULES:
            raise ValidationError(
                "智能派工策略不正确，请选择：时间余量少的先做 / 交期更紧、剩余时间更吃紧的先做 / 综合判断更紧急的先做。",
                field="智能派工策略",
            )

        with self.tx_manager.transaction():
            self.repo.set("dispatch_mode", dm, description="派工方式：batch_order/sgs（sgs=就绪集合动态派工）")
            self.repo.set("dispatch_rule", dr, description="SGS 派工规则：slack/cr/atc（仅 dispatch_mode=sgs 生效）")
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def set_auto_assign_enabled(self, value: Any) -> None:
        v = str(value or "").strip().lower()
        yes_no = "yes" if v in ("yes", "y", "true", "1", "on") else "no"
        with self.tx_manager.transaction():
            self.repo.set("auto_assign_enabled", yes_no, description="算法自动分配缺省资源（内部工序 machine/operator 未填时）")
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def set_ortools(self, enabled: Any, time_limit_seconds: Any) -> None:
        en = str(enabled or "").strip().lower()
        en_yesno = "yes" if en in ("yes", "y", "true", "1", "on") else "no"
        if time_limit_seconds is None or str(time_limit_seconds).strip() == "":
            tl = int(self.DEFAULT_ORTOOLS_TIME_LIMIT_SECONDS)
        else:
            tl = int(parse_finite_int(time_limit_seconds, field="自动优化计算时间", allow_none=False))
        tl = max(1, int(tl))
        with self.tx_manager.transaction():
            self.repo.set("ortools_enabled", en_yesno, description="可选 OR-Tools 高质量模式（若环境已安装）")
            self.repo.set("ortools_time_limit_seconds", str(tl), description="OR-Tools 单次求解时间上限（秒；仅 ortools_enabled=yes 生效）")
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def set_prefer_primary_skill(self, value: Any) -> None:
        """
        工序补充页偏好开关：
        - yes：优先推荐/排序主操设备与高技能人员
        - no：保持默认顺序
        """
        v = str(value or "").strip().lower()
        yes_no = "yes" if v in ("yes", "y", "true", "1", "on") else "no"
        with self.tx_manager.transaction():
            self.repo.set("prefer_primary_skill", yes_no, description="工序补充页：优先推荐主操/高技能人员（yes/no）")
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def set_enforce_ready_default(self, value: Any) -> None:
        """
        执行排产的默认行为开关：
        - yes：排产页面“启用齐套约束”默认勾选
        - no：默认不勾选（推荐：齐套作为可选功能）
        """
        v = str(value or "").strip().lower()
        yes_no = "yes" if v in ("yes", "y", "true", "1", "on") else "no"
        with self.tx_manager.transaction():
            self.repo.set("enforce_ready_default", yes_no, description="执行排产：默认启用齐套约束（yes/no）")
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def set_holiday_default_efficiency(self, value: Any) -> None:
        """
        工作日历：假期默认效率（>0）。
        - 用于日历配置/Excel 导入在“假期安排工作且效率为空”时的兜底值
        - 工作日默认效率固定为 1.0（不通过此配置项控制）
        """
        if value is None or str(value).strip() == "":
            v = float(self.DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY)
        else:
            v = float(parse_finite_float(value, field="假期工作效率", allow_none=False))
        if v <= 0:
            raise ValidationError("假期工作效率必须大于 0。", field="假期工作效率")
        with self.tx_manager.transaction():
            self.repo.set(
                "holiday_default_efficiency",
                str(float(v)),
                description="工作日历：假期默认效率（>0；假期安排工作且效率未填时使用）",
            )
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def set_algo_mode(self, value: Any) -> None:
        v = str(value or "").strip().lower()
        if v not in self.VALID_ALGO_MODES:
            raise ValidationError("计算模式不正确，请选择：快速计算 或 精细计算。", field="计算模式")
        with self.tx_manager.transaction():
            self.repo.set("algo_mode", v, description="算法模式：greedy/improve（improve=多起点+目标函数+时间预算）")
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def set_time_budget_seconds(self, value: Any) -> None:
        if value is None or str(value).strip() == "":
            raise ValidationError("计算时间上限不能为空。", field="计算时间上限")
        v = int(parse_finite_int(value, field="计算时间上限", allow_none=False))
        v = max(1, int(v))
        with self.tx_manager.transaction():
            self.repo.set("time_budget_seconds", str(v), description="算法时间预算（秒；仅 improve 模式生效；建议<=180）")
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def set_objective(self, value: Any) -> None:
        v = str(value or "").strip().lower()
        if v not in self.VALID_OBJECTIVES:
            raise ValidationError("优化目标不正确，请选择：最少超期 / 最少拖期小时 / 最少加权拖期小时 / 最少换型次数。", field="优化目标")
        with self.tx_manager.transaction():
            self.repo.set("objective", v, description="目标函数：min_overdue/min_tardiness/min_weighted_tardiness/min_changeover")
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

    def set_freeze_window(self, enabled: Any, days: Any) -> None:
        en = str(enabled or "").strip().lower()
        en_yesno = "yes" if en in ("yes", "y", "true", "1", "on") else "no"
        if days is None or str(days).strip() == "":
            d = 0
        else:
            d = int(parse_finite_int(days, field="锁定天数", allow_none=False))
        d = max(0, int(d))
        with self.tx_manager.transaction():
            self.repo.set("freeze_window_enabled", en_yesno, description="冻结窗口开关（yes/no）：复用上一版本窗口内排程")
            self.repo.set("freeze_window_days", str(d), description="冻结窗口天数（>=0；仅 freeze_window_enabled=yes 生效）")
            self.repo.set_batch(
                self._active_preset_updates(self.ACTIVE_PRESET_CUSTOM, reason=self.ACTIVE_PRESET_REASON_MANUAL)
            )

