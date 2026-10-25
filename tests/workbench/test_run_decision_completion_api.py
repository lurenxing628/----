"""Exact candidate completion sets and remaining work retain independent anchors."""

import csv
import io
from types import SimpleNamespace

from openpyxl import load_workbook

from core.services.workbench.facts.completion_scope import project_completion_summary
from core.services.workbench.run.decision_completion_queries import completion_batches, normalize_completion_filters
from tests.workbench.legacy_run_archive_support import install_complete_legacy_archive, install_different_work_archive
from tests.workbench.run_candidate_support import BASE, api, compute
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401
from tests.workbench.test_completion_scope import batch_item
from tests.workbench.test_run_decision_api import decision
from tests.workbench.test_run_decision_impact_api import detail, many_batches, operation_ref

RUN, FIRST, SECOND, VIEWER = (format(number, "048x") for number in range(1, 5))


def completion_source(deliveries, pending, *, unavailable=()):
    scopes = {key: project_completion_summary(items, pending[key], available=key not in unavailable)
              for key, items in deliveries.items()}
    scope = {"run_ref": RUN, "selected_candidate_ref": VIEWER, "comparison_mode": "candidates",
             "reference": {"kind": "candidate", "candidate_ref": FIRST}, "reference_state": "available",
             "range_start": "2026-10-13T08:00:00", "range_end": "2026-10-13T09:00:00",
             "resource_view": "selected_batches", "metric_scope": "full_admission", "time_basis": "factory_local",
             "batch_refs": sorted({row["batch_ref"] for items in deliveries.values() for row in items})}
    rows = [{"candidate_ref": key, "status": "failed" if key in unavailable else "completed",
             "artifact": {"label": "候选 " + str(index), "failure_reason": "历史结果缺失" if key in unavailable else None}}
            for index, key in enumerate(deliveries, 1)]
    source = SimpleNamespace(run={"run_ref": RUN}, scope=scope, baseline={"kind": "candidate", "candidate_ref": FIRST,
                            "state": "available"}, selected_ref=VIEWER, rows=rows, reference_ref=FIRST,
                             comparison_mode="candidates", resource_view="selected_batches")
    source._candidate_reference = lambda key, require_result=True: next(row for row in rows if row["candidate_ref"] == key)
    source.completion = SimpleNamespace(
        delivery=deliveries.__getitem__, scope=lambda key, coverage=None: scopes[key],
        remaining_batches=lambda key: {row["batch_ref"]: row for row in scopes[key]["remaining_batches"]},
        remaining_operation_refs=lambda key: set(scopes[key]["unplanned_operation_refs"] + scopes[key]["deferred_operation_refs"]),
    )
    return source


