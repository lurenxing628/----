"""Control chains follow captured joins and retain zero-duration route stages."""

import pytest

from core.services.scheduler.gantt.critical_chain import (
    compute_critical_chain_from_dependencies,
    compute_critical_chain_from_rows,
)


def row(key, start, end, **values):
    return {"op_code": key, "operation_ref": "op-" + key, "start_time": "2026-10-12 " + start,
            "end_time": "2026-10-12 " + end, **values}


def test_explicit_join_follows_later_branch_and_preserves_point_stages():
    rows = [row("start", "08:00", "08:00"), row("fast", "08:00", "09:00"),
            row("slow", "08:00", "10:00"), row("join", "10:00", "10:00"),
            row("finish", "10:00", "10:00")]
    previous = {"start": [], "fast": ["start"], "slow": ["start"],
                "join": ["fast", "slow"], "finish": ["join"]}
    chain = compute_critical_chain_from_dependencies(rows, previous)
    assert chain["ids"] == ["start", "slow", "join", "finish"]
    assert chain["dropped_count"] == 0 and chain["critical_chain_partial"] is False
    assert [edge["edge_type"] for edge in chain["edges"]] == ["process"] * 3


@pytest.mark.parametrize("resource,edge_type", [("machine_id", "machine"), ("operator_id", "operator")])
def test_resource_can_control_start_after_the_process_predecessor_finishes(resource, edge_type):
    rows = [row("process", "08:00", "09:00"), row("resource", "08:00", "10:00", **{resource: "R"}),
            row("target", "10:00", "11:00", **{resource: "R"})]
    chain = compute_critical_chain_from_dependencies(rows, {"target": ["process"]})
    assert chain["ids"] == ["resource", "target"]
    assert chain["edges"][0]["edge_type"] == edge_type


def test_equal_time_selection_uses_permanent_operation_identity_after_adoption():
    rows = [row("candidate-a", "08:00", "09:00", operation_ref="operation-b"),
            row("candidate-z", "08:00", "09:00", operation_ref="operation-a"),
            row("candidate-end", "09:00", "10:00", operation_ref="operation-end")]
    previous = {"candidate-end": ["candidate-a", "candidate-z"]}
    before = compute_critical_chain_from_dependencies(rows, previous)
    renamed = {"candidate-a": "adopted-z", "candidate-z": "adopted-a", "candidate-end": "adopted-end"}
    after = compute_critical_chain_from_dependencies(
        [dict(item, op_code=renamed[item["op_code"]]) for item in reversed(rows)],
        {renamed[child]: [renamed[parent] for parent in parents] for child, parents in previous.items()},
    )
    assert after["ids"] == [renamed[key] for key in before["ids"]]


def test_point_operation_does_not_interrupt_or_create_resource_occupancy():
    rows = [row("occupied", "08:00", "10:00", machine_id="M"),
            row("point", "09:00", "09:00", machine_id="M"),
            row("next", "10:00", "11:00", machine_id="M")]
    chain = compute_critical_chain_from_dependencies(rows, {})
    assert chain["ids"] == ["occupied", "next"]
    assert chain["edges"][0]["edge_type"] == "machine"


def test_critical_chain_preserves_padded_identities_without_spurious_predecessors():
    rows = [
        row(" op-padded ", "08:00", "10:00", batch_id=" B1 ", piece_id=" P1 ", seq=1, machine_id=" M1 ", operator_id=" O1 "),
        row("op-clean", "10:00", "11:00", batch_id="B1", piece_id="P1", seq=2, machine_id="M1", operator_id="O1"),
    ]
    chain = compute_critical_chain_from_rows(rows)
    assert chain["ids"] == ["op-clean"]
    assert chain["edges"] == []

    related = compute_critical_chain_from_rows(rows, target_id=" op-padded ")
    assert related["ids"] == [" op-padded "]
    assert related["edges"] == []


def test_dependency_chain_reports_rows_dropped_for_unusable_times():
    rows = [row("first", "08:00", "09:00"), row("broken", "10:00", "09:00"), row("next", "09:00", "10:00")]
    chain = compute_critical_chain_from_dependencies(rows, {"next": ["first"]})
    assert chain["ids"] == ["first", "next"]
    assert chain["dropped_count"] == 1 and chain["critical_chain_partial"] is True

    empty = compute_critical_chain_from_dependencies([row("broken", "10:00", "09:00")], {})
    assert empty["ids"] == [] and empty["dropped_count"] == 1 and empty["critical_chain_partial"] is True

