"""The v34 flexible objects (calendar periods, machine capabilities, material stages) and their missing-schema issues."""

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