def test_partial_completion_anchor_and_remaining_export_exclude_arranged_prefixes(candidate_case, monkeypatch):
    case = candidate_case
    # Explicit old saved directories retain two genuinely different completed work sets.
    install_different_work_archive(monkeypatch)
    case.conn.execute("UPDATE Batches SET quantity=1,due_date='2026-09-09' WHERE batch_id='B1'")
    case.conn.execute("UPDATE BatchOperations SET setup_hours=2,unit_hours=3 WHERE id=?", (case.op_id,))
    case.batch("B2", quantity=1, due_date="2026-09-10")
    first_b2 = case.operation("B2", unit_hours=4)
    second_b2 = case.operation("B2", seq=2, unit_hours=2)
    case.config(dispatch_mode="batch_order", sort_strategy="due_date_first")
    run_ref, refs = compute(case, case.settings("B1", "B2", end_date="2026-09-09"))
    client, _ = api(case)
    query = {"selected_candidate_ref": refs[-2], "reference_candidate_ref": refs[0]}
    overview = decision(client, run_ref, **query)["data"]
    recommendation = overview["recommendation"]
    fixed = recommendation["candidate_ref"]
    assert fixed != refs[0] and recommendation["viewed_candidate_ref"] == refs[-2]
    assert len(overview["completion_groups"]) == 2
    batch_refs = {code: case.ref("batch", code) for code in ("B1", "B2")}
    op_refs = {operation_ref(case, op) for op in (case.op_id, first_b2, second_b2)}
    default_anchor = detail(client, run_ref, "completion-batches", **query)["data"]
    assert default_anchor["candidate"]["candidate_ref"] == default_anchor["filters"]["completion_candidate_ref"] == refs[-2]
    for anchor, completed, missing, count in ((refs[0], "B1", "B2", 2), (fixed, "B2", "B1", 1)):
        all_batches = detail(client, run_ref, "completion-batches", **dict(query, completion_candidate_ref=anchor))
        data = all_batches["data"]
        assert data["candidate"]["candidate_ref"] == anchor
        assert data["scope"]["selected_candidate_ref"] == refs[-2]
        assert data["source"]["role"] == "completion_anchor"
        assert data["source"]["grain"] == "full_admission_per_candidate_batch" and data["source"]["available"] is True
        token = all_batches["meta"]["snapshot_ref"]
        assert data["filters"]["section"] == "completion-batches" and data["filters"]["completion_candidate_ref"] == anchor
        assert {row["batch_ref"] for row in data["items"]} == set(batch_refs.values())
        complete = detail(client, run_ref, "completion-batches", **dict(query, completion_candidate_ref=anchor,
                                                                       completion_filter="complete"))["data"]
        unfinished = detail(client, run_ref, "completion-batches", **dict(query, completion_candidate_ref=anchor,
                                                                         completion_filter="unfinished"))["data"]
        assert [row["batch_ref"] for row in complete["items"]] == [batch_refs[completed]]
        assert complete["items"][0]["remaining_drill"] is None
        assert [row["batch_ref"] for row in unfinished["items"]] == [batch_refs[missing]]
        item = unfinished["items"][0]
        assert item["completion_state"] == "incomplete" and item["schedule_complete"] is False
        assert item["unplanned_operation_count"] == item["remaining_work"]["operation_count"] == count
        assert item["deferred_operation_count"] == 0
        assert item["remaining_drill"]["candidate_ref"] == anchor
        assert item["remaining_drill"]["detail_query"]["work_scope"] == "remaining"
        assert item["remaining_drill"]["detail_query"]["batch_ref"] == batch_refs[missing]
        assert unfinished["summary"] == complete["summary"] == data["summary"]
        changed = client.get(BASE + "/runs/" + run_ref + "/decision/completion-batches",
                             query_string=dict(query, completion_candidate_ref=anchor, completion_filter="unfinished", snapshot_ref=token))
        assert changed.status_code == 409 and changed.get_json()["error"]["code"] == "snapshot_stale"
        other_anchor = fixed if anchor == refs[0] else refs[0]
        changed = client.get(BASE + "/runs/" + run_ref + "/decision/completion-batches",
                             query_string=dict(query, completion_candidate_ref=other_anchor, snapshot_ref=token))
        assert changed.status_code == 409 and changed.get_json()["error"]["code"] == "snapshot_stale"
    drill = recommendation["completion_scope"]["drill"]
    assert drill["candidate_ref"] == fixed and drill["detail_query"]["work_scope"] == "remaining"
    preparation_query = {"selected_candidate_ref": fixed, "reference_candidate_ref": refs[0]}
    full = detail(client, run_ref, "preparation", **preparation_query)["data"]
    remaining = detail(client, run_ref, "preparation", **dict(preparation_query, work_scope="remaining"))
    assert {row["operation_ref"] for row in full["items"]} == op_refs and full["page"]["total"] == 3
    assert [row["operation_ref"] for row in remaining["data"]["items"]] == [operation_ref(case, case.op_id)]
    assert remaining["data"]["page"]["total"] == 1 and remaining["data"]["summary"] == full["summary"]
    assert remaining["data"]["items"][0]["after"]["allocation_state"] == "unplanned"
    assert remaining["data"]["items"][0]["after"]["required_standard_hours"] == 5
    empty = detail(client, run_ref, "preparation", **dict(preparation_query, work_scope="remaining", batch_ref=batch_refs["B2"]))
    assert empty["data"]["items"] == [] and empty["data"]["page"]["total"] == 0
    empty = detail(client, run_ref, "preparation", **dict(preparation_query, work_scope="remaining", allocation_state="new_schedule"))
    assert empty["data"]["items"] == [] and empty["data"]["page"]["total"] == 0
    intersected = detail(client, run_ref, "preparation", **dict(preparation_query, work_scope="remaining", allocation_state="unplanned",
                                                               batch_ref=batch_refs["B1"], machine_ref=case.ref("machine", "M1")))
    assert intersected["data"]["items"] == remaining["data"]["items"]
    export_query = dict(preparation_query, work_scope="remaining", snapshot_ref=remaining["meta"]["snapshot_ref"], section="preparation")
    for fmt in ("csv", "xlsx"):
        response = client.get(BASE + "/runs/" + run_ref + "/decision/export", query_string=dict(export_query, format=fmt))
        assert response.status_code == 200, response.get_json()
        assert response.headers["X-Workbench-Snapshot-Ref"] == remaining["meta"]["snapshot_ref"]
        assert int(response.headers["X-Workbench-Row-Count"]) == 1
        if fmt == "csv":
            records = list(csv.DictReader(io.StringIO(response.data.decode("utf-8-sig"))))
            assert len(records) == 1 and records[0]["工序永久编号"] == operation_ref(case, case.op_id)
            assert records[0]["所选工序安排状态"] == "unplanned" and float(records[0]["所选所需标准工时"]) == 5
        else:
            book = load_workbook(io.BytesIO(response.data), read_only=True, data_only=False)
            try:
                rows = list(book["准备需求"].iter_rows())
                assert len(rows) == 2
                cells = dict(zip((cell.value for cell in rows[0]), rows[1]))
                assert cells["工序永久编号"].value == operation_ref(case, case.op_id)
                assert cells["所选所需标准工时"].value == 5 and cells["所选所需标准工时"].data_type == "n"
            finally:
                book.close()
    stale = client.get(BASE + "/runs/" + run_ref + "/decision/preparation",
                       query_string=dict(preparation_query, snapshot_ref=remaining["meta"]["snapshot_ref"], work_scope="all"))
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "snapshot_stale"


