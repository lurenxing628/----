"""A pool build shares qualification facts and retains successfully read empty downtime."""

from datetime import datetime
from types import SimpleNamespace

from core.services.personnel.operator_qualification import OperatorQualificationService
from core.services.scheduler import resource_pool_builder
from core.services.workbench.run.input_runtime import runtime_resource_facts
from core.services.workbench.run.preflight_facts import PreflightFacts
from data.repositories import MachineDowntimeRepository

START = datetime(2026, 10, 14, 8)


def _service(conn):
    return SimpleNamespace(conn=conn, logger=None)


def test_empty_downtime_is_read_once_when_extending_pool(schema_conn, monkeypatch):
    conn = schema_conn
    conn.executemany("INSERT INTO Machines(machine_id, name) VALUES (?, ?)", [("M_A", "A"), ("M_B", "B")])
    conn.execute(
        "INSERT INTO MachineDowntimes(machine_id, start_time, end_time) VALUES ('M_B', ?, ?)",
        ("2026-10-14 09:00:00", "2026-10-14 10:00:00"),
    )
    conn.commit()
    def read(*args):
        raise AssertionError("downtime was already captured for this transaction")

    monkeypatch.setattr(MachineDowntimeRepository, "list_active_after", read)
    svc = _service(conn)
    meta, warnings = {}, []
    sql = []
    conn.set_trace_callback(sql.append)
    facts = PreflightFacts(conn)
    try:
        with facts.snapshot(fingerprint=False):
            resources = runtime_resource_facts(facts)
            assert runtime_resource_facts(facts) is resources
            downtime = resource_pool_builder.load_machine_downtimes(
                svc, algo_ops=[SimpleNamespace(source="internal", machine_id="M_A")],
                start_dt=START, downtimes=resources.downtimes, meta=meta, warnings=warnings,
            )
            assert downtime == {"M_A": []}
            pool = {"operators_by_machine": {"M_A": ["O1"], "M_B": ["O1"]}}
            for _ in range(2):
                assert resource_pool_builder.extend_downtime_map_for_resource_pool(
                    svc, cfg=SimpleNamespace(auto_assign_enabled="yes"), resource_pool=pool,
                    downtime_map=downtime, start_dt=START, downtimes=resources.downtimes,
                    meta=meta, warnings=warnings,
                ) is downtime
    finally:
        conn.set_trace_callback(None)
    assert sum(' FROM "MachineDowntimes" ' in statement for statement in sql) == 1
    assert downtime == {"M_A": [], "M_B": [(datetime(2026, 10, 14, 9), datetime(2026, 10, 14, 10))]}
    assert meta["downtime_load_ok"] is True and meta["downtime_extend_ok"] is True
    assert warnings == []


def _seed_multi_work_type_pool(conn):
    conn.executemany("INSERT INTO OpTypes(op_type_id, name) VALUES (?, ?)", [("OT_A", "A"), ("OT_B", "B")])
    conn.executemany(
        "INSERT INTO Machines(machine_id, name, op_type_id) VALUES (?, ?, 'OT_A')",
        [("M_A", "multi"), ("M_B", "single")],
    )
    conn.execute("INSERT INTO MachineOpTypes(machine_id, op_type_id) VALUES ('M_A', 'OT_B')")
    conn.executemany(
        "INSERT INTO Operators(operator_id, name) VALUES (?, ?)",
        [("O_SKILLED", "skilled"), ("O_LEGACY", "legacy"), ("O_EMPTY", "empty")],
    )
    conn.executemany(
        "INSERT INTO WorkbenchOperatorProfiles(operator_id, skills_declared) VALUES (?, 1)",
        [("O_SKILLED",), ("O_EMPTY",)],
    )
    conn.execute("INSERT INTO OperatorSkill(operator_id, op_type_id) VALUES ('O_SKILLED', 'OT_B')")
    conn.executemany(
        "INSERT INTO OperatorMachine(operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
        [("O_LEGACY", "M_A", "normal", "no"), ("O_SKILLED", "M_A", "expert", "yes"),
         ("O_EMPTY", "M_A", "expert", "yes"), ("O_LEGACY", "M_B", "beginner", "no"),
         ("O_SKILLED", "M_B", "expert", "yes")],
    )
    conn.commit()


def test_multi_work_type_pool_loads_qualifications_once_and_keeps_selection(schema_conn, monkeypatch):
    conn = schema_conn
    _seed_multi_work_type_pool(conn)
    conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('OT_UNUSED','unused','external')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O_UNUSED','unused')")
    conn.execute("INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES ('O_UNUSED','OT_UNUSED')")
    conn.commit()
    loads = []
    original = OperatorQualificationService.project_facts

    def project(operator_ids, profiles, skills):
        loads.append(list(operator_ids))
        return original(operator_ids, profiles, skills)

    monkeypatch.setattr(OperatorQualificationService, "project_facts", staticmethod(project))
    sql = []
    conn.set_trace_callback(sql.append)
    meta = {}
    try:
        facts = PreflightFacts(conn)
        with facts.snapshot(fingerprint=False):
            resources = runtime_resource_facts(facts)
            resources.validate_fixed(conn, [SimpleNamespace(source="internal", op_type_id="OT_B",
                                                           machine_id="M_A", operator_id="O_SKILLED")])
            for _ in range(2):
                pool, warnings = resource_pool_builder.build_resource_pool(
                    _service(conn), cfg=SimpleNamespace(auto_assign_enabled="yes"),
                    algo_ops=[SimpleNamespace(source="internal", op_type_id=code, machine_id=None, operator_id=None)
                              for code in ("OT_A", "OT_B")], meta=meta, resource_facts=resources,
                )
    finally:
        conn.set_trace_callback(None)
    assert loads == [["O_SKILLED"], ["O_EMPTY", "O_LEGACY"]]
    for table in ("Operators", "OperatorMachine", "OperatorSkill", "WorkbenchOperatorProfiles"):
        assert sum(' FROM "' + table + '" ' in statement for statement in sql) == 1
    assert not any("FROM Operators AS o" in statement or "FROM OperatorSkill AS s" in statement for statement in sql)
    assert pool == {
        "machines_by_op_type": {"OT_A": ["M_A", "M_B"], "OT_B": ["M_A"]},
        "operators_by_machine": {"M_A": ["O_SKILLED", "O_LEGACY"], "M_B": ["O_LEGACY"]},
        "machines_by_operator": {"O_LEGACY": ["M_A", "M_B"], "O_SKILLED": ["M_A"]},
        "pair_rank": {("O_LEGACY", "M_A"): 11, ("O_SKILLED", "M_A"): 0, ("O_LEGACY", "M_B"): 12},
        "operator_skills": {"O_EMPTY": [], "O_LEGACY": None, "O_SKILLED": ["OT_B"]},
    }
    assert warnings == [] and meta["resource_pool_build_ok"] is True
