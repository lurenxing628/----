import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


@dataclass
class _StubCalendar:
    def adjust_to_working_time(self, dt: datetime, priority=None, operator_id: str = None) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None, operator_id: str = None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, machine_id: str = None, operator_id: str = None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float, machine_id: str = None, operator_id: str = None) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


class _StubCfgSvc:
    VALID_STRATEGIES = ["priority_first", "due_date_first", "weighted", "fifo"]
    VALID_DISPATCH_RULES = ["slack", "cr", "atc"]


class _StubLogger:
    """
    故意让 warning 不支持 exc_info 参数，用于验证 schedule_optimizer 的回退逻辑不会崩溃。
    """

    def __init__(self):
        self.warnings: List[str] = []

    def warning(self, msg: str):
        self.warnings.append(str(msg))

    def info(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None

    def exception(self, *args, **kwargs):
        return None


@dataclass
class _StubCfg:
    sort_strategy: str = "PRIORITY_FIRST"
    priority_weight: float = 0.4
    due_weight: float = 0.5
    algo_mode: str = "improve"
    objective: str = "min_overdue"
    time_budget_seconds: int = 1
    dispatch_mode: str = "batch_order"
    dispatch_rule: str = "slack"
    ortools_enabled: str = "yes"
    ortools_time_limit_seconds: int = 1

    def to_dict(self):
        return {
            "sort_strategy": self.sort_strategy,
            "priority_weight": self.priority_weight,
            "due_weight": self.due_weight,
            "algo_mode": self.algo_mode,
            "objective": self.objective,
            "time_budget_seconds": self.time_budget_seconds,
            "dispatch_mode": self.dispatch_mode,
            "dispatch_rule": self.dispatch_rule,
            "ortools_enabled": self.ortools_enabled,
            "ortools_time_limit_seconds": self.ortools_time_limit_seconds,
        }


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    # 若 OR-Tools 模块可导入，则打补丁让它必定抛错，从而进入 except+logger.warning 路径
    try:
        import core.algorithms.ortools_bottleneck as ob

        def _boom(*args, **kwargs):
            raise RuntimeError("ortools boom (test)")

        ob.try_solve_bottleneck_batch_order = _boom  # type: ignore[attr-defined]
    except Exception:
        # 若依赖缺失导致导入失败，同样会触发 schedule_optimizer 的 except 分支
        pass

    from core.services.scheduler.schedule_optimizer import optimize_schedule

    logger = _StubLogger()
    _outcome = optimize_schedule(
        calendar_service=_StubCalendar(),
        cfg_svc=_StubCfgSvc(),
        cfg=_StubCfg(),
        algo_ops_to_schedule=[],
        batches={},
        start_dt=datetime(2026, 1, 1, 8, 0, 0),
        end_date=date(2026, 1, 2),
        downtime_map={},
        seed_results=[],
        resource_pool=None,
        version=1,
        logger=logger,
    )

    # 关键：不要求一定出现 warning（取决于 ortools 分支是否被执行到），但必须保证不崩溃
    print("OK")


if __name__ == "__main__":
    main()

