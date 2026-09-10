"""Relation semantics, permanent identities, read snapshots and scale proofs."""

import re
import sqlite3
from datetime import date

import pytest

from core.infrastructure.database import get_connection
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.personnel.operator_qualification import OperatorQualificationService
from core.services.workbench.resource_queries import WorkbenchResourceQueryService
from core.services.workbench.resource_relations import ResourceRelationRequest, WorkbenchResourceRelationService
from data.repositories.workbench_resource_relation_repo import WorkbenchResourceRelationRepository
from tests.workbench.resource_relations_support import (
    BASE,
    get_page,
    measured_read,
    read_page,
    ref_for,
    relation_application,
    relation_database,
    seed_scale,
    stored_state,
    url_for_relation,
)


def test_real_machine_bindings_include_all_statuses_and_not_other_types(relation_conn):
    _, data = read_page(relation_conn)
    assert [row["business_code"] for row in data["entities"]] == ["A1", "A2", "A3", "A4"]
    assert [row["status"] for row in data["entities"]] == ["active", "maintain", "inactive", "unknown"]
    assert data["basis"]["code"] == "machine_op_type_binding"
    assert data["entities"][-1]["fields"]["legacy_status"] == " Legacy Hold "
    assert all(row["fields"]["relation_source"] == "op_type_binding" for row in data["entities"])


def test_people_are_related_facts_not_only_qualification_candidates(relation_conn, monkeypatch):
    original = OperatorQualificationService.load
    calls = []

    def load(self, ids):
        calls.append(ids)
        return original(self, ids)

    monkeypatch.setattr(OperatorQualificationService, "load", load)
    _, data = read_page(relation_conn, "operators")
    people = {row["business_code"]: row for row in data["entities"]}
    assert set(people) == {"LEG", "ZERO", "OK", "EMPTY", "WRONG", "UNAUTH", "OFF", "LEAVE", "UNKNOWN", "MAINT"}
    assert len(calls) == 1 and set(calls[0]) == set(people)
    assert data["basis"]["code"] == "recorded_skills_and_machine_authorizations"
    for code in ("LEG", "ZERO"):
        fields = people[code]["fields"]
        assert fields["qualification_basis"] == "legacy_fallback"
        assert fields["qualification_matches"] and not fields["skills_declared"] and not fields["skill_registered"]
        assert fields["skill_level"] is None
    assert people["LEG"]["fields"]["machine_authorization_count"] == 3
    assert people["LEG"]["fields"]["matching_machine_authorization_count"] == 2
    assert people["LEG"]["fields"]["enabled_matching_machine_authorization_count"] == 1
    assert people["OK"]["fields"]["relation_source"] == "mixed"
    assert people["OK"]["fields"]["skills_declared"] and not people["OK"]["fields"]["explicit_declaration"]
    assert people["OK"]["fields"]["skill_level"] == "beginner"
    assert people["OK"]["fields"]["skill_is_primary"] == "no"
    for code, basis in (("EMPTY", "explicit_empty"), ("WRONG", "explicit_mismatch")):
        assert people[code]["fields"]["qualification_basis"] == basis
        assert not people[code]["fields"]["qualification_matches"]
        assert any(issue["code"] == "operator_skill_not_qualified" for issue in people[code]["issues"])
    assert people["UNAUTH"]["fields"]["relation_source"] == "skill"
    assert people["UNAUTH"]["fields"]["matching_machine_authorization_count"] == 0
    assert any(issue["code"] == "matching_machine_authorization_missing" for issue in people["UNAUTH"]["issues"])
    assert any(issue["code"] == "enabled_matching_machine_missing" for issue in people["MAINT"]["issues"])
    assert [people[code]["status"] for code in ("OFF", "LEAVE", "UNKNOWN")] == ["inactive", "leave", "unknown"]
    assert all(any(issue["code"] == "qualification_scope" for issue in row["issues"]) for row in people.values())


