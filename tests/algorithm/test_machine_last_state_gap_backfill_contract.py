"""合同测试（audit 2026-07-20 A16）：机台末态快照 (last_end, last_op_type) 必须同守卫。

背景：非 seed 路径原来 last_end 只在更晚时更新、last_op_type 却无条件覆盖；gap 回填
（把更早的空档排进已有更晚工序的机台）后快照变成"末尾时间不变、工种换成回填工序"的
自相矛盾状态，换型惩罚（internal_slot._changeover_penalty）与自动选机排序按错的上一工种计算。
合同：仅当机台时间线末尾真实推进时才更新 (end, type)；gap 回填后快照仍一致指向时间线真实末尾。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from core.algorithm_contracts.types import ScheduleResult
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithm_runtime.runtime_state import update_machine_last_state

BASE = datetime(2026, 7, 20, 8, 0, 0)


def _update(last_end, last_type, *, end_time, op_type_name, seed_mode=False):
    update_machine_last_state(
        last_end_by_machine=last_end,
        last_op_type_by_machine=last_type,
        machine_id="M1",
        end_time=end_time,
        op_type_name=op_type_name,
        seed_mode=seed_mode,
    )


def test_dispatch_gap_backfill_keeps_end_and_type_pointing_at_timeline_tail():
    # 机台末尾 18:00/A 已在，回填 13:00/B：(end, type) 都不动。
    last_end = {"M1": BASE + timedelta(hours=10)}  # 18:00
    last_type = {"M1": "A"}

    _update(last_end, last_type, end_time=BASE + timedelta(hours=5), op_type_name="B")

    assert last_end["M1"] == BASE + timedelta(hours=10)
    assert last_type["M1"] == "A"


def test_dispatch_equal_end_time_does_not_overwrite_type():
    last_end = {"M1": BASE + timedelta(hours=10)}
    last_type = {"M1": "A"}

    _update(last_end, last_type, end_time=BASE + timedelta(hours=10), op_type_name="B")

    assert last_end["M1"] == BASE + timedelta(hours=10)
    assert last_type["M1"] == "A"


def test_dispatch_real_advance_updates_end_and_type_together():
    last_end = {"M1": BASE + timedelta(hours=10)}
    last_type = {"M1": "A"}

    _update(last_end, last_type, end_time=BASE + timedelta(hours=12), op_type_name="B")

    assert last_end["M1"] == BASE + timedelta(hours=12)
    assert last_type["M1"] == "B"


def test_dispatch_advance_with_unknown_type_keeps_last_known_type():
    # 工种未知（空）时末尾时间照常推进，工种保持上一已知值——工种表只记录已知工种。
    last_end = {"M1": BASE + timedelta(hours=10)}
    last_type = {"M1": "A"}

    _update(last_end, last_type, end_time=BASE + timedelta(hours=12), op_type_name="")

    assert last_end["M1"] == BASE + timedelta(hours=12)
    assert last_type["M1"] == "A"


def test_seed_gap_backfill_guard_unchanged():
    # seed 路径本来就同守卫（audit A16 修复前后行为一致）：不回退已更晚的末态。
    last_end = {"M1": BASE + timedelta(hours=10)}
    last_type = {"M1": "A"}

    _update(last_end, last_type, end_time=BASE + timedelta(hours=5), op_type_name="B", seed_mode=True)

    assert last_end["M1"] == BASE + timedelta(hours=10)
    assert last_type["M1"] == "A"


def _internal_result(op_id, start, end, op_type_name):
    return ScheduleResult(
        op_id=op_id,
        op_code=f"OP{op_id}",
        batch_id="B1",
        seq=op_id,
        machine_id="M1",
        operator_id="O1",
        start_time=start,
        end_time=end,
        source="internal",
        op_type_name=op_type_name,
    )


def test_run_state_gap_backfill_snapshot_consistent_with_timeline_tail():
    state = ScheduleRunState(base_time=BASE)
    # 先排到末尾 18:00/A，再 gap 回填 12:00-13:00/B。
    state.record_dispatch_success(_internal_result(1, BASE + timedelta(hours=8), BASE + timedelta(hours=10), "A"))
    state.record_dispatch_success(_internal_result(2, BASE + timedelta(hours=4), BASE + timedelta(hours=5), "B"))

    assert state.last_end_by_machine["M1"] == BASE + timedelta(hours=10)
    assert state.last_op_type_by_machine["M1"] == "A"
