"""Compare legacy columns exactly while accounting for nullable v34 additions."""

import re

from core.infrastructure.calendar_periods_schema import objects as calendar_objects
from core.infrastructure.machine_capabilities_schema import objects as machine_objects
from core.infrastructure.material_stages_schema import objects as material_objects
from core.infrastructure.migration_state import current_schema_contract_issues
from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_objects
from core.infrastructure.workbench_metadata_schema import canonical_ddl_parts, canonical_sql

OBJECTS = {**calendar_objects(), **machine_objects(), **material_objects()}
TABLES = tuple(name for name, sql in OBJECTS.items() if sql.startswith("CREATE TABLE"))
CALENDARS = {"WorkCalendar", "OperatorCalendar"}


def missing_issues():
    result = {"missing_calendar_periods:" + name for name in calendar_objects()}
    result |= {"missing_machine_capabilities:" + name for name in machine_objects()}
    result |= {"missing_material_stages:" + name for name in material_objects()}
    for table in CALENDARS:
        result |= {"missing_column: " + table + ".periods_json", "missing_calendar_periods:" + table + ".periods_json"}
    return result


def missing_v37_issues():
    return {"invalid_execution_ledger:WorkbenchProductionReports",
            "missing_execution_ledger:idx_wb_execution_reports_legacy",
            "missing_execution_ledger:wb_execution_legacy_link_active_unique"}


def _ddl_signature(row, *, preserve_column_order=True):
    sql = row[3] or ""
    # Preserve physical column/constraint order as well as normalized SQL.
    parts = tuple(canonical_ddl_parts(sql)) if preserve_column_order else ()
    return row[:3], canonical_sql(sql), parts


def _assert_report_ddl_delta(before, after):
    table = "WorkbenchProductionReports"
    old = {row[1]: row for row in before if row[2] == table}
    new = {row[1]: row for row in after if row[2] == table}
    definitions = execution_ledger_objects()
    prior = execution_ledger_objects(legacy_link_unique=True)
    removed = "sqlite_autoindex_WorkbenchProductionReports_3"
    added = definitions.keys() - prior.keys()
    assert table in old, table
    assert removed in old, removed
    assert (_ddl_signature(old[table]), _ddl_signature(new[table])) == (
        _ddl_signature(("table", table, table, prior[table])),
        _ddl_signature(("table", table, table, definitions[table])))
    assert old[removed] == ("index", removed, table, None)
    assert old.keys() - new.keys() == {removed}
    assert new.keys() - old.keys() == added
    for name in added:
        kind = definitions[name].split()[1].lower()
        assert _ddl_signature(new[name]) == _ddl_signature((kind, name, table, definitions[name]))
    for name in (old.keys() & new.keys()) - {table}:
        assert _ddl_signature(new[name]) == _ddl_signature(old[name]), name
    return removed


def assert_migrated_legacy_ddl(conn, before, *, preserve_column_order=True):
    """Prove the declared v37 report delta and every remaining historical object."""
    assert current_schema_contract_issues(conn) == []
    after = [tuple(row) for row in conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")]
    removed = _assert_report_ddl_delta(before, after)
    current = {row[1]: row for row in after}
    assert {row[1] for row in before} - current.keys() == {removed}
    for old in before:
        if old[1] == removed:
            continue
        actual = current[old[1]]
        expected = actual if old[1] == "WorkbenchProductionReports" else old
        if old[1] in CALENDARS and "periods_json" not in (old[3] or ""):
            # Only the declared nullable v34 addition is projected out; objects
            # already present in the historical scope are never discarded.
            actual = legacy_ddl([actual])[0]
        assert (_ddl_signature(actual, preserve_column_order=preserve_column_order)
                == _ddl_signature(expected, preserve_column_order=preserve_column_order)), old[1]


def legacy_ddl(rows):
    result = []
    for kind, name, table, sql in rows:
        if name in OBJECTS or table in TABLES:
            continue
        if kind == "table" and name in CALENDARS:
            sql = re.sub(r",\s*periods_json\s+TEXT\b", "", sql, flags=re.IGNORECASE)
        result.append((kind, name, table, sql))
    return result


def legacy_rows(after, before):
    result = {key: value for key, value in after.items() if key in before and key != "SchemaVersion"}
    for table in CALENDARS & set(result):
        expected_size = len(before[table][0]) if before[table] else None
        values = []
        for row in result[table]:
            if expected_size is not None and len(row) == expected_size + 2:
                half = len(row) // 2
                assert row[half - 1] is None and row[-1] == "null"
                row = row[:half - 1] + row[half:-1]
            values.append(row)
        result[table] = values
    return result


def legacy_business(after, before):
    """Prove old PRAGMA columns and rowids/values survive the nullable addition."""
    result = {key: after[key] for key in before}
    for name in CALENDARS & set(result):
        columns, rows = result[name]
        if len(columns) == len(before[name][0]) + 1:
            assert columns[-1][1:] == ("periods_json", "TEXT", 0, None, 0)
            assert all(row[-1] is None for row in rows)
            result[name] = (columns[:-1], tuple(row[:-1] for row in rows))
    return result
