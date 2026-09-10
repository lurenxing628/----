"""Real SQLite resource graphs and measured reads; no application startup."""

from contextlib import contextmanager
from time import perf_counter

import pytest

from core.infrastructure.migration_state import ensure_schema_version
from core.models.workbench_resource_query import ResourcePageRequest
from core.services.workbench.resource_queries import WorkbenchResourceQueryService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from tests.workbench.identity_metadata_support import business_snapshot, schema_snapshot, table_rows


@pytest.fixture(name="metrics_conn")
def metrics_database(schema_conn):
    conn = schema_conn
    ensure_schema_version(conn)
    conn.executemany("INSERT INTO OpTypes(op_type_id,name,category,remark) VALUES (?,?,?,?)", [
        (code, "Type " + code, category, "capacity note " + code)
        for code, category in (("A", "internal"), ("B", "internal"), ("C", "internal"),
                               ("X", "external"), ("Y", "external"), ("Z", "external"))])
    conn.executemany("INSERT INTO Machines(machine_id,name,op_type_id,status) VALUES (?,?,?,?)", [
        (code, "Machine " + code, work_type, status)
        for code, work_type, status in (("A1", "A", "active"), ("A2", "A", "active"),
                                       ("AM", "A", "maintain"), ("AI", "A", "inactive"),
                                       ("B1", "B", "active"), ("UNBOUND", None, "active"))])
    conn.executemany("INSERT INTO Operators(operator_id,name,status) VALUES (?,?,?)", [
        (code, "Person " + code, status) for code, status in
        (("LEG", "active"), ("OK", "active"), ("EMPTY", "active"), ("WRONG", "active"),
         ("UNAUTH", "active"), ("OFF", "inactive"), ("LEAVE", "inactive"), ("UNKNOWN", "inactive"))])
    conn.executemany("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)", [
        ("LEG", "A1"), ("LEG", "A2"), ("LEG", "B1"), ("OK", "A1"), ("EMPTY", "A1"),
        ("WRONG", "A1"), ("OFF", "A1"), ("LEAVE", "A1")])
    conn.executemany("INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES (?,?)", [
        ("OK", "A"), ("WRONG", "B"), ("UNAUTH", "A"), ("OFF", "A"), ("LEAVE", "A")])
    conn.executemany("INSERT INTO WorkbenchOperatorProfiles(operator_id,skills_declared,inactive_reason) VALUES (?,?,?)", [
        ("EMPTY", 1, None), ("OFF", 1, "disabled"), ("LEAVE", 1, "leave")])
    conn.executemany("INSERT INTO WorkbenchMachineGroups(group_id,name) VALUES (?,?)", [(code, code) for code in ("G1", "G2", "G0")])
    conn.executemany("INSERT INTO WorkbenchMachineGroupMembers(machine_id,group_id) VALUES (?,?)", [("A1", "G1"), ("A2", "G1"), ("B1", "G2")])
    conn.executemany("INSERT INTO Suppliers(supplier_id,name,op_type_id,status) VALUES (?,?,?,?)", [
        (code, code, work_type, status) for code, work_type, status in
        (("S1", "X", "active"), ("S2", None, "active"), ("S3", None, "inactive"),
         ("S4", "Z", "inactive"), ("S5", "X", "inactive"), ("S6", None, "active"))])
    conn.executemany("INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES (?,?)", [
        ("S1", "X"), ("S1", "Y"), ("S2", "Y"), ("S3", "Y")])
    conn.executemany("INSERT INTO WorkbenchSupplierProfiles(supplier_id,inactive_reason) VALUES (?,?)", [("S3", "pending_review"), ("S4", "disabled")])
    conn.executemany("INSERT INTO WorkbenchOpTypePolicies(op_type_id,default_merge_mode) VALUES (?,?)", [("X", "merged"), ("Y", "separate")])
    conn.commit()
    return conn


def reader(conn, kind="op_type"):
    return WorkbenchResourceQueryService(conn, kind)


def page(conn, kind="op_type", **kwargs):
    service = reader(conn, kind)
    with service.read_snapshot():
        return service.page(ResourcePageRequest(kind, **kwargs))


def detail(conn, code="A", kind="op_type"):
    service = reader(conn, kind)
    identity = WorkbenchIdentityRepository(conn).find_active(kind, code)
    with service.read_snapshot():
        return service.detail(identity.ref)


def stored_state(conn):
    return (schema_snapshot(conn), business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs"),
            table_rows(conn, "WorkbenchCommandReceipts"), conn.total_changes)


@contextmanager
def measured_read(conn):
    result = {"statements": [], "vm_steps": 0}
    conn.set_trace_callback(result["statements"].append)

    def progress():
        result["vm_steps"] += 1000
        return 0

    conn.set_progress_handler(progress, 1000)
    started = perf_counter()
    try:
        yield result
    finally:
        result["seconds"] = perf_counter() - started
        conn.set_trace_callback(None)
        conn.set_progress_handler(None, 0)


def seed_scale(conn, count):
    conn.executemany("INSERT INTO OpTypes(op_type_id,name,category) VALUES (?,?,'internal')", [
        (f"T{i:05d}", f"Scale {i:05d}") for i in range(count)])
    conn.executemany("INSERT INTO Machines(machine_id,name,op_type_id,status) VALUES (?,?,?,?)", [
        (f"M{i:05d}-{j}", "M", f"T{i:05d}", "maintain" if j == 2 else "active")
        for i in range(count) for j in range(3)])
    conn.executemany("INSERT INTO Operators(operator_id,name,status) VALUES (?,?,'active')", [
        (f"O{i:05d}-{j}", "O") for i in range(count) for j in range(3)])
    conn.executemany("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)", [
        (f"O{i:05d}-{j}", f"M{i:05d}-{k}") for i in range(count) for j in range(3) for k in range(2)])
    conn.executemany("INSERT INTO WorkbenchOperatorProfiles(operator_id,skills_declared) VALUES (?,1)", [
        (f"O{i:05d}-1",) for i in range(count)])
    conn.executemany("INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES (?,?)", [
        (f"O{i:05d}-2", f"T{i:05d}") for i in range(count)])
    conn.executemany("INSERT INTO Parts(part_no,part_name) VALUES (?,?)", [(f"P{i:05d}", "P") for i in range(count)])
    conn.executemany("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name) VALUES (?,?,?,?)", [
        (f"P{i:05d}", j, f"T{i:05d}", "Scale") for i in range(count) for j in range(10)])
    conn.commit()
