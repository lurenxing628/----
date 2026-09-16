"""合同测试：SGS 图模式失败簿记与固定后继冲突降级（审计 A02 / A04）。

A04：图模式下批内派工顺序跟随图链（precedence_builder 按 (seq, op_code, node_id)
排），而批内列表按 (seq, id) 排；同批同 seq（多 piece 合法形态）时两套 tie-break
错位，旧实现按列表位置切片（operations[idx0:]）簿记会造成失败工序双记、已成功
工序被记跳过、真被阻塞工序零留痕（scheduled+failed 可超 total）。本文件复刻审计
实测的三种错位形态（链中失败/链头失败/4 工序错位），锁定：
- 计数守恒：scheduled + failed <= total（本组用例中恒等于 total）；
- 明细与真实一致：失败工序恰记一次、被图链阻塞工序有 graph_blocked_after_failure
  留痕、已成功工序不出现在任何失败明细里。

A02：现场对后道工序先报工（PROCESSING/PAUSED 进固定集）而前道仍在待排集时，
前道派工失败不再让 _block_graph_operation 抛整趟 ValidationError，而是降级为
按批失败：失败明细带可读原因（graph_fixed_successor_order_conflict）、阻塞该批、
继续排其余批次；传播撞到"本趟已完成"工序仍保持 fail-loud（内部不变量）。

非图模式簿记行为保持不变（按列表位置切片），文末回归用例锁定。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import pytest

from core.algorithm_contracts.types import ScheduleResult
from core.algorithm_runtime.run_state import ScheduleRunState
from core.infrastructure.errors import ValidationError

_BASE_TIME = datetime(2026, 1, 1, 8, 0, 0)


class _StubCalendarService:
    def adjust_to_working_time(self, dt: datetime, priority=None) -> datetime:
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority=None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


def _op(op_id: int, *, batch_id: str = "B1", seq: int = 10, op_code: Optional[str] = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=op_id,
        op_code=op_code or f"OP-{op_id:03d}",
        batch_id=batch_id,
        seq=seq,
        source="internal",
        machine_id="M1",
        operator_id="O1",
        setup_hours=1.0,
        unit_hours=0.0,
        op_type_id=None,
        op_type_name=None,
        supplier_id=None,
        ext_days=None,
        ext_group_id=None,
        ext_merge_mode=None,
        ext_group_total_days=None,
    )


def _batch(batch_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        batch_id=batch_id,
        priority="normal",
        due_date=None,
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
    )


def _successors_from_predecessors(predecessors: Dict[int, set]) -> Dict[int, set]:
    successors: Dict[int, set] = {op_id: set() for op_id in predecessors}
    for op_id, predecessor_ids in predecessors.items():
        for predecessor_id in predecessor_ids:
            successors.setdefault(predecessor_id, set()).add(op_id)
            successors.setdefault(op_id, set())
    return successors


def _graph_context(
    *,
    schedulable_ids: set,
    fixed_ids: set,
    predecessors: Dict[int, set],
    chain_order: List[int],
) -> Dict[str, Any]:
    # sort_key 按图链位置给出（生产侧 (seq, op_code, node_id) 排序的等价投影）。
    sort_key_by_op_id = {op_id: (10, index, op_id) for index, op_id in enumerate(chain_order)}
    return {
        "enabled": True,
        "schedulable_op_ids": set(schedulable_ids),
        "fixed_op_ids": set(fixed_ids),
        "predecessor_op_ids_by_op_id": predecessors,
        "successor_op_ids_by_op_id": _successors_from_predecessors(predecessors),
        "sort_key_by_op_id": sort_key_by_op_id,
    }


def _install_schedule_stub(monkeypatch: pytest.MonkeyPatch, *, fail_op_ids: set = frozenset(), raise_op_ids: set = frozenset()) -> None:
    def _stub_schedule_op(ctx: Any, *, op: Any, batch: Any, state: Any, **_kwargs: Any) -> Tuple[Optional[ScheduleResult], bool]:
        if int(op.id) in raise_op_ids:
            raise RuntimeError(f"injected dispatch crash for op {op.id}")
        if int(op.id) in fail_op_ids:
            return None, False
        start = state.prev_end(str(op.batch_id))
        result = ScheduleResult(
            op_id=int(op.id),
            op_code=str(op.op_code),
            batch_id=str(op.batch_id),
            seq=int(op.seq),
            machine_id="M1",
            operator_id="O1",
            start_time=start,
            end_time=start + timedelta(hours=1),
            source="internal",
        )
        return result, False

    # ``_schedule_op`` is read from ``sgs_dispatch_step``'s globals at call time (moved there by the SGS
    # decode-acceleration split); patching the old ``sgs`` name would no longer intercept anything.
    monkeypatch.setattr("core.algorithms.greedy.dispatch.sgs_dispatch_step._schedule_op", _stub_schedule_op)
    monkeypatch.setattr(
        "core.algorithms.greedy.dispatch.sgs._score_internal_candidate",
        lambda **kwargs: (0.0,),
    )


def _run_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sorted_ops: List[Any],
    batches: Dict[str, Any],
    graph_ready_context: Optional[Dict[str, Any]],
    fail_op_ids: set = frozenset(),
    raise_op_ids: set = frozenset(),
) -> Tuple[int, int, ScheduleRunState]:
    from core.algorithms.greedy.dispatch.sgs import dispatch_sgs

    _install_schedule_stub(monkeypatch, fail_op_ids=fail_op_ids, raise_op_ids=raise_op_ids)
    state = ScheduleRunState(base_time=_BASE_TIME)
    scheduled_count, failed_count = dispatch_sgs(
        SimpleNamespace(calendar_service=_StubCalendarService()),
        sorted_ops=sorted_ops,
        batches=batches,
        batch_order={batch_id: index for index, batch_id in enumerate(sorted(batches))},
        dispatch_rule="slack",
        base_time=_BASE_TIME,
        end_dt_exclusive=None,
        machine_downtimes={},
        state=state,
        auto_assign_enabled=False,
        resource_pool=None,
        strict_mode=False,
        graph_ready_context=graph_ready_context,
    )
    return scheduled_count, failed_count, state


def _detail_pairs(state: ScheduleRunState) -> List[Tuple[str, int]]:
    return sorted((str(item["code"]), int(item["op_id"])) for item in state.failure_details)


# ---------------------------------------------------------------------------
# A04：三种图链/列表位置错位形态的计数守恒与明细正确性
# ---------------------------------------------------------------------------


def test_graph_chain_middle_failure_same_seq_keeps_counts_conserved(monkeypatch: pytest.MonkeyPatch) -> None:
    # 同批同 seq 三工序，op_code 使图链序为 2 -> 3 -> 1，而列表序按 (seq,id) 为 [1,2,3]。
    # 链上第 2 个（id=3）失败：旧位置切片会双记失败工序、把已成功的记成跳过、
    # 真被阻塞的 id=1 零留痕（实测 scheduled+failed=4>3）。
    ops = [
        _op(1, op_code="P_C"),
        _op(2, op_code="P_A"),
        _op(3, op_code="P_B"),
    ]
    predecessors = {2: set(), 3: {2}, 1: {3}}
    context = _graph_context(schedulable_ids={1, 2, 3}, fixed_ids=set(), predecessors=predecessors, chain_order=[2, 3, 1])

    scheduled, failed, state = _run_dispatch(
        monkeypatch,
        sorted_ops=ops,
        batches={"B1": _batch("B1")},
        graph_ready_context=context,
        fail_op_ids={3},
    )

    assert scheduled == 1
    assert failed == 2
    assert scheduled + failed == len(ops)
    assert _detail_pairs(state) == [
        ("dispatch_operation_failed", 3),
        ("graph_blocked_after_failure", 1),
    ]
    blocked_detail = next(item for item in state.failure_details if item["code"] == "graph_blocked_after_failure")
    assert blocked_detail["failed_op_id"] == 3
    # 已成功排产的 id=2 不出现在任何失败明细里。
    assert all(int(item["op_id"]) != 2 for item in state.failure_details)


def test_graph_chain_head_failure_same_seq_keeps_counts_conserved(monkeypatch: pytest.MonkeyPatch) -> None:
    # 链头（id=2）失败：全链 3 工序都失败，失败工序只记一次，其余两道都有阻塞留痕。
    ops = [
        _op(1, op_code="P_C"),
        _op(2, op_code="P_A"),
        _op(3, op_code="P_B"),
    ]
    predecessors = {2: set(), 3: {2}, 1: {3}}
    context = _graph_context(schedulable_ids={1, 2, 3}, fixed_ids=set(), predecessors=predecessors, chain_order=[2, 3, 1])

    scheduled, failed, state = _run_dispatch(
        monkeypatch,
        sorted_ops=ops,
        batches={"B1": _batch("B1")},
        graph_ready_context=context,
        fail_op_ids={2},
    )

    assert scheduled == 0
    assert failed == 3
    assert _detail_pairs(state) == [
        ("dispatch_operation_failed", 2),
        ("graph_blocked_after_failure", 1),
        ("graph_blocked_after_failure", 3),
    ]


def test_graph_four_op_misalignment_success_not_reported_blocked_not_lost(monkeypatch: pytest.MonkeyPatch) -> None:
    # 4 工序错位（审计案例 D）：链序 4 -> 2 -> 3 -> 1，列表序 [1,2,3,4]。
    # 链头 id=4 成功后 id=2 失败：旧实现把已成功的 id=4 记进 skipped 明细、
    # 真被阻塞的 id=3 从计数与明细中消失且 failed 多算（1+2+1=4，scheduled+failed=5>4）。
    ops = [
        _op(1, op_code="P_D"),
        _op(2, op_code="P_B"),
        _op(3, op_code="P_C"),
        _op(4, op_code="P_A"),
    ]
    predecessors = {4: set(), 2: {4}, 3: {2}, 1: {3}}
    context = _graph_context(
        schedulable_ids={1, 2, 3, 4},
        fixed_ids=set(),
        predecessors=predecessors,
        chain_order=[4, 2, 3, 1],
    )

    scheduled, failed, state = _run_dispatch(
        monkeypatch,
        sorted_ops=ops,
        batches={"B1": _batch("B1")},
        graph_ready_context=context,
        fail_op_ids={2},
    )

    assert scheduled == 1
    assert failed == 3
    assert scheduled + failed == len(ops)
    assert _detail_pairs(state) == [
        ("dispatch_operation_failed", 2),
        ("graph_blocked_after_failure", 1),
        ("graph_blocked_after_failure", 3),
    ]
    assert all(int(item["op_id"]) != 4 for item in state.failure_details)


def test_graph_exception_path_bookkeeping_follows_graph_state(monkeypatch: pytest.MonkeyPatch) -> None:
    # 异常路径同样按图状态簿记：id=3 抛异常，id=1 是其图链后继（列表位置在它之前）。
    ops = [
        _op(1, op_code="P_C"),
        _op(2, op_code="P_A"),
        _op(3, op_code="P_B"),
    ]
    predecessors = {2: set(), 3: {2}, 1: {3}}
    context = _graph_context(schedulable_ids={1, 2, 3}, fixed_ids=set(), predecessors=predecessors, chain_order=[2, 3, 1])

    scheduled, failed, state = _run_dispatch(
        monkeypatch,
        sorted_ops=ops,
        batches={"B1": _batch("B1")},
        graph_ready_context=context,
        raise_op_ids={3},
    )

    assert scheduled == 1
    assert failed == 2
    assert scheduled + failed == len(ops)
    assert _detail_pairs(state) == [
        ("dispatch_operation_exception", 3),
        ("graph_blocked_after_failure", 1),
    ]
    assert state.blocked_batches == {"B1"}


# ---------------------------------------------------------------------------
# A02：固定后继冲突降级为按批失败留痕
# ---------------------------------------------------------------------------


def test_fixed_successor_conflict_degrades_to_batch_failure_and_other_batches_continue(monkeypatch: pytest.MonkeyPatch) -> None:
    # B1：前道 id=1 待排、后道 id=99 已报工进固定集、id=7 是固定工序的下游待排工序；
    # B2：正常批次。前道派工失败时：不再抛整趟 ValidationError，B1 按批失败留痕
    # （失败原因写清报工顺序异常），B2 继续正常排产。
    ops = [
        _op(1, batch_id="B1", seq=10),
        _op(7, batch_id="B1", seq=30),
        _op(5, batch_id="B2", seq=10),
    ]
    predecessors = {1: set(), 7: {99}, 5: set(), 99: {1}}
    context = _graph_context(
        schedulable_ids={1, 7, 5},
        fixed_ids={99},
        predecessors=predecessors,
        chain_order=[1, 7, 5],
    )

    scheduled, failed, state = _run_dispatch(
        monkeypatch,
        sorted_ops=ops,
        batches={"B1": _batch("B1"), "B2": _batch("B2")},
        graph_ready_context=context,
        fail_op_ids={1},
    )

    # 其余批次正常：B2 的 id=5 排上；B1 整批失败（前道 1 + 不再可达的 7）。
    assert scheduled == 1
    assert failed == 2
    assert state.blocked_batches == {"B1"}
    assert _detail_pairs(state) == [
        ("dispatch_operation_failed", 1),
        ("graph_fixed_successor_order_conflict", 1),
        ("skipped_after_batch_failure", 7),
    ]
    conflict = next(item for item in state.failure_details if item["code"] == "graph_fixed_successor_order_conflict")
    assert conflict["fixed_successor_op_ids"] == [99]


def test_fixed_successor_conflict_message_renders_readable_reason() -> None:
    # 新结构化 code 必须有用户可读文案，不能被公开错误渲染层静默丢弃。
    from core.models.scheduler_public_errors import build_public_error_records

    state = ScheduleRunState(base_time=_BASE_TIME)
    state.record_graph_fixed_order_conflict(
        _op(1, op_code="OP-001"),
        "B1",
        fixed_successor_op_ids=[99],
    )

    records = build_public_error_records([], structured_details=state.failure_details)
    assert len(records) == 1
    assert records[0]["code"] == "graph_fixed_successor_order_conflict"
    message = records[0]["message"]
    assert "OP-001" in message
    assert "报工顺序" in message


def test_run_completed_successor_conflict_still_fails_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    # 内部不变量保持 fail-loud：传播撞到"本趟已完成"（非输入固定）的工序必须抛错。
    from core.algorithms.greedy.dispatch.sgs_graph import _block_graph_operation, _prepare_graph_ready_state

    ops_by_batch = {"B1": [_op(1, op_code="P_A"), _op(2, op_code="P_B")]}
    context = _graph_context(
        schedulable_ids={1, 2},
        fixed_ids=set(),
        predecessors={1: set(), 2: {1}},
        chain_order=[1, 2],
    )
    graph_state = _prepare_graph_ready_state(context, ops_by_batch=ops_by_batch)
    assert graph_state is not None
    graph_state["completed_or_fixed_op_ids"].add(2)

    with pytest.raises(ValidationError, match="固定/已完成工序冲突"):
        _block_graph_operation(graph_state, 1)


# ---------------------------------------------------------------------------
# 非图模式回归：簿记行为保持按列表位置切片，不受 A04 改动影响
# ---------------------------------------------------------------------------


def test_non_graph_mode_bookkeeping_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    ops = [
        _op(1, op_code="P_C"),
        _op(2, op_code="P_A"),
        _op(3, op_code="P_B"),
    ]

    scheduled, failed, state = _run_dispatch(
        monkeypatch,
        sorted_ops=ops,
        batches={"B1": _batch("B1")},
        graph_ready_context=None,
        fail_op_ids={2},
    )

    # 非图模式派工顺序 = 列表序 [1,2,3]：1 成功，2 失败，3 按位置切片记跳过。
    assert scheduled == 1
    assert failed == 2
    assert scheduled + failed == len(ops)
    assert _detail_pairs(state) == [
        ("dispatch_operation_failed", 2),
        ("skipped_after_batch_failure", 3),
    ]
    assert state.blocked_batches == {"B1"}
