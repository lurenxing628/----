"""Strict v22 DDL and lossless snapshots for the backed-up upgrade only."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.infrastructure.migration_state import current_schema_contract_issues, get_schema_version, set_schema_version
from core.infrastructure.workbench_dashboard_external_schema import workbench_dashboard_external_objects
from core.infrastructure.workbench_execution_ledger_schema import LEGACY_COLUMNS, execution_ledger_objects
from core.infrastructure.workbench_lineage_lookup_schema import lineage_lookup_objects
from core.infrastructure.workbench_metadata_schema import _canonical_sql
from core.infrastructure.workbench_outsourcing_schema import workbench_outsourcing_objects
from core.infrastructure.workbench_plan_identity_schema import plan_identity_objects
from core.infrastructure.workbench_plan_identity_write_guard import plan_identity_write_guard_objects
from core.infrastructure.workbench_process_schema import process_objects
from core.infrastructure.workbench_process_workflow_schema import WORKFLOW_TABLES, workflow_objects
from core.infrastructure.workbench_run_schema import RUN_TABLES, workbench_run_objects
from core.infrastructure.workbench_template_lineage_schema import template_lineage_objects
from core.infrastructure.workbench_trial_schema import workbench_trial_objects
from tests.workbench.execution_ledger_migration_support import V27_TABLES
from tests.workbench.identity_metadata_support import insert_row, seed_resources, table_rows
from tests.workbench.legacy_migration_current_support import (
    V30_TABLES,
    V31_TABLES,
    assert_v30_source_maps_only,
    assert_v31_receipt_maps_only,
)
from tests.workbench.schema29_regression_support import V29_TABLES, assert_v29_source_maps_only, missing_v29_issues


def ddl_snapshot(conn):
    return {row[0]: tuple(row[1:]) for row in conn.execute(
        "SELECT name, type, tbl_name, sql FROM sqlite_master ORDER BY name")}


def typed_rows(conn, table, columns=None):
    columns = columns or [row[1] for row in conn.execute('PRAGMA table_info("' + table + '")')]
    quoted = ['"' + column.replace('"', '""') + '"' for column in columns]
    selection = ",".join(quoted + ["typeof(" + column + ")" for column in quoted])
    return sorted((tuple(row) for row in conn.execute('SELECT ' + selection + ' FROM "' + table + '"')), key=repr)


def table_snapshot(conn):
    """Include EVERY old table, its column/FK contract, rowids, values and types."""
    return {name: (
        tuple(tuple(row) for row in conn.execute('PRAGMA table_info("' + name + '")')),
        tuple(tuple(row) for row in conn.execute('PRAGMA foreign_key_list("' + name + '")')),
        typed_rows(conn, name, ["rowid"] + [row[1] for row in conn.execute('PRAGMA table_info("' + name + '")')]),
    ) for name, in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")}


def assert_v22_schema(conn):
    assert get_schema_version(conn) == 22
    actual = ddl_snapshot(conn)
    generations = (
        (workflow_objects(), "missing_workbench_process_workflow: "),
        (plan_identity_objects(), "missing_workbench_plan_identity: "),
        (execution_ledger_objects(), "missing_execution_ledger:"),
        (workbench_run_objects(), "missing_run_schema:"),
        (template_lineage_objects(), "missing_template_lineage:"),
        (workbench_trial_objects(), "missing_trial_schema:"),
        (lineage_lookup_objects(), "missing_lineage_lookup:"),
        (workbench_outsourcing_objects(), "missing_outsourcing_schema:"),
        (plan_identity_write_guard_objects(), "missing_workbench_plan_write_guard: "),
        (workbench_dashboard_external_objects(), "missing_dashboard_external_schema:"),
    )
    expected_issues = missing_v29_issues()
    for objects, prefix in generations:
        assert not set(objects) & actual.keys()
        expected_issues.update(prefix + name for name in objects)
    current = process_objects()
    changed = set()
    for name, sql in process_objects(legacy=True).items():
        assert actual[name][0] == "trigger"
        assert _canonical_sql(actual[name][2]) == _canonical_sql(sql)
        if _canonical_sql(sql) != _canonical_sql(current[name]):
            changed.add(name)
    assert changed == {"wb_ref_template_operation_insert", "wb_ref_template_operation_update"}
    expected_issues.update("bad_workbench_process: " + name for name in changed)
    assert set(current_schema_contract_issues(conn)) == expected_issues


def seed_v22(conn):
    assert not ddl_snapshot(conn)
    source = Path(__file__).parent / "fixtures" / "schema-v24.sql"
    conn.executescript(source.read_text(encoding="utf-8"))
    original = ddl_snapshot(conn)
    # v22.run installs template identities only. v23.run adds workflow and
    # optimizes the exact legacy=True triggers; v24.run adds plan identities.
    removed = dict(workflow_objects(), **plan_identity_objects())
    for name in reversed(removed):
        conn.execute('DROP ' + original[name][0].upper() + ' "' + name + '"')
    for name, sql in process_objects(legacy=True).items():
        conn.execute('DROP TRIGGER "' + name + '"')
        conn.execute(sql)
    actual = ddl_snapshot(conn)
    assert actual.keys() == {name for name, value in original.items() if name not in removed and value[1] not in removed}
    for name, value in actual.items():
        if name not in process_objects():
            assert value == original[name], name
    set_schema_version(conn, 22)
    assert_v22_schema(conn)
    seed_resources(conn, relations=True)
    insert_row(conn, "ScheduleHistory", dict(version=7, strategy="legacy", result_status="success",
                                             result_summary='{"private":"retained"}'))
    insert_row(conn, "PartOperations", dict(id=22, part_no="P1", seq=2, op_type_name="deleted-template",
                                            source="unknown", setup_hours=None, unit_hours=None, status="deleted"))
    insert_row(conn, "PartOperations", dict(id=23, part_no="P1", seq=3, op_type_name="retired-template"))
    conn.execute("DELETE FROM PartOperations WHERE id=23")
    conn.execute("UPDATE Parts SET remark=? WHERE part_no='P1'", (sqlite3.Binary(b"private\x00part\xff"),))
    conn.execute("UPDATE ExternalGroups SET remark=? WHERE group_id='EG1'", (sqlite3.Binary(b"private\x00rule\xff"),))
    insert_row(conn, "WorkbenchCommandReceipts", dict(
        request_key="legacy-request-0001", receipt_ref="a" * 32, action="legacy.process",
        context_ref="legacy-context", input_hash="b" * 64, outcome_json='{"private":"receipt"}'))
    for event_id, event_type, status, stamp in (
        (71, "start", "processing", "2026-09-09 22:30:00"),
        (72, "finish", "completed", "2026-09-10 06:30:00"),
    ):
        insert_row(conn, "OperationExecutionEvents", dict(
            id=event_id, schedule_version=7, schedule_id=41, op_id=31, batch_id="B1",
            source_table="schedule", effective_plan_role="adopted", event_type=event_type,
            reported_status=status, event_time=stamp, actual_machine_id="M1", actual_operator_id="O1",
            quantity_done=None, remark=sqlite3.Binary(b"private\x00event\xff"), created_by="legacy-user",
            idempotency_key="legacy-event-" + str(event_id), request_fingerprint="legacy-fingerprint-" + str(event_id),
            previous_state_revision="31:0:0" if event_id == 71 else "31:1:71", created_at="2020-02-03 04:05:06"))
    conn.commit()
    assert_v22_schema(conn)
    assert {tuple(row) for row in conn.execute("SELECT kind,entity_key,active FROM WorkbenchEntityRefs WHERE kind LIKE 'template_%'")} == {
        ("template_operation", "21", 1), ("template_operation", "22", 1), ("template_operation", "23", 0),
        ("template_external_group", "EG1", 1),
    }
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def assert_old_tables_preserved(conn, before, objects):
    after = table_snapshot(conn)
    for table, state in before.items():
        if table == "SchemaVersion":
            assert after[table][:2] == state[:2]
        else:
            assert after[table] == state, table
    actual, current = ddl_snapshot(conn), process_objects()
    for name, value in objects.items():
        if name in current:
            assert actual[name][:2] == value[:2]
            assert _canonical_sql(actual[name][2]) == _canonical_sql(current[name]), name
        else:
            assert actual[name] == value, name


def assert_new_metadata(conn, old_tables):
    new_tables = set(WORKFLOW_TABLES + RUN_TABLES + V27_TABLES + V29_TABLES + V30_TABLES + V31_TABLES) | {
        "WorkbenchPlanSourceRefs", "WorkbenchTaskRefs", "WorkbenchPlanIdentityClock",
        "WorkbenchExecutionLedgerClock", "WorkbenchExecutionLegacyFacts",
        "WorkbenchProductionReports", "WorkbenchProductionReportRevisions",
    }
    assert table_snapshot(conn).keys() - old_tables.keys() == new_tables
    empty = WORKFLOW_TABLES + RUN_TABLES + V27_TABLES + ("WorkbenchProductionReports", "WorkbenchProductionReportRevisions")
    assert all(table_rows(conn, table) == [] for table in empty)
    assert_v29_source_maps_only(conn)
    assert_v30_source_maps_only(conn)
    assert_v31_receipt_maps_only(conn)
    assert table_rows(conn, "WorkbenchPlanIdentityClock") == [(1, 1)]
    assert table_rows(conn, "WorkbenchExecutionLedgerClock") == [(1, 3, 1)]
    assert typed_rows(conn, "WorkbenchExecutionLegacyFacts", LEGACY_COLUMNS) == typed_rows(conn, "OperationExecutionEvents", LEGACY_COLUMNS)
    refs = {row["kind"]: dict(row) for row in conn.execute("SELECT * FROM WorkbenchPlanSourceRefs")}
    assert len(table_rows(conn, "WorkbenchPlanSourceRefs")) == 3
    assert {kind: (row["source_key"], row["active"]) for kind, row in refs.items()} == {
        "official": ("7", 1), "operation": ("31", 1), "schedule_row": ("41", 1),
    }
    assert refs["official"]["version"] == refs["schedule_row"]["version"] == 7
    assert refs["schedule_row"]["operation_ref"] == refs["operation"]["ref"]
    assert refs["schedule_row"]["operation_id"] == 31
    tasks = table_rows(conn, "WorkbenchTaskRefs")
    assert len(tasks) == 1 and tasks[0][1:] == (refs["official"]["ref"], refs["schedule_row"]["ref"])
    resources = {row[0]: row[1] for row in conn.execute(
        "SELECT kind,ref FROM WorkbenchEntityRefs WHERE kind IN ('machine','operator') AND active=1")}
    expected_binding = (refs["operation"]["ref"], tasks[0][0], refs["official"]["ref"], resources["machine"], resources["operator"])
    bindings = [tuple(row) for row in conn.execute("SELECT operation_ref,recorded_against_task_ref,"
        "recorded_against_plan_ref,actual_machine_ref,actual_operator_ref FROM WorkbenchExecutionLegacyFacts ORDER BY id")]
    assert bindings == [expected_binding, expected_binding]
