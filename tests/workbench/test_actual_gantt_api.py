"""Real ledger + plan read composition and original-snapshot CSV contracts."""

import csv
import io
import json
from datetime import date, datetime

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.actual_gantt import ActualGanttService
from core.services.workbench.actual_gantt_scope import ActualGanttScope, cohort_match, deadlines
from tests.workbench.actual_gantt_support import BASE, actual_api_fixture, prepare, seed_report
from tests.workbench.plan_read_support import add_tasks, assert_no_private_facts


def read(api, **query):
    response = api.client.get(BASE, query_string={"plan_ref": api.ref(), **query})
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    payload = response.get_json()
    assert_no_private_facts(payload)
    return payload


def test_same_snapshot_plan_reports_resource_switch_unknown_and_readonly(actual_api):
    before = actual_api.state()
    response = read(actual_api)
    d, e = response["data"], response["data"]["items"][0]["execution"]
    assert response["meta"]["time_basis"] == "factory_local"
    assert d["availability"]["state"] == "available"
    assert d["task_count"] == 1 and d["report_count"] == 3
    assert e["execution_state"] == "partial"
    assert e["known_completed_quantity"] == 2 and e["remaining_quantity"] is None
    assert e["remaining_plan"] is None and e["confirmed_finish"] is None
    assert [r["completed_quantity"] for r in e["reports"]] == [2, None, 0]
    assert e["reports"][2]["actual_end"] is None
    assert d["axis_span"]["start"] == "2026-09-08T22:00:00"
    assert d["axis_span"]["end"] > response["meta"]["as_of"]
    assert d["plan_span"]["end"] == "2026-09-09T06:00:00"
    assert read(actual_api, snapshot_ref=response["meta"]["snapshot_ref"])["meta"]["as_of"] == response["meta"]["as_of"]
    assert actual_api.state() == before
    assert not any(sql.lstrip().split(" ")[0].upper() in {"INSERT", "UPDATE", "DELETE", "CREATE", "ALTER"} for sql in actual_api.statements)


def test_product_get_connection_date_timestamp_and_capacity(actual_api):
    with actual_api.db() as conn:
        row = conn.execute('SELECT ? AS "day [DATE]", ? AS "at [TIMESTAMP]"',
                           ("2026-09-08", "2026-09-08 22:00:00.123456")).fetchone()
        assert type(row["day"]) is date and type(row["at"]) is datetime
        assert type(conn.execute("SELECT date FROM WorkCalendar").fetchone()[0]) is date
        assert type(conn.execute("SELECT date FROM OperatorCalendar").fetchone()[0]) is date
        assert type(conn.execute("SELECT due_date FROM Batches").fetchone()[0]) is date
    result = read(actual_api)
    calendar = result["data"]["calendar"]
    assert calendar["global"]["state"] == "available" and calendar["global"]["available_hours"] == 8
    assert calendar["global"]["windows"][0]["provenance"] == "work_calendar"
    for row in calendar["resources"]:
        assert row["state"] == "available" and row["available_hours"] == 8
    pinned = dict(plan_ref=actual_api.ref(), snapshot_ref=result["meta"]["snapshot_ref"], format="csv")
    assert actual_api.client.get(BASE + "/export", query_string=pinned).status_code == 200
    with actual_api.db() as conn:
        conn.execute("UPDATE WorkCalendar SET remark=?", (b'changed-private-calendar',))
    response = actual_api.client.get(BASE + "/export", query_string=pinned)
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"


def test_resource_cohort_retains_all_reports_and_original_plan(actual_api):
    result = read(actual_api)
    other = next(r["ref"] for r in result["data"]["resources"] if r["business_code"] == "ACTUAL-M2")
    matched = read(actual_api, resource_type="machine", resource_ref=other)
    assert matched["data"]["report_count"] == 3
    assert matched["data"]["items"][0]["task"] == result["data"]["items"][0]["task"]


def test_plan_finish_date_scope_and_overlap_are_not_actual_date_filters(actual_api):
    assert read(actual_api, plan_finish_date_from="2026-09-09", plan_finish_date_to="2026-09-09")["data"]["report_count"] == 3
    assert read(actual_api, plan_finish_date_from="2026-09-08", plan_finish_date_to="2026-09-08")["data"]["task_count"] == 0
    assert read(actual_api, range_start="2026-09-09T00:00:00", range_end="2026-09-09T01:00:00")["data"]["report_count"] == 3
    assert read(actual_api, range_start="2026-09-09T06:00:00", range_end="2026-09-09T07:00:00")["data"]["task_count"] == 0


