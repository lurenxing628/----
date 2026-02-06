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
class _StubCalendar:
    def add_calendar_days(self, start: datetime, days: float, machine_id=None, operator_id=None) -> datetime:
        return start + timedelta(days=float(days or 0.0))


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

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

    print("OK")


if __name__ == "__main__":
    main()

