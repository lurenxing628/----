from __future__ import annotations

import pytest

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
