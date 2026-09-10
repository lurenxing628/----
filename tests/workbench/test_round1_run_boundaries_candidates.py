"""R1-I: archived identities, scheduled scope and real point candidate API."""

import hashlib

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.services.workbench.run_candidate_facts import GenerationFacts
from core.services.workbench.run_candidate_projection import scheduled_ids
from tests.workbench.test_run_candidate_baseline_support import baseline
from tests.workbench.test_run_candidate_support import api, compute, read, retained
from tests.workbench.test_run_candidate_support import candidate_case as _candidate_case


@pytest.mark.parametrize("patch,count", [
    ({"scheduled_op_ids": None}, 1), ({"scheduled_op_ids": [True]}, 1),
    ({"scheduled_op_ids": [0]}, 1), ({"scheduled_op_ids": [1, 1]}, 2),
    ({}, 2), ({"out_of_scope_op_ids": [2]}, 1), ({"validation_errors": ["invalid"]}, 1),
    ({"schedule_rows": None}, 1), ({"schedule_rows": [None]}, 1),
    ({"schedule_rows": [{"op_id": True}]}, 1),
    ({"schedule_rows": [{"op_id": 2}]}, 1),
    ({"scheduled_op_ids": [1, 2], "schedule_rows": [{"op_id": 1}, {"op_id": 1}]}, 2),
])
def test_scheduled_scope_and_rows_must_match_exactly(patch, count):
    payload = {"scheduled_op_ids": [1], "schedule_rows": [{"op_id": 1}],
               "out_of_scope_op_ids": [], "validation_errors": [], **patch}
    with pytest.raises(WorkbenchCommandRejected) as error:
        scheduled_ids({"artifact": {"validated_payload": payload}, "task_count": count})
    assert error.value.code == "candidate_artifact_invalid"


def test_missing_payload_is_unknown_but_real_empty_payload_is_an_empty_set():
    assert scheduled_ids({"artifact": {}, "task_count": 0}) is None
    assert scheduled_ids({"artifact": {"validated_payload": {
        "scheduled_op_ids": [], "schedule_rows": [], "out_of_scope_op_ids": [], "validation_errors": []}},
        "task_count": 0}) == set()


def _capture(entity_rows, operation_rows):
    facts = {"schema": [
        ["table", "WorkbenchEntityRefs", "WorkbenchEntityRefs",
         "CREATE TABLE WorkbenchEntityRefs(kind,entity_key,ref,active)"],
        ["table", "WorkbenchPlanSourceRefs", "WorkbenchPlanSourceRefs",
         "CREATE TABLE WorkbenchPlanSourceRefs(kind,source_key,ref,active)"],
    ], "tables": {"WorkbenchEntityRefs": entity_rows, "WorkbenchPlanSourceRefs": operation_rows}}
    text = canonical_json(facts)
    return {"facts_text": text, "facts_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(), "execution": []}


def test_archived_indices_keep_only_active_refs_without_current_database():
    facts = GenerationFacts(_capture(
        [["batch", "B1", "a" * 48, 1], [None, None, None, 0]],
        [["operation", "1", "b" * 48, 1], ["operation", None, None, 0], ["official", None, None, 1]]))
    assert facts.entity_refs == {("batch", "B1"): "a" * 48}
    assert facts.operations == {"b" * 48: 1} and facts.execution == {}
    assert all(table == {} for table in facts.tables.values())


@pytest.mark.parametrize("key", [None, 1, "01", "1.0", "-1", ""])
def test_archived_operation_keys_must_be_canonical_text_integers(key):
    with pytest.raises(WorkbenchCommandRejected):
        GenerationFacts(_capture([], [["operation", key, "a" * 48, 1]]))


@pytest.mark.parametrize("damage", ["digest", "entity_key", "entity_duplicate", "operation_duplicate", "ref"])
def test_archived_identity_corruption_is_not_replaced_by_current_facts(damage):
    entities = [["batch", "B1", "a" * 48, 1]]
    operations = [["operation", "1", "b" * 48, 1]]
    if damage == "entity_key":
        entities[0][1] = 1
    elif damage == "entity_duplicate":
        entities.append(list(entities[0]))
    elif damage == "operation_duplicate":
        operations.append(list(operations[0]))
    elif damage == "ref":
        operations[0][2] = "bad"
    capture = _capture(entities, operations)
    if damage == "digest":
        capture["facts_hash"] = "0" * 64
    with pytest.raises(WorkbenchCommandRejected):
        GenerationFacts(capture)


@pytest.mark.parametrize("quantity", [0, 3])
def test_all_four_real_point_candidates_keep_full_public_dto_and_baseline(candidate_case, quantity):
    case = candidate_case
    case.conn.execute("UPDATE Batches SET quantity=?", (quantity,))
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0,setup_hours=0")
    case.conn.commit()
    run_ref, refs = compute(case)
    assert len(refs) == 4
    client, _ = api(case)
    with retained(case.conn):
        for ref in refs:
            workspace = read(client, "/candidates/" + ref)["data"]
            task, = workspace["tasks"]
            assert workspace["generation"]["run_ref"] == run_ref
            assert workspace["tasks_complete"] is True and workspace["task_count"] == 1
            assert task["start"] == task["end"]
            assert task["event_kind"] == "point" and task["duration_seconds"] == 0
            assert task["occupies_resources"] is False and task["locked"] is False
            assert task["piece_id"] is None and task["quantity"] == task["batch_quantity"] == quantity
            execution = task["execution_at_generation"]
            assert execution["target_quantity"] == execution["remaining_quantity"] == quantity
            assert execution["known_completed_quantity"] == 0
            compared, _ = baseline(case, ref)
            row, = compared["comparisons"]
            assert row["row_ref"] == task["row_ref"] and row["operation_ref"] == task["operation_ref"]
            assert row["candidate"]["event_kind"] == "point"
            assert row["candidate"]["duration_seconds"] == 0
            assert row["candidate"]["occupies_resources"] is False
            assert row["status"] == "newly_scheduled" and row["improvement_assessment"] is None
