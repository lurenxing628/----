"""Real selected plan/identity/resource fixtures for backend calendar projections."""

from contextlib import contextmanager
from time import perf_counter

import pytest

from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.plan_calendar import project_plan_calendar
from core.services.workbench.plan_occupancy import project_plan_occupancy
from core.services.workbench.plan_queries import WorkbenchPlanQueryService
from tests.workbench.plan_catalog_support import history, seed_operation
from tests.workbench.plan_read_support import assert_no_private_facts

START, END = "2026-09-09T00:00:00", "2026-09-10T00:00:00"


class CalendarCase:
    def __init__(self, conn):
        self.conn = conn
        self.op_id = seed_operation(conn)
        conn.executemany("INSERT INTO OpTypes(op_type_id,name,category) VALUES (?,?,'internal')",
                         [("INT", "Turning"), ("OTHER", "Grinding")])
        conn.execute("INSERT INTO Machines(machine_id,name,status,op_type_id) VALUES ('PRIVATE-M1','Machine one','active','INT')")
        conn.execute("INSERT INTO Operators(operator_id,name,status) VALUES ('PRIVATE-O1','Person one','active')")
        conn.execute("INSERT INTO OperatorMachine(machine_id,operator_id) VALUES ('PRIVATE-M1','PRIVATE-O1')")
        conn.execute("UPDATE BatchOperations SET op_type_id='INT',source='internal'")
        history(conn, 1, op_id=self.op_id)
        conn.execute("UPDATE Schedule SET start_time='2026-09-09 08:00:00',end_time='2026-09-09 16:00:00',"
                     "machine_id='PRIVATE-M1',operator_id='PRIVATE-O1'")
        conn.commit()

    def execute(self, sql, params=()):
        self.conn.execute(sql, params)
        self.conn.commit()

    def calendar(self, day="2026-09-09", start="08:00", end=None, hours=8, efficiency=1,
                 normal="yes", urgent="yes", operator=None):
        fields = (day, start, end, hours, efficiency, normal, urgent)
        if operator is None:
            self.execute("INSERT OR REPLACE INTO WorkCalendar(date,shift_start,shift_end,shift_hours,efficiency,allow_normal,allow_urgent) "
                         "VALUES (?,?,?,?,?,?,?)", fields)
        else:
            self.execute("INSERT OR REPLACE INTO OperatorCalendar(operator_id,date,shift_start,shift_end,shift_hours,efficiency,"
                         "allow_normal,allow_urgent) VALUES (?,?,?,?,?,?,?,?)", (operator,) + fields)

    def shift(self, days, *, status="active"):
        self.execute("INSERT INTO WorkbenchShiftProfiles(profile_id,name,anchor_date,cycle_days,status) "
                     "VALUES ('PRIVATE-SHIFT','Shift','2026-09-09',?,?)", (len(days), status))
        self.conn.executemany("INSERT INTO WorkbenchShiftPatternDays(profile_id,day_offset,shift_start,shift_end,is_rest) "
                              "VALUES ('PRIVATE-SHIFT',?,?,?,?)", [(offset,) + day for offset, day in enumerate(days)])
        self.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id) VALUES ('PRIVATE-O1','PRIVATE-SHIFT')")

    def downtime(self, start, end, *, status="active", machine="PRIVATE-M1"):
        self.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,status) VALUES (?,?,?,?)",
                     (machine, start, end, status))

    def task(self, start="2026-09-09 10:00:00", end="2026-09-09 12:00:00", *, version=1,
             machine="PRIVATE-M1", operator="PRIVATE-O1", source="internal"):
        seq = self.conn.execute("SELECT MAX(seq)+1 FROM BatchOperations").fetchone()[0]
        op_id = self.conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source) "
                                  "VALUES (?,'CAT-B',?,'INT','Turning',?)", ("OP-" + str(seq), seq, source)).lastrowid
        self.conn.execute("INSERT INTO Schedule(version,op_id,start_time,end_time,machine_id,operator_id) VALUES (?,?,?,?,?,?)",
                          (version, op_id, start, end, machine, operator))
        self.conn.commit()
        return op_id

    @contextmanager
    def selected(self, start=START, end=END, *, version=1, role="adopted", scenario_id=None):
        service = WorkbenchPlanQueryService(self.conn)
        with service.read_snapshot():
            ref = service.references.get_plan_ref(WorkbenchPlanLocator(version, role, scenario_id))
            scope = PlanReadScope(ref, start, end)
            repo, entry, span = service._selected(ref)
            rows = service._task_rows(repo, entry, scope)
            resources, _ = service._resources(rows)
            yield dict(entry=entry, scope=scope, rows=rows, resources=resources, plan_span=span)

    def project(self, *args, **kwargs):
        with self.selected(*args, **kwargs) as selected:
            calendar, calendar_facts = project_plan_calendar(self.conn, **selected)
            occupancy, occupancy_facts = project_plan_occupancy(self.conn, calendar_facts=calendar_facts, **selected)
            assert_no_private_facts(calendar)
            assert_no_private_facts(occupancy)
            return calendar, occupancy, calendar_facts, occupancy_facts


@pytest.fixture(name="calendar_case")
def plan_calendar_case(schema_conn):
    return CalendarCase(schema_conn)


def resource(dto, kind="machine", label=None):
    return next(row for row in dto["resources"] if row["kind"] == kind and (label is None or row["label"] == label))


def codes(items):
    return {item["code"] for item in items}


@contextmanager
def measured(conn):
    result = {"sql": [], "vm_steps": 0}
    conn.set_trace_callback(result["sql"].append)

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
