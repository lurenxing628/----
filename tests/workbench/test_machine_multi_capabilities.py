"""The same machine can process two work types, each with its own qualified people."""

from dataclasses import replace

from core.models.resource_capabilities import machine_types
from core.services.scheduler.config.config_service import ConfigService
from core.services.scheduler.resource_pool_builder import build_resource_pool
from core.services.scheduler.schedule_service import ScheduleService
from core.services.workbench.resource.metrics import WorkbenchResourceMetricsService
from data.repositories import MachineRepository
from tests.workbench.operator_qualification_support import auto_attempt, qualification_database, register_case


def test_auto_assignment_filters_skills_for_each_work_type_on_one_machine(qualification_conn):
    conn = qualification_conn
    register_case(conn, True, 1, ["TURN"])
    conn.execute("UPDATE OpTypes SET category='both' WHERE op_type_id='MILL'")
    conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M1','MILL')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O2','铣工')")
    conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O2','M1')")
    conn.execute("INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES ('O2','MILL')")
    conn.commit()
    machine = MachineRepository(conn).list(op_type_id="MILL")
    assert len(machine) == 1 and machine_types(machine[0]) == ("TURN", "MILL")
    svc = ScheduleService(conn)
    turn = svc.op_repo.get(10)
    mill = replace(turn, op_type_id="MILL", op_type_name="铣削")
    pool, warnings = build_resource_pool(svc, cfg=ConfigService(conn).get_snapshot(), algo_ops=[turn, mill])
    assert not warnings and pool["machines_by_op_type"] == {"TURN": ["M1"], "MILL": ["M1"]}
    assert auto_attempt(conn, pool, op=turn).operator_id == "O1"
    assert auto_attempt(conn, pool, op=mill).operator_id == "O2"
    metrics = WorkbenchResourceMetricsService(conn)
    assert metrics.availability("TURN") == {"machines": 1, "operators": 1, "basis": "enabled_authorized_matching"}
    assert metrics.availability("MILL") == {"machines": 1, "operators": 1, "basis": "enabled_authorized_matching"}
