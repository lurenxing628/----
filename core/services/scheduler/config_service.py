from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.transaction import TransactionManager
from data.repositories import ConfigRepository
from .config_snapshot import ScheduleConfigSnapshot, build_schedule_config_snapshot
from .config_validator import normalize_preset_snapshot
from .number_utils import parse_finite_float, parse_finite_int


class ConfigService:
    """排产策略配置服务（ScheduleConfig）。"""

    PRESET_PREFIX = "preset."
    ACTIVE_PRESET_KEY = "active_preset"
    ACTIVE_PRESET_CUSTOM = "custom"
    BUILTIN_PRESET_DEFAULT = "默认-稳定"
    BUILTIN_PRESET_DUE_FIRST = "交期优先"
    BUILTIN_PRESET_MIN_CHANGEOVER = "换型最少"
    BUILTIN_PRESET_IMPROVE_SLOW = "改进-更优(慢)"

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
    VALID_OBJECTIVES = ("min_overdue", "min_tardiness", "min_changeover")
    VALID_DISPATCH_MODES = ("batch_order", "sgs")
    VALID_DISPATCH_RULES = ("slack", "cr", "atc")

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
        v = float(parse_finite_float(value, field=field, allow_none=False) or 0.0)
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
            return float(parse_finite_float(val, field=field, allow_none=False) or 0.0)

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
            to_set.append(("objective", self.DEFAULT_OBJECTIVE, "目标函数：min_overdue/min_tardiness/min_changeover"))
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
        """
        返回内置模板列表：(name, snapshot, description)。
        - 仅在缺失时创建，不覆盖用户自定义模板
        """
        base = self._default_snapshot()
        due_first = ScheduleConfigSnapshot(
            **{
                **base.to_dict(),
                "sort_strategy": "due_date_first",
                "priority_weight": 0.2,
                "due_weight": 0.7,
                "ready_weight": 0.1,
            }
        )
        min_changeover = ScheduleConfigSnapshot(
            **{
                **base.to_dict(),
                "algo_mode": "improve",
                "time_budget_seconds": 30,
                "objective": "min_changeover",
            }
        )
        improve_slow = ScheduleConfigSnapshot(
            **{
                **base.to_dict(),
                "algo_mode": "improve",
                "time_budget_seconds": 120,
                "objective": "min_tardiness",
            }
        )
        return [
            (self.BUILTIN_PRESET_DEFAULT, base, "默认方案：快速、稳定（推荐日常使用）"),
            (self.BUILTIN_PRESET_DUE_FIRST, due_first, "交期优先：更关注交期（适合赶交付场景）"),
            (self.BUILTIN_PRESET_MIN_CHANGEOVER, min_changeover, "换型最少：倾向减少换型（可能更慢）"),
            (self.BUILTIN_PRESET_IMPROVE_SLOW, improve_slow, "改进更优：允许更长搜索时间（更慢）"),
        ]

    @staticmethod
    def _snapshot_close(a: ScheduleConfigSnapshot, b: ScheduleConfigSnapshot) -> bool:
        def _eq_float(x: float, y: float) -> bool:
            try:
                return abs(float(x) - float(y)) <= 1e-9
            except Exception:
                return False

        return (
            (a.sort_strategy == b.sort_strategy)
            and _eq_float(a.priority_weight, b.priority_weight)
            and _eq_float(a.due_weight, b.due_weight)
            and _eq_float(a.ready_weight, b.ready_weight)
            and _eq_float(a.holiday_default_efficiency, b.holiday_default_efficiency)
            and (a.enforce_ready_default == b.enforce_ready_default)
            and (a.prefer_primary_skill == b.prefer_primary_skill)
            and (a.dispatch_mode == b.dispatch_mode)
            and (a.dispatch_rule == b.dispatch_rule)
            and (a.auto_assign_enabled == b.auto_assign_enabled)
            and (a.ortools_enabled == b.ortools_enabled)
            and (int(a.ortools_time_limit_seconds) == int(b.ortools_time_limit_seconds))
            and (a.algo_mode == b.algo_mode)
            and (int(a.time_budget_seconds) == int(b.time_budget_seconds))
            and (a.objective == b.objective)
            and (a.freeze_window_enabled == b.freeze_window_enabled)
            and (int(a.freeze_window_days) == int(b.freeze_window_days))
        )

    def _ensure_builtin_presets(self, existing_keys: Optional[set] = None) -> None:
        """
        确保内置模板与 active_preset 存在（缺失则创建，不覆盖用户配置）。
        """
        keys = existing_keys if existing_keys is not None else {c.config_key for c in self.repo.list_all()}
        presets_to_create: List[Tuple[str, str, str]] = []
        for name, snap, desc in self._builtin_presets():
            k = self._preset_key(name)
            if k in keys:
                continue
            presets_to_create.append(
                (
                    k,
                    json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True),
                    f"排产配置模板：{desc}",
                )
            )

        # active_preset：老库升级时可能缺失；尽量不误导
        need_active = self.ACTIVE_PRESET_KEY not in keys
        active_value = None
        if need_active:
            try:
                cur = self._get_snapshot_from_repo()
                default_snap = self._default_snapshot()
                active_value = self.BUILTIN_PRESET_DEFAULT if self._snapshot_close(cur, default_snap) else self.ACTIVE_PRESET_CUSTOM
            except Exception:
                active_value = self.ACTIVE_PRESET_CUSTOM

        if not presets_to_create and not need_active:
            return

        with self.tx_manager.transaction():
            for k, v, d in presets_to_create:
                self.repo.set(k, v, description=d)
            if need_active:
                self.repo.set(self.ACTIVE_PRESET_KEY, str(active_value or self.ACTIVE_PRESET_CUSTOM), description="当前启用排产配置模板")

    def _get_snapshot_from_repo(self) -> ScheduleConfigSnapshot:
        """
        从 repo 读取 snapshot（不调用 ensure_defaults；避免递归）。
        - 缺键时使用默认值
        - 适用于 ensure_defaults 内部调用
        """
        defaults = {
            "sort_strategy": self.DEFAULT_SORT_STRATEGY,
            "priority_weight": float(self.DEFAULT_PRIORITY_WEIGHT),
            "due_weight": float(self.DEFAULT_DUE_WEIGHT),
            "ready_weight": float(self.DEFAULT_READY_WEIGHT),
            "holiday_default_efficiency": float(self.DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY),
            "enforce_ready_default": str(self.DEFAULT_ENFORCE_READY_DEFAULT),
            "dispatch_mode": self.DEFAULT_DISPATCH_MODE,
            "dispatch_rule": self.DEFAULT_DISPATCH_RULE,
            "auto_assign_enabled": self.DEFAULT_AUTO_ASSIGN_ENABLED,
            "ortools_enabled": self.DEFAULT_ORTOOLS_ENABLED,
            "ortools_time_limit_seconds": int(self.DEFAULT_ORTOOLS_TIME_LIMIT_SECONDS),
            "algo_mode": self.DEFAULT_ALGO_MODE,
            "time_budget_seconds": int(self.DEFAULT_TIME_BUDGET_SECONDS),
            "objective": self.DEFAULT_OBJECTIVE,
            "freeze_window_enabled": self.DEFAULT_FREEZE_WINDOW_ENABLED,
            "freeze_window_days": int(self.DEFAULT_FREEZE_WINDOW_DAYS),
        }
        return build_schedule_config_snapshot(
            self.repo,
            defaults=defaults,
            valid_strategies=self.VALID_STRATEGIES,
            valid_dispatch_modes=self.VALID_DISPATCH_MODES,
            valid_dispatch_rules=self.VALID_DISPATCH_RULES,
            valid_algo_modes=self.VALID_ALGO_MODES,
            valid_objectives=self.VALID_OBJECTIVES,
        )

    def get_active_preset(self) -> Optional[str]:
        self.ensure_defaults()
        raw = self.repo.get_value(self.ACTIVE_PRESET_KEY, default=None)
        v = str(raw).strip() if raw is not None else ""
        return v if v else None

    def set_active_preset(self, name: Optional[str]) -> None:
        v = ("" if name is None else str(name)).strip()
        with self.tx_manager.transaction():
            self.repo.set(self.ACTIVE_PRESET_KEY, v if v else self.ACTIVE_PRESET_CUSTOM, description="当前启用排产配置模板")

    def mark_active_preset_custom(self) -> None:
        self.set_active_preset(self.ACTIVE_PRESET_CUSTOM)

    def list_presets(self) -> List[Dict[str, Any]]:
        self.ensure_defaults()
        items = self.repo.list_all()
        out: List[Dict[str, Any]] = []
        for c in items:
            if not (c.config_key or "").startswith(self.PRESET_PREFIX):
                continue
            name = str(c.config_key)[len(self.PRESET_PREFIX) :]
            if not name:
                continue
            out.append({"name": name, "updated_at": c.updated_at, "config_key": c.config_key, "description": c.description})
        out.sort(key=lambda x: x.get("name") or "")
        return out

    def save_preset(self, name: Any) -> str:
        n = self._normalize_text(name)
        if not n:
            raise ValidationError("模板名称不能为空", field="preset_name")
        if len(n) > 50:
            raise ValidationError("模板名称过长（建议 ≤50 字）", field="preset_name")
        if self._is_builtin_preset(n):
            raise ValidationError("内置模板不允许覆盖，请换一个名称另存", field="preset_name")

        snap = self.get_snapshot()
        payload = json.dumps(snap.to_dict(), ensure_ascii=False, sort_keys=True)
        with self.tx_manager.transaction():
            self.repo.set(self._preset_key(n), payload, description="排产配置模板（用户自定义）")
            self.repo.set(self.ACTIVE_PRESET_KEY, n, description="当前启用排产配置模板")
        return n

    def delete_preset(self, name: Any) -> None:
        n = self._normalize_text(name)
        if not n:
            raise ValidationError("模板名称不能为空", field="preset_name")
        if self._is_builtin_preset(n):
            raise ValidationError("内置模板不允许删除", field="preset_name")

        active = self.get_active_preset()
        with self.tx_manager.transaction():
            self.repo.delete(self._preset_key(n))
            if active == n:
                self.repo.set(self.ACTIVE_PRESET_KEY, self.ACTIVE_PRESET_CUSTOM, description="当前启用排产配置模板")

    def _normalize_preset_snapshot(self, data: Dict[str, Any]) -> ScheduleConfigSnapshot:
        """
        将 JSON 里的 snapshot dict 归一化为合法 ScheduleConfigSnapshot。
        说明：这里做“容错+兜底”，避免模板数据坏了导致整个系统不可用。
        """
        base = self._default_snapshot()
        return normalize_preset_snapshot(
            data,
            base=base,
            valid_strategies=self.VALID_STRATEGIES,
            valid_dispatch_modes=self.VALID_DISPATCH_MODES,
            valid_dispatch_rules=self.VALID_DISPATCH_RULES,
            valid_algo_modes=self.VALID_ALGO_MODES,
            valid_objectives=self.VALID_OBJECTIVES,
        )

    def apply_preset(self, name: Any) -> str:
        n = self._normalize_text(name)
        if not n:
            raise ValidationError("模板名称不能为空", field="preset_name")

        self.ensure_defaults()
        raw = self.repo.get_value(self._preset_key(n), default=None)
        if raw is None or str(raw).strip() == "":
            raise BusinessError(ErrorCode.NOT_FOUND, f"未找到模板：{n}")

        try:
            data = json.loads(str(raw))
            if not isinstance(data, dict):
                raise ValueError("preset json is not dict")
        except Exception:
            raise ValidationError("模板数据已损坏（JSON 无法解析）", field="preset")

        snap = self._normalize_preset_snapshot(data)

        # 原子写入：一次性更新所有配置键 + active_preset
        updates = [
            ("sort_strategy", snap.sort_strategy, None),
            ("priority_weight", str(float(snap.priority_weight)), None),
            ("due_weight", str(float(snap.due_weight)), None),
            ("ready_weight", str(float(snap.ready_weight)), None),
            ("holiday_default_efficiency", str(float(snap.holiday_default_efficiency)), None),
            ("enforce_ready_default", str(snap.enforce_ready_default), None),
            ("prefer_primary_skill", str(snap.prefer_primary_skill), None),
            ("dispatch_mode", str(snap.dispatch_mode), None),
            ("dispatch_rule", str(snap.dispatch_rule), None),
            ("auto_assign_enabled", str(snap.auto_assign_enabled), None),
            ("ortools_enabled", str(snap.ortools_enabled), None),
            ("ortools_time_limit_seconds", str(int(snap.ortools_time_limit_seconds)), None),
            ("algo_mode", str(snap.algo_mode), None),
            ("time_budget_seconds", str(int(snap.time_budget_seconds)), None),
            ("objective", str(snap.objective), None),
            ("freeze_window_enabled", str(snap.freeze_window_enabled), None),
            ("freeze_window_days", str(int(snap.freeze_window_days)), None),
            (self.ACTIVE_PRESET_KEY, n, "当前启用排产配置模板"),
        ]
        with self.tx_manager.transaction():
            self.repo.set_batch(updates)

        return n


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
        return self._get_snapshot_from_repo()

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
            ("objective", self.DEFAULT_OBJECTIVE, "目标函数：min_overdue/min_tardiness/min_changeover"),
            ("freeze_window_enabled", self.DEFAULT_FREEZE_WINDOW_ENABLED, "冻结窗口开关（yes/no）：复用上一版本窗口内排程"),
            ("freeze_window_days", str(self.DEFAULT_FREEZE_WINDOW_DAYS), "冻结窗口天数（>=0；仅 freeze_window_enabled=yes 生效）"),
            (self.ACTIVE_PRESET_KEY, self.BUILTIN_PRESET_DEFAULT, "当前启用排产配置模板"),
        ]
        with self.tx_manager.transaction():
            self.repo.set_batch(updates)

    def set_dispatch(self, dispatch_mode: Any, dispatch_rule: Any) -> None:
        dm = str(dispatch_mode or "").strip().lower()
        if not dm:
            dm = self.DEFAULT_DISPATCH_MODE
        if dm not in self.VALID_DISPATCH_MODES:
            raise ValidationError("派工方式不合法（允许：batch_order / sgs）", field="dispatch_mode")

        dr = str(dispatch_rule or "").strip().lower()
        if not dr:
            dr = self.DEFAULT_DISPATCH_RULE
        if dr not in self.VALID_DISPATCH_RULES:
            raise ValidationError("SGS 派工规则不合法（允许：slack / cr / atc）", field="dispatch_rule")

        with self.tx_manager.transaction():
            self.repo.set("dispatch_mode", dm, description="派工方式：batch_order/sgs（sgs=就绪集合动态派工）")
            self.repo.set("dispatch_rule", dr, description="SGS 派工规则：slack/cr/atc（仅 dispatch_mode=sgs 生效）")

    def set_auto_assign_enabled(self, value: Any) -> None:
        v = str(value or "").strip().lower()
        yes_no = "yes" if v in ("yes", "y", "true", "1", "on") else "no"
        with self.tx_manager.transaction():
            self.repo.set("auto_assign_enabled", yes_no, description="算法自动分配缺省资源（内部工序 machine/operator 未填时）")

    def set_ortools(self, enabled: Any, time_limit_seconds: Any) -> None:
        en = str(enabled or "").strip().lower()
        en_yesno = "yes" if en in ("yes", "y", "true", "1", "on") else "no"
        if time_limit_seconds is None or str(time_limit_seconds).strip() == "":
            tl = int(self.DEFAULT_ORTOOLS_TIME_LIMIT_SECONDS)
        else:
            tl = int(parse_finite_int(time_limit_seconds, field="ortools_time_limit_seconds", allow_none=False) or 0)
        tl = max(1, int(tl))
        with self.tx_manager.transaction():
            self.repo.set("ortools_enabled", en_yesno, description="可选 OR-Tools 高质量模式（若环境已安装）")
            self.repo.set("ortools_time_limit_seconds", str(tl), description="OR-Tools 单次求解时间上限（秒；仅 ortools_enabled=yes 生效）")

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

    def set_holiday_default_efficiency(self, value: Any) -> None:
        """
        工作日历：假期默认效率（>0）。
        - 用于日历配置/Excel 导入在“假期安排工作且效率为空”时的兜底值
        - 工作日默认效率固定为 1.0（不通过此配置项控制）
        """
        if value is None or str(value).strip() == "":
            v = float(self.DEFAULT_HOLIDAY_DEFAULT_EFFICIENCY)
        else:
            v = float(parse_finite_float(value, field="holiday_default_efficiency", allow_none=False) or 0.0)
        if v <= 0:
            raise ValidationError("假期默认效率必须大于 0", field="holiday_default_efficiency")
        with self.tx_manager.transaction():
            self.repo.set(
                "holiday_default_efficiency",
                str(float(v)),
                description="工作日历：假期默认效率（>0；假期安排工作且效率未填时使用）",
            )

    def set_algo_mode(self, value: Any) -> None:
        v = str(value or "").strip().lower()
        if v not in self.VALID_ALGO_MODES:
            raise ValidationError("算法模式不合法（允许：greedy / improve）", field="algo_mode")
        with self.tx_manager.transaction():
            self.repo.set("algo_mode", v, description="算法模式：greedy/improve（improve=多起点+目标函数+时间预算）")

    def set_time_budget_seconds(self, value: Any) -> None:
        if value is None or str(value).strip() == "":
            raise ValidationError("时间预算不能为空", field="time_budget_seconds")
        v = int(parse_finite_int(value, field="time_budget_seconds", allow_none=False) or 0)
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
            d = int(parse_finite_int(days, field="freeze_window_days", allow_none=False) or 0)
        d = max(0, int(d))
        with self.tx_manager.transaction():
            self.repo.set("freeze_window_enabled", en_yesno, description="冻结窗口开关（yes/no）：复用上一版本窗口内排程")
            self.repo.set("freeze_window_days", str(d), description="冻结窗口天数（>=0；仅 freeze_window_enabled=yes 生效）")

