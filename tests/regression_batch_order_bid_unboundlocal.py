import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


@dataclass
class _StubCalendarService:
    """
    最小日历服务桩：满足 GreedyScheduler.schedule 所需接口。

    本回归用例仅验证：batch_order 模式下 bid 赋值失败时，不应在 except 中因 bid 未定义而崩溃。
    """

    def adjust_to_working_time(self, dt: datetime, priority=None) -> datetime:  # noqa: D401
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


class _FlakyBatchIdOp:
    """
    构造一个“batch_id 第二次读取抛异常”的工序对象：
    - 第 1 次读取用于 schedule() 内部排序 key 计算（应成功）
    - 第 2 次读取发生在 batch_order 分支 try 的首行 bid 赋值（应抛异常）

    修复前会在 except 中触发 UnboundLocalError（bid 未定义）；修复后应正常吞掉异常并计入 failed_ops。
    """

    def __init__(self, batch_id: str):
        self._batch_id = str(batch_id)
        self._read_cnt = 0

        # schedule() 里会使用到的字段
        self.id = 1
        self.op_code = "OP_ERR"
        self.seq = 1
        self.source = "internal"
        self.machine_id = "M1"
        self.operator_id = "O1"
        self.setup_hours = 1.0
        self.unit_hours = 0.0
        self.op_type_id = None
        self.op_type_name = None
        self.supplier_id = None
        self.ext_days = None
        self.ext_group_id = None
        self.ext_merge_mode = None
        self.ext_group_total_days = None

    @property
    def batch_id(self) -> str:
        self._read_cnt += 1
        if self._read_cnt >= 2:
            raise RuntimeError("boom")
        return self._batch_id


def _build_quiet_logger() -> logging.Logger:
    # 本回归会故意触发排产异常；为避免控制台输出 traceback，使用静默 logger
    lg = logging.getLogger("aps.regression_batch_order_bid_unboundlocal")
    lg.handlers = []
    lg.addHandler(logging.NullHandler())
    lg.propagate = False
    lg.setLevel(logging.CRITICAL)
    return lg


def main():
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.algorithms import GreedyScheduler

    batch = SimpleNamespace(
        batch_id="B001",
        priority="normal",
        due_date=None,
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
    )
    batches = {"B001": batch}
    operations = [_FlakyBatchIdOp(batch_id="B001")]
    start_dt = datetime(2026, 1, 1, 8, 0, 0)

    sched = GreedyScheduler(calendar_service=_StubCalendarService(), logger=_build_quiet_logger())
    results, summary, _strategy, used_params = sched.schedule(
        operations=operations,
        batches=batches,
        start_dt=start_dt,
        dispatch_mode="batch_order",
        dispatch_rule="slack",
    )

    assert used_params.get("dispatch_mode") == "batch_order", f"dispatch_mode 解析异常：{used_params!r}"
    assert summary.total_ops == 1, f"total_ops 应为 1，实际 {summary.total_ops}"
    assert summary.scheduled_ops == 0, f"scheduled_ops 应为 0，实际 {summary.scheduled_ops}"
    assert summary.failed_ops == 1, f"failed_ops 应为 1，实际 {summary.failed_ops}"
    assert len(results) == 0, f"不应产出排程结果，实际 results={len(results)}"

    assert summary.errors, "应记录异常到 summary.errors"
    assert any(("OP_ERR" in e and "请查看系统日志" in e) for e in summary.errors), f"errors 未包含公开异常文案：{summary.errors!r}"
    assert not any("boom" in e for e in summary.errors), f"errors 不应暴露原异常：{summary.errors!r}"
    assert not any("UnboundLocalError" in e for e in summary.errors), f"不应出现 UnboundLocalError：{summary.errors!r}"

    print("OK")


if __name__ == "__main__":
    main()
