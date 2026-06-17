"""回归测试：greedy.external_groups.schedule_external 对 ext_merge_mode 大小写不敏感——"Merged" 等混用大小写仍按合并外协组排产，按 ext_group_total_days 计算 start/end_time、写入 external_group_cache、不被窗口阻断、不产生 errors。"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace


@dataclass
class _StubCalendar:
    def add_calendar_days(self, start: datetime, days: float, machine_id=None, operator_id=None) -> datetime:
        return start + timedelta(days=float(days or 0.0))


def test_external_merge_mode_case_insensitive() -> None:

    from core.algorithms.greedy.external_groups import schedule_external

    scheduler = SimpleNamespace(calendar=_StubCalendar())

    base_time = datetime(2026, 1, 1, 8, 0, 0)
    op = SimpleNamespace(
        id=1,
        op_code="OP_EXT_01",
        batch_id="B001",
        seq=1,
        source="external",
        ext_merge_mode="Merged",  # 关键：大小写混用
        ext_group_id="G001",
        ext_group_total_days=3,
        ext_days=None,
        op_type_name=None,
    )
    batch = SimpleNamespace(batch_id="B001")

    batch_progress = {}
    external_group_cache = {}
    errors = []

    result, blocked = schedule_external(
        scheduler,
        op=op,
        batch=batch,
        batch_progress=batch_progress,
        external_group_cache=external_group_cache,
        base_time=base_time,
        errors=errors,
        end_dt_exclusive=None,
    )

    assert blocked is False, f"不应被窗口阻断，实际 blocked={blocked}"
    assert result is not None and result.start_time and result.end_time, "应返回有效 ScheduleResult"
    assert result.start_time == base_time, f"merged 外协组 start_time 异常：{result.start_time!r}"
    assert result.end_time == base_time + timedelta(days=3), f"merged 外协组 end_time 异常：{result.end_time!r}"
    assert ("B001", "G001") in external_group_cache, "merged 外协组应写入 external_group_cache"
    assert not errors, f"不应产生 errors，实际 errors={errors!r}"