def test_suppliers_union_deduplicates_and_retains_source_and_status(relation_conn):
    _, data = read_page(relation_conn, "suppliers", "X")
    assert data["page"]["total"] == 5
    rows = data["entities"]
    assert [row["business_code"] for row in rows] == ["S1", "S2", "S3", "S4", "S5"]
    assert [row["fields"]["relation_source"] for row in rows] == ["mixed", "explicit", "legacy", "mixed", "legacy"]
    assert [row["status"] for row in rows] == ["active", "active", "unknown", "inactive", "pending_review"]
    assert all(row["fields"]["default_days"] == 2.75 for row in rows)
    assert [row["business_code"] for row in read_page(relation_conn, "suppliers", "Y")[1]["entities"]] == ["S1", "S6"]


@pytest.mark.parametrize("relation,code", [("machines", "C"), ("operators", "C"), ("suppliers", "Z")])
def test_verified_empty_set_has_explicit_scope(relation_conn, relation, code):
    _, data = read_page(relation_conn, relation, code)
    assert data["entities"] == [] and data["basis"]["code"]
    assert data["page"] == {"number": 1, "size": 20, "total": 0, "pages": 1,
                             "sort": [{"field": "business_code", "direction": "asc"}]}


@pytest.mark.parametrize("relation,code,kind", [("machines", "A", "machine"), ("operators", "A", "operator"), ("suppliers", "X", "supplier")])
def test_reduced_dto_uses_persisted_refs_canonical_status_and_no_write_context(relation_conn, relation, code, kind):
    _, data = read_page(relation_conn, relation, code)
    assert data["parent_ref"] == ref_for(relation_conn, code=code) and data["parent_kind"] == "op_type"
    reader = WorkbenchResourceQueryService(relation_conn, kind)
    for entity in data["entities"]:
        assert entity["ref"] == ref_for(relation_conn, kind, entity["business_code"])
        assert re.fullmatch(r"[0-9a-f]{48}", entity["ref"])
        assert entity["write_context"] is None and entity["kind"] == kind
        assert reader.detail(entity["ref"]).entity["status"] == entity["status"]
        assert not set(entity) & {"entity_key", "revision", "id", "write_token", "state"}
        assert not set(entity["fields"]) & {"operator_id", "machine_id", "supplier_id", "op_type_id", "id", "revision"}


def test_queries_filter_and_count_before_paging_without_fallback(relation_conn):
    _, data = read_page(relation_conn, "operators", query="person un", size=1)
    assert data["page"]["total"] == 2 and data["page"]["pages"] == 2
    second = read_page(relation_conn, "operators", query="person un", size=1, number=2)[1]
    assert {data["entities"][0]["business_code"], second["entities"][0]["business_code"]} == {"UNKNOWN", "UNAUTH"}
    assert read_page(relation_conn, "operators", query="absent")[1]["page"]["total"] == 0
    assert read_page(relation_conn, query="%")[1]["page"]["total"] == 0
    with pytest.raises(WorkbenchCommandRejected) as error:
        read_page(relation_conn, number=99)
    assert error.value.code == "snapshot_stale"


@pytest.mark.parametrize("relation,code", [("suppliers", "A"), ("machines", "X"), ("operators", "X")])
def test_wrong_category_is_not_empty_success(relation_client, relation, code):
    result = relation_client.get(url_for_relation(relation_client, code), query_string={"relation": relation})
    assert result.status_code == 400 and result.get_json()["error"]["code"] == "invalid_input"


@pytest.mark.parametrize("params", [[], [("relation", "bogus")], [("relation", "")],
    [("relation", "machines"), ("relation", "operators")], [("relation", "machines"), ("page", "0")],
    [("relation", "machines"), ("page", "1.0")], [("relation", "machines"), ("size", "201")],
    [("relation", "machines"), ("status", "active")], [("relation", "machines"), ("query", "x" * 201)]])
def test_bad_http_parameters_are_explicit_errors(relation_client, params):
    response = relation_client.get(url_for_relation(relation_client), query_string=params)
    assert response.status_code == 400 and response.get_json()["error"]["code"] == "invalid_input"


