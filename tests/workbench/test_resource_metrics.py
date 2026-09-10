"""Static live counts, exact qualification reuse, snapshots and scale contracts."""

import sqlite3

import pytest

from core.infrastructure.errors import AppError, ErrorCode
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_query import ResourcePageRequest
from core.services.personnel.operator_qualification import OperatorQualificationError, OperatorQualificationService
from data.repositories.operator_qualification_repo import OperatorQualificationRepository
from tests.workbench.resource_metrics_support import (
    detail,
    measured_read,
    metrics_database,
    page,
    reader,
    seed_scale,
    stored_state,
)


def test_availability_uses_enabled_matching_authorizations_not_references(metrics_conn):
    record = detail(metrics_conn)
    assert record.entity["availability"] == {"machines": 2, "operators": 2, "basis": "enabled_authorized_matching"}
    assert record.entity["relationships"]["counts"]["machines"] == 4
    assert record.entity["relationships"]["counts"]["skills"] == 4
    assert record.entity["fields"]["remark"] == "capacity note A"
    assert detail(metrics_conn, "B").entity["availability"]["operators"] == 1
    assert detail(metrics_conn, "C").entity["availability"] == {"machines": 0, "operators": 0, "basis": "enabled_authorized_matching"}
    assert "availability" not in detail(metrics_conn, "X").entity


def test_qualification_is_shared_and_read_once_per_population(metrics_conn, monkeypatch):
    original = OperatorQualificationService.eligible_links
    calls = []

    def recorded(self, rows, machines, active_operator_ids, operations):
        calls.append((len(rows), len(machines), active_operator_ids, operations))
        return original(self, rows, machines, active_operator_ids, operations)

    monkeypatch.setattr(OperatorQualificationService, "eligible_links", recorded)
    rows, _ = page(metrics_conn, category="internal", size=200)
    assert len(rows) == 3 and len(calls) == 1
    assert calls[0][2] == {"LEG", "OK", "EMPTY", "WRONG", "UNAUTH"}
    assert calls[0][3] == []


def test_filtered_metrics_cover_all_matching_rows_not_the_current_page(metrics_conn):
    first, first_page = page(metrics_conn, category="internal", size=1)
    second, second_page = page(metrics_conn, category="internal", size=1, number=2)
    assert first[0].identity != second[0].identity
    assert first_page["metrics"] == second_page["metrics"]
    assert first_page["total"] == 3
    counts = first_page["metrics"]["counts"]
    assert counts == {"total": 3, "internal": 3, "external": 0, "linked_machines": 5,
                      "available_operators": 2, "without_machines": 1, "available_suppliers": 0,
                      "merged": 0, "separate": 0, "merge_mode_unset": 0}
    _, filtered = page(metrics_conn, query="Type B", category="internal", size=1)
    assert filtered["metrics"]["counts"]["total"] == 1
    assert filtered["metrics"]["counts"]["available_operators"] == 1


@pytest.mark.parametrize("kind,expected", [
    ("machine", {"total": 6, "active": 4, "maintain": 1, "inactive": 1, "unknown": 0, "groups": 2}),
    ("operator", {"total": 8, "active": 5, "leave": 1, "inactive": 1, "unknown": 1, "skills": 5}),
    ("supplier", {"total": 6, "active": 3, "pending_review": 1, "inactive": 1, "unknown": 1}),
])
def test_statistics_keep_real_statuses_and_explicit_relationships(metrics_conn, kind, expected):
    _, result = page(metrics_conn, kind, size=1)
    assert result["metrics"]["counts"] == expected
    if expected["unknown"]:
        assert result["metrics"]["issues"][0]["count"] == expected["unknown"]


def test_supplier_capability_union_is_unique_and_unset_policy_is_not_guessed(metrics_conn):
    _, result = page(metrics_conn, category="external", size=1)
    counts = result["metrics"]["counts"]
    assert counts["available_suppliers"] == 2
    assert (counts["merged"], counts["separate"], counts["merge_mode_unset"]) == (1, 1, 1)
    assert page(metrics_conn, category="external", query="Type X")[1]["metrics"]["counts"]["available_suppliers"] == 1


