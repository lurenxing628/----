"""Isolated templates with untouched batch facts for process read contracts."""

import sqlite3

import pytest

from tests.workbench.identity_metadata_support import business_snapshot, schema_snapshot, table_rows


def seed_process(conn):
    conn.executemany("INSERT INTO OpTypes(op_type_id,name,category) VALUES (?,?,?)", [
        ("PROC-IN", "车削", "internal"), ("PROC-Q", "检验", "internal"), ("PROC-EX", "热处理", "external")])
    conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id,default_days,status) VALUES ('PROC-S','热处理厂','PROC-EX',3.25,'active')")
    conn.execute("INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES ('PROC-S','PROC-EX')")
    conn.executemany("INSERT INTO Parts(part_no,part_name,route_raw,route_parsed,remark) VALUES (?,?,?,?,?)", [
        ("PROC-001", "轴套", "10车削20热处理30检验", "yes", "旧备注必须保留"),
        ("PROC-002", "空路线", None, "no", None), ("PROC-003", "未归类", "10待归类", "yes", None),
        ("PROC-004", "只有历史工序", "10车削", "yes", None), ("PROC-%_", "字面查询", None, "no", None)])
    conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id,remark) VALUES ('PROC-G','PROC-001',20,20,'merged',6.75,'PROC-S','保留合并规则')")
    conn.executemany("""INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days,
        ext_group_id,setup_hours,unit_hours,status) VALUES (?,?,?,?,?,?,?,?,?,?,?)""", [
        ("PROC-001", 10, "PROC-IN", "车削", "internal", None, None, None, .5, .125, "active"),
        ("PROC-001", 20, "PROC-EX", "热处理", "external", "PROC-S", 3.25, "PROC-G", 0, 0, "active"),
        ("PROC-001", 30, "PROC-Q", "检验", "internal", None, None, None, 0, 0, "active"),
        ("PROC-003", 10, None, "待归类", "legacy", None, None, None, None, None, "active"),
        ("PROC-004", 10, "PROC-IN", "车削", "internal", None, None, None, 1.75, .375, "deleted")])
    conn.execute("INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date) VALUES ('PROC-B','PROC-001','旧批次名称',17,'2026-10-01')")
    conn.commit()


def ref_for(conn, kind="part", code="PROC-001"):
    return conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind=? AND entity_key=? AND active=1", (kind, code)).fetchone()[0]


def stored(conn):
    return schema_snapshot(conn), business_snapshot(conn), table_rows(conn, "WorkbenchEntityRefs"), table_rows(conn, "WorkbenchCommandReceipts")


@pytest.fixture(name="process_read_conn")
def process_read_database(schema_conn):
    seed_process(schema_conn)
    return schema_conn


@pytest.fixture(name="process_read_client")
def process_read_application(app_client):
    with sqlite3.connect(app_client.application.config["DATABASE_PATH"]) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        seed_process(conn)
    return app_client
