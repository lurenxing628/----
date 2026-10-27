"""Temporary SQLite fixtures for the workbench identity and metadata contract."""

from __future__ import annotations

import pytest

from core.infrastructure.migration_state import (
    CURRENT_SCHEMA_VERSION,
    current_schema_contract_issues,
    ensure_schema_version,
    get_schema_version,
    is_truly_empty_db,
)
from core.infrastructure.schema_declaration import load_schema_sql
from core.infrastructure.workbench_run_schema import RUN_TABLES
from tests._support.sqlite_snapshot import schema_snapshot as schema_snapshot
from tests._support.sqlite_snapshot import table_rows as table_rows

RESOURCE_CASES = {
    "part": ("Parts", ("part_no",)),
    "op_type": ("OpTypes", ("op_type_id",)),
    "machine": ("Machines", ("machine_id",)),
    "operator": ("Operators", ("operator_id",)),
    "supplier": ("Suppliers", ("supplier_id",)),
    "material": ("Materials", ("material_id",)),
    "calendar": ("WorkCalendar", ("date",)),
    "operator_calendar": ("OperatorCalendar", ("operator_id", "date")),
    "batch": ("Batches", ("batch_id",)),
    "resource_team": ("ResourceTeams", ("team_id",)),
}
METADATA_TABLES = ("WorkbenchEntityRefs", "WorkbenchCommandReceipts")
STAMP = "2020-02-03 04:05:06"
SEED_ROWS = {
    "ResourceTeams": dict(team_id="T1", name="team", status="inactive", remark="team-note"),
    "OpTypes": dict(op_type_id="OT1", name="turning", category="internal", default_hours=2.75, remark="op-note"),
    "Operators": dict(operator_id="O1", name="operator", status="active", remark="operator-note", team_id="T1"),
    "Machines": dict(machine_id="M1", name="lathe", op_type_id="OT1", category="precision", status="maintain",
                     remark="machine-note", team_id="T1"),
    "Suppliers": dict(supplier_id="S1", name="supplier", default_days=3.25,
                      status="inactive", remark="supplier-note"),
    "Parts": dict(part_no="P1", part_name="part", route_raw="unparsed:route", route_parsed="no", remark="part-note"),
    "Materials": dict(material_id="MAT1", name="steel", spec="D25", unit="kg", stock_qty=12.375,
                      status="inactive", remark="material-note"),
    "WorkCalendar": dict(date="2026-09-09", day_type="workday", shift_start="22:30", shift_end="06:30",
                         shift_hours=8.0, efficiency=0.875, allow_normal="no", allow_urgent="yes", remark="night"),
    "OperatorCalendar": dict(operator_id="O1", date="2026-09-09", day_type="workday", shift_start="23:15",
                             shift_end="07:45", shift_hours=8.5, efficiency=0.625, allow_normal="yes",
                             allow_urgent="no", remark="operator-night"),
    "Batches": dict(batch_id="B1", part_no="P1", part_name="historical-name", quantity=17,
                    due_date="2026-10-01", priority="urgent", ready_status="no", ready_date="2026-09-15",
                    status="pending", remark="batch-note"),
}
RELATION_ROWS = {
    "OperatorMachine": dict(id=11, operator_id="O1", machine_id="M1", skill_level="expert", is_primary="yes"),
    "OperatorSkill": dict(id=12, operator_id="O1", op_type_id="OT1", skill_level="normal", is_primary="no"),
    "PartOperations": dict(id=21, part_no="P1", seq=1, op_type_id="OT1", op_type_name="original-op",
                           source="external", supplier_id="S1", ext_days=1.25, ext_group_id="EG1",
                           setup_hours=0.5, unit_hours=0.125, status="active"),
    "ExternalGroups": dict(group_id="EG1", part_no="P1", start_seq=1, end_seq=1, merge_mode="separate",
                           total_days=1.25, supplier_id="S1", remark="group-note"),
    "BatchOperations": dict(id=31, op_code="B1:1", batch_id="B1", piece_id="piece:1", seq=1,
                            op_type_id="OT1", op_type_name="original-op", source="internal", machine_id="M1",
                            operator_id="O1", supplier_id="S1", setup_hours=0.75, unit_hours=0.375,
                            ext_days=2.25, status="pending"),
    "Schedule": dict(id=41, op_id=31, machine_id="M1", operator_id="O1", start_time="2026-09-09 22:30:00",
                     end_time="2026-09-10 06:30:00", lock_status="locked", version=7),
    "BatchMaterials": dict(id=51, batch_id="B1", material_id="MAT1", required_qty=20.75,
                           available_qty=4.25, ready_status="no"),
    "MachineDowntimes": dict(id=61, machine_id="M1", scope_type="category", scope_value="precision",
                             start_time="2026-09-12 22:00:00", end_time="2026-09-13 07:00:00",
                             reason_code="maintenance", reason_detail="retained-detail", status="cancelled"),
}


