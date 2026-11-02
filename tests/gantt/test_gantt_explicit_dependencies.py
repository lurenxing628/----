"""Control chains follow captured joins and retain zero-duration route stages."""

from datetime import datetime

import pytest

from core.services.scheduler.gantt.critical_chain import compute_critical_chain_from_dependencies


def task(key, start, end, **values):
    return ({"task_ref": key, "operation_ref": "op-" + key, "machine_ref": None, "operator_ref": None, **values},
            (datetime.fromisoformat("2026-10-12T" + start), datetime.fromisoformat("2026-10-12T" + end)))


def critical_chain(tasks, previous):
    return compute_critical_chain_from_dependencies(
        [item for item, _ in tasks], previous,
        task_intervals={item["task_ref"]: interval for item, interval in tasks},
    )


def test_explicit_join_follows_later_branch_and_preserves_point_stages():
    tasks = [task("start", "08:00", "08:00"), task("fast", "08:00", "09:00"),
             task("slow", "08:00", "10:00"), task("join", "10:00", "10:00"),
             task("finish", "10:00", "10:00")]
    previous = {"start": [], "fast": ["start"], "slow": ["start"],
                "join": ["fast", "slow"], "finish": ["join"]}
    chain = critical_chain(tasks, previous)
    assert chain["ids"] == ["start", "slow", "join", "finish"]
    assert [edge["edge_type"] for edge in chain["edges"]] == ["process"] * 3


@pytest.mark.parametrize("resource,edge_type", [("machine_ref", "machine"), ("operator_ref", "operator")])
def test_resource_can_control_start_after_the_process_predecessor_finishes(resource, edge_type):
    tasks = [task("process", "08:00", "09:00"), task("resource", "08:00", "10:00", **{resource: "R"}),
             task("target", "10:00", "11:00", **{resource: "R"})]
    chain = critical_chain(tasks, {"process": [], "resource": [], "target": ["process"]})
    assert chain["ids"] == ["resource", "target"]
    assert chain["edges"][0]["edge_type"] == edge_type


def test_equal_time_selection_uses_permanent_operation_identity_after_adoption():
    tasks = [task("candidate-a", "08:00", "09:00", operation_ref="operation-b"),
             task("candidate-z", "08:00", "09:00", operation_ref="operation-a"),
             task("candidate-end", "09:00", "10:00", operation_ref="operation-end")]
    previous = {"candidate-a": [], "candidate-z": [], "candidate-end": ["candidate-a", "candidate-z"]}
    before = critical_chain(tasks, previous)
    renamed = {"candidate-a": "adopted-z", "candidate-z": "adopted-a", "candidate-end": "adopted-end"}
    after = critical_chain(
        [(dict(item, task_ref=renamed[item["task_ref"]]), interval) for item, interval in reversed(tasks)],
        {renamed[child]: [renamed[parent] for parent in parents] for child, parents in previous.items()},
    )
    assert after["ids"] == [renamed[key] for key in before["ids"]]


def test_point_operation_does_not_interrupt_or_create_resource_occupancy():
    tasks = [task("occupied", "08:00", "10:00", machine_ref="M"),
             task("point", "09:00", "09:00", machine_ref="M"),
             task("next", "10:00", "11:00", machine_ref="M")]
    chain = critical_chain(tasks, {"occupied": [], "point": [], "next": []})
    assert chain["ids"] == ["occupied", "next"]
    assert chain["edges"][0]["edge_type"] == "machine"


def test_critical_chain_preserves_padded_identities_without_spurious_predecessors():
    tasks = [
        task("padded", "08:00", "10:00", machine_ref=" M1 ", operator_ref=" O1 "),
        task("clean", "10:00", "11:00", machine_ref="M1", operator_ref="O1"),
    ]
    chain = critical_chain(tasks, {"padded": [], "clean": []})
    assert chain["ids"] == ["clean"]
    assert chain["edges"] == []
