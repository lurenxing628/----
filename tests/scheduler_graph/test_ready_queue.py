"""回归测试：图调度 ready 队列契约（get_ready_operation_ids 与增量队列）——前置全完成才释放工序、固定工序释放后继但自身不入队、被阻塞工序不释放后继且输入顺序不改变稳定排序；并对缺前置映射/None 前置/blocked 与 completed 重叠/非法 sort_key 形状或类型/传图对象等违约输入抛 ReadyQueueContractError 或 ValidationError，且增量结果与全量扫描一致。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.algorithms.greedy.dispatch.sgs_graph import (
    _block_graph_operation,
    _collect_candidates,
    _ensure_graph_ready_complete,
    _mark_graph_operation_completed,
    _op_id,
    _prepare_graph_ready_state,
)
from core.infrastructure.errors import ValidationError
from core.services.scheduler.graph.ready_queue import ReadyQueueContractError, get_ready_operation_ids


def _sort_key_by_op_id(*op_ids: int) -> dict:
    return {op_id: (index, index * 10, op_id) for index, op_id in enumerate(op_ids)}


def _ready(
    *,
    schedulable,
    done=(),
    blocked=(),
    predecessors=None,
    sort_keys=None,
):
    return get_ready_operation_ids(
        schedulable_op_ids=schedulable,
        completed_or_fixed_op_ids=done,
        blocked_op_ids=blocked,
        predecessor_op_ids_by_op_id=predecessors or {},
        sort_key_by_op_id=sort_keys if sort_keys is not None else _sort_key_by_op_id(*schedulable),
    )


def _op(op_id: int, *, batch_id: str = "B1"):
    return SimpleNamespace(id=op_id, batch_id=batch_id, op_code=f"OP-{op_id:03d}", seq=op_id * 10)


def _successors_from_predecessors(predecessors):
    successors = {op_id: set() for op_id in predecessors}
    for op_id, predecessor_ids in predecessors.items():
        for predecessor_id in predecessor_ids:
            successors.setdefault(predecessor_id, set()).add(op_id)
            successors.setdefault(op_id, set())
    return successors


def _graph_state(predecessors, *, fixed=(), sort_keys=None, ops_by_batch=None):
    if ops_by_batch is None:
        ops_by_batch = {"B1": [_op(op_id) for op_id in sorted(predecessors)]}
    schedulable_op_ids = {_op_id(op) for operations in ops_by_batch.values() for op in operations}
    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": schedulable_op_ids,
        "fixed_op_ids": set(fixed),
        "predecessor_op_ids_by_op_id": predecessors,
        "successor_op_ids_by_op_id": _successors_from_predecessors(predecessors),
        "sort_key_by_op_id": sort_keys if sort_keys is not None else _sort_key_by_op_id(*schedulable_op_ids),
    }
    return _prepare_graph_ready_state(graph_ready_context, ops_by_batch=ops_by_batch), ops_by_batch


def _incremental_ready_ids(graph_state, ops_by_batch, *, blocked_batches=None):
    candidates = _collect_candidates(
        graph_state=graph_state,
        batch_ids=list(ops_by_batch),
        ops_by_batch=ops_by_batch,
        next_idx={batch_id: 0 for batch_id in ops_by_batch},
        blocked_batches=set(blocked_batches or set()),
    )
    return [_op_id(op) for _batch_id, op in candidates]


def _full_scan_ready_ids(graph_state):
    return get_ready_operation_ids(
        schedulable_op_ids=set(graph_state["op_by_id"]),
        completed_or_fixed_op_ids=graph_state["completed_or_fixed_op_ids"],
        blocked_op_ids=graph_state["blocked_op_ids"],
        predecessor_op_ids_by_op_id=graph_state["predecessor_op_ids_by_op_id"],
        sort_key_by_op_id=graph_state["sort_key_by_op_id"],
    )


def test_linear_chain_initially_returns_first_operation_only() -> None:
    predecessors = {1: set(), 2: {1}, 3: {2}}

    assert _ready(schedulable={1, 2, 3}, predecessors=predecessors) == [1]


def test_linear_chain_releases_next_operation_after_predecessor_done() -> None:
    predecessors = {1: set(), 2: {1}, 3: {2}}

    assert _ready(schedulable={1, 2, 3}, done={1}, predecessors=predecessors) == [2]


def test_linear_chain_releases_third_operation_after_first_two_done() -> None:
    predecessors = {1: set(), 2: {1}, 3: {2}}

    assert _ready(schedulable={1, 2, 3}, done={1, 2}, predecessors=predecessors) == [3]


def test_input_order_does_not_change_stable_ready_order() -> None:
    predecessors = {1: set(), 2: {1}, 3: {2}}

    assert _ready(
        schedulable=[3, 2, 1],
        predecessors=predecessors,
        sort_keys={1: (0, 10, 1), 2: (0, 20, 2), 3: (0, 30, 3)},
    ) == [1]


def test_fork_releases_multiple_successors_in_stable_order() -> None:
    predecessors = {1: set(), 2: {1}, 3: {1}}

    assert _ready(
        schedulable={1, 2, 3},
        done={1},
        predecessors=predecessors,
        sort_keys={1: (0, 10, 1), 2: (0, 20, 2), 3: (1, 10, 3)},
    ) == [2, 3]


def test_join_waits_for_all_predecessors() -> None:
    predecessors = {1: set(), 2: set(), 3: {1, 2}}

    assert _ready(schedulable={1, 2, 3}, done={1}, predecessors=predecessors) == [2]
    assert _ready(schedulable={1, 2, 3}, done={1, 2}, predecessors=predecessors) == [3]


def test_fixed_operation_releases_successor_but_never_becomes_ready() -> None:
    predecessors = {1: set(), 2: {1}, 3: {2}}

    assert _ready(
        schedulable={2, 3},
        done={1},
        predecessors=predecessors,
        sort_keys={2: (0, 20, 2), 3: (0, 30, 3)},
    ) == [2]


def test_blocked_operation_does_not_release_successor() -> None:
    predecessors = {1: set(), 2: {1}}

    assert _ready(
        schedulable={1, 2},
        blocked={1},
        predecessors=predecessors,
    ) == []


def test_missing_predecessor_mapping_reports_contract_error() -> None:
    predecessors = {2: {999}}

    with pytest.raises(ReadyQueueContractError, match="前置工序 999"):
        _ready(schedulable={2}, predecessors=predecessors)


def test_missing_predecessor_key_for_schedulable_operation_reports_contract_error() -> None:
    with pytest.raises(ReadyQueueContractError, match="缺少工序 2 的前置集合"):
        _ready(schedulable={2}, predecessors={})


def test_none_predecessor_set_reports_contract_error() -> None:
    with pytest.raises(ReadyQueueContractError, match="工序 2 的前置集合不能为空"):
        _ready(schedulable={2}, predecessors={2: None})


@pytest.mark.parametrize("bad_predecessors", [0, False, ""])
def test_bad_predecessor_collection_reports_contract_error(bad_predecessors) -> None:
    with pytest.raises(ReadyQueueContractError, match=r"predecessor_op_ids_by_op_id\[2\] 必须是 op_id 集合"):
        _ready(schedulable={2}, predecessors={2: bad_predecessors})


def test_blocked_operation_cannot_also_release_successor_as_completed() -> None:
    predecessors = {1: set(), 2: {1}}

    with pytest.raises(ReadyQueueContractError, match="blocked_op_ids 不能同时出现在 completed_or_fixed_op_ids"):
        _ready(schedulable={1, 2}, done={1}, blocked={1}, predecessors=predecessors)


def test_missing_sort_key_reports_contract_error() -> None:
    with pytest.raises(ReadyQueueContractError, match="缺少工序 1 的排序 key"):
        _ready(schedulable={1}, predecessors={1: set()}, sort_keys={})


def test_sort_key_mapping_must_be_mapping() -> None:
    with pytest.raises(ReadyQueueContractError, match="sort_key_by_op_id 必须是映射"):
        get_ready_operation_ids(
            schedulable_op_ids={1},
            completed_or_fixed_op_ids=set(),
            blocked_op_ids=set(),
            predecessor_op_ids_by_op_id={1: set()},
            sort_key_by_op_id=None,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("raw_key", ["1", True])
def test_sort_key_mapping_key_must_be_strict_positive_int(raw_key) -> None:
    with pytest.raises(ReadyQueueContractError, match="sort_key_by_op_id 的 key 必须是正整数 op_id"):
        _ready(schedulable={1}, predecessors={1: set()}, sort_keys={raw_key: (0, 10, 1)})


def test_sort_key_mapping_must_be_valid_even_when_no_operation_is_ready() -> None:
    with pytest.raises(ReadyQueueContractError, match="sort_key_by_op_id 必须是映射"):
        get_ready_operation_ids(
            schedulable_op_ids={1},
            completed_or_fixed_op_ids=set(),
            blocked_op_ids={1},
            predecessor_op_ids_by_op_id={1: set()},
            sort_key_by_op_id=None,  # type: ignore[arg-type]
        )


def test_op_id_inputs_must_be_iterable_collections() -> None:
    with pytest.raises(ReadyQueueContractError, match="schedulable_op_ids 必须是 op_id 集合"):
        get_ready_operation_ids(
            schedulable_op_ids=1,  # type: ignore[arg-type]
            completed_or_fixed_op_ids=set(),
            blocked_op_ids=set(),
            predecessor_op_ids_by_op_id={1: set()},
            sort_key_by_op_id={1: (0, 1, 1)},
        )


def test_graph_like_object_is_not_accepted_as_op_id_collection() -> None:
    class GraphLike:
        nodes = (1, 2)
        edges = ()

        def __iter__(self):
            return iter(self.nodes)

    with pytest.raises(ReadyQueueContractError, match="不能传图对象"):
        get_ready_operation_ids(
            schedulable_op_ids=GraphLike(),
            completed_or_fixed_op_ids=set(),
            blocked_op_ids=set(),
            predecessor_op_ids_by_op_id={1: set(), 2: set()},
            sort_key_by_op_id={1: (0, 1, 1), 2: (0, 2, 2)},
        )


def test_bad_sort_key_shape_reports_contract_error() -> None:
    with pytest.raises(ReadyQueueContractError, match="排序 key 必须是三元组"):
        _ready(schedulable={1}, predecessors={1: set()}, sort_keys={1: (0, 1)})


def test_bad_sort_key_value_reports_contract_error() -> None:
    with pytest.raises(ReadyQueueContractError, match="排序 key 必须只包含整数"):
        _ready(schedulable={1}, predecessors={1: set()}, sort_keys={1: (0, "bad", 1)})


def test_bool_sort_key_value_reports_contract_error() -> None:
    with pytest.raises(ReadyQueueContractError, match="排序 key 必须只包含整数"):
        _ready(schedulable={1}, predecessors={1: set()}, sort_keys={1: (False, 1, 1)})


def test_predecessor_key_outside_known_scope_reports_contract_error() -> None:
    predecessors = {999: set()}

    with pytest.raises(ReadyQueueContractError, match="工序 999 不在待排或已固定集合"):
        _ready(schedulable={2}, predecessors=predecessors)


def test_incremental_ready_queue_matches_full_scan_for_branch_join() -> None:
    predecessors = {1: set(), 2: {1}, 3: {1}, 4: {2, 3}}
    sort_keys = {1: (0, 10, 1), 2: (0, 20, 2), 3: (0, 30, 3), 4: (0, 40, 4)}
    graph_state, ops_by_batch = _graph_state(predecessors, sort_keys=sort_keys)

    assert _incremental_ready_ids(graph_state, ops_by_batch) == _full_scan_ready_ids(graph_state) == [1]

    _mark_graph_operation_completed(graph_state, 1)
    assert _incremental_ready_ids(graph_state, ops_by_batch) == _full_scan_ready_ids(graph_state) == [2, 3]

    _mark_graph_operation_completed(graph_state, 2)
    assert _incremental_ready_ids(graph_state, ops_by_batch) == _full_scan_ready_ids(graph_state) == [3]

    _mark_graph_operation_completed(graph_state, 3)
    assert _incremental_ready_ids(graph_state, ops_by_batch) == _full_scan_ready_ids(graph_state) == [4]


def test_incremental_ready_queue_respects_fixed_predecessor() -> None:
    predecessors = {1: set(), 2: {1}, 3: {2}}
    graph_state, ops_by_batch = _graph_state(
        predecessors,
        fixed={1},
        ops_by_batch={"B1": [_op(2), _op(3)]},
        sort_keys={2: (0, 20, 2), 3: (0, 30, 3)},
    )

    assert _incremental_ready_ids(graph_state, ops_by_batch) == _full_scan_ready_ids(graph_state) == [2]


def test_graph_ready_state_rejects_schedulable_fixed_overlap() -> None:
    predecessors = {1: set()}

    with pytest.raises(ValidationError, match="不能同时是固定"):
        _graph_state(
            predecessors,
            fixed={1},
            ops_by_batch={"B1": [_op(1)]},
            sort_keys={1: (0, 10, 1)},
        )


def test_graph_ready_state_rejects_non_positive_fixed_op_id() -> None:
    predecessors = {1: set()}

    with pytest.raises(ValidationError, match="大于等于 1"):
        _graph_state(predecessors, fixed={0})


@pytest.mark.parametrize(
    ("predecessors", "successors", "message"),
    [
        ({1: {999}}, {1: set(), 999: {1}}, "前置工序 999"),
        ({1: set(), 999: set()}, {1: set(), 999: set()}, "工序 999 不在待排或已固定集合"),
        ({1: set()}, {1: {999}, 999: set()}, "后继工序 999"),
    ],
)
def test_graph_ready_state_rejects_unknown_link_scope(predecessors, successors, message: str) -> None:
    graph_ready_context = {
        "enabled": True,
        "schedulable_op_ids": {1},
        "fixed_op_ids": set(),
        "predecessor_op_ids_by_op_id": predecessors,
        "successor_op_ids_by_op_id": successors,
        "sort_key_by_op_id": {1: (0, 10, 1)},
    }

    with pytest.raises(ValidationError, match=message):
        _prepare_graph_ready_state(graph_ready_context, ops_by_batch={"B1": [_op(1)]})


def test_incremental_ready_queue_removes_blocked_descendants() -> None:
    predecessors = {1: set(), 2: {1}, 3: {2}}
    graph_state, ops_by_batch = _graph_state(predecessors)

    assert _incremental_ready_ids(graph_state, ops_by_batch) == [1]

    _block_graph_operation(graph_state, 1)

    assert _incremental_ready_ids(graph_state, ops_by_batch) == []
    assert graph_state["blocked_op_ids"] == {1, 2, 3}


def test_graph_ready_blocking_rejects_fixed_successor_conflict() -> None:
    predecessors = {1: set(), 2: {1}}
    graph_state, _ops_by_batch = _graph_state(
        predecessors,
        fixed={2},
        ops_by_batch={"B1": [_op(1)]},
        sort_keys={1: (0, 10, 1)},
    )

    with pytest.raises(ValidationError, match="固定/已完成工序冲突"):
        _block_graph_operation(graph_state, 1)


def test_incremental_ready_queue_respects_blocked_batches_for_completion_check() -> None:
    predecessors = {1: set(), 2: set()}
    graph_state, ops_by_batch = _graph_state(
        predecessors,
        ops_by_batch={"B1": [_op(1), _op(2)]},
        sort_keys={1: (0, 10, 1), 2: (0, 20, 2)},
    )

    assert _incremental_ready_ids(graph_state, ops_by_batch, blocked_batches={"B1"}) == []
    _ensure_graph_ready_complete(graph_state=graph_state, ops_by_batch=ops_by_batch, blocked_batches={"B1"})
