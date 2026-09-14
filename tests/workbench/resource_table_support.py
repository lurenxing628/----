"""Temporary tables with independent display oracles and native Flask registration."""

import sqlite3
from dataclasses import replace

import pytest
from flask import Blueprint

from core.models.workbench_material_query import MaterialPageRequest
from core.models.workbench_resource_query import ResourcePageRequest
from core.services.workbench.material_queries import WorkbenchMaterialQueryService
from core.services.workbench.resource_queries import WorkbenchResourceQueryService
from tests.workbench.resource_relations_support import measured_read, seed_relations, stored_state
from web.routes.workbench.resource_table_queries import register_resource_table_routes

BASE = "/api/workbench/v1/entities/"
VIEWS = [("material", None), ("op_type", "internal"), ("op_type", "external"),
         ("machine", None), ("operator", None), ("supplier", None)]
COLUMNS = {
    ("material", None): ["business_code", "label", "spec", "stock_qty", "status"],
    ("op_type", "internal"): ["business_code", "label", "available_machines", "available_operators", "remark"],
    ("op_type", "external"): ["business_code", "label", "default_merge_mode", "remark"],
    ("machine", None): ["business_code", "label", "op_type_ref", "group_ref", "status"],
    ("operator", None): ["business_code", "label", "skill_refs", "shift_profile_ref", "status"],
    ("supplier", None): ["business_code", "label", "op_type_refs", "default_days", "status"],
}


def seed_tables(conn):
    seed_relations(conn)
    conn.executemany("INSERT INTO Materials(material_id,name,spec,stock_qty,unit,status) VALUES (?,?,?,?,?,?)", [
        ("MAT1", "Beta", "Round", 0, "kg", "active"), ("MAT2", "Alpha", None, None, "kg", None),
        ("MAT3", "Alpha", "", 2, "pcs", "inactive"), ("MAT4", "Gamma", "Round", 10, "kg", "active"),
        ("MAT5", " Alpha ", " Round ", 0, "pcs", " Legacy Hold ")])
    conn.execute("UPDATE OpTypes SET remark='capacity note' WHERE op_type_id='A'")
    conn.execute("UPDATE OpTypes SET remark='' WHERE op_type_id='C'")
    conn.executemany("INSERT INTO WorkbenchOpTypePolicies(op_type_id,default_merge_mode) VALUES (?,?)", [("X", "merged"), ("Y", "separate")])
    conn.executemany("INSERT INTO WorkbenchMachineGroups(group_id,name) VALUES (?,?)", [("G1", "Z group"), ("G2", "A group")])
    conn.executemany("INSERT INTO WorkbenchMachineGroupMembers(machine_id,group_id) VALUES (?,?)", [("A1", "G1"), ("A2", "G2"), ("A3", "G1")])
    conn.executemany("INSERT INTO WorkbenchShiftProfiles(profile_id,name,anchor_date,cycle_days) VALUES (?,?,?,?)", [
        ("H1", "Z shift", "2026-09-09", 1), ("H2", "A shift", "2026-09-09", 1)])
    conn.executemany("INSERT INTO WorkbenchShiftPatternDays(profile_id,day_offset,is_rest,shift_start,shift_end) VALUES (?,0,0,'23:15','07:45')", [("H1",), ("H2",)])
    conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id,skills_declared) VALUES ('OK','H1',0)")
    conn.execute("UPDATE WorkbenchOperatorProfiles SET shift_profile_id='H2' WHERE operator_id='ZERO'")
    conn.execute("INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES ('OK','B')")
    conn.commit()


@pytest.fixture(name="table_conn")
def table_database(schema_conn):
    seed_tables(schema_conn)
    return schema_conn


@pytest.fixture(name="table_client")
def table_application(app_client):
    app = app_client.application
    if not any(rule.rule == "/api/workbench/v1/entities/<kind>/facets" for rule in app.url_map.iter_rules()):
        bp = Blueprint("resource_table_test_registration", __name__)
        register_resource_table_routes(bp)
        app.register_blueprint(bp)
    with sqlite3.connect(app.config["DATABASE_PATH"]) as conn:
        seed_tables(conn)
    return app_client


def reader(conn, kind):
    return WorkbenchMaterialQueryService(conn) if kind == "material" else WorkbenchResourceQueryService(conn, kind)


def query_for(kind, category=None, **kwargs):
    return MaterialPageRequest(**kwargs) if kind == "material" else ResourcePageRequest(kind, category=category, **kwargs)


def conditions(column, keys, mode="include"):
    return {column: {"mode": mode, "values": keys}}


def facet_key(service, query, column, label):
    values = service.facets(query, column)["options"]
    return next(row["key"] for row in values if row["label"] == label)


def post(client, kind, operation, body):
    response = client.post(BASE + kind + "/" + operation, json=body)
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def facet_body(category=None, **kwargs):
    return {"scope": {"category": category} if category else {}, **kwargs}


def oracle_cell(entity, column):
    raw = entity["fields"]
    relations = entity.get("relationships", {})
    if column in ("business_code", "label"):
        value = entity[column]
    elif column == "status":
        value = {"active": "启用", "inactive": "停用", "maintain": "停机", "leave": "请假", "pending_review": "待复核"}.get(entity["status"], "旧状态 / 原因未知")
        if entity["status"] == "active":
            value = "可用" if "op_type_ref" in relations else "在岗" if "skill_refs" in relations else value
    elif column in ("stock_qty", "default_days", "available_machines", "available_operators"):
        value = entity["availability"][column.split("_", 1)[1]] if column.startswith("available_") else raw[column]
        return (0, 0) if value is None else (1, value)
    elif column.endswith("_ref") or column.endswith("_refs"):
        field = {"op_type_ref": "op_type", "group_ref": "group", "skill_refs": "skills", "shift_profile_ref": "shift_profile", "op_type_refs": "op_types"}[column]
        rows = relations[field]
        rows = rows if isinstance(rows, list) else [rows] if rows else []
        return 1, tuple(sorted(" ".join(row["label"].split()) for row in rows))
    elif column == "default_merge_mode":
        value = {"merged": "合并设置", "separate": "分别设置"}.get(raw[column], raw[column])
    else:
        value = raw[column]
    return (0, "") if value is None else (1, " ".join(str(value).split()))


def seed_scale(conn, start, count):
    indexes = range(start, start + count)
    conn.executemany("INSERT INTO Materials(material_id,name,spec,stock_qty,unit,status) VALUES (?,?,?,?,'kg','active')", [
        (f"L{i:05d}", "Scale", f"Value {i:05d}", i) for i in indexes])
    conn.executemany("INSERT INTO Machines(machine_id,name,op_type_id) VALUES (?,?,'A')", [(f"Q{i:05d}", "Scale") for i in indexes])
    conn.executemany("INSERT INTO Operators(operator_id,name) VALUES (?,?)", [(f"P{i:05d}", "Scale") for i in indexes])
    conn.executemany("INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES (?,'A')", [(f"P{i:05d}",) for i in indexes])
    conn.executemany("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)", [(f"P{i:05d}", f"Q{i:05d}") for i in indexes])
    conn.executemany("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES (?,?,'X')", [(f"V{i:05d}", "Scale") for i in indexes])
    conn.commit()
