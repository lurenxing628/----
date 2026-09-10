"""Batch validation and atomic import boundaries after responsibility splits."""

import pytest
from flask import Flask

from core.errors import ValidationError
from core.models.workbench_batch_query import batch_scope
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.batch_template_validation import template_diagnostics
from tests.workbench.batch_support import batch_database, ref_for, state
from tests.workbench.test_batch_files import confirm, uploaded
from web.routes.workbench.batch_context import read_scope

_batch_fixture = batch_database


@pytest.mark.parametrize("values", [
    {"page": True}, {"page": 0}, {"page": 1000001}, {"size": 101}, {"size": 1.5},
    {"query": None}, {"query": "x" * 201}, {"status": "unknown"}, {"ready_status": False},
    {"sort": "hidden"}, {"direction": None}, {"focus": "unknown"},
    {"column_filters": {"hidden": []}}, {"column_filters": {"quantity": "1"}},
    {"column_filters": {"quantity": [True]}}, {"column_filters": {"quantity": [float("nan")]}},
    {"column_filters": {"quantity": [float("inf")]}}, {"column_filters": {"quantity": [9007199254740992]}},
    {"batch_ids": "B1"}, {"batch_ids": [None]}, {"batch_ids": [""]},
])
def test_scope_rejects_invalid_values_without_coercion(values):
    with pytest.raises(WorkbenchCommandRejected) as error:
        batch_scope(values)
    assert error.value.code == "invalid_input"
    assert error.value.status == 400
    assert error.value.committed is False


def test_scope_keeps_null_zero_empty_filter_and_exact_numeric_boundaries():
    values = {"page": 1000000, "size": 100, "query": "  exact  ", "focus": "gaps", "batch_ids": [],
              "column_filters": {"quantity": [None, 0, 1.5, -9007199254740991], "ready_status": []}}
    result = batch_scope(values)
    assert result == {"status": None, "ready_status": None, "sort": "business_code", "direction": "asc",
                      **values, "query": "exact"}
    assert values["query"] == "  exact  "


def test_query_string_numbers_are_parsed_before_domain_validation():
    with Flask(__name__).test_request_context("/?page=2&size=100&query=part"):
        result = read_scope()
    assert type(result["page"]) is int and result["page"] == 2
    assert type(result["size"]) is int and result["size"] == 100
    assert result["query"] == "part"


@pytest.mark.parametrize("query", ("page=1&page=2", "page=01", "page=-1", "size=true", "size=101"))
def test_query_string_rejects_duplicates_and_invalid_numbers(query):
    with Flask(__name__).test_request_context("/?" + query):
        with pytest.raises(WorkbenchCommandRejected) as error:
            read_scope()
    assert error.value.code == "invalid_input" and error.value.status == 400


@pytest.mark.parametrize("mode", ("overwrite", "append", "replace"))
def test_invalid_first_row_still_reserves_its_duplicate_code(batch_client, mode):
    before = state(batch_client)
    response = uploaded(batch_client, [["NEW", "P1", 0, None, None, None, None, None],
                                       ["NEW", "P1", 2, None, None, None, None, None]], mode)
    assert response.status_code == 200
    document = response.get_json()["data"]
    assert document["count"] == 2 and not document["can_confirm"]
    assert document["write_context"] is None
    assert all(row["action"] == "rejected" and row["input"] is None for row in document["rows"])
    assert document["rows"][0]["errors"] and document["rows"][1]["errors"]
    assert document["rows"][0]["errors"] != document["rows"][1]["errors"]
    assert state(batch_client) == before


def test_append_does_not_skip_validation_of_an_existing_row(batch_client):
    before = state(batch_client)
    response = uploaded(batch_client, [["FREE-001", "P1", True, None, None, None, None, None]], "append")
    document = response.get_json()["data"]
    assert document["rows"][0]["action"] == "rejected"
    assert document["rows"][0]["errors"]
    assert not document["can_confirm"] and state(batch_client) == before


@pytest.mark.parametrize("mode", ("overwrite", "append", "replace"))
def test_later_file_insert_failure_restores_all_rows_and_receipts(batch_client, mode):
    client, conn = batch_client, batch_client.batch_conn
    if mode == "replace":
        conn.execute("DELETE FROM Schedule")
        conn.execute("DELETE FROM BatchMaterials")
    conn.execute("""CREATE TRIGGER fail_second_batch BEFORE INSERT ON Batches WHEN NEW.batch_id='NEW-SECOND'
        BEGIN SELECT RAISE(ABORT,'round1 second batch failure'); END""")
    conn.commit()
    original_ref = ref_for(client)
    response = uploaded(client, [["NEW-FIRST", "P1", 2, None, None, None, None, None],
                                 ["NEW-SECOND", "P1", 3, None, None, None, None, None]], mode)
    document = response.get_json()["data"]
    assert document["can_confirm"]
    before = state(client)
    result = confirm(client, document)
    assert result.status_code == 500
    assert result.get_json()["error"]["code"] == "storage_failure"
    assert result.get_json()["committed"] == "unknown"
    assert state(client) == before
    assert ref_for(client) == original_ref and not conn.in_transaction


def test_template_missing_hours_remain_missing_and_hidden_external_values_are_not_normalized():
    rows = [dict(seq=1, source="internal", op_type_id="T", setup_hours=None, unit_hours=0),
            dict(seq=2, source="external", op_type_id="T", ext_group_id=None, ext_days=None,
                 supplier_id=None, setup_hours=b"raw", unit_hours="unknown")]
    assert len(template_diagnostics(rows, {"ExternalGroups": []}, {"part_no": "P"})) == 3
    assert rows[0]["setup_hours"] is None and rows[0]["unit_hours"] == 0
    assert rows[1]["setup_hours"] == b"raw" and rows[1]["unit_hours"] == "unknown"


@pytest.mark.parametrize("changes", ({"seq": 0}, {"seq": True}, {"source": " EXTERNAL "}))
def test_template_identity_and_source_are_not_guessed(changes):
    row = dict(seq=1, source="internal", op_type_id="T", setup_hours=0, unit_hours=0)
    row.update(changes)
    with pytest.raises(WorkbenchCommandRejected) as error:
        template_diagnostics([row], {"ExternalGroups": []}, {"part_no": "P"})
    assert error.value.code == "constraint_conflict"


@pytest.mark.parametrize("group", (None, {"group_id": "G", "part_no": "OTHER", "merge_mode": "merged", "total_days": 3},
                                   {"group_id": "G", "part_no": "P", "merge_mode": "unknown", "total_days": 3}))
def test_external_group_link_must_be_complete(group):
    row = dict(seq=1, source="external", op_type_id="T", ext_group_id="G", ext_days=2, supplier_id="S")
    facts = {"ExternalGroups": [] if group is None else [group]}
    with pytest.raises(WorkbenchCommandRejected) as error:
        template_diagnostics([row], facts, {"part_no": "P"})
    assert error.value.code == "constraint_conflict"


def test_merged_external_period_is_validated_instead_of_hidden_per_operation_value():
    row = dict(seq=1, source="external", op_type_id="T", ext_group_id="G", ext_days="legacy", supplier_id="S")
    group = dict(group_id="G", part_no="P", merge_mode="merged", total_days=3)
    assert template_diagnostics([row], {"ExternalGroups": [group]}, {"part_no": "P"}) == []
    group["total_days"] = -1
    with pytest.raises(ValidationError) as error:
        template_diagnostics([row], {"ExternalGroups": [group]}, {"part_no": "P"})
    assert error.value.field == "external_days"
