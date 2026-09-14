"""Sparse/null/source/identity contracts independent of the file coordinator."""

from copy import deepcopy

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_file import INT64_MAX
from core.models.workbench_resource_action import ResourceActionPreview, public_action_row
from core.services.workbench.process_file_hours import ProcessHoursFileOperations
from core.services.workbench.process_queries import WorkbenchProcessQueryService
from tests.workbench.process_file_hours_support import (
    apply,
    decoded,
    hours_database,
    part_ref,
    preview,
    reconfirm_source,
    snapshot,
)
from tests.workbench.process_route_support import read_only_probe


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_canonical_preview_is_readonly_sparse_and_serializable(hours_conn, fmt):
    before = snapshot(hours_conn)
    facts = WorkbenchProcessQueryService(hours_conn).facts()
    original = deepcopy(facts)
    service = ProcessHoursFileOperations(hours_conn)
    with read_only_probe(hours_conn) as statements:
        rows, extra = service.preview_rows(decoded({"sequence": 1, "unit_hours": 2.125}), facts)
    assert all(sql.lstrip().upper().startswith("SELECT") for sql in statements)
    assert len(statements) <= 3 and facts == original and snapshot(hours_conn) == before
    from_file, file_extra = preview(hours_conn, {"sequence": 1, "unit_hours": 2.125}, fmt=fmt)
    assert (rows, extra) == (from_file, file_extra)
    row = rows[0]
    assert row["entity_ref"] == part_ref(hours_conn) and row["expected"]["operation_ref"] == row["expected"]["operation"]["ref"]
    assert row["changes"] == {"unit_hours": {"before": 0.0, "after": 2.125}}
    assert row["result"] == "update" and extra == {"affected_groups": [], "zero_review_required": False,
        "skipped_count": 0, "skipped_refs": [], "skipped_rows": []}
    public = public_action_row(ResourceActionPreview.build("process.hours.import", {}, rows).as_dict()["rows"][0])
    assert public["entity_ref"] == part_ref(hours_conn) and "operation_ref" not in public
    assert not {"expected", "input", "related"} & set(public)
    assert set(public["before"]) == {"business_code", "sequence", "op_type_name", "source", "setup_hours", "unit_hours",
                                    "external_days", "group_start", "group_end", "group_total_days"}


@pytest.mark.parametrize("field,value", [("setup_hours", None), ("unit_hours", None), ("unit_hours", -1),
    ("unit_hours", True), ("unit_hours", float("inf")), ("unit_hours", float("nan")), ("unit_hours", " "),
    ("unit_hours", 10 ** 400), ("external_days", 1), ("group_total_days", 1)])
def test_bad_internal_values_reject_entire_file(hours_conn, field, value):
    before = snapshot(hours_conn)
    rows, _ = preview(hours_conn, {"sequence": 3, "external_days": 9}, {"sequence": 1, field: value})
    assert rows[1]["result"] == "rejected"
    assert rows[1]["errors"][0]["field"] == field
    with pytest.raises(WorkbenchCommandRejected, match="被拒绝的行"):
        apply(hours_conn, rows, ack=True)
    assert snapshot(hours_conn) == before


@pytest.mark.parametrize("sequence,fields", [(1, {"external_days": None, "group_total_days": None}),
    (3, {"setup_hours": None, "unit_hours": None}), (1, {"setup_hours": "", "unit_hours": ""})])
def test_not_applicable_null_and_empty_fields_never_clear_hidden_values(hours_conn, sequence, fields):
    before = snapshot(hours_conn)
    rows, _ = preview(hours_conn, {"sequence": sequence, **fields})
    assert rows[0]["result"] == "unchanged" and not rows[0]["input"]["hours"]
    apply(hours_conn, rows, ack=True)
    assert snapshot(hours_conn) == before


@pytest.mark.parametrize("field,value", [("source", "external"), ("source", None), ("op_type_name", "other"),
    ("op_type_name", None), ("group_start", 3), ("group_end", 5), ("group_start", True)])