@pytest.mark.parametrize("ref", ["A", "0" * 47, "0" * 49, "F" * 48, "0" * 48])
def test_parent_requires_real_active_48hex_reference(relation_client, ref):
    response = relation_client.get(BASE + "op_type/" + ref + "/relations?relation=machines")
    assert response.status_code == 404 and response.get_json()["error"]["code"] == "entity_not_found"


def test_wrong_kind_or_cross_kind_ref_rejected(relation_client):
    with sqlite3.connect(relation_client.application.config["DATABASE_PATH"]) as conn:
        ref = ref_for(conn, "machine", "A1")
    for kind in ("op_type", "machine", "unknown"):
        response = relation_client.get(BASE + kind + "/" + ref + "/relations?relation=machines")
        assert response.status_code == 404


def test_real_flask_cross_page_snapshot_and_read_only_response(relation_client):
    first = get_page(relation_client, size=2)
    second = get_page(relation_client, size=2, page=2, snapshot_ref=first["meta"]["snapshot_ref"])
    assert first["schema_version"] == 1 and first["meta"]["source"] == "production"
    assert first["meta"]["as_of"] == second["meta"]["as_of"]
    assert first["data"]["page"]["total"] == second["data"]["page"]["total"] == 4
    refs = [row["ref"] for result in (first, second) for row in result["data"]["entities"]]
    assert len(refs) == len(set(refs)) == 4
    for row in second["data"]["entities"]:
        response = relation_client.get(BASE + row["kind"] + "/" + row["ref"])
        assert response.status_code == 200 and response.get_json()["data"]["label"] == row["label"]
    url = url_for_relation(relation_client)
    assert relation_client.get(url, query_string={"relation": "machines"}).headers["Cache-Control"] == "no-store"
    assert relation_client.post(url, json={}).status_code == 405
    for changes in ({"page": 2}, {"snapshot_ref": ""}, {"page": 3, "snapshot_ref": first["meta"]["snapshot_ref"]},
                    {"query": "A1", "snapshot_ref": first["meta"]["snapshot_ref"]},
                    {"size": 1, "snapshot_ref": first["meta"]["snapshot_ref"]}):
        response = relation_client.get(url, query_string={"relation": "machines", "size": 2, **changes})
        assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"


@pytest.mark.parametrize("relation,code,sql", [
    ("machines", "A", "UPDATE Machines SET op_type_id='B' WHERE machine_id='A4'"),
    ("machines", "A", "UPDATE Machines SET name='Changed' WHERE machine_id='A4'"),
    ("operators", "A", "UPDATE OperatorMachine SET machine_id='A2' WHERE operator_id='OK'"),
    ("operators", "A", "UPDATE OperatorSkill SET op_type_id='B' WHERE operator_id='UNAUTH'"),
    ("operators", "A", "UPDATE WorkbenchOperatorProfiles SET skills_declared=0 WHERE operator_id='EMPTY'"),
    ("operators", "A", "UPDATE OperatorMachine SET skill_level='normal' WHERE operator_id='LEG'"),
    ("operators", "A", "UPDATE Machines SET status='inactive' WHERE machine_id='A1'"),
    ("suppliers", "X", "DELETE FROM WorkbenchSupplierOpTypes WHERE supplier_id='S1' AND op_type_id='X'"),
    ("suppliers", "X", "UPDATE Suppliers SET op_type_id='Y' WHERE supplier_id='S3'"),
    ("suppliers", "X", "UPDATE WorkbenchSupplierProfiles SET inactive_reason='disabled' WHERE supplier_id='S5'"),
])
def test_association_change_invalidates_cross_page_snapshot(relation_client, relation, code, sql):
    first = get_page(relation_client, code, relation, size=1)
    with sqlite3.connect(relation_client.application.config["DATABASE_PATH"]) as conn:
        conn.execute(sql)
    response = relation_client.get(url_for_relation(relation_client, code), query_string={
        "relation": relation, "size": 1, "page": 2, "snapshot_ref": first["meta"]["snapshot_ref"]})
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"