def test_csv_all_rows_null_preservation_formula_and_local_view(actual_api):
    result = read(actual_api)
    query = dict(plan_ref=actual_api.ref(), snapshot_ref=result["meta"]["snapshot_ref"], format="csv", local_query="FG-003")
    response = actual_api.client.get(BASE + "/export", query_string=query)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.data.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(io.StringIO(response.data.decode("utf-8-sig"))))
    assert len(rows) == 3 and response.headers["X-Workbench-Operation-Count"] == "1"
    assert rows[1]["本次数量"] == "" and rows[2]["本次数量"] == "0"
    assert rows[2]["本次结束"] == "" and rows[2]["剩余数量"] == ""
    assert rows[0]["备注"].startswith("'=")
    assert all(row["快照引用"] == result["meta"]["snapshot_ref"] for row in rows)
    query["local_query"] = "no-match"
    empty = actual_api.client.get(BASE + "/export", query_string=query)
    assert empty.headers["X-Workbench-Operation-Count"] == "0"


def test_stale_snapshot_never_refreshed_on_export(actual_api):
    result = read(actual_api)
    with actual_api.db() as conn:
        seed_report(conn, result["data"]["items"][0]["task"], "FG-004", quantity=1)
    for suffix in ("", "/export"):
        response = actual_api.client.get(BASE + suffix, query_string=dict(plan_ref=actual_api.ref(), snapshot_ref=result["meta"]["snapshot_ref"], **({"format": "csv"} if suffix else {})))
        assert response.status_code == 409
        assert response.get_json()["error"]["code"] == "snapshot_stale"


def test_missing_schema_explicitly_unavailable_never_installed(tmp_path):
    api = prepare(tmp_path / "missing.db", ledger=False)
    before = api.state()
    result = read(api)
    assert result["data"]["availability"]["state"] == "unavailable"
    assert result["data"]["report_count"] is None and result["data"]["items"][0]["execution"] is None
    response = api.client.get(BASE + "/export", query_string=dict(plan_ref=api.ref(), format="csv", snapshot_ref=result["meta"]["snapshot_ref"]))
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "execution_ledger_unavailable"
    assert before == api.state()


@pytest.mark.parametrize("query", [{"typo": "x"}, {"source": "demo"}, {"plan_finish_date_from": "2026-09-09"},
    {"range_start": "2026-09-09T00:00:00Z", "range_end": "2026-09-10T00:00:00Z"}, {"resource_type": "machine"}, {"batch_ids": "not-json"}])
def test_invalid_scope_is_rejected(actual_api, query):
    response = actual_api.client.get(BASE, query_string={"plan_ref": actual_api.ref(), **query})
    assert response.status_code == 400 and response.get_json()["committed"] is False


def test_10_minute_boundary_and_legacy_completion_are_display_only():
    item = {"task": {"end": "2026-09-09T10:00:00"}, "execution": {"execution_state": "complete", "completion_basis": "legacy_finish_event", "confirmed_finish": "2026-09-09T10:10:00", "remaining_plan": None}}
    assert not deadlines(item, "2026-09-09T11:00:00")["finishLate"]
    item["execution"]["confirmed_finish"] = "2026-09-09T10:10:01"
    assert deadlines(item, "2026-09-09T11:00:00")["finishLate"]
    assert not deadlines(item, "2026-09-09T11:00:00")["unclosed"]


def test_unmatched_selected_ref_and_changed_cohort_rejected(actual_api):
    result = read(actual_api)
    query = dict(plan_ref=actual_api.ref(), snapshot_ref=result["meta"]["snapshot_ref"], format="csv")
    response = actual_api.client.get(BASE + "/export", query_string={**query, "selected_task_ref": "f" * 48})
    assert response.status_code == 400
    response = actual_api.client.get(BASE + "/export", query_string={**query, "batch_ids": json.dumps(["other"])})
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"