def insert_row(conn, table, payload, *, verb="INSERT"):
    columns = ", ".join('"' + column + '"' for column in payload)
    marks = ", ".join("?" for _ in payload)
    conn.execute(f'{verb} INTO "{table}" ({columns}) VALUES ({marks})', tuple(payload.values()))


def seed_resources(conn, *, relations=False):
    seeds = dict(SEED_ROWS)
    if relations:
        seeds.update(RELATION_ROWS)
    for table, values in seeds.items():
        payload = dict(values)
        columns = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
        payload.update({name: STAMP for name in ("created_at", "updated_at") if name in columns})
        if "periods_json" in columns:
            payload["periods_json"] = None
        assert set(payload) == columns, table
        insert_row(conn, table, payload)
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    conn.commit()


def resource_payload(kind):
    table, columns = RESOURCE_CASES[kind]
    payload = dict(SEED_ROWS[table])
    payload[columns[-1]] = "2030-01-01" if "date" in columns else payload[columns[-1]] + "-test"
    if "name" in payload:
        payload["name"] += "-test"
    return payload


def resource_key(kind, payload):
    values = tuple(payload[column] for column in RESOURCE_CASES[kind][1])
    # Independent oracle; do not call the production encoder to predict its own output.
    return values[0] if len(values) == 1 else ":".join(value.translate({37: "%25", 58: "%3A"}) for value in values)


def where_key(kind, payload):
    columns = RESOURCE_CASES[kind][1]
    return " AND ".join('"' + column + '" = ?' for column in columns), tuple(payload[column] for column in columns)


def business_snapshot(conn):
    names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    return {
        name: (tuple(tuple(row) for row in conn.execute(f'PRAGMA table_info("{name}")')),
               tuple(tuple(row) for row in conn.execute(f'SELECT rowid, * FROM "{name}" ORDER BY rowid')))
        for name in names if name not in METADATA_TABLES + ("SchemaVersion",)
    }


@pytest.fixture(name="identity_conn")
def identity_database(schema_conn):
    assert get_schema_version(schema_conn) == 0 and is_truly_empty_db(schema_conn)
    assert table_rows(schema_conn, "WorkbenchPlanIdentityClock") == [(1, 1)]
    assert table_rows(schema_conn, "WorkbenchExecutionLedgerClock") == [(1, 1, 1)]
    ensure_schema_version(schema_conn, schema_sql=load_schema_sql())
    assert get_schema_version(schema_conn) == CURRENT_SCHEMA_VERSION
    seed_resources(schema_conn)
    assert current_schema_contract_issues(
        schema_conn, schema_version=CURRENT_SCHEMA_VERSION, schema_sql=load_schema_sql()) == []
    assert all(not table_rows(schema_conn, table) for table in RUN_TABLES)
    schema_conn.commit()
    return schema_conn

