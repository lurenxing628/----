"""Dedicated file-backed SQLite fixture; no production application bootstrap."""

import json
import sqlite3
from pathlib import Path

import pytest
from flask import Blueprint, Flask, g

from web.routes.workbench.master_overview import BASE, register_master_overview_routes

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(name="overview_client")
def overview_client(tmp_path):
    path = tmp_path / "master-overview.sqlite"
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
    seed(conn)
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="overview-isolated-fixture-only")
    bp = Blueprint("workbench", __name__)
    register_master_overview_routes(bp)
    app.register_blueprint(bp)

    @app.before_request
    def connection():
        g.db = conn

    client = app.test_client()
    client.conn, client.db_path = conn, path
    try:
        yield client
    finally:
        conn.close()


def seed(conn):
    conn.executemany("INSERT INTO OpTypes(op_type_id,name,category) VALUES (?,?,?)", [("IN", "车削", "internal"), ("EX", "热处理", "external")])
    conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id,default_days,status) VALUES ('S1','热处理厂','EX',3,'active')")
    conn.execute("INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES ('S1','EX')")
    conn.execute("INSERT INTO WorkbenchOpTypePolicies(op_type_id,default_merge_mode) VALUES ('EX','merged')")
    conn.executemany("INSERT INTO Machines(machine_id,name,op_type_id,status) VALUES (?,?,?,?)", [
        (f"M{index:03d}", "精密车床", "IN", "active") for index in range(31)])
    conn.execute("INSERT INTO Operators(operator_id,name,status) VALUES ('O1','操作员','inactive')")
    conn.execute("INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES ('O1','IN')")
    conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M000')")
    conn.execute("INSERT INTO Materials(material_id,name,spec,unit,stock_qty) VALUES ('MAT0','钢材','D20','kg',0)")
    conn.execute("INSERT INTO Materials(material_id,name,spec,unit,stock_qty) VALUES ('MAT-UNKNOWN','未核实钢材',NULL,'kg',NULL)")
    conn.executemany("INSERT INTO Parts(part_no,part_name,route_raw,route_parsed) VALUES (?,?,?,?)", [
        (f"P{index:03d}", ("超长中文零件名称用于验证换行布局与完整导出" * 8) if index == 0 else "零件" + str(index),
         "10车削20热处理" if index == 0 else None, "yes" if index == 0 else "no") for index in range(65)])
    conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id) VALUES ('G1','P000',20,20,'merged',3,'S1')")
    conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours) VALUES ('P000',10,'IN','车削','internal',0,0)")
    conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_group_id,ext_days) VALUES ('P000',20,'EX','热处理','external','S1','G1',NULL)")
    for index in range(23):
        code = f"B{index:03d}"
        conn.execute("INSERT INTO Batches(batch_id,part_no,part_name,quantity) VALUES (?,'P000','旧批次名称',1)", (code,))
        conn.execute("INSERT INTO BatchMaterials(batch_id,material_id,required_qty,available_qty) VALUES (?,'MAT0',2,0)", (code,))
    conn.execute("INSERT INTO WorkCalendar(date,day_type,shift_hours,efficiency,shift_start,shift_end) VALUES ('2026-09-09','workday',8,1,'22:00','06:00')")
    conn.commit()


def ref_for(client, kind, code):
    return client.conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind=? AND entity_key=? AND active=1", (kind, str(code))).fetchone()[0]


def query(client, scope=None, token=None, page=1):
    args = {"scope": json.dumps(scope or {"view": "entities"}), "page": str(page)}
    if token is not None:
        args["snapshot_ref"] = token
    response = client.get(BASE, query_string=args)
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def args(result):
    return {"scope": json.dumps(result["data"]["scope"]), "snapshot_ref": result["meta"]["snapshot_ref"]}


def detail(client, result, domain, ref, section="fields", page=1):
    response = client.get(BASE + "/entities/" + domain + "/" + ref, query_string={**args(result), "section": section, "detail_page": page})
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def stored(client):
    tables = [row[0] for row in client.conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    return {table: [tuple(row) for row in client.conn.execute('SELECT * FROM "' + table + '" ORDER BY rowid')] for table in tables}
