"""Small independent examples for the sample's preserved scheduling rules."""

import copy

import pytest

from web.bootstrap.sample_constraint_checks import check_candidate


@pytest.fixture
def candidate_inputs():
    fields = {"quantity": 2, "priority": "urgent", "due_date": "2026-09-05", "ready_date": "2026-09-01"}
    operations = [{"seq": 1, "source": "internal", "op_type_code": "TURN", "supplier_code": None},
                  {"seq": 2, "source": "external", "op_type_code": "HEAT", "supplier_code": "S"},
                  {"seq": 3, "source": "external", "op_type_code": "COAT", "supplier_code": "S"}]
    part = {"business_code": "P", "operations": operations, "groups": [{"sequences": [2, 3]}]}
    blueprint = {"parts": [part], "batches": [{"business_code": "B", "part_code": "P", "fields": fields}],
                 "resources": {"machines": [{"business_code": "M", "relationships": {"op_type_codes": ["TURN"]}}],
                               "operators": [{"business_code": "O", "relationships": {"skill_codes": ["TURN"]}}]},
                 "operator_machine_permissions": [{"operator_code": "O", "machine_codes": ["M"]}],
                 "schedule_window": {"start_date": "2026-09-01", "end_date": "2026-09-05"},
                 "calendar_days": [], "operator_calendar_days": [], "machine_downtimes": []}
    seed = {"blueprint": blueprint, "operation_refs": {"B": {1: "OP1", 2: "OP2", 3: "OP3"}},
            "refs": {"batch": {"B": "batch-ref"}, "machine": {"M": "machine-ref"},
                     "operator": {"O": "operator-ref"}, "supplier": {"S": "supplier-ref"}}}
    tasks = [{"operation_ref": "OP1", "batch_ref": "batch-ref", "sequence": 1, "quantity": 2,
              "source": "internal", "due_date": "2026-09-05", "start": "2026-09-01T08:00:00",
              "end": "2026-09-01T09:00:00", "machine": {"ref": "machine-ref"},
              "operator": {"ref": "operator-ref"}, "supplier": None}]
    for sequence in (2, 3):
        tasks.append({"operation_ref": "OP" + str(sequence), "batch_ref": "batch-ref", "sequence": sequence,
                      "quantity": 2, "source": "external", "due_date": "2026-09-05",
                      "start": "2026-09-01T09:00:00", "end": "2026-09-02T09:00:00", "machine": None,
                      "operator": None, "supplier": {"ref": "supplier-ref"}})
    workspace = {"tasks_complete": True, "tasks": tasks, "unplanned_operation_count": 0,
                 "candidate": {"completeness": "complete"}}
    preflight = {"tasks": [{"operation_ref": "OP1", "material_ready_date": "2026-09-01"},
                            {"operation_ref": "OP2"}, {"operation_ref": "OP3"}]}
    return workspace, seed, preflight


def test_preserved_counts_and_merged_external_period(candidate_inputs):
    result = check_candidate(*candidate_inputs)
    assert result["operation_count"] == 3 and result["batch_count"] == 1
    assert result["source_counts"] == {"internal": 1, "external": 2}
    assert result["qualified_internal_tasks"] == result["merged_external_cycles"] == result["material_release_checks"] == 1
    assert result["precedence_checks"] == 2 and result["resource_nonoverlap_checks"] == 0
    assert result["machine_count"] == result["operator_count"] == 1
    assert result["priority_counts"] == {"urgent": 1}


@pytest.mark.parametrize("index, field, value, message", [
    (0, "quantity", 3, "数量"), (0, "source", "external", "归属"),
    (0, "due_date", "2026-09-06", "交期"), (0, "start", "2026-08-31T08:00:00", "窗口"),
    (1, "start", "2026-09-01T08:30:00", "后道"), (2, "end", "2026-09-02T10:00:00", "同一真实周期"),
    (0, "machine", None, "真实设备"), (1, "operator", {"ref": "operator-ref"}, "占用了内部"),
    (1, "supplier", {"ref": "other-supplier"}, "供应商"),
])
def test_each_existing_task_rule_still_rejects(candidate_inputs, index, field, value, message):
    workspace, seed, preflight = candidate_inputs
    workspace["tasks"][index][field] = value
    with pytest.raises(RuntimeError, match=message):
        check_candidate(workspace, seed, preflight)


@pytest.mark.parametrize("kind, relation, message", [("machines", "op_type_codes", "设备工种"),
                                                    ("operators", "skill_codes", "人员技能")])
def test_qualification_rules_are_not_weakened(candidate_inputs, kind, relation, message):
    workspace, seed, preflight = candidate_inputs
    seed["blueprint"]["resources"][kind][0]["relationships"][relation] = []
    with pytest.raises(RuntimeError, match=message):
        check_candidate(workspace, seed, preflight)


def test_permission_and_release_rules_are_not_weakened(candidate_inputs):
    workspace, seed, preflight = candidate_inputs
    seed["blueprint"]["operator_machine_permissions"] = []
    with pytest.raises(RuntimeError, match="操作关系"):
        check_candidate(workspace, seed, preflight)
    preflight["tasks"][0]["material_ready_date"] = "2026-09-02"
    with pytest.raises(RuntimeError, match="物料放行"):
        check_candidate(workspace, seed, preflight)


def test_shared_resource_overlap_is_still_rejected(candidate_inputs):
    workspace, seed, preflight = candidate_inputs
    other = copy.deepcopy(seed["blueprint"]["batches"][0])
    other["business_code"] = "B2"
    seed["blueprint"]["batches"].append(other)
    seed["refs"]["batch"]["B2"] = "batch-two"
    seed["operation_refs"]["B2"] = {1: "OTHER1", 2: "OTHER2", 3: "OTHER3"}
    for task in copy.deepcopy(workspace["tasks"]):
        task.update(operation_ref="OTHER" + str(task["sequence"]), batch_ref="batch-two")
        if task["source"] == "internal":
            task.update(start="2026-09-01T08:30:00", end="2026-09-01T09:30:00")
        else:
            task.update(start="2026-09-01T09:30:00", end="2026-09-02T09:30:00")
        workspace["tasks"].append(task)
        preflight["tasks"].append({"operation_ref": task["operation_ref"]})
    with pytest.raises(RuntimeError, match="资源.*重叠"):
        check_candidate(workspace, seed, preflight)
