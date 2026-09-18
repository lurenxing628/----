"""Sparse Excel skips, exact counts and old importer preservation contracts."""

from copy import deepcopy

import pytest

from core.services.workbench.process_file_codec import decode_process_file, encode_process_file
from core.services.workbench.process_file_hours import ProcessHoursFileOperations
from core.services.workbench.process_queries import WorkbenchProcessQueryService
from core.services.workbench.process_quota_protection import quota_skip_summary
from tests.workbench.process_quota_protection_support import (
    adopt,
    assert_rejected,
    file_apply,
    file_preview,
    preserved,
    snapshot,
    templates,
)
from tests.workbench.process_quota_protection_support import locked_quota_case as _locked  # noqa: F401
from tests.workbench.process_quota_protection_support import quota_case as _quota  # noqa: F401
from tests.workbench.template_lineage_support import ledger_fixture as _ledger  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as _lineage  # noqa: F401


@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_real_mixed_file_skips_locked_row_and_counts_without_hidden_writes(locked_quota_case, fmt):
    case = locked_quota_case
    content = encode_process_file("hours", [{"business_code": "P1", "sequence": 1, "setup_hours": 9, "unit_hours": 99},
        {"business_code": "P1", "sequence": 2, "unit_hours": 8}], fmt).content
    source = decode_process_file("hours", content, fmt)
    before, old = snapshot(case.conn), templates(case.conn)
    reader = WorkbenchProcessQueryService(case.conn)
    with reader.read_snapshot():
        rows, extra = ProcessHoursFileOperations(case.conn).preview_rows(source, reader.facts())
    assert snapshot(case.conn) == before
    assert [row["result"] for row in rows] == ["skipped", "update"]
    assert rows[0]["before"] == rows[0]["after"] and rows[0]["changes"] == {}
    assert rows[0]["skip_reason"]["template_operation_ref"] == case.template_ref
    assert rows[0]["skip_reason"]["reason"] == "Adopt verified completed production samples"
    original = deepcopy(rows)
    results, affected = file_apply(case.conn, rows)
    assert rows == original
    assert [row["result"] for row in results] == ["skipped", "committed"]
    summary = quota_skip_summary(results)
    assert summary["skipped_count"] == 1 and summary["skipped_refs"] == [case.template_ref]
    assert all(summary[key] == extra[key] for key in summary)
    assert affected == [case.ref("part", "P1")]
    assert templates(case.conn) == {1: old[1], 2: {**old[2], "unit_hours": 8}}
    preserved(before, snapshot(case.conn))


@pytest.mark.parametrize("values,expected", [({"setup_hours": 9}, "committed"),
    ({"setup_hours": 9, "unit_hours": 3}, "committed"), ({"unit_hours": 3}, "unchanged")])
def test_locked_quota_does_not_block_setup_or_report_noop_as_skip(locked_quota_case, values, expected):
    case = locked_quota_case
    rows, extra = file_preview(case.conn, {"sequence": 1, **values})
    result, _ = file_apply(case.conn, rows)
    assert result[0]["result"] == expected and extra["skipped_count"] == 0
    assert templates(case.conn)[1]["unit_hours"] == 3


def test_skipped_zero_requires_no_zero_ack_and_all_skipped_has_no_affected_refs(locked_quota_case):
    case = locked_quota_case
    before = snapshot(case.conn)
    rows, extra = file_preview(case.conn, {"sequence": 1, "unit_hours": 0})
    assert not extra["zero_review_required"] and extra["skipped_count"] == 1
    result, affected = file_apply(case.conn, rows)
    assert result[0]["result"] == "skipped" and affected == [] and snapshot(case.conn) == before


def test_adoption_between_domain_preview_and_apply_is_rechecked_before_writes(quota_case):
    case = quota_case
    rows, extra = file_preview(case.conn, {"sequence": 1, "unit_hours": 99}, {"sequence": 2, "unit_hours": 8})
    assert extra["skipped_count"] == 0
    adopt(case)
    before = snapshot(case.conn)
    result, _ = file_apply(case.conn, rows)
    assert [row["result"] for row in result] == ["skipped", "committed"]
    assert templates(case.conn)[1]["unit_hours"] == 3 and templates(case.conn)[2]["unit_hours"] == 8
    preserved(before, snapshot(case.conn))


def test_duplicate_or_invalid_locked_rows_remain_errors_not_silent_skips(locked_quota_case):
    case = locked_quota_case
    rows, _ = file_preview(case.conn, {"sequence": 1, "unit_hours": 99}, {"sequence": 1, "unit_hours": 98})
    assert all(row["result"] == "rejected" for row in rows)
    before = snapshot(case.conn)
    assert_rejected("constraint_conflict", lambda: file_apply(case.conn, rows))
    assert snapshot(case.conn) == before


