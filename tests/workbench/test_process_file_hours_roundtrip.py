"""Real exporter/codec/coordinator roundtrips keep source-inapplicable legacy data."""

import pytest

from core.infrastructure.transaction import TransactionManager
from core.services.workbench.process_file_codec import decode_process_file, encode_process_file
from core.services.workbench.process_file_export import process_export_rows
from core.services.workbench.process_files import WorkbenchProcessFileService
from core.services.workbench.process_queries import WorkbenchProcessQueryService
from tests.workbench.process_workflow_support import confirm_all
from tests.workbench.test_process_file_hours_support import (
    confirmations,
    groups,
    hours_database,
    op_rows,
    part_ref,
    snapshot,
)


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
@pytest.mark.parametrize("mode", ("merged", "separate", "ungrouped"))
def test_real_export_null_na_roundtrip_preserves_hidden_facts_and_stamps(hours_conn, fmt, mode):
    hours_conn.execute("UPDATE PartOperations SET ext_days=17.125 WHERE part_no='P1' AND source='internal'")
    if mode == "ungrouped":
        hours_conn.execute("UPDATE PartOperations SET ext_group_id=NULL WHERE part_no='P1' AND status='active'")
    else:
        hours_conn.execute("UPDATE ExternalGroups SET merge_mode=? WHERE group_id='P1-G'", (mode,))
    if mode == "merged":
        hours_conn.execute("UPDATE PartOperations SET ext_days=NULL WHERE part_no='P1' AND seq=3")
    hours_conn.commit()
    confirm_all(hours_conn, "P1")
    facts = WorkbenchProcessQueryService(hours_conn).facts()
    part = next(row for row in facts["parts"] if row["part_no"] == "P1")
    exported = list(process_export_rows("hours", [part], facts))
    content = encode_process_file("hours", exported, fmt).content
    decoded = decode_process_file("hours", content, fmt)
    assert all(not row["errors"] for row in decoded)
    values = {row["values"]["sequence"]: row["values"] for row in decoded}
    assert values[1]["external_days"] is None and values[1]["group_total_days"] is None
    assert values[3]["setup_hours"] is None and values[3]["unit_hours"] is None
    assert values[3]["group_total_days"] == (6.75 if mode == "merged" else None)
    before = snapshot(hours_conn)
    service = WorkbenchProcessFileService(hours_conn)
    preview, extra = service.preview_import("hours", content, file_format=fmt, target_ref=part_ref(hours_conn))
    assert extra == {"affected_groups": [], "zero_review_required": True,
                     "skipped_count": 0, "skipped_refs": [], "skipped_rows": []}
    assert all(row["result"] == "unchanged" and row["route_summary"] is None for row in preview.as_dict()["rows"])
    assert all(row["entity_ref"] == part_ref(hours_conn) for row in preview.as_dict()["rows"])
    with TransactionManager(hours_conn).transaction(begin_immediate=True):
        outcome = service.confirm_import(preview, content, discard_group_refs=[], confirm_zero_unit_hours=True)
    assert outcome.result == "unchanged" and snapshot(hours_conn) == before

    # Editing one applicable value in that same export still cannot erase N/A data.
    for row in exported:
        if row["sequence"] == 3:
            row["external_days"] = 12.5
    content = encode_process_file("hours", exported, fmt).content
    operations, original_groups, stamps = op_rows(hours_conn), groups(hours_conn), confirmations(hours_conn)
    preview, _ = service.preview_import("hours", content, file_format=fmt, target_ref=part_ref(hours_conn))
    with TransactionManager(hours_conn).transaction(begin_immediate=True):
        outcome = service.confirm_import(preview, content, discard_group_refs=[], confirm_zero_unit_hours=True)
    assert outcome.result == "committed"
    assert op_rows(hours_conn) == {**operations, 3: {**operations[3], "ext_days": 12.5}}
    assert groups(hours_conn) == original_groups and confirmations(hours_conn) == stamps
    assert outcome.data["affected_refs"] == [part_ref(hours_conn)]
    assert all(row["entity_ref"] == part_ref(hours_conn) for row in outcome.data["rows"])
    assert all("stage" not in row for row in outcome.data["rows"])
