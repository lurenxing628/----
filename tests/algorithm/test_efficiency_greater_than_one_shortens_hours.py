"""回归测试：真实工作日历当天效率大于 1（如 1.2）时，GreedyScheduler 经日历的有效工时折算缩短实际工时——setup_hours=6 在 08:00-16:00、效率 1.2 的班内应得 end_time = start + 5 小时，而非按原始工时排程。"""

from datetime import timedelta

from tests._support.algo_operations import make_algo_op, make_batch
from tests._support.busy_block_case import BASE, day_row, native_calendar
from tests._support.schedule_decode import config_snapshot, production_decode


def test_efficiency_greater_than_one_shortens_hours() -> None:

    from core.algorithms.greedy.scheduler import GreedyScheduler

    start = BASE
    batches = {"B001": make_batch(batch_id="B001", quantity=1)}

    # setup=6h, eff=1.2 => 实际工时应为 5h
    op = make_algo_op(id=1, batch_id="B001", machine_id="M1", operator_id="O1", setup_hours=6.0, unit_hours=0.0,
                      op_type_id="OT01", op_type_name="车削")

    with native_calendar(rows=[day_row(0, efficiency=1.2)]) as calendar:
        sched = GreedyScheduler(calendar_service=calendar, config_service=config_snapshot())
        decoded = production_decode(sched, operations=[op], batches=batches, start_dt=start, dispatch_mode="batch_order")
    results, summary = decoded.results, decoded.summary
    assert summary.total_ops == 1 and summary.scheduled_ops == 1 and summary.failed_ops == 0, f"排产摘要异常：{summary!r}"
    assert len(results) == 1, f"结果数量异常：{len(results)}"

    r = results[0]
    expected_end = start + timedelta(hours=(6.0 / 1.2))
    assert r.start_time == start, f"start_time 异常：{r.start_time!r}"
    assert r.end_time is not None, "end_time 不能为空"
    assert abs((r.end_time - expected_end).total_seconds()) < 1e-6, f"效率>1 未生效：end={r.end_time!r} expected={expected_end!r}"