def test_summary_numeric_contract_and_independent_metrics_method(metrics_conn):
    service = reader(metrics_conn)
    with service.read_snapshot():
        counts = service.summary()
        metrics = service.summary_metrics()
        filtered = service.metrics(ResourcePageRequest("op_type", category="internal"))
    assert all(type(value) is int for value in counts.values())
    assert counts["machine_group"] == 3
    assert metrics["scope"] == "all" and metrics["groups"]["internal_op_type"]["counts"]["available_operators"] == 2
    assert filtered["scope"] == "filtered" and filtered["counts"]["total"] == 3


def test_gets_leave_all_rows_statuses_references_receipts_and_schema_unchanged(metrics_conn):
    before = stored_state(metrics_conn)
    for kind in ("op_type", "machine", "operator", "supplier", "machine_group", "shift_profile"):
        page(metrics_conn, kind)
    service = reader(metrics_conn)
    with service.read_snapshot():
        service.summary()
        service.summary_metrics()
    assert stored_state(metrics_conn) == before


@pytest.mark.parametrize("kind,table,key,code", [("operator", "Operators", "operator_id", "OK"),
                                                ("machine", "Machines", "machine_id", "A1"),
                                                ("supplier", "Suppliers", "supplier_id", "S1")])
@pytest.mark.parametrize("status", [None, " Legacy Hold "])
def test_bad_old_status_is_unknown_with_issue_and_never_normalized(metrics_conn, kind, table, key, code, status):
    metrics_conn.execute(f"UPDATE {table} SET status=? WHERE {key}=?", (status, code))
    metrics_conn.commit()
    before = stored_state(metrics_conn)
    row = detail(metrics_conn, code, kind).entity
    assert row["status"] == "unknown" and row["fields"]["legacy_status"] == status and row["issues"]
    _, result = page(metrics_conn, kind, status="unknown")
    assert result["metrics"]["counts"]["unknown"] >= 1
    assert stored_state(metrics_conn) == before


@pytest.mark.parametrize("kind,statement", [
    ("op_type", "INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('GHOST','A1')"),
    ("op_type", "INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('OK','GHOST')"),
    ("op_type", "INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES ('GHOST','A')"),
    ("op_type", "UPDATE Machines SET op_type_id='GHOST' WHERE machine_id='A1'"),
    ("op_type", "UPDATE Machines SET op_type_id='X' WHERE machine_id='A1'"),
    ("op_type", "UPDATE Suppliers SET op_type_id='A' WHERE supplier_id='S1'"),
    ("op_type", "INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES ('GHOST','X')"),
    ("machine", "UPDATE WorkbenchMachineGroupMembers SET group_id='GHOST' WHERE machine_id='A1'"),
    ("operator", "UPDATE WorkbenchOperatorProfiles SET shift_profile_id='GHOST' WHERE operator_id='EMPTY'"),
])
def test_missing_or_mismatched_relationships_fail_without_repairs(metrics_conn, kind, statement):
    metrics_conn.execute("PRAGMA foreign_keys=OFF")
    metrics_conn.execute(statement)
    metrics_conn.commit()
    before = stored_state(metrics_conn)
    if kind == "op_type":
        _, result = page(metrics_conn, kind)
        issues = result["metrics"]["issues"]
        assert any(issue["code"] == "resource_availability_unavailable" for issue in issues)
        for issue in issues:
            assert not set(issue.get("unavailable_fields", ())) & set(result["metrics"]["counts"])
    else:
        with pytest.raises(WorkbenchCommandRejected):
            page(metrics_conn, kind)
    assert stored_state(metrics_conn) == before


