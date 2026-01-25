from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from data.repositories import ConfigRepository


@dataclass
class ScheduleConfigSnapshot:
    sort_strategy: str
    priority_weight: float
    due_weight: float
    ready_weight: float
    prefer_primary_skill: str  # yes/no：工序补充页优先推荐主操/高技能人员
    algo_mode: str  # greedy/improve
    time_budget_seconds: int  # 用户可自由设置（建议 <=180）
    objective: str  # min_overdue/min_tardiness/min_changeover
    freeze_window_enabled: str  # yes/no
    freeze_window_days: int  # >=0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sort_strategy": self.sort_strategy,
            "priority_weight": self.priority_weight,
            "due_weight": self.due_weight,
            "ready_weight": self.ready_weight,
            "prefer_primary_skill": self.prefer_primary_skill,
            "algo_mode": self.algo_mode,
            "time_budget_seconds": int(self.time_budget_seconds),
            "objective": self.objective,
            "freeze_window_enabled": self.freeze_window_enabled,
            "freeze_window_days": int(self.freeze_window_days),
        }


class ConfigService:
    """排产策略配置服务（ScheduleConfig）。"""

    # 开发文档默认值（weighted 模式）
    DEFAULT_SORT_STRATEGY = "priority_first"
    DEFAULT_PRIORITY_WEIGHT = 0.4
    DEFAULT_DUE_WEIGHT = 0.5
    DEFAULT_READY_WEIGHT = 0.1

    # 算法增强（V1.1：默认关闭“改进模式”）
    DEFAULT_ALGO_MODE = "greedy"  # greedy/improve
    DEFAULT_TIME_BUDGET_SECONDS = 20  # 用户可自由设置（建议 <=180）
    DEFAULT_OBJECTIVE = "min_overdue"
    DEFAULT_FREEZE_WINDOW_ENABLED = "no"
    DEFAULT_FREEZE_WINDOW_DAYS = 0

    VALID_STRATEGIES = ("priority_first", "due_date_first", "weighted", "fifo")
    VALID_ALGO_MODES = ("greedy", "improve")
    VALID_OBJECTIVES = ("min_overdue", "min_tardiness", "min_changeover")

    STRATEGY_NAME_ZH = {
        "priority_first": "优先级优先",
        "due_date_first": "交期优先",
        "weighted": "权重混合",
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
        if value is None:
            return None
        if isinstance(value, str):
            v = value.strip()
            return v if v != "" else None
        v = str(value).strip()
        return v if v != "" else None

    @staticmethod
    def _normalize_weight(value: Any, field: str) -> float:
        """
        权重标准化为 0~1 的小数：
        - 允许输入 0.4
        - 允许输入 40（视为百分比）
        """
        if value is None or (isinstance(value, str) and value.strip() == ""):
            raise ValidationError(f"“{field}”不能为空", field=field)
        try:
            v = float(value)
        except Exception:
            raise ValidationError(f"“{field}”必须是数字", field=field)
        if v < 0:
            raise ValidationError(f"“{field}”不能为负数", field=field)
        if v > 1.0:
            v = v / 100.0
        # 防御：避免 1000% 这种输入
        if v > 1.0:
            raise ValidationError(f"“{field}”范围不合理（期望 0~1 或 0~100%）", field=field)
        return float(v)

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
        if "prefer_primary_skill" not in existing:
            to_set.append(("prefer_primary_skill", "no", "工序补充页：优先推荐主操/高技能人员（yes/no）"))
        if "algo_mode" not in existing:
            to_set.append(("algo_mode", self.DEFAULT_ALGO_MODE, "算法模式：greedy/improve（improve=多起点+目标函数+时间预算）"))
        if "time_budget_seconds" not in existing:
            to_set.append(("time_budget_seconds", str(self.DEFAULT_TIME_BUDGET_SECONDS), "算法时间预算（秒；仅 improve 模式生效；建议<=180）"))
        if "objective" not in existing:
            to_set.append(("objective", self.DEFAULT_OBJECTIVE, "目标函数：min_overdue/min_tardiness/min_changeover"))
        if "freeze_window_enabled" not in existing:
            to_set.append(("freeze_window_enabled", self.DEFAULT_FREEZE_WINDOW_ENABLED, "冻结窗口开关（yes/no）：复用上一版本窗口内排程"))
        if "freeze_window_days" not in existing:
            to_set.append(("freeze_window_days", str(self.DEFAULT_FREEZE_WINDOW_DAYS), "冻结窗口天数（>=0；仅 freeze_window_enabled=yes 生效）"))

        if not to_set:
            return
        with self.tx_manager.transaction():
            for k, v, d in to_set:
                self.repo.set(k, v, description=d)

    def get(self, config_key: str, default: Any = None) -> Any:
        """
        读取配置值（算法层会用到）。

        说明：
        - 会先 ensure_defaults，避免关键键缺失
        - 返回类型保持为字符串或 default（调用方可自行 float/int 转换）
        """
        self.ensure_defaults()
        return self.repo.get_value(str(config_key), default=str(default) if default is not None else None)

    # -------------------------
    # 查询
    # -------------------------
    def get_available_strategies(self) -> List[Dict[str, str]]:
        return [{"key": k, "name": self.STRATEGY_NAME_ZH.get(k, k)} for k in self.VALID_STRATEGIES]

    def get_snapshot(self) -> ScheduleConfigSnapshot:
        self.ensure_defaults()
        strategy = self.repo.get_value("sort_strategy", default=self.DEFAULT_SORT_STRATEGY) or self.DEFAULT_SORT_STRATEGY
        if strategy not in self.VALID_STRATEGIES:
            # 配置被手工改坏时做兜底
            strategy = self.DEFAULT_SORT_STRATEGY

        def _get_float(key: str, default: float) -> float:
            raw = self.repo.get_value(key, default=str(default))
            try:
                return float(raw) if raw is not None else float(default)
            except Exception:
                return float(default)

        pw = _get_float("priority_weight", self.DEFAULT_PRIORITY_WEIGHT)
        dw = _get_float("due_weight", self.DEFAULT_DUE_WEIGHT)
        rw = _get_float("ready_weight", self.DEFAULT_READY_WEIGHT)

        raw_pref = self.repo.get_value("prefer_primary_skill", default="no")
        pref = "yes" if str(raw_pref or "").strip().lower() in ("yes", "y", "true", "1", "on") else "no"

        algo_mode = (self.repo.get_value("algo_mode", default=self.DEFAULT_ALGO_MODE) or self.DEFAULT_ALGO_MODE).strip()
        if algo_mode not in self.VALID_ALGO_MODES:
            algo_mode = self.DEFAULT_ALGO_MODE

        obj = (self.repo.get_value("objective", default=self.DEFAULT_OBJECTIVE) or self.DEFAULT_OBJECTIVE).strip()
        if obj not in self.VALID_OBJECTIVES:
            obj = self.DEFAULT_OBJECTIVE

        def _get_int(key: str, default: int) -> int:
            raw = self.repo.get_value(key, default=str(default))
            try:
                return int(float(raw)) if raw is not None else int(default)
            except Exception:
                return int(default)

        time_budget = _get_int("time_budget_seconds", int(self.DEFAULT_TIME_BUDGET_SECONDS))
        time_budget = max(1, int(time_budget))

        fw_enabled_raw = self.repo.get_value("freeze_window_enabled", default=self.DEFAULT_FREEZE_WINDOW_ENABLED)
        fw_enabled = "yes" if str(fw_enabled_raw or "").strip().lower() in ("yes", "y", "true", "1", "on") else "no"
        fw_days = _get_int("freeze_window_days", int(self.DEFAULT_FREEZE_WINDOW_DAYS))
        fw_days = max(0, int(fw_days))

        return ScheduleConfigSnapshot(
            sort_strategy=strategy,
            priority_weight=pw,
            due_weight=dw,
            ready_weight=rw,
            prefer_primary_skill=pref,
            algo_mode=algo_mode,
            time_budget_seconds=int(time_budget),
            objective=obj,
            freeze_window_enabled=fw_enabled,
            freeze_window_days=int(fw_days),
        )

    # -------------------------
    # 更新
    # -------------------------
    def set_strategy(self, sort_strategy: Any) -> None:
        v = self._normalize_text(sort_strategy)
        if not v:
            raise ValidationError("“排产策略”不能为空", field="排产策略")
        if v not in self.VALID_STRATEGIES:
            raise ValidationError("排产策略不合法", field="排产策略")
        with self.tx_manager.transaction():
            self.repo.set("sort_strategy", v, description="当前排序策略")

    def set_weights(self, priority_weight: Any, due_weight: Any, ready_weight: Any, require_sum_1: bool = True) -> None:
        pw = self._normalize_weight(priority_weight, field="优先级权重")
        dw = self._normalize_weight(due_weight, field="交期权重")
        rw = self._normalize_weight(ready_weight, field="齐套权重")

        total = pw + dw + rw
        if require_sum_1 and abs(total - 1.0) > 1e-6:
            raise ValidationError("权重总和应为 1（或 100%）", field="权重")

        with self.tx_manager.transaction():
            self.repo.set("priority_weight", str(pw), description="权重模式-优先级权重")
            self.repo.set("due_weight", str(dw), description="权重模式-交期权重")
            self.repo.set("ready_weight", str(rw), description="权重模式-齐套权重")

    def restore_default(self) -> None:
        with self.tx_manager.transaction():
            self.repo.set("sort_strategy", self.DEFAULT_SORT_STRATEGY, description="当前排序策略")
            self.repo.set("priority_weight", str(self.DEFAULT_PRIORITY_WEIGHT), description="权重模式-优先级权重")
            self.repo.set("due_weight", str(self.DEFAULT_DUE_WEIGHT), description="权重模式-交期权重")
            self.repo.set("ready_weight", str(self.DEFAULT_READY_WEIGHT), description="权重模式-齐套权重")
            self.repo.set("prefer_primary_skill", "no", description="工序补充页：优先推荐主操/高技能人员（yes/no）")
            self.repo.set("algo_mode", self.DEFAULT_ALGO_MODE, description="算法模式：greedy/improve（improve=多起点+目标函数+时间预算）")
            self.repo.set("time_budget_seconds", str(self.DEFAULT_TIME_BUDGET_SECONDS), description="算法时间预算（秒；仅 improve 模式生效；建议<=180）")
            self.repo.set("objective", self.DEFAULT_OBJECTIVE, description="目标函数：min_overdue/min_tardiness/min_changeover")
            self.repo.set("freeze_window_enabled", self.DEFAULT_FREEZE_WINDOW_ENABLED, description="冻结窗口开关（yes/no）：复用上一版本窗口内排程")
            self.repo.set("freeze_window_days", str(self.DEFAULT_FREEZE_WINDOW_DAYS), description="冻结窗口天数（>=0；仅 freeze_window_enabled=yes 生效）")

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

    def set_algo_mode(self, value: Any) -> None:
        v = str(value or "").strip().lower()
        if v not in self.VALID_ALGO_MODES:
            raise ValidationError("算法模式不合法（允许：greedy / improve）", field="algo_mode")
        with self.tx_manager.transaction():
            self.repo.set("algo_mode", v, description="算法模式：greedy/improve（improve=多起点+目标函数+时间预算）")

    def set_time_budget_seconds(self, value: Any) -> None:
        if value is None or str(value).strip() == "":
            raise ValidationError("时间预算不能为空", field="time_budget_seconds")
        try:
            v = int(float(value))
        except Exception:
            raise ValidationError("时间预算必须是整数（秒）", field="time_budget_seconds")
        v = max(1, int(v))
        with self.tx_manager.transaction():
            self.repo.set("time_budget_seconds", str(v), description="算法时间预算（秒；仅 improve 模式生效；建议<=180）")

    def set_objective(self, value: Any) -> None:
        v = str(value or "").strip()
        if v not in self.VALID_OBJECTIVES:
            raise ValidationError("目标函数不合法（允许：min_overdue / min_tardiness / min_changeover）", field="objective")
        with self.tx_manager.transaction():
            self.repo.set("objective", v, description="目标函数：min_overdue/min_tardiness/min_changeover")

    def set_freeze_window(self, enabled: Any, days: Any) -> None:
        en = str(enabled or "").strip().lower()
        en_yesno = "yes" if en in ("yes", "y", "true", "1", "on") else "no"
        if days is None or str(days).strip() == "":
            d = 0
        else:
            try:
                d = int(float(days))
            except Exception:
                raise ValidationError("冻结窗口天数必须是整数", field="freeze_window_days")
        d = max(0, int(d))
        with self.tx_manager.transaction():
            self.repo.set("freeze_window_enabled", en_yesno, description="冻结窗口开关（yes/no）：复用上一版本窗口内排程")
            self.repo.set("freeze_window_days", str(d), description="冻结窗口天数（>=0；仅 freeze_window_enabled=yes 生效）")

