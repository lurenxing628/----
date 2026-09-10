"""Temporary SQLite graphs and real Flask wiring for read-only relations."""

import sqlite3
from contextlib import contextmanager
from time import perf_counter

import pytest
from flask import Blueprint

from core.services.workbench.resource_relations import ResourceRelationRequest, WorkbenchResourceRelationService
from tests.workbench.identity_metadata_support import business_snapshot, schema_snapshot, table_rows
from web.routes.workbench.resource_relations import register_resource_relation_routes

BASE = "/api/workbench/v1/entities/"


def seed_relations(conn):
    conn.executemany("INSERT INTO OpTypes(op_type_id,name,category) VALUES (?,?,?)", [
        (code, "Type " + code, category) for code, category in
        (("A", "internal"), ("B", "internal"), ("C", "internal"), ("X", "external"), ("Y", "external"), ("Z", "external"))])
    conn.executemany("INSERT INTO Machines(machine_id,name,op_type_id,status,remark) VALUES (?,?,?,?,?)", [
        (code, "Machine " + code, work_type, status, "retained " + code) for code, work_type, status in
        (("A1", "A", "active"), ("A2", "A", "maintain"), ("A3", "A", "inactive"),
         ("A4", "A", " Legacy Hold "), ("B1", "B", "active"), ("FREE", None, "active"))])
    conn.executemany("INSERT INTO Operators(operator_id,name,status) VALUES (?,?,?)", [
        (code, "Person " + code, status) for code, status in
        (("LEG", "active"), ("ZERO", "active"), ("OK", "active"), ("EMPTY", "active"),
         ("WRONG", "active"), ("UNAUTH", "active"), ("OFF", "inactive"), ("LEAVE", "inactive"),
         ("UNKNOWN", "inactive"), ("MAINT", "active"), ("NOT_RELATED", "active"))])
    conn.executemany("INSERT INTO OperatorMachine(operator_id,machine_id,skill_level,is_primary) VALUES (?,?,?,?)", [
        (oid, mid, "expert", "yes") for oid, mid in
        (("LEG", "A1"), ("LEG", "A2"), ("LEG", "B1"), ("ZERO", "A1"), ("OK", "A1"),
         ("EMPTY", "A1"), ("WRONG", "A1"), ("OFF", "A1"), ("LEAVE", "A1"), ("MAINT", "A2"))])
    conn.executemany("INSERT INTO OperatorSkill(operator_id,op_type_id,skill_level,is_primary) VALUES (?,?,?,?)", [
        (oid, work_type, "beginner", "no") for oid, work_type in
        (("OK", "A"), ("WRONG", "B"), ("UNAUTH", "A"), ("OFF", "A"), ("LEAVE", "A"), ("UNKNOWN", "A"))])
    conn.executemany("INSERT INTO WorkbenchOperatorProfiles(operator_id,skills_declared,inactive_reason) VALUES (?,?,?)", [
        ("ZERO", 0, None), ("EMPTY", 1, None), ("OFF", 1, "disabled"), ("LEAVE", 1, "leave"), ("NOT_RELATED", 1, None)])
    conn.executemany("INSERT INTO Suppliers(supplier_id,name,op_type_id,status,default_days) VALUES (?,?,?,?,?)", [
        (code, "Supplier " + code, work_type, status, 2.75) for code, work_type, status in
        (("S1", "X", "active"), ("S2", None, "active"), ("S3", "X", "inactive"),
         ("S4", "X", "inactive"), ("S5", "X", "inactive"), ("S6", "Y", "active"))])
    conn.executemany("INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES (?,?)", [
        ("S1", "X"), ("S1", "Y"), ("S2", "X"), ("S4", "X")])
    conn.executemany("INSERT INTO WorkbenchSupplierProfiles(supplier_id,inactive_reason) VALUES (?,?)", [
        ("S4", "disabled"), ("S5", "pending_review")])
    conn.commit()


@pytest.fixture(name="relation_conn")
def relation_database(schema_conn):
    seed_relations(schema_conn)
    return schema_conn


@pytest.fixture(name="relation_client")
def relation_application(app_client):
    app = app_client.application
    rule = "/api/workbench/v1/entities/<kind>/<ref>/relations"
    if not any(item.rule == rule for item in app.url_map.iter_rules()):
        bp = Blueprint("relation_test_registration", __name__)
        register_resource_relation_routes(bp)
        app.register_blueprint(bp)
    with sqlite3.connect(app.config["DATABASE_PATH"]) as conn:
        seed_relations(conn)
    return app_client


def ref_for(conn, kind="op_type", code="A"):
    return conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind=? AND entity_key=? AND active=1", (kind, code)).fetchone()[0]


def read_page(conn, relation="machines", code="A", **kwargs):
    service = WorkbenchResourceRelationService(conn)
    with service.read_snapshot("op_type", ref_for(conn, code=code), ResourceRelationRequest(relation, **kwargs)) as result:
        return result


def url_for_relation(client, code="A", kind="op_type"):
    with sqlite3.connect(client.application.config["DATABASE_PATH"]) as conn:
        ref = ref_for(conn, kind, code)
    return BASE + kind + "/" + ref + "/relations"


def get_page(client, code="A", relation="machines", **kwargs):
    response = client.get(url_for_relation(client, code), query_string={"relation": relation, **kwargs})
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def stored_state(conn):
    return (schema_snapshot(conn), business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs"),
            table_rows(conn, "WorkbenchCommandReceipts"), table_rows(conn, "SchemaVersion"), conn.total_changes)


@contextmanager
def measured_read(conn):
    result = {"statements": [], "vm_steps": 0}
    conn.set_trace_callback(result["statements"].append)

    def progress():
        result["vm_steps"] += 1000
        return 0

    conn.set_progress_handler(progress, 1000)
    start = perf_counter()
    try:
        yield result
    finally:
        result["seconds"] = perf_counter() - start
        conn.set_trace_callback(None)
        conn.set_progress_handler(None, 0)


def seed_scale(conn, start, count):
    indexes = range(start, start + count)
    conn.executemany("INSERT INTO Machines(machine_id,name,op_type_id) VALUES (?,?,'A')", [
        (f"M{i:05d}", f"Machine {i:05d}") for i in indexes])
    conn.executemany("INSERT INTO Operators(operator_id,name) VALUES (?,?)", [
        (f"O{i:05d}", f"Operator {i:05d}") for i in indexes])
    conn.executemany("INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES (?,'A')", [(f"O{i:05d}",) for i in indexes])
    conn.executemany("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)", [
        (f"O{i:05d}", f"M{i:05d}") for i in indexes])
    conn.executemany("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES (?,?,'X')", [
        (f"V{i:05d}", f"Supplier {i:05d}") for i in indexes])
    conn.executemany("INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES (?,'X')", [(f"V{i:05d}",) for i in indexes])
    conn.commit()