@pytest.mark.parametrize("statement", [
    "UPDATE OperatorSkill SET op_type_id='X' WHERE operator_id='OK'",
    "UPDATE OperatorSkill SET op_type_id='MISSING' WHERE operator_id='OFF'",
    "UPDATE WorkbenchOperatorProfiles SET skills_declared=2 WHERE operator_id='EMPTY'",
    "DROP TABLE OperatorSkill",
])
def test_primary_qualification_rejects_invalid_facts_even_offline_inactive(metrics_conn, statement):
    metrics_conn.execute("PRAGMA foreign_keys=OFF")
    metrics_conn.execute("PRAGMA ignore_check_constraints=ON")
    metrics_conn.execute(statement)
    metrics_conn.commit()
    before = stored_state(metrics_conn)
    if statement.startswith("DROP"):
        with pytest.raises(AppError):
            page(metrics_conn)
    else:
        rows, result = page(metrics_conn, category="internal")
        assert all("availability" not in row.entity for row in rows)
        assert all(any(issue["code"] == "resource_availability_unavailable" for issue in row.entity["issues"]) for row in rows)
        assert "available_operators" not in result["metrics"]["counts"]
    assert stored_state(metrics_conn) == before


@pytest.mark.parametrize("statement", [
    "UPDATE Machines SET status='maintain' WHERE machine_id='A1'",
    "UPDATE Machines SET op_type_id='B' WHERE machine_id='A1'",
    "UPDATE Operators SET status='inactive' WHERE operator_id='OK'",
    "UPDATE OperatorMachine SET machine_id='B1' WHERE operator_id='OK'",
    "UPDATE OperatorSkill SET op_type_id='B' WHERE operator_id='OK'",
    "UPDATE WorkbenchOperatorProfiles SET skills_declared=0 WHERE operator_id='EMPTY'",
    "UPDATE WorkbenchSupplierOpTypes SET op_type_id='Z' WHERE supplier_id='S2'",
    "UPDATE WorkbenchOpTypePolicies SET default_merge_mode='merged' WHERE op_type_id='Y'",
    "UPDATE WorkbenchMachineGroupMembers SET group_id='G0' WHERE machine_id='B1'",
])
def test_fingerprint_covers_same_size_metric_dependencies_not_just_ref_counts(metrics_conn, monkeypatch, statement):
    service = reader(metrics_conn)
    monkeypatch.setattr(service.repo, "scope_state", lambda kind: {})
    before = service.state_fingerprint()
    metrics_conn.execute(statement)
    metrics_conn.commit()
    assert service.state_fingerprint() != before


def test_snapshot_cache_is_request_local_and_page_write_state_matches_domain(metrics_conn):
    service = reader(metrics_conn)
    with service.read_snapshot():
        rows, _ = service.page(ResourcePageRequest("op_type"))
        for row in rows:
            assert row.state == service.domain.snapshot(row.identity)
    metrics_conn.execute("UPDATE Machines SET status='inactive' WHERE machine_id='A1'")
    metrics_conn.commit()
    with service.read_snapshot():
        rows, _ = service.page(ResourcePageRequest("op_type", query="Type A"))
        assert rows[0].entity["availability"] == {"machines": 1, "operators": 1, "basis": "enabled_authorized_matching"}


def test_missing_permanent_reference_fails_without_backfill(metrics_conn):
    metrics_conn.execute("DELETE FROM WorkbenchEntityRefs WHERE kind='op_type' AND entity_key='A'")
    metrics_conn.commit()
    before = stored_state(metrics_conn)
    with pytest.raises(WorkbenchCommandRejected, match="永久引用缺失"):
        page(metrics_conn)
    assert stored_state(metrics_conn) == before


