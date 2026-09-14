"""Additional lifecycle, confirmation, scale and partial-source contracts."""

import csv
import io
import json
import time

from core.models.workbench_master_overview import MasterOverviewScope
from core.services.process.workflow_state import record_confirmation, start_workflow
from core.services.workbench.master_overview import MasterOverviewService
from tests.workbench.master_overview_support import BASE, args, detail, query, ref_for, stored
from tests.workbench.master_overview_support import overview_client as _overview_client


def test_content_confirmed_zero_no_longer_flagged_but_no_health_claim(overview_client):
    client = overview_client
    old = query(client)
    client.conn.execute("BEGIN")
    start_workflow(client.conn, "P000")
    for stage in ("route", "source", "hours"):
        record_confirmation(client.conn, "P000", stage)
    client.conn.commit()
    before = stored(client)
    result = query(client)
    route = detail(client, result, "route", ref_for(client, "part", "P000"), "issues")
    assert route["data"]["page"]["total"] == 0
    assert route["data"]["entity"]["status"] == "checked"
    assert "不代表可以排产" in result["data"]["overview"]["basis"]
    assert stored(client) == before
    assert client.get(BASE + "/export", query_string=args(old)).status_code == 409


def test_missing_explicit_skill_source_is_not_empty_qualification(overview_client):
    client = overview_client
    client.conn.execute("DROP TABLE OperatorSkill")
    client.conn.commit()
    result = query(client)
    operator = detail(client, result, "personnel", ref_for(client, "operator", "O1"), "fields")
    assert operator["data"]["entity"]["relations_complete"] is False
    assert operator["data"]["entity"]["relation_count"] is None
    assert result["data"]["overview"]["stats"]["relations"] is None
    assert any(gap["source"] == "OperatorSkill" for gap in result["data"]["overview"]["gaps"])


def test_calendar_equal_endpoints_mean_24h_and_no_rows_are_invented(overview_client):
    client = overview_client
    client.conn.execute("UPDATE WorkCalendar SET shift_start='08:00',shift_end='08:00',shift_hours=24")
    client.conn.commit()
    result = query(client)
    ref = ref_for(client, "calendar", "2026-09-09")
    issues = detail(client, result, "calendar", ref, "issues")
    assert issues["data"]["page"]["total"] == 0
    assert issues["data"]["entity"]["target"]["context"] == {"source": "production", "kind": "calendar", "month": "2026-09", "date": "2026-09-09"}
    assert client.conn.execute("SELECT COUNT(*) FROM WorkCalendar").fetchone()[0] == 1


def test_detail_cannot_silently_escape_original_filter(overview_client):
    result = query(overview_client, {"view": "entities", "domain": "part", "query": "P064"})
    response = overview_client.get(BASE + "/entities/part/" + ref_for(overview_client, "part", "P000"), query_string=args(result))
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "scope_mismatch"


def test_service_reuse_reads_fresh_facts_and_negative_stock_remains_explicit(overview_client):
    client = overview_client
    reader = MasterOverviewService(client.conn)
    with reader.read_snapshot() as old:
        pass
    client.conn.execute("UPDATE Materials SET stock_qty=-2 WHERE material_id='MAT0'")
    client.conn.commit()
    with reader.read_snapshot() as current:
        entity = reader.resolve("material", ref_for(client, "material", "MAT0"))
        stock = next(field for field in entity["fields"] if field["label"] == "库存数量")
        assert stock["value"] == -2 and stock["state"] == "invalid"
        assert current != old


def test_resource_and_template_navigation_contract(overview_client):
    client = overview_client
    result = query(client, {"view": "entities", "size": 100})
    kinds = {"equipment": "machine", "personnel": "operator", "opType": "op_type", "supplier": "supplier", "part": "part", "route": "part", "material": "material"}
    for row in result["data"]["rows"]:
        if row["domain"] == "calendar":
            continue
        context = row["target"]["context"]
        assert context["source"] == "production" and context["kind"] == kinds[row["domain"]]
        assert context["entity_ref"] == row["ref"]
        assert not {"business_code", "domain", "node", "entity_kind", "catalogkind"} & set(context)
        if row["domain"] == "opType":
            assert context["category"] == ("internal" if row["business_code"] == "IN" else "external")


def test_large_catalog_export_and_late_page_relation_no_n_plus_one(overview_client):
    client = overview_client
    client.conn.executemany("INSERT INTO Machines(machine_id,name,op_type_id) VALUES (?,?,?)", [
        (f"SCALE-{index:05d}", "大型设备" + str(index), "IN") for index in range(2500)])
    client.conn.commit()
    traces = []
    client.conn.set_trace_callback(traces.append)
    started = time.monotonic()
    scope = MasterOverviewScope(view="entities", domain="equipment", sort="business_code", direction="asc")
    reader = MasterOverviewService(client.conn)
    with reader.read_snapshot():
        last = reader.page(scope, 127)
        content, count = reader.csv(scope)
        assert count == 2531 and last["page"]["total"] == 2531
        assert last["rows"][-1]["business_code"] == "SCALE-02499"
        op = reader.resolve("opType", ref_for(client, "op_type", "IN"))
        assert op["relation_count"] == 2533
    rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
    assert len(rows) == 2532
    selects = sum(line.lstrip().upper().startswith("SELECT") for line in traces)
    assert selects < 80, selects
    assert time.monotonic() - started < 15


def test_duplicate_http_parameters_and_export_page_are_rejected(overview_client):
    client = overview_client
    assert client.get(BASE + '?scope={}&scope={}').status_code == 400
    result = query(client)
    assert client.get(BASE + "/export", query_string={**args(result), "page": 2}).status_code == 400
    assert client.get(BASE, query_string={"scope": json.dumps({"view": "entities"}), "page": "01"}).status_code == 400


def test_invalid_calendar_is_visible_but_navigation_is_not_guessed(overview_client):
    client = overview_client
    client.conn.execute("INSERT INTO WorkCalendar(date,day_type,shift_hours,efficiency) VALUES ('invalid-date','workday',8,1)")
    client.conn.commit()
    result = query(client, {"view": "entities", "domain": "calendar"})
    row = next(item for item in result["data"]["rows"] if item["business_code"] == "invalid-date")
    assert "日期填得不对" in row["target"]["unavailable_reason"]
    issues = detail(client, result, "calendar", row["ref"], "issues")
    assert all(item["target"]["unavailable_reason"] for item in issues["data"]["rows"])


def test_duplicate_batch_material_rows_retain_each_diagnostic(overview_client):
    client = overview_client
    client.conn.execute("INSERT INTO BatchMaterials(batch_id,material_id,required_qty,available_qty) VALUES ('B000','MAT0',5,1)")
    client.conn.commit()
    result = query(client, {"view": "issues", "domain": "material", "column_filters": {"evidence": "B000"}})
    rows = result["data"]["rows"]
    assert len(rows) == 2 and len({row["issue_ref"] for row in rows}) == 2
    assert {row["rule"] for row in rows} == {"batch_material.pending"}
    assert all(set(row["target"]["context"]) == {"entity_ref"} for row in rows)
    response = client.get(BASE + "/export", query_string=args(result))
    assert len(list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))) == 3
