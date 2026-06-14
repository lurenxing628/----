"""临期（near_due）切分边界单测：与超期共用同一 finish vs due_exclusive 口径、严格互斥零重叠。

临期 = finish 落在 [due_exclusive - NEAR_DUE_WINDOW_DAYS 天, due_exclusive)；超期 = finish >= due_exclusive。
build_overdue_items 保持 (items, meta) 二元返回，临期走 meta["near_due_items"]。
"""

from datetime import datetime
from types import SimpleNamespace

from core.services.scheduler.summary.due_risk_items import NEAR_DUE_WINDOW_DAYS
from core.services.scheduler.summary.schedule_summary import build_overdue_items


class _StubSvc:
    logger = None

    @staticmethod
    def _normalize_text(value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _format_dt(value: datetime) -> str:
        return value.strftime("%Y-%m-%d %H:%M:%S")


def _run(batches, finish):
    summary = SimpleNamespace(warnings=[])
    return build_overdue_items(_StubSvc(), batches=batches, finish_by_batch=finish, summary=summary)


def test_near_due_window_constant_is_three():
    assert NEAR_DUE_WINDOW_DAYS == 3


def test_overdue_and_near_due_two_side_split():
    # due 2026-06-20 -> due_exclusive 2026-06-21 00:00; near window [06-18 00:00, 06-21 00:00)
    batches = {b: SimpleNamespace(due_date="2026-06-20") for b in ("OVR", "NEAR_MID", "NEAR_LOW", "HEALTHY", "NOFIN")}
    finish = {
        "OVR": datetime(2026, 6, 21, 0, 0, 0),         # == due_exclusive -> overdue
        "NEAR_MID": datetime(2026, 6, 20, 18, 0, 0),   # inside window -> near_due
        "NEAR_LOW": datetime(2026, 6, 18, 0, 0, 0),    # window lower bound (inclusive) -> near_due
        "HEALTHY": datetime(2026, 6, 17, 23, 0, 0),    # buffer > window -> healthy/skip
    }
    items, meta = _run(batches, finish)
    assert [i["batch_id"] for i in items] == ["OVR"]
    assert sorted(i["batch_id"] for i in meta["near_due_items"]) == ["NEAR_LOW", "NEAR_MID"]


def test_finish_equal_due_exclusive_is_overdue_not_near_due():
    batches = {"B": SimpleNamespace(due_date="2026-06-20")}
    finish = {"B": datetime(2026, 6, 21, 0, 0, 0)}  # exactly due_exclusive
    items, meta = _run(batches, finish)
    assert [i["batch_id"] for i in items] == ["B"]
    assert meta["near_due_items"] == []


def test_window_lower_bound_inclusive():
    batches = {"B": SimpleNamespace(due_date="2026-06-20")}
    finish = {"B": datetime(2026, 6, 18, 0, 0, 0)}  # due_exclusive - 3 days, inclusive
    items, meta = _run(batches, finish)
    assert items == []
    assert [i["batch_id"] for i in meta["near_due_items"]] == ["B"]


def test_just_before_window_lower_bound_is_healthy():
    batches = {"B": SimpleNamespace(due_date="2026-06-20")}
    finish = {"B": datetime(2026, 6, 17, 23, 59, 59)}  # one second before window -> healthy
    items, meta = _run(batches, finish)
    assert items == []
    assert meta["near_due_items"] == []


def test_no_finish_time_skipped():
    batches = {"B": SimpleNamespace(due_date="2026-06-20")}
    items, meta = _run(batches, {})
    assert items == []
    assert meta["near_due_items"] == []


def test_invalid_due_recorded_not_near_due():
    batches = {"B": SimpleNamespace(due_date="2026-13-40")}
    finish = {"B": datetime(2026, 6, 20, 18, 0, 0)}
    items, meta = _run(batches, finish)
    assert items == []
    assert meta["near_due_items"] == []
    assert meta["invalid_due_count"] == 1


def test_mutual_exclusion_overdue_and_near_disjoint():
    batches = {
        "OVR": SimpleNamespace(due_date="2026-06-20"),
        "NEAR": SimpleNamespace(due_date="2026-06-20"),
    }
    finish = {
        "OVR": datetime(2026, 6, 22, 0, 0, 0),
        "NEAR": datetime(2026, 6, 20, 0, 0, 0),
    }
    items, meta = _run(batches, finish)
    overdue_ids = {i["batch_id"] for i in items}
    near_ids = {i["batch_id"] for i in meta["near_due_items"]}
    assert not (overdue_ids & near_ids)


def test_binary_unpack_contract_preserved():
    batches = {"B": SimpleNamespace(due_date="2026-06-20")}
    finish = {"B": datetime(2026, 6, 20, 12, 0, 0)}
    result = build_overdue_items(_StubSvc(), batches=batches, finish_by_batch=finish, summary=SimpleNamespace(warnings=[]))
    assert isinstance(result, tuple) and len(result) == 2
    items, meta = result
    assert isinstance(items, list) and isinstance(meta, dict)
    assert "near_due_items" in meta
