"""资源×日桶负荷聚合契约（fusion-gantt-load-strip，契约 4.6）。

钉死点：同日多段累加；跨午夜按自然日切分；窗口外裁剪；外协行不计；容量
正午采样 shift_hours×efficiency（capacity_hours_at_noon 单源）；节假日
（shift_hours=0）与日历异常 ratio 置 None 不伪装 0；日历异常出中文降级事件；
排序=资源周内总负荷降序；输出行恰 6 个公开字段（禁内部字段）；4.6 红线
grep——新负荷链路禁直调 calculations.capacity_hours。
"""

from __future__ import annotations

from types import SimpleNamespace

from core.services.scheduler.gantt_range import resolve_week_range
from core.services.scheduler.gantt_resource_load import compute_gantt_resource_day_load
from tests._support.paths import REPO_ROOT


class _CalendarStub:
    def __init__(self, policies=None, fail_days=None):
        self._policies = policies or {}
        self._fail_days = set(fail_days or [])
        self.sampled = []

    def policy_for_datetime(self, dt):
        self.sampled.append(dt)
        key = dt.date().isoformat()
        if key in self._fail_days:
            raise RuntimeError("calendar boom")
        return self._policies.get(key, SimpleNamespace(shift_hours=8.0, efficiency=1.0))


def _wr():
    return resolve_week_range(start_date="2026-06-15", end_date="2026-06-21")


def _row(machine_id, start, end, source="internal", machine_name="", operator_id="OP1", operator_name=""):
    return {
        "machine_id": machine_id,
        "machine_name": machine_name,
        "supplier_name": "",
        "operator_id": operator_id,
        "operator_name": operator_name,
        "source": source,
        "start_time": start,
        "end_time": end,
    }


def test_same_day_segments_accumulate_and_capacity_noon_sampled():
    cal = _CalendarStub({"2026-06-15": SimpleNamespace(shift_hours=8.0, efficiency=0.9)})
    outcome = compute_gantt_resource_day_load(
        view="machine",
        rows=[
            _row("MC1", "2026-06-15 08:00:00", "2026-06-15 11:00:00"),
            _row("MC1", "2026-06-15 13:00:00", "2026-06-15 15:00:00"),
        ],
        wr=_wr(),
        calendar=cal,
    )
    assert outcome.value == [
        {
            "date": "2026-06-15",
            "resource_id": "MC1",
            "resource_label": "MC1",
            "hours": 5.0,
            "capacity_hours": 7.2,
            "ratio": round(5.0 / 7.2, 4),
        }
    ]
    # 容量采样必须是正午（4.6 跨午夜归属口径）
    assert all(dt.hour == 12 for dt in cal.sampled)


def test_cross_midnight_split_and_window_clamp():
    outcome = compute_gantt_resource_day_load(
        view="machine",
        # 周一 22:00 → 周二 02:00 跨午夜；另一段从窗口前伸入（只算窗口内）
        rows=[
            _row("MC1", "2026-06-15 22:00:00", "2026-06-16 02:00:00"),
            _row("MC2", "2026-06-14 20:00:00", "2026-06-15 01:00:00"),
        ],
        wr=_wr(),
        calendar=_CalendarStub(),
    )
    by_key = {(r["resource_id"], r["date"]): r["hours"] for r in outcome.value}
    assert by_key[("MC1", "2026-06-15")] == 2.0
    assert by_key[("MC1", "2026-06-16")] == 2.0
    assert by_key[("MC2", "2026-06-15")] == 1.0  # 6-14 段被窗口裁掉
    assert ("MC2", "2026-06-14") not in by_key


