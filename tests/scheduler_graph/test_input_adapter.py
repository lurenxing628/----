from __future__ import annotations

import builtins
import importlib
import json
import sys
from dataclasses import asdict
from datetime import date

import pytest

from core.services.scheduler.graph.input_adapter import GraphInputContractError, build_operation_nodes_from_rows


def _batch(**overrides):
    data = {
        "batch_id": "B001",
        "part_no": "P001",
        "quantity": 10,
        "priority": "urgent",
        "due_date": date(2026, 5, 20),
    }
    data.update(overrides)
    return data


def _internal_row(**overrides):
    data = {
        "id": 1,
        "batch_id": "B001",
        "op_code": "B001_10",
        "seq": 10,
        "op_type_name": "下料",
        "source": "internal",
        "setup_hours": 1,
        "unit_hours": 0.5,
        "op_type_id": "cut",
    }
    data.update(overrides)
    return data


def _external_row(**overrides):
    data = {
        "id": 2,
        "batch_id": "B001",
        "op_code": "B001_20",
        "seq": 20,
        "op_type_name": "外协热处理",
        "source": "external",
        "ext_days": 2,
    }
    data.update(overrides)
    return data


def _resource_pool():
    return {
        "machines_by_op_type": {"cut": ["M01", "M02"]},
        "operators_by_machine": {"M01": ["U01"], "M02": ["U02"]},
        "machines_by_operator": {"U01": ["M01"], "U02": ["M02"]},
    }


def test_build_internal_operation_node_duration() -> None:
    nodes = build_operation_nodes_from_rows([_internal_row()], batches={"B001": _batch()})

    assert len(nodes) == 1
    node = nodes[0]
    assert node.node_id == "op:1"
    assert node.batch_id == "B001"
    assert node.op_code == "B001_10"
    assert node.seq == 10
    assert node.name == "下料"
    assert node.duration_minutes == 360
    assert node.part_no == "P001"
    assert node.priority == "urgent"
    assert node.due_date == "2026-05-20"
    assert node.source == "internal"


def test_build_external_operation_node_duration() -> None:
    nodes = build_operation_nodes_from_rows([_external_row()], batches={"B001": _batch()})

    assert nodes[0].duration_minutes == 2880
    assert nodes[0].source == "external"


def test_build_merged_external_operation_node_duration() -> None:
    row = _external_row(ext_days=2, ext_group_id="EG01", ext_merge_mode="merged", ext_group_total_days=3)

    nodes = build_operation_nodes_from_rows([row], batches={"B001": _batch()})

    assert nodes[0].duration_minutes == 4320
    assert nodes[0].ext_group_id == "EG01"
    assert nodes[0].ext_merge_mode == "merged"
    assert nodes[0].ext_group_total_days == 3


def test_candidate_resources_from_resource_pool() -> None:
    nodes = build_operation_nodes_from_rows([_internal_row()], batches={"B001": _batch()}, resource_pool=_resource_pool())

    assert nodes[0].candidate_machine_ids == ("M01", "M02")
    assert nodes[0].candidate_operator_ids == ("U01", "U02")


def test_fixed_resources_win_over_pool_candidates() -> None:
    matching = build_operation_nodes_from_rows(
        [_internal_row(machine_id="M01", operator_id="U01")],
        batches={"B001": _batch()},
        resource_pool=_resource_pool(),
    )[0]
    mismatching_machine = build_operation_nodes_from_rows(
        [_internal_row(machine_id="M03", operator_id="U01")],
        batches={"B001": _batch()},
        resource_pool=_resource_pool(),
    )[0]

    assert matching.candidate_machine_ids == ("M01",)
    assert matching.candidate_operator_ids == ("U01",)
    assert mismatching_machine.candidate_machine_ids == ()
    assert mismatching_machine.candidate_operator_ids == ("U01",)


