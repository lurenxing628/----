"""Calendar default periods and mandatory daily work periods schema contract."""

from .schema_structure import SchemaStructure
from .workbench_metadata_schema import canonical_sql


def objects():
    return {
        "WorkbenchCalendarDefaults": """CREATE TABLE WorkbenchCalendarDefaults (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            state_ref TEXT NOT NULL DEFAULT (lower(hex(randomblob(24)))),
            revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), periods_json TEXT NOT NULL)""",
    }


def contract_issues(structure: SchemaStructure):
    actual = structure.sql
    issues = [("missing_calendar_periods:" if name not in actual else "invalid_calendar_periods:") + name
              for name, sql in objects().items()
              if name not in actual or canonical_sql(sql) != canonical_sql(actual[name])]
    for table in ("WorkCalendar", "OperatorCalendar"):
        columns = {row[1]: row for row in structure.table_info(table)}
        if "periods_json" not in columns:
            issues.append("missing_calendar_periods:" + table + ".periods_json")
        elif not columns["periods_json"][3]:
            issues.append("invalid_calendar_periods:" + table + ".periods_json")
    return issues