def test_daily_rest_downtime_and_scheduled_load_do_not_change_static_availability(metrics_conn):
    before = detail(metrics_conn).entity["availability"]
    metrics_conn.execute("INSERT INTO WorkCalendar(date,day_type,shift_hours) VALUES ('2026-09-09','restday',0)")
    metrics_conn.execute("INSERT INTO OperatorCalendar(operator_id,date,day_type,shift_hours) VALUES ('LEG','2026-09-09','restday',0)")
    metrics_conn.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time) VALUES ('A1','2026-09-09 00:00','2026-09-10 00:00')")
    metrics_conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('BUSY-P','Busy')")
    metrics_conn.execute("INSERT INTO Batches(batch_id,part_no,quantity,due_date) VALUES ('BUSY-B','BUSY-P',1,'2026-09-10')")
    operation = metrics_conn.execute("""INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,machine_id,operator_id)
        VALUES ('BUSY-O','BUSY-B',10,'A','Type A','A1','LEG')""").lastrowid
    metrics_conn.execute("""INSERT INTO Schedule(op_id,machine_id,operator_id,start_time,end_time)
        VALUES (?,'A1','LEG','2026-09-09 00:00','2026-09-10 00:00')""", (operation,))
    metrics_conn.commit()
    state = stored_state(metrics_conn)
    assert detail(metrics_conn).entity["availability"] == before
    assert stored_state(metrics_conn) == state


def test_empty_population_reports_verified_zero_without_inventing_policies(schema_conn):
    rows, result = page(schema_conn)
    assert rows == [] and result["total"] == 0
    assert all(value == 0 for value in result["metrics"]["counts"].values())
    service = reader(schema_conn)
    with service.read_snapshot():
        summary = service.summary_metrics()
    assert all(group["counts"]["total"] == 0 for group in summary["groups"].values())


def test_summary_and_list_share_one_graph_read_inside_snapshot(metrics_conn):
    service = reader(metrics_conn)
    query = ResourcePageRequest("op_type", category="internal", size=200)
    with measured_read(metrics_conn) as measured:
        with service.read_snapshot():
            _, result = service.page(query)
            assert service.metrics(query) == result["metrics"]
            service.summary_metrics()
            service.summary()
    sql = measured["statements"]
    assert sum("SELECT * FROM OperatorMachine" in statement for statement in sql) == 1
    assert sum("SELECT * FROM OperatorSkill" in statement for statement in sql) == 1
    assert sum("FROM Operators AS o" in statement for statement in sql) == 2  # Active and inactive populations.


@pytest.mark.parametrize("statement,kind,filters", [
    ("UPDATE Suppliers SET op_type_id='A' WHERE supplier_id='S1'", "machine", {}),
    ("UPDATE Suppliers SET op_type_id='A' WHERE supplier_id='S1'", "operator", {}),
    ("UPDATE Suppliers SET op_type_id='A' WHERE supplier_id='S1'", "op_type", {"category": "internal"}),
    ("UPDATE OperatorSkill SET op_type_id='X' WHERE operator_id='OK'", "supplier", {}),
    ("UPDATE OperatorSkill SET op_type_id='X' WHERE operator_id='OK'", "op_type", {"category": "external"}),
    ("UPDATE Machines SET op_type_id='X' WHERE machine_id='A1'", "supplier", {}),
    ("UPDATE Machines SET op_type_id='X' WHERE machine_id='A1'", "operator", {}),
])
def test_unrelated_domain_bad_relations_do_not_block_reads(metrics_conn, statement, kind, filters):
    metrics_conn.execute(statement)
    metrics_conn.commit()
    before = stored_state(metrics_conn)
    with measured_read(metrics_conn) as measured:
        rows, result = page(metrics_conn, kind, **filters)
    assert rows and result["metrics"]["counts"]["total"] > 0
    assert stored_state(metrics_conn) == before
    if kind in ("machine", "operator"):
        assert not any("SELECT * FROM Suppliers" in sql or "SELECT * FROM WorkbenchSupplierOpTypes" in sql for sql in measured["statements"])
    if kind == "supplier":
        assert not any("SELECT * FROM OperatorSkill" in sql or "FROM Operators AS o" in sql for sql in measured["statements"])


def test_invalid_own_binding_stays_visible_for_correction(metrics_conn):
    metrics_conn.execute("UPDATE Suppliers SET op_type_id='A' WHERE supplier_id='S1'")
    metrics_conn.execute("UPDATE Machines SET op_type_id='X' WHERE machine_id='A1'")
    metrics_conn.execute("UPDATE OperatorSkill SET op_type_id='X' WHERE operator_id='OK'")
    metrics_conn.commit()
    for kind, code, issue in (("supplier", "S1", "supplier_capability_invalid"),
                              ("machine", "A1", "machine_work_type_invalid"),
                              ("operator", "OK", "operator_skill_invalid")):
        row = detail(metrics_conn, code, kind).entity
        assert issue in {item["code"] for item in row["issues"]}
    for category, field in (("external", "available_suppliers"), ("internal", "available_operators")):
        rows, result = page(metrics_conn, category=category)
        assert rows and field not in result["metrics"]["counts"]
        assert result["metrics"]["issues"][0]["code"] == "resource_availability_unavailable"