def test_completion_batches_api_paginates_all_members_under_one_snapshot(candidate_case, monkeypatch):
    case = candidate_case
    # Multiple saved identities keep the completion-anchor snapshot rejection contract.
    install_complete_legacy_archive(monkeypatch)
    run_ref, refs, codes = many_batches(case)
    client, _ = api(case)
    query = {"selected_candidate_ref": refs[-2], "reference_candidate_ref": refs[0],
             "completion_candidate_ref": refs[0], "completion_filter": "complete", "sort": "batch_id", "order": "asc"}
    first = detail(client, run_ref, "completion-batches", **query)
    token = first["meta"]["snapshot_ref"]
    second = detail(client, run_ref, "completion-batches", **dict(query, page=2, snapshot_ref=token))
    wide = detail(client, run_ref, "completion-batches", **dict(query, size=50, snapshot_ref=token))
    one, two, all_rows = (response["data"] for response in (first, second, wide))
    assert second["meta"]["snapshot_ref"] == wide["meta"]["snapshot_ref"] == token
    assert one["items"] + two["items"] == all_rows["items"]
    assert one["page"] == {"number": 1, "size": 20, "total": 27, "has_more": True}
    assert two["page"] == {"number": 2, "size": 20, "total": 27, "has_more": False}
    assert len(two["items"]) == 7 and all_rows["page"]["has_more"] is False
    expected = sorted((code, case.ref("batch", code)) for code in codes)
    assert [(row["batch_label"], row["batch_ref"]) for row in all_rows["items"]] == expected
    assert len(all_rows["items"]) == len({row["batch_ref"] for row in all_rows["items"]}) == 27
    assert all_rows["scope"]["selected_candidate_ref"] == refs[-2]
    assert all_rows["candidate"]["candidate_ref"] == refs[0]
    assert all(row["completion_state"] == "complete" and row["remaining_work"]["operation_count"] == 0
               and row["remaining_drill"] is None for row in all_rows["items"])
    assert all_rows["summary"]["complete_batch_count"] == 27
    assert one["summary"] == two["summary"] == all_rows["summary"]
    beyond = detail(client, run_ref, "completion-batches", **dict(query, page=3, snapshot_ref=token))["data"]
    assert beyond["items"] == [] and beyond["page"]["total"] == 27 and beyond["page"]["has_more"] is False
    empty = detail(client, run_ref, "completion-batches", **dict(query, completion_filter="unfinished"))["data"]
    assert empty["items"] == [] and empty["page"]["total"] == 0 and empty["page"]["has_more"] is False
    assert empty["filters"]["completion_filter"] == "unfinished" and empty["summary"] == all_rows["summary"]
    path = BASE + "/runs/" + run_ref + "/decision/completion-batches"
    for changed in ({"order": "desc"}, {"completion_filter": "unfinished"}, {"completion_candidate_ref": refs[1]}):
        rejected = client.get(path, query_string=dict(query, snapshot_ref=token, **changed))
        assert rejected.status_code == 409 and rejected.get_json()["error"]["code"] == "snapshot_stale"
    rejected = client.get(path, query_string=dict(query, sort="sequence", snapshot_ref=token))
    assert rejected.status_code == 422 and rejected.get_json()["error"]["code"] == "invalid_input"


def test_unknown_arranged_batch_has_no_invented_remaining_work_and_unavailable_source_keeps_nulls():
    ref = format(101, "048x")
    unknown = [batch_item(ref, finish=None)]
    source = completion_source({FIRST: unknown, SECOND: unknown}, {FIRST: [], SECOND: []}, unavailable=(SECOND,))
    known = completion_batches(source, normalize_completion_filters(completion_candidate_ref=FIRST, completion_filter="unknown"))
    assert known["source"]["available"] is True and known["page"]["total"] == 1
    item = known["items"][0]
    assert item["completion_state"] == "unknown" and item["schedule_complete"] is False
    assert item["scheduled_operation_count"] == 1 and item["remaining_work"]["operation_count"] == 0
    assert item["remaining_drill"] is None and "schedule_time_invalid" in item["issues"]
    assert known["summary"]["unknown_batch_count"] == 1 and known["summary"]["remaining_work"]["operation_count"] == 0
    absent = completion_batches(source, normalize_completion_filters(completion_candidate_ref=SECOND, completion_filter="unknown"))
    assert absent["source"]["available"] is False and absent["source"]["reason"] is not None
    assert absent["page"]["total"] == 1
    missing = absent["items"][0]
    assert missing["completion_state"] == "unknown" and missing["remaining_drill"] is None
    assert missing["remaining_work"]["operation_count"] is None
    assert missing["unplanned_operation_count"] is missing["deferred_operation_count"] is None
    assert absent["summary"]["remaining_work"]["operation_count"] is None
    assert all(value["value"] is None and value["state"] == "unavailable" for value in missing["remaining_work"]["metrics"].values())
