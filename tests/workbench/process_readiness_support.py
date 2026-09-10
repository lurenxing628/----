"""Isolated catalog fixtures and all-table oracles for process summary reads."""

from datetime import datetime

from core.infrastructure.transaction import TransactionManager
from core.services.process.workflow_state import record_confirmation, start_workflow
from core.services.workbench.resource_queries import WorkbenchResourceQueryService
from tests.workbench.process_workflow_support import seed_workflow


def summary(conn, reader=None):
    reader = reader or WorkbenchResourceQueryService(conn, "op_type")
    with reader.read_snapshot():
        return reader.summary_projection(clock=lambda: datetime(2026, 9, 9, 12))


def process_item(conn):
    return summary(conn)["readiness"]["items"]["process"]


def enroll(conn, part_no="P1", stages=()):
    with TransactionManager(conn).transaction():
        start_workflow(conn, part_no)
        for stage in stages:
            record_confirmation(conn, part_no, stage)


def seed_mixed_catalog(conn):
    seed_workflow(conn)
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('LEGACY-EMPTY','empty')")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('MANAGED-EMPTY','empty')")
    conn.commit()
    enroll(conn, "MANAGED-EMPTY")
    for code, stages in (("ROUTE", ()), ("SOURCE", ("route",)), ("HOURS", ("route", "source")),
                         ("READY", ("route", "source", "hours"))):
        seed_workflow(conn, code, catalog=False)
        enroll(conn, code, stages)


def seed_catalog_scale(conn, count):
    conn.executemany("INSERT INTO Parts(part_no,part_name,route_raw,route_parsed) VALUES (?,?,'turning','yes')",
                     [("SCALE-" + str(index), "part") for index in range(count)])
    conn.executemany("""INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours)
        VALUES (?,1,'TI','turning','internal',0,0)""", [("SCALE-" + str(index),) for index in range(count)])
    conn.commit()