def test_unrelated_bad_capability_does_not_block_real_crud_and_supplier_repair(app_client):
    with sqlite3.connect(app_client.application.config["DATABASE_PATH"]) as conn:
        conn.executemany("INSERT INTO OpTypes(op_type_id,name,category) VALUES (?,?,?)", [("I", "I", "internal"), ("E", "E", "external")])
        conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M','M','I')")
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O','O')")
        conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S','S','I')")
    base = "/api/workbench/v1/entities/"
    for kind in ("machine", "operator"):
        response = app_client.get(base + kind)
        assert response.status_code == 200, response.get_json()
        create = response.get_json()["data"]["create_context"]
        created = app_client.post(base + kind + "/create", json={"request_key": "unrelated-bad-capability-" + kind,
            "write_token": create["write_token"], "input": {"business_code": "NEW", "label": "New"}})
        assert created.status_code == 200 and created.get_json()["result"] == "committed"
    assert app_client.get(base + "op_type?category=internal").status_code == 200
    external_types = app_client.get(base + "op_type?category=external")
    assert external_types.status_code == 200
    external_ref = external_types.get_json()["data"]["entities"][0]["ref"]
    suppliers = app_client.get(base + "supplier")
    assert suppliers.status_code == 200
    entity = suppliers.get_json()["data"]["entities"][0]
    assert any(issue["code"] == "supplier_capability_invalid" for issue in entity["issues"])
    repaired = app_client.post(base + "supplier/" + entity["ref"] + "/update", json={
        "request_key": "repair-supplier-capability", "write_token": entity["write_context"]["write_token"],
        "input": {"relationships": {"op_type_refs": [external_ref]}}})
    assert repaired.status_code == 200 and repaired.get_json()["result"] == "committed"
    assert app_client.get(base + "op_type?category=external").status_code == 200


def test_bad_skill_can_be_selected_and_repaired_through_real_api(app_client):
    with sqlite3.connect(app_client.application.config["DATABASE_PATH"]) as conn:
        conn.executemany("INSERT INTO OpTypes(op_type_id,name,category) VALUES (?,?,?)", [("I", "I", "internal"), ("E", "E", "external")])
        conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M','M','I')")
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O','O')")
        conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O','M')")
        conn.execute("INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES ('O','E')")
    base = "/api/workbench/v1/entities/"
    choices = app_client.get(base + "op_type?category=internal")
    assert choices.status_code == 200
    work_type = choices.get_json()["data"]["entities"][0]
    assert "availability" not in work_type
    assert any(issue["code"] == "resource_availability_unavailable" for issue in work_type["issues"])
    people = app_client.get(base + "operator")
    assert people.status_code == 200
    person = people.get_json()["data"]["entities"][0]
    assert any(issue["code"] == "operator_skill_invalid" for issue in person["issues"])
    repaired = app_client.post(base + "operator/" + person["ref"] + "/update", json={
        "request_key": "repair-operator-skill", "write_token": person["write_context"]["write_token"],
        "input": {"relationships": {"skill_refs": [work_type["ref"]]}}})
    assert repaired.status_code == 200 and repaired.get_json()["result"] == "committed"
    after = app_client.get(base + "op_type?category=internal").get_json()["data"]["entities"][0]
    assert after["availability"] == {"machines": 1, "operators": 1, "basis": "enabled_authorized_matching"}
    assert not any(issue["code"] == "resource_availability_unavailable" for issue in after["issues"])