def test_fixed_operator_resolves_machine_candidates() -> None:
    by_operator = build_operation_nodes_from_rows(
        [_internal_row(operator_id="U01")],
        batches={"B001": _batch()},
        resource_pool=_resource_pool(),
    )[0]
    reverse_lookup = build_operation_nodes_from_rows(
        [_internal_row(operator_id="U01")],
        batches={"B001": _batch()},
        resource_pool={
            "machines_by_op_type": {"cut": ["M01", "M02"]},
            "operators_by_machine": {"M01": ["U01"], "M02": ["U02"]},
            "machines_by_operator": {},
        },
    )[0]

    assert by_operator.candidate_machine_ids == ("M01",)
    assert by_operator.candidate_operator_ids == ("U01",)
    assert reverse_lookup.candidate_machine_ids == ("M01",)
    assert reverse_lookup.candidate_operator_ids == ("U01",)


@pytest.mark.parametrize(
    "field_name, row",
    [
        ("batch_id", _internal_row(batch_id="")),
        ("op_code", _internal_row(op_code="")),
        ("seq", _internal_row(seq="abc")),
        ("source", _internal_row(source="")),
    ],
)
def test_missing_required_field_raises_contract_error(field_name, row) -> None:
    with pytest.raises(GraphInputContractError, match=field_name):
        build_operation_nodes_from_rows([row], batches={"B001": _batch()})


def test_missing_batch_raises_contract_error() -> None:
    with pytest.raises(GraphInputContractError, match="找不到批次"):
        build_operation_nodes_from_rows([_internal_row(batch_id="B404")], batches={"B001": _batch()})


def test_invalid_source_raises_contract_error() -> None:
    with pytest.raises(GraphInputContractError, match="source"):
        build_operation_nodes_from_rows([_internal_row(source="unknown")], batches={"B001": _batch()})


@pytest.mark.parametrize(
    "row, batches, message",
    [
        (_internal_row(setup_hours=None), {"B001": _batch()}, "setup_hours"),
        (_internal_row(unit_hours=None), {"B001": _batch()}, "unit_hours"),
        (_internal_row(), {"B001": _batch(quantity=None)}, "quantity"),
        (_external_row(ext_days=None), {"B001": _batch()}, "ext_days"),
        (_external_row(ext_days=0), {"B001": _batch()}, "ext_days"),
        (_external_row(ext_merge_mode="merged", ext_group_total_days=0), {"B001": _batch()}, "ext_group_total_days"),
    ],
)
def test_missing_duration_inputs_raise_contract_error(row, batches, message) -> None:
    with pytest.raises(GraphInputContractError, match=message):
        build_operation_nodes_from_rows([row], batches=batches)


def test_resource_pool_missing_mapping_keeps_empty_candidates() -> None:
    node = build_operation_nodes_from_rows(
        [_internal_row(op_type_id="cut")],
        batches={"B001": _batch()},
        resource_pool={},
    )[0]

    assert node.candidate_machine_ids == ()
    assert node.candidate_operator_ids == ()


def test_raw_snapshot_is_json_serializable_and_frozen() -> None:
    row = _internal_row()
    node = build_operation_nodes_from_rows([row], batches={"B001": _batch()})[0]

    json.dumps(dict(node.raw), ensure_ascii=False)
    json.dumps(asdict(node), ensure_ascii=False)
    row["op_code"] = "CHANGED"

    assert node.raw["op_code"] == "B001_10"
    with pytest.raises(TypeError):
        node.raw["op_code"] = "CHANGED"


def test_input_adapter_does_not_import_networkx(monkeypatch) -> None:
    sys.modules.pop("core.services.scheduler.graph.input_adapter", None)
    sys.modules.pop("networkx", None)

    real_import = builtins.__import__
    imported = []

    def tracking_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "networkx" or name.startswith("networkx."):
            imported.append(name)
            raise AssertionError("input_adapter import must not import networkx")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", tracking_import)

    importlib.import_module("core.services.scheduler.graph.input_adapter")

    assert imported == []