def test_external_rows_and_missing_resource_skipped():
    outcome = compute_gantt_resource_day_load(
        view="machine",
        rows=[
            _row("MC1", "2026-06-15 08:00:00", "2026-06-15 09:00:00"),
            _row("MC9", "2026-06-15 08:00:00", "2026-06-15 18:00:00", source="external"),
            _row("", "2026-06-15 08:00:00", "2026-06-15 18:00:00"),  # 外协未分配：无 machine_id
        ],
        wr=_wr(),
        calendar=_CalendarStub(),
    )
    assert [r["resource_id"] for r in outcome.value] == ["MC1"]
    assert not outcome.events


def test_rest_day_and_calendar_failure_ratio_none_with_event():
    cal = _CalendarStub(
        {"2026-06-15": SimpleNamespace(shift_hours=0, efficiency=1.0)},
        fail_days=["2026-06-16"],
    )
    outcome = compute_gantt_resource_day_load(
        view="machine",
        rows=[
            _row("MC1", "2026-06-15 08:00:00", "2026-06-15 09:00:00"),
            _row("MC1", "2026-06-16 08:00:00", "2026-06-16 09:00:00"),
        ],
        wr=_wr(),
        calendar=cal,
    )
    by_date = {r["date"]: r for r in outcome.value}
    assert by_date["2026-06-15"]["capacity_hours"] == 0.0
    assert by_date["2026-06-15"]["ratio"] is None  # 休息日不伪装 0%
    assert by_date["2026-06-16"]["capacity_hours"] is None
    assert by_date["2026-06-16"]["ratio"] is None
    events = [e for e in outcome.events if e.code == "resource_load_capacity_failed"]
    assert len(events) == 1
    assert "容量暂时算不了" in events[0].message


def test_sorted_by_resource_total_hours_desc_and_operator_view():
    outcome = compute_gantt_resource_day_load(
        view="operator",
        rows=[
            _row("MC1", "2026-06-15 08:00:00", "2026-06-15 09:00:00", operator_id="OP-A", operator_name="张三"),
            _row("MC1", "2026-06-16 08:00:00", "2026-06-16 14:00:00", operator_id="OP-B", operator_name="李四"),
        ],
        wr=_wr(),
        calendar=_CalendarStub(),
    )
    assert [r["resource_id"] for r in outcome.value] == ["OP-B", "OP-A"]  # 6h > 1h
    assert outcome.value[0]["resource_label"] == "OP-B 李四"


def test_output_rows_only_public_fields():
    outcome = compute_gantt_resource_day_load(
        view="machine",
        rows=[_row("MC1", "2026-06-15 08:00:00", "2026-06-15 09:00:00")],
        wr=_wr(),
        calendar=_CalendarStub(),
    )
    assert set(outcome.value[0].keys()) == {
        "date", "resource_id", "resource_label", "hours", "capacity_hours", "ratio",
    }


def test_capacity_failed_code_has_public_message_not_generic():
    # HTTP 出口的公开消息表必须认识专用 code——否则被泛化成 scheduler_degradation
    # 丢掉「容量暂时算不了」的准确文案（Codex 实现审核阻塞 3）
    from core.models.scheduler_degradation_messages import public_degradation_event_message

    message = public_degradation_event_message("resource_load_capacity_failed")
    assert "容量暂时算不了" in message
    assert message != public_degradation_event_message("__unknown_code__")


def test_no_direct_capacity_hours_call_in_load_chain():
    # 4.6 红线：负荷链路禁直调 calculations.capacity_hours（midnight 采样错归属）；
    # capacity_hours_at_noon( 是单源 helper 白名单
    for rel in (
        "core/services/scheduler/gantt_resource_load.py",
        "core/services/scheduler/gantt_service.py",
        "web/routes/domains/scheduler/scheduler_gantt.py",
    ):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "capacity_hours(" not in text.replace("capacity_hours_at_noon(", ""), rel
    # 反向依赖断言：scheduler 新文件零 report 包 import
    load_text = (REPO_ROOT / "core/services/scheduler/gantt_resource_load.py").read_text(encoding="utf-8")
    assert "from core.services.report" not in load_text