def test_internal_assertions_never_mutate_facts(hours_conn, field, value):
    rows, _ = preview(hours_conn, {"sequence": 1, field: value, "unit_hours": 1})
    assert rows[0]["result"] == "rejected" and rows[0]["errors"][0]["field"] == field


@pytest.mark.parametrize("field,value", [("group_start", None), ("group_end", 3), ("source", "internal"),
    ("setup_hours", 0), ("unit_hours", 0), ("group_total_days", None), ("group_total_days", 0),
    ("external_days", 0), ("external_days", -1)])
def test_external_assertions_and_cycles_are_strict(hours_conn, field, value):
    rows, _ = preview(hours_conn, {"sequence": 3, field: value})
    assert rows[0]["result"] == "rejected" and rows[0]["errors"][0]["field"] == field


@pytest.mark.parametrize("merged", (False, True))
def test_member_clear_requires_existing_merged_group_with_positive_total(hours_conn, merged):
    if not merged:
        hours_conn.execute("UPDATE ExternalGroups SET merge_mode='separate' WHERE group_id='P1-G'")
        hours_conn.commit()
        reconfirm_source(hours_conn)
    rows, _ = preview(hours_conn, {"sequence": 3, "external_days": None})
    assert rows[0]["result"] == ("update" if merged else "rejected")


def test_clear_can_use_positive_group_total_supplied_by_another_member(hours_conn):
    hours_conn.execute("UPDATE ExternalGroups SET total_days=NULL WHERE group_id='P1-G'")
    hours_conn.commit()
    rows, _ = preview(hours_conn, {"sequence": 3, "external_days": None})
    assert rows[0]["result"] == "rejected"
    rows, _ = preview(hours_conn, {"sequence": 3, "external_days": None}, {"sequence": 5, "group_total_days": 8.25})
    assert [row["result"] for row in rows] == ["update", "update"]
    assert all(row["after"]["group_total_days"] == 8.25 for row in rows)
    apply(hours_conn, rows)


@pytest.mark.parametrize("source", ("duplicate", "codec_error", "deleted", "unknown", "bad_int", "bad_code", "unknown_field"))
def test_rejected_rows_prevent_any_apply(hours_conn, source):
    values = {"sequence": 1, "unit_hours": 1}
    rows = decoded(values, values) if source == "duplicate" else decoded(values)
    if source == "codec_error":
        rows[0]["errors"] = [{"row": 2, "field": "unit_hours", "code": "invalid_input", "message": "codec failure"}]
    elif source in ("deleted", "unknown", "bad_int"):
        rows[0]["values"]["sequence"] = {"deleted": 4, "unknown": 99, "bad_int": float(INT64_MAX)}[source]
    elif source == "bad_code":
        rows[0]["values"]["business_code"] = " P1 "
    elif source == "unknown_field":
        rows[0]["values"]["supplier_id"] = "S"
    before = snapshot(hours_conn)
    result, _ = ProcessHoursFileOperations(hours_conn).preview_rows(rows, WorkbenchProcessQueryService(hours_conn).facts())
    assert all(row["result"] == "rejected" for row in result)
    with pytest.raises(WorkbenchCommandRejected):
        apply(hours_conn, result, ack=True)
    assert snapshot(hours_conn) == before


def test_detail_ref_binds_every_row_and_does_not_guess_part_codes(hours_conn):
    rows, _ = preview(hours_conn, {"sequence": 1, "unit_hours": 2},
                      {"business_code": "P2", "sequence": 1, "unit_hours": 2}, target_ref=part_ref(hours_conn))
    assert [row["result"] for row in rows] == ["update", "rejected"]
    with pytest.raises(WorkbenchCommandRejected):
        apply(hours_conn, rows)
    with pytest.raises(WorkbenchCommandRejected):
        preview(hours_conn, {"sequence": 1}, target_ref="f" * 48)


def test_source_confirmation_must_be_current_for_target_but_not_unrelated_operation(hours_conn):
    hours_conn.execute("UPDATE PartOperations SET supplier_id=NULL WHERE part_no='P1' AND seq=3")
    hours_conn.commit()
    rows, _ = preview(hours_conn, {"sequence": 1, "unit_hours": 2})
    assert rows[0]["result"] == "update"
    rows, _ = preview(hours_conn, {"sequence": 3, "external_days": 2})
    assert rows[0]["result"] == "rejected" and rows[0]["errors"][0]["code"] == "stage_not_ready"