def test_summary_keeps_other_domains_when_capacity_or_group_facts_are_invalid(metrics_conn):
    metrics_conn.execute("UPDATE Suppliers SET op_type_id='A' WHERE supplier_id='S1'")
    metrics_conn.execute("UPDATE OperatorSkill SET op_type_id='X' WHERE operator_id='OK'")
    metrics_conn.commit()
    service = reader(metrics_conn)
    with service.read_snapshot():
        counts, metrics = service.summary(), service.summary_metrics()
    assert counts["machine"] == 6 and counts["operator"] == 8 and counts["supplier"] == 6
    groups = metrics["groups"]
    assert groups["machine"]["counts"]["active"] == 4
    assert groups["supplier"]["counts"]["active"] == 3
    for key, field in (("internal_op_type", "available_operators"), ("external_op_type", "available_suppliers")):
        assert groups[key]["counts"]["total"] == 3
        assert field not in groups[key]["counts"]
        assert groups[key]["issues"][0]["code"] == "resource_availability_unavailable"
    metrics_conn.execute("PRAGMA foreign_keys=OFF")
    metrics_conn.execute("UPDATE WorkbenchMachineGroupMembers SET group_id='MISSING' WHERE machine_id='A1'")
    metrics_conn.commit()
    with service.read_snapshot():
        groups = service.summary_metrics()["groups"]
    assert groups["machine"]["counts"] == {} and groups["machine"]["issues"]
    assert groups["operator"]["counts"]["active"] == 5


def test_database_errors_wrapped_by_primary_qualification_are_not_hidden(metrics_conn, monkeypatch):
    def fail(self, operator_ids):
        raise AppError(ErrorCode.DB_QUERY_ERROR, "injected database read failure")

    monkeypatch.setattr(OperatorQualificationRepository, "read_skill_facts", fail)
    before = stored_state(metrics_conn)
    with pytest.raises(OperatorQualificationError) as error:
        page(metrics_conn, category="internal")
    assert isinstance(error.value.__cause__, AppError)
    assert error.value.__cause__.code == ErrorCode.DB_QUERY_ERROR
    assert stored_state(metrics_conn) == before


def test_200_row_complex_page_is_batch_read_and_linear_with_population(schema_conn, record_property):
    seed_scale(schema_conn, 240)
    with measured_read(schema_conn) as first:
        rows, result = page(schema_conn, category="internal", size=200)
    assert len(rows) == 200 and result["total"] == 240
    assert result["metrics"]["counts"]["available_operators"] == 480
    for row in rows:
        assert row.entity["availability"] == {"machines": 2, "operators": 2, "basis": "enabled_authorized_matching"}
        assert row.entity["relationships"]["counts"]["part_operations"] == 10
    queries = [sql for sql in first["statements"] if sql.lstrip().upper().startswith("SELECT")]
    assert len(queries) <= 50
    assert sum("FROM PartOperations" in sql for sql in queries) <= 2
    assert not any("FROM OperatorMachine" in sql and "WHERE" in sql for sql in queries)
    record_property("resource_200_rows", {"sql": len(queries), "vm_steps": first["vm_steps"], "seconds": first["seconds"]})
    # Grow the graph tenfold while keeping the page size constant; no per-row graph scans.
    for table in ("PartOperations", "Parts", "OperatorMachine", "OperatorSkill", "WorkbenchOperatorProfiles", "Operators", "Machines", "OpTypes"):
        schema_conn.execute("DELETE FROM " + table)
    schema_conn.commit()
    seed_scale(schema_conn, 2400)
    with measured_read(schema_conn) as large:
        large_rows, large_page = page(schema_conn, category="internal", size=200)
    large_queries = [sql for sql in large["statements"] if sql.lstrip().upper().startswith("SELECT")]
    assert len(large_rows) == 200 and large_page["total"] == 2400
    assert large_page["metrics"]["counts"]["available_operators"] == 4800
    assert large["vm_steps"] < first["vm_steps"] * 15
    assert len(large_queries) <= 85
    record_property("resource_2400_types", {"sql": len(large_queries), "vm_steps": large["vm_steps"], "seconds": large["seconds"]})