def test_cross_version_preserves_comparison_and_recorded_refs(actual_api):
    current = read(actual_api)["data"]["items"][0]
    historical = actual_api.client.get(BASE, query_string={"plan_ref": actual_api.ref(version=1)})
    assert historical.status_code == 200, historical.get_data(as_text=True)
    item = historical.get_json()["data"]["items"][0]
    assert item["task"]["plan_ref"] != current["task"]["plan_ref"]
    assert item["execution"]["comparison_task_ref"] == item["task"]["task_ref"]
    assert item["execution"]["current_task_ref"] == current["task"]["task_ref"]
    assert item["execution"]["reports"] == current["execution"]["reports"]


def test_legacy_finish_stays_complete_unknown_without_synthetic_report(tmp_path):
    api = prepare(tmp_path / "legacy.db", reports=False)
    with api.db() as conn:
        schedule, op = conn.execute("SELECT id,op_id FROM Schedule WHERE version=3").fetchone()
        for index, event, status, time in [(0, "start", "processing", "2026-09-08 22:00:00"), (1, "finish", "completed", "2026-09-09 06:12:00")]:
            previous = conn.execute("SELECT coalesce(max(id),0) FROM OperationExecutionEvents").fetchone()[0]
            conn.execute("INSERT INTO OperationExecutionEvents(schedule_version,schedule_id,op_id,batch_id,source_table,effective_plan_role,event_type,reported_status,event_time,actual_machine_id,actual_operator_id,quantity_done,created_by,idempotency_key,request_fingerprint,previous_state_revision) VALUES (3,?,?,'CAT-B','schedule','adopted',?,?,?,'ACTUAL-M2','PRIVATE-O1',NULL,'fixture',?,'fixture',?)",
                         (schedule, op, event, status, time, "legacy-actual-" + str(index), f"{op}:{index}:{previous}"))
    before = api.state()
    result = read(api)
    e = result["data"]["items"][0]["execution"]
    assert e["execution_state"] == "complete" and e["completion_basis"] == "legacy_finish_event"
    assert e["remaining_quantity"] is None and e["reports"] == []
    assert e["data_quality"] == "legacy_incomplete" and len(e["legacy_facts"]) == 2
    assert deadlines(result["data"]["items"][0], result["meta"]["as_of"])["finishLate"]
    resource = e["legacy_facts"][0]["actual_machine_ref"]
    matched = read(api, resource_type="machine", resource_ref=resource)
    assert matched["data"]["task_count"] == 1 and matched["data"]["report_count"] == 0
    assert before == api.state()


def test_real_10000_operations_are_complete_and_over_limit_rejected(tmp_path):
    api = prepare(tmp_path / "capacity.db", reports=False)
    with api.db() as conn:
        add_tasks(conn, 9999, start="2026-09-08 22:00:00", end="2026-09-09 06:00:00")
    result = read(api)
    assert result["data"]["task_count"] == 10000 and result["data"]["items_complete"]
    assert result["data"]["report_count"] == 0
    assert len({i["execution"]["operation_ref"] for i in result["data"]["items"]}) == 10000
    with api.db() as conn:
        add_tasks(conn, 1)
    response = api.client.get(BASE, query_string={"plan_ref": api.ref()})
    assert response.status_code == 413 and response.get_json()["error"]["code"] == "query_too_large"


def test_read_transaction_does_not_mix_concurrent_ledger_commit(actual_api):
    with actual_api.db() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
    scope = ActualGanttScope(actual_api.ref())
    with actual_api.db() as reader:
        service = ActualGanttService(reader)
        with service.read_snapshot():
            data, state = service.workspace(scope)
            with actual_api.db() as writer:
                seed_report(writer, data["items"][0]["task"], "FG-CONCURRENT", quantity=1)
            assert service.workspace(scope) == (data, state)
        with service.read_snapshot():
            fresh, next_state = service.workspace(scope)
        assert fresh["report_count"] == data["report_count"] + 1 and next_state != state


def test_unresolved_legacy_resource_is_not_silently_excluded(actual_api):
    item = read(actual_api)["data"]["items"][0]
    item["execution"]["data_gaps"].append({"code": "legacy_resource_identity_unresolved", "message": "旧资源身份不明确", "fields": ["actual_machine_ref"]})
    with pytest.raises(WorkbenchCommandRejected, match="不能将可能匹配"):
        cohort_match(item, ActualGanttScope(actual_api.ref(), resource_type="machine", resource_ref="f" * 48))
    assert cohort_match(item, ActualGanttScope(actual_api.ref(), resource_type="machine", resource_ref=item["task"]["machine_ref"]))