@pytest.mark.parametrize("stage", ("route", "source"))
def test_no_stored_confirmation_is_not_inferred_from_existing_hours(hours_conn, stage):
    assignments = ",".join(stage + suffix + "=NULL" for suffix in ("_signature", "_confirmed_at", "_confirmed_by"))
    hours_conn.execute("UPDATE WorkbenchProcessWorkflow SET " + assignments + " WHERE part_ref=?", (part_ref(hours_conn),))
    if stage == "source":
        hours_conn.execute("DELETE FROM WorkbenchProcessOperationConfirmations WHERE stage='source' AND part_ref=?", (part_ref(hours_conn),))
    hours_conn.commit()
    rows, _ = preview(hours_conn, {"sequence": 1, "unit_hours": 1})
    assert rows[0]["errors"][0]["code"] == "stage_not_ready"


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_int64_sequence_and_group_bounds_remain_exact(hours_conn, fmt):
    hours_conn.execute("UPDATE PartOperations SET seq=? WHERE part_no='P1' AND seq=3", (INT64_MAX - 1,))
    hours_conn.execute("UPDATE PartOperations SET seq=? WHERE part_no='P1' AND seq=5", (INT64_MAX,))
    hours_conn.execute("UPDATE ExternalGroups SET start_seq=?,end_seq=? WHERE group_id='P1-G'", (INT64_MAX - 1, INT64_MAX))
    hours_conn.commit()
    reconfirm_source(hours_conn)
    rows, _ = preview(hours_conn, {"sequence": INT64_MAX, "group_start": INT64_MAX - 1,
                                  "group_end": INT64_MAX, "external_days": 8.125}, fmt=fmt)
    assert rows[0]["sequence"] == str(INT64_MAX) and rows[0]["before"]["group_start"] == str(INT64_MAX - 1)
    assert rows[0]["result"] == "update"
    results, refs = apply(hours_conn, rows)
    assert results[0]["sequence"] == str(INT64_MAX) and refs == [part_ref(hours_conn)]


def test_ungrouped_external_cycle_cannot_be_cleared_or_create_a_group(hours_conn):
    hours_conn.execute("UPDATE PartOperations SET ext_group_id=NULL WHERE part_no='P1' AND seq=3")
    hours_conn.commit()
    reconfirm_source(hours_conn)
    for fields in ({"external_days": None}, {"group_start": 3, "group_end": 3}, {"group_total_days": 2}):
        rows, _ = preview(hours_conn, {"sequence": 3, **fields})
        assert rows[0]["result"] == "rejected"


def test_foreign_group_member_blocks_total_edit_without_losing_or_repairing_relation(hours_conn):
    hours_conn.execute("UPDATE PartOperations SET ext_group_id='P1-G' WHERE part_no='P2' AND seq=3")
    hours_conn.commit()
    before = snapshot(hours_conn)
    rows, _ = preview(hours_conn, {"sequence": 3, "group_total_days": 9})
    assert rows[0]["result"] == "rejected" and rows[0]["errors"][0]["code"] == "group_invalid"
    with pytest.raises(WorkbenchCommandRejected):
        apply(hours_conn, rows)
    assert snapshot(hours_conn) == before


def test_missing_target_group_rejects_and_retains_dangling_key(hours_conn):
    hours_conn.execute("PRAGMA foreign_keys=OFF")
    hours_conn.execute("UPDATE PartOperations SET ext_group_id='missing-target' WHERE part_no='P1' AND seq=3")
    hours_conn.commit()
    hours_conn.execute("PRAGMA foreign_keys=ON")
    before = snapshot(hours_conn)
    rows, _ = preview(hours_conn, {"sequence": 3, "external_days": 9})
    assert rows[0]["result"] == "rejected" and rows[0]["errors"][0]["code"] == "group_invalid"
    with pytest.raises(WorkbenchCommandRejected):
        apply(hours_conn, rows)
    assert snapshot(hours_conn) == before
