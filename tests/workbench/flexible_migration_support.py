"""Compare legacy columns exactly while accounting for nullable v34 additions."""

import re

from core.infrastructure.calendar_periods_schema import objects as calendar_objects
from core.infrastructure.machine_capabilities_schema import objects as machine_objects
from core.infrastructure.material_stages_schema import objects as material_objects

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
