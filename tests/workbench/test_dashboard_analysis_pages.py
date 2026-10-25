"""Dashboard summaries cover complete facts while every detail stays reachable."""

import pytest

from tests.workbench.dashboard_support import api, source_rows
from tests.workbench.dashboard_support import dashboard_case as dashboard_fixture  # noqa: F401

BASE = "/api/workbench/v1/dashboard"


def add_batch(case, number):
    batch = "DB" + str(number)
    case.conn.execute("INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date,ready_status) "
                      "VALUES (?,'DP1','Part',2,'2026-09-08','no')", (batch,))
    op = case.conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,unit_hours,setup_hours) "
                           "VALUES (?,?,1,'DT1','Turning','internal',0.5,0)", ("OP" + str(number), batch)).lastrowid
    case.conn.execute("INSERT INTO Schedule(version,op_id,machine_id,operator_id,start_time,end_time) "
                      "VALUES (1,?,'DM1','DO1','2026-09-09T08:00:00','2026-09-09T10:00:00')", (op,))


def test_overview_and_pages_preserve_complete_counts_and_stale_source_binding(dashboard_case, monkeypatch):
    from core.services.execution import ledger_reader

    case = dashboard_case
    add_batch(case, 2)
    add_batch(case, 3)
    case.conn.commit()
    before = source_rows(case.conn)
    # Exercise crossing an admitted ledger block without creating a second
    # large fixture for a cardinality boundary already checked by the reader.
    monkeypatch.setattr(ledger_reader, "MAX_OPERATIONS", 2)
    client = api(case, monkeypatch)
    listing = client.get(BASE)
    assert listing.status_code == 200, listing.get_json()
    overview = listing.get_json()["data"]["analysis"]
    assert overview["pagination"]["section"] == "overview"
    assert overview["pagination"]["totals"]["tasks"] == overview["pagination"]["totals"]["execution"] == 3
    assert overview["pending"]["known_count"] == 3
    assert not any(overview[key] for key in ("tasks", "resources", "execution", "deliveries", "overlaps", "downtimes"))
    assert overview["pending"]["items"] == []
    assert "resources" not in listing.get_json()["data"]["resource_pressure"]
    fields = {"delivery": "deliveries", "timeline": "tasks", "actual": "execution", "material": "pending", "pressure": "resources"}
    tokens = {}
    for section, field in fields.items():
        found, snapshot = [], None
        for number in range(1, (2 if section == "pressure" else 3) + 1):
            query = {"section": section, "page": number, "size": 1}
            if snapshot:
                query["snapshot_ref"] = snapshot
            response = client.get(BASE + "/analysis", query_string=query)
            assert response.status_code == 200, response.get_json()
            body = response.get_json()
            if snapshot:
                assert body["meta"]["snapshot_ref"] == snapshot
            snapshot = body["meta"]["snapshot_ref"]
            data = body["data"]
            rows = data["pending"]["items"] if section == "material" else data[field]
            assert len(rows) == 1 and data["pagination"]["number"] == number
            found.extend(rows)
        identities = [row["source"]["task_ref"] if section == "actual" else row[
            "resource_ref" if section == "pressure" else "task_ref" if section == "timeline" else "batch_ref"] for row in found]
        assert len(found) == len(set(identities))
        tokens[section] = snapshot
    assert source_rows(case.conn) == before
    case.conn.execute("UPDATE Batches SET part_name='Changed source' WHERE batch_id='DB3'")
    case.conn.commit()
    stale = client.get(BASE + "/analysis", query_string={"section": "actual", "page": 1, "size": 1,
                                                        "snapshot_ref": tokens["actual"]})
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "snapshot_stale"


def test_resource_day_pages_preserve_half_open_window_and_full_window_metrics(dashboard_case, monkeypatch):
    case = dashboard_case
    case.conn.execute("UPDATE Schedule SET end_time='2026-09-12T00:00:00' WHERE version=1")
    case.conn.commit()
    client = api(case, monkeypatch)
    response = client.get(BASE + "/analysis", query_string={"section": "pressure"})
    assert response.status_code == 200, response.get_json()
    pressure = response.get_json()["data"]
    resource = pressure["resources"][0]
    dates, snapshot = [], None
    for number in range(1, 4):
        query = {"section": "resource_days", "resource_ref": resource["resource_ref"], "page": number, "size": 1}
        if snapshot:
            query["snapshot_ref"] = snapshot
        response = client.get(BASE + "/analysis", query_string=query)
        assert response.status_code == 200, response.get_json()
        body = response.get_json()
        snapshot = body["meta"]["snapshot_ref"]
        detail = body["data"]["resources"][0]
        assert detail["window_metrics"] == resource["window_metrics"]
        assert body["data"]["pagination"]["total"] == body["data"]["pagination"]["totals"]["resource_days"] == 3
        dates.extend(day["date"] for day in detail["days"])
    assert dates == ["2026-09-09", "2026-09-10", "2026-09-11"]
    invalid = client.get(BASE + "/analysis", query_string={"section": "resource_days", "resource_ref": resource["resource_ref"], "page": 4, "size": 1})
    assert invalid.status_code == 400