@pytest.mark.parametrize("kind,code,relation,parent", [("machine", "A4", "machines", "A"),
    ("operator", "UNAUTH", "operators", "A"), ("supplier", "S5", "suppliers", "X")])
def test_missing_child_refs_anywhere_in_scope_fail_without_repair(relation_conn, kind, code, relation, parent):
    relation_conn.execute("DELETE FROM WorkbenchEntityRefs WHERE kind=? AND entity_key=?", (kind, code))
    relation_conn.commit()
    before = stored_state(relation_conn)
    with pytest.raises(WorkbenchCommandRejected, match="永久引用缺失"):
        read_page(relation_conn, relation, parent, size=1)
    assert stored_state(relation_conn) == before


@pytest.mark.parametrize("sql", ["DELETE FROM OpTypes WHERE op_type_id='C'", "DELETE FROM WorkbenchEntityRefs WHERE kind='op_type' AND entity_key='C'"])
def test_deleted_or_missing_parent_ref_does_not_retarget(relation_conn, sql):
    old = ref_for(relation_conn, code="C")
    relation_conn.execute(sql)
    if "DELETE FROM OpTypes" in sql:
        relation_conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('C','Type C','internal')")
        assert ref_for(relation_conn, code="C") != old
    relation_conn.commit()
    before = stored_state(relation_conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        with WorkbenchResourceRelationService(relation_conn).read_snapshot("op_type", old, ResourceRelationRequest("machines")):
            pass
    assert error.value.code == "entity_not_found" and stored_state(relation_conn) == before


def test_deleted_recreated_child_invalidates_snapshot_even_same_business_code(relation_client):
    first = get_page(relation_client, size=2)
    url = url_for_relation(relation_client)
    with sqlite3.connect(relation_client.application.config["DATABASE_PATH"]) as conn:
        old = ref_for(conn, "machine", "A4")
        conn.execute("DELETE FROM Machines WHERE machine_id='A4'")
        conn.execute("INSERT INTO Machines(machine_id,name,op_type_id,status) VALUES ('A4','Machine A4','A',' Legacy Hold ')")
        assert ref_for(conn, "machine", "A4") != old
    response = relation_client.get(url, query_string={"relation": "machines", "size": 2, "page": 2, "snapshot_ref": first["meta"]["snapshot_ref"]})
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"
    assert relation_client.get(BASE + "machine/" + old).status_code == 404


@pytest.mark.parametrize("relation,code,sql", [
    ("machines", "A", "UPDATE OpTypes SET category='broken' WHERE op_type_id='A'"),
    ("operators", "A", "INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES ('GHOST','A')"),
    ("operators", "A", "INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('GHOST','A1')"),
    ("operators", "A", "INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('UNAUTH','GHOST')"),
    ("operators", "A", "UPDATE OperatorSkill SET op_type_id='X' WHERE operator_id='OK'"),
    ("operators", "A", "UPDATE OperatorSkill SET op_type_id='GHOST' WHERE operator_id='OFF'"),
    ("operators", "A", "UPDATE WorkbenchOperatorProfiles SET skills_declared=2 WHERE operator_id='EMPTY'"),
    ("operators", "A", "UPDATE Machines SET op_type_id='X' WHERE machine_id='A2'"),
    ("suppliers", "X", "INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES ('GHOST','X')"),
    ("suppliers", "X", "UPDATE Suppliers SET op_type_id='A' WHERE supplier_id='S1'"),
    ("suppliers", "X", "INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES ('S1','A')"),
    ("suppliers", "X", "INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES ('S1','GHOST')"),
])
def test_invalid_related_facts_fail_closed_even_inactive_or_off_page(relation_conn, relation, code, sql):
    relation_conn.execute("PRAGMA foreign_keys=OFF")
    relation_conn.execute("PRAGMA ignore_check_constraints=ON")
    relation_conn.execute(sql)
    relation_conn.commit()
    before = stored_state(relation_conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        read_page(relation_conn, relation, code, size=1)
    assert error.value.code == "storage_failure" and stored_state(relation_conn) == before


def test_reads_are_select_only_and_preserve_all_tables_in_real_flask(relation_client, monkeypatch):
    def no_write_token(*args, **kwargs):
        pytest.fail("Relation GET must not issue write context")

    monkeypatch.setattr("web.routes.workbench.write_context.issue_write_context", no_write_token)
    with sqlite3.connect(relation_client.application.config["DATABASE_PATH"]) as conn:
        before = stored_state(conn)
        for relation, code in (("machines", "A"), ("operators", "A"), ("suppliers", "X")):
            get_page(relation_client, code, relation)
        assert stored_state(conn) == before


def test_sql_read_authorizer_and_single_snapshot_transaction(relation_conn):
    before = stored_state(relation_conn)
    seen = []
    allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_SAVEPOINT}

    def authorize(action, arg1, arg2, database, source):
        seen.append(action)
        if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ):
            assert relation_conn.in_transaction
        return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY

    ref = ref_for(relation_conn)
    relation_conn.set_authorizer(authorize)
    try:
        for relation in ("machines", "operators"):
            with WorkbenchResourceRelationService(relation_conn).read_snapshot("op_type", ref, ResourceRelationRequest(relation)):
                assert relation_conn.in_transaction
    finally:
        relation_conn.set_authorizer(lambda *args: sqlite3.SQLITE_OK)
    assert seen and stored_state(relation_conn) == before


