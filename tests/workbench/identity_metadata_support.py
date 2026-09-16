"""Temporary SQLite fixtures for the v19/v20 identity contract."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

import pytest

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.migration_state import (
    CURRENT_SCHEMA_VERSION,
    current_schema_contract_issues,
    ensure_schema_version,
    get_schema_version,
    is_truly_empty_db,
    set_schema_version,
)
from core.infrastructure.migrations import MIGRATIONS
from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_objects
from core.infrastructure.workbench_lineage_lookup_schema import lineage_lookup_contract_issues, lineage_lookup_objects
from core.infrastructure.workbench_metadata_schema import metadata_objects
from core.infrastructure.workbench_plan_identity_schema import plan_identity_objects
from core.infrastructure.workbench_process_schema import process_objects
from core.infrastructure.workbench_process_workflow_schema import WORKFLOW_TABLES, workflow_objects
from core.infrastructure.workbench_resource_schema import RESOURCE_TABLE_NAMES, resource_objects
from core.infrastructure.workbench_run_schema import RUN_TABLES, workbench_run_contract_issues, workbench_run_objects
from core.infrastructure.workbench_template_lineage_schema import (
    template_lineage_contract_issues,
    template_lineage_objects,
)
from core.infrastructure.workbench_trial_schema import workbench_trial_contract_issues, workbench_trial_objects
from tests._support.sqlite_snapshot import schema_snapshot as schema_snapshot
from tests._support.sqlite_snapshot import table_rows as table_rows
from tests.workbench.execution_ledger_migration_support import V27_TABLES
from tests.workbench.legacy_migration_current_support import missing_v30_issues, missing_v31_issues, missing_v32_issues
from tests.workbench.plan_identity_support import (
    LEDGER_TABLES,
    load_v24_schema,
)
from tests.workbench.plan_identity_support import (
    legacy_schema as remove_plan_identities,
)
from tests.workbench.schema29_regression_support import missing_v29_issues

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
    "Suppliers": dict(supplier_id="S1", name="supplier", op_type_id="OT1", default_days=3.25,
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


def remove_resources_for_v20(conn):
    lookup = lineage_lookup_objects()
    present = schema_snapshot(conn)
    if set(lookup) & present.keys():
        assert lineage_lookup_contract_issues(conn) == []
        for name in lookup:
            conn.execute('DROP INDEX "' + name + '"')
    for objects, contract in ((workbench_trial_objects(), workbench_trial_contract_issues),
                              (template_lineage_objects(), template_lineage_contract_issues)):
        present = schema_snapshot(conn)
        if set(objects) & present.keys():
            assert contract(conn) == []
            assert all(not table_rows(conn, table) for table in V27_TABLES if table in objects)
            for name in reversed(objects):
                conn.execute('DROP ' + present[name][0].upper() + ' "' + name + '"')
    run = workbench_run_objects()
    present = schema_snapshot(conn)
    if set(run) & present.keys():
        assert workbench_run_contract_issues(conn) == []
        assert all(not table_rows(conn, table) for table in RUN_TABLES)
        for name in reversed(run):
            conn.execute('DROP ' + present[name][0].upper() + ' "' + name + '"')
    ledger = execution_ledger_objects()
    present = schema_snapshot(conn)
    if set(ledger) & present.keys():
        assert set(ledger) <= present.keys()
        assert table_rows(conn, "WorkbenchExecutionLedgerClock") == [(1, 1, 1)]
        assert all(not table_rows(conn, table) for table in LEDGER_TABLES[1:])
        for name in reversed(ledger):
            conn.execute('DROP ' + present[name][0].upper() + ' "' + name + '"')
    remove_plan_identities(conn)
    assert all(not table_rows(conn, table) for table in WORKFLOW_TABLES)
    for table in reversed(WORKFLOW_TABLES):
        conn.execute(f'DROP TABLE "{table}"')
    for name in process_objects():
        conn.execute(f'DROP TRIGGER IF EXISTS "{name}"')
    conn.execute("DELETE FROM WorkbenchEntityRefs WHERE kind IN ('template_operation','template_external_group')")
    assert all(not table_rows(conn, table) for table in RESOURCE_TABLE_NAMES)
    before = schema_snapshot(conn)
    names = set(resource_objects())
    assert names <= before.keys()
    for object_type in ("trigger", "index"):
        for name in sorted(names):
            if before[name][0] == object_type:
                conn.execute(f'DROP {object_type.upper()} "{name}"')
    for table in reversed(RESOURCE_TABLE_NAMES):
        conn.execute(f'DROP TABLE "{table}"')
    assert schema_snapshot(conn) == {
        name: value for name, value in before.items() if name not in names and value[1] not in RESOURCE_TABLE_NAMES
    }
    set_schema_version(conn, 20)
    conn.commit()


def remove_metadata_for_v19(conn):
    remove_resources_for_v20(conn)
    before = schema_snapshot(conn)
    names = set(metadata_objects())
    assert names <= before.keys()
    for object_type in ("trigger", "index", "table"):
        for name in sorted(names):
            if before[name][0] == object_type:
                conn.execute(f'DROP {object_type.upper()} "{name}"')
    assert schema_snapshot(conn) == {
        name: value for name, value in before.items() if name not in names and value[1] not in METADATA_TABLES
    }
    set_schema_version(conn, 19)
    conn.commit()
    assert set(current_schema_contract_issues(conn)) == (
        {"missing_workbench_metadata: " + name for name in names}
        | {"missing_workbench_resource: " + name for name in resource_objects()}
        | {"missing_workbench_process: " + name for name in process_objects()}
        | {"missing_workbench_process_workflow: " + name for name in workflow_objects()}
        | {"missing_workbench_plan_identity: " + name for name in plan_identity_objects()}
        | {"missing_execution_ledger:" + name for name in execution_ledger_objects()}
        | {"missing_run_schema:" + name for name in workbench_run_objects()}
        | {"missing_template_lineage:" + name for name in template_lineage_objects()}
        | {"missing_trial_schema:" + name for name in workbench_trial_objects()}
        | {"missing_lineage_lookup:" + name for name in lineage_lookup_objects()}
        | missing_v29_issues() | missing_v30_issues() | missing_v31_issues() | missing_v32_issues())


@pytest.fixture(name="v19_conn")
def legacy_identity_database(mem_conn):
    conn = load_v24_schema(mem_conn)
    remove_metadata_for_v19(conn)
    return conn


@pytest.fixture(name="identity_conn", params=("fresh", "v19"))
def identity_database(request):
    if request.param == "v19":
        schema_conn = load_v24_schema(request.getfixturevalue("mem_conn"))
        remove_metadata_for_v19(schema_conn)
        seed_resources(schema_conn)
        chain = tuple(range(20, CURRENT_SCHEMA_VERSION + 1))
        assert CURRENT_SCHEMA_VERSION == chain[-1]
        for version in chain:
            assert get_schema_version(schema_conn) == version - 1
            assert MIGRATIONS[version](schema_conn) == MigrationOutcome.APPLIED
            if version == CURRENT_SCHEMA_VERSION:
                assert current_schema_contract_issues(schema_conn) == []
            set_schema_version(schema_conn, version)
    else:
        schema_conn = request.getfixturevalue("schema_conn")
        assert get_schema_version(schema_conn) == 0 and is_truly_empty_db(schema_conn)
        assert table_rows(schema_conn, "WorkbenchPlanIdentityClock") == [(1, 1)]
        assert table_rows(schema_conn, "WorkbenchExecutionLedgerClock") == [(1, 1, 1)]
        ensure_schema_version(schema_conn)
        assert get_schema_version(schema_conn) == CURRENT_SCHEMA_VERSION
        seed_resources(schema_conn)
    assert current_schema_contract_issues(schema_conn) == []
    assert all(not table_rows(schema_conn, table) for table in RUN_TABLES + V27_TABLES)
    schema_conn.commit()
    return schema_conn


@contextmanager
def connect_temp(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def copy_to_temp(conn, path):
    assert not conn.in_transaction
    with connect_temp(path) as target:
        conn.backup(target)
