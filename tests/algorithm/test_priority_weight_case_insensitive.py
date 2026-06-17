"""回归测试：compute_metrics 计算加权拖期时，批次 priority 应先小写归一化——priority="Urgent" 须命中 urgent 权重 2.0，
使 tardiness 10h 得出 weighted_tardiness_hours 20h（total_tardiness_hours 仍为 10h）。"""

from datetime import datetime, timedelta
from types import SimpleNamespace


def test_priority_weight_case_insensitive():

    from core.algorithms.evaluation import compute_metrics
    from core.algorithms.greedy import ScheduleResult

    # 构造一个批次：priority 为非小写（应按小写归一化后命中 urgent 权重=2.0）
    batch = SimpleNamespace(
        batch_id="B001",
        priority="Urgent",
        due_date="2026-01-01",
    )
    batches = {"B001": batch}

    due_exclusive = datetime(2026, 1, 2, 0, 0, 0)
    fin = due_exclusive + timedelta(hours=10)

    results = [
        ScheduleResult(
            op_id=1,
            op_code="B001_01",
            batch_id="B001",
            seq=1,
            start_time=datetime(2026, 1, 1, 8, 0, 0),
            end_time=fin,
            source="internal",
        )
    ]

    m = compute_metrics(results, batches)

    # tardiness = 10h, urgent weight=2.0 => weighted tardiness = 20h
    assert abs(float(m.total_tardiness_hours) - 10.0) < 1e-9, f"total_tardiness_hours 异常：{m.total_tardiness_hours}"
    assert abs(float(m.weighted_tardiness_hours) - 20.0) < 1e-9, f"weighted_tardiness_hours 异常：{m.weighted_tardiness_hours}"