@pytest.mark.parametrize("relation,code,table,key,child", [("machines", "A", "Machines", "machine_id", "A1"),
    ("operators", "A", "Operators", "operator_id", "OK"), ("suppliers", "X", "Suppliers", "supplier_id", "S1")])
@pytest.mark.parametrize("raw_status", [None, " Legacy Hold "])
def test_unknown_status_values_remain_visible_and_unchanged(relation_conn, relation, code, table, key, child, raw_status):
    relation_conn.execute(f"UPDATE {table} SET status=? WHERE {key}=?", (raw_status, child))
    relation_conn.commit()
    before = stored_state(relation_conn)
    _, data = read_page(relation_conn, relation, code)
    entity = next(row for row in data["entities"] if row["business_code"] == child)
    assert entity["status"] == "unknown" and entity["fields"]["legacy_status"] == raw_status
    assert any(issue["code"] == "legacy_status_unknown" for issue in entity["issues"])
    assert stored_state(relation_conn) == before


def test_factory_native_dates_are_preserved_and_not_used_as_relation_availability(relation_client, monkeypatch):
    conn = get_connection(relation_client.application.config["DATABASE_PATH"])
    try:
        conn.execute("INSERT INTO WorkCalendar(date,day_type,shift_hours) VALUES ('2026-09-09','restday',0)")
        conn.execute("INSERT INTO OperatorCalendar(operator_id,date,day_type,shift_start,shift_end,shift_hours,remark) "
                     "VALUES ('OK','2026-09-09','workday','23:15','07:45',8.5,'keep personal exception')")
        conn.commit()
        assert type(conn.execute("SELECT date FROM WorkCalendar").fetchone()[0]) is date
        assert type(conn.execute("SELECT date FROM OperatorCalendar").fetchone()[0]) is date
        before = stored_state(conn)
        original = WorkbenchResourceRelationRepository.rows
        observed = []

        def check_native(self, code, relation):
            observed.append(type(self.conn.execute("SELECT date FROM OperatorCalendar").fetchone()[0]))
            return original(self, code, relation)

        monkeypatch.setattr(WorkbenchResourceRelationRepository, "rows", check_native)
        first = get_page(relation_client, relation="operators", size=2)
        second = get_page(relation_client, relation="operators", size=2, page=2, snapshot_ref=first["meta"]["snapshot_ref"])
        for relation, code in (("machines", "A"), ("suppliers", "X")):
            get_page(relation_client, code, relation)
        assert observed == [date] * 4 and second["data"]["page"]["total"] == 10
        assert stored_state(conn) == before
        conn.execute("UPDATE OperatorCalendar SET day_type='restday',shift_hours=0 WHERE operator_id='OK'")
        conn.commit()
        # Date exceptions do not invent or erase resource relations or static qualification facts.
        unchanged = get_page(relation_client, relation="operators", size=2, page=2, snapshot_ref=first["meta"]["snapshot_ref"])
        assert unchanged["data"] == second["data"]
    finally:
        conn.close()