def test_timeline_batch_locator_resolves_original_page_and_keeps_snapshot_scope(dashboard_case, monkeypatch):
    case = dashboard_case
    add_batch(case, 2)
    add_batch(case, 3)
    case.conn.commit()
    client = api(case, monkeypatch)
    complete = client.get(BASE + "/analysis", query_string={"section": "timeline", "size": 100}).get_json()["data"]
    target = complete["tasks"][-1]
    initial = client.get(BASE + "/analysis", query_string={"section": "timeline", "size": 1}).get_json()
    token = initial["meta"]["snapshot_ref"]
    query = {"section": "timeline", "size": 1, "locate_batch_ref": target["batch_ref"], "snapshot_ref": token}
    located = client.get(BASE + "/analysis", query_string=query)
    assert located.status_code == 200, located.get_json()
    body = located.get_json()
    assert body["meta"]["snapshot_ref"] == token
    data = body["data"]
    assert data["pagination"]["number"] == 3
    assert data["tasks"] == [target]
    assert data["pagination"]["total"] == initial["data"]["pagination"]["total"] == 3
    assert data["pagination"]["totals"] == initial["data"]["pagination"]["totals"]
    for key in ("pending", "pressure", "resource_common", "time_scope", "as_of"):
        assert data[key] == initial["data"][key]
    assert {row["batch_ref"] for row in data["deliveries"]} == {target["batch_ref"]}
    manual = client.get(BASE + "/analysis", query_string={"section": "timeline", "page": 1, "size": 1, "snapshot_ref": token})
    assert manual.status_code == 200, manual.get_json()
    assert manual.get_json()["meta"]["snapshot_ref"] == token
    assert manual.get_json()["data"]["tasks"] == initial["data"]["tasks"]
    assert manual.get_json()["data"]["tasks"][0]["batch_ref"] != target["batch_ref"]
    assert client.get(BASE + "/analysis", query_string={"section": "timeline", "locate_batch_ref": "f" * 48}).status_code == 404
    case.conn.execute("UPDATE Batches SET part_name='Changed locator source' WHERE batch_id=?", (target["batch_id"],))
    case.conn.commit()
    stale = client.get(BASE + "/analysis", query_string=query)
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "snapshot_stale"


@pytest.mark.parametrize("query", [{"page": "0"}, {"size": "101"}, {"section": "all"},
                                  {"section": "resource_days"}, {"resource_ref": "a" * 48},
                                  {"locate_batch_ref": "a" * 48}, {"section": "timeline", "locate_batch_ref": "invalid"}])
def test_analysis_rejects_invalid_page_or_resource_scope(dashboard_case, monkeypatch, query):
    assert api(dashboard_case, monkeypatch).get(BASE + "/analysis", query_string=query).status_code in (400, 404)


def test_material_section_handles_unavailable_batches_source(dashboard_case):
    from core.models.workbench_dashboard import DashboardAnalysisQuery
    from core.services.workbench.dashboard.analysis_projection import project_dashboard_analysis
    from core.services.workbench.dashboard.facts import DashboardFacts
    from core.services.workbench.dashboard.projection import safe_material
    from core.services.workbench.dashboard.service import WorkbenchDashboardService
    from tests.workbench.dashboard_support import NOW

    with WorkbenchDashboardService(dashboard_case.conn).read_snapshot():
        facts = DashboardFacts(dashboard_case.conn, NOW).load(include_candidates=False)
        facts.raw["Batches"] = None
        material = safe_material(facts)
    data = project_dashboard_analysis(facts.project(), material, query=DashboardAnalysisQuery("material"))
    assert data["pending"]["state"] == "unavailable"
    assert data["pending"]["items"] == []
    assert data["pagination"]["total"] == data["pagination"]["totals"]["pending"] == 0