def test_concurrent_committed_change_is_not_mixed_into_current_read(relation_client, monkeypatch):
    path = relation_client.application.config["DATABASE_PATH"]
    with sqlite3.connect(path) as writer:
        writer.execute("PRAGMA journal_mode=WAL")
    original = WorkbenchResourceRelationRepository.rows

    def change_after_rows(self, code, relation):
        rows = original(self, code, relation)
        with sqlite3.connect(path) as writer:
            writer.execute("UPDATE Machines SET op_type_id='B' WHERE machine_id='A4'")
        return rows

    with monkeypatch.context() as patch:
        patch.setattr(WorkbenchResourceRelationRepository, "rows", change_after_rows)
        first = get_page(relation_client, size=2)
        assert first["data"]["page"]["total"] == 4
    response = relation_client.get(url_for_relation(relation_client), query_string={
        "relation": "machines", "size": 2, "page": 2, "snapshot_ref": first["meta"]["snapshot_ref"]})
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"


@pytest.mark.parametrize("relation,code", [("machines", "A"), ("operators", "A"), ("suppliers", "X")])
def test_two_thousand_related_objects_use_batched_reads_not_per_row_scans(relation_conn, relation, code, record_property):
    seed_scale(relation_conn, 0, 200)
    with measured_read(relation_conn) as small:
        read_page(relation_conn, relation, code, size=200)
    seed_scale(relation_conn, 200, 1800)
    before = stored_state(relation_conn)
    with measured_read(relation_conn) as large:
        _, data = read_page(relation_conn, relation, code, size=200, number=2)
    assert len(data["entities"]) == 200 and data["page"]["total"] >= 2000
    selects = [sql for sql in large["statements"] if sql.lstrip().upper().startswith(("SELECT", "WITH"))]
    assert len(selects) <= 35
    assert large["vm_steps"] < max(small["vm_steps"], 1000) * 15
    assert stored_state(relation_conn) == before
    record_property(relation + "_2000", {"selects": len(selects), "vm_steps": large["vm_steps"], "seconds": large["seconds"]})


@pytest.mark.parametrize("relation,code,query", [("machines", "A", "M0"), ("operators", "A", "O0"), ("suppliers", "X", "V0")])
def test_real_http_two_thousand_objects_have_exact_filtered_pages(relation_client, relation, code, query):
    with sqlite3.connect(relation_client.application.config["DATABASE_PATH"]) as conn:
        seed_scale(conn, 0, 2000)
        before = stored_state(conn)
        first = get_page(relation_client, code, relation, query=query, size=200)
        second = get_page(relation_client, code, relation, query=query, size=200, page=2, snapshot_ref=first["meta"]["snapshot_ref"])
        last = get_page(relation_client, code, relation, query=query, size=200, page=10, snapshot_ref=first["meta"]["snapshot_ref"])
        for result in (first, second, last):
            data = result["data"]
            assert data["page"]["total"] == 2000 and data["page"]["pages"] == 10
            assert len(data["entities"]) == 200
            assert all(set(row) == {"kind", "ref", "business_code", "label", "status", "fields", "issues", "write_context"}
                       and row["write_context"] is None for row in data["entities"])
        assert len({row["ref"] for result in (first, second, last) for row in result["data"]["entities"]}) == 600
        assert stored_state(conn) == before
