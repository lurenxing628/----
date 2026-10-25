"""A pool build shares qualification facts and retains successfully read empty downtime."""

from datetime import datetime
from types import SimpleNamespace

from core.services.personnel.operator_qualification import OperatorQualificationService
from core.services.scheduler import resource_pool_builder
from core.services.workbench.run.input_runtime import downtime_overlap, held_machine_downtimes, runtime_resource_facts
from core.services.workbench.run.preflight_facts import PreflightFacts
from tests._support.algo_operations import make_algo_op

START = datetime(2026, 10, 14, 8)


def test_empty_downtime_is_read_once_when_extending_pool(schema_conn):
    conn = schema_conn
    conn.executemany("INSERT INTO Machines(machine_id, name) VALUES (?, ?)", [("M_A", "A"), ("M_B", "B")])
    conn.execute(
        "INSERT INTO MachineDowntimes(machine_id, start_time, end_time) VALUES ('M_B', ?, ?)",
        ("2026-10-14 09:00:00", "2026-10-14 10:00:00"),
    )
    conn.commit()
    meta = {}
    sql = []
    conn.set_trace_callback(sql.append)
    facts = PreflightFacts(conn)
    try:
        with facts.snapshot(fingerprint=False):
            resources = runtime_resource_facts(facts)
            assert runtime_resource_facts(facts) is resources
            downtime = resource_pool_builder.load_machine_downtimes(
                algo_ops=[make_algo_op(machine_id="M_A")],
                start_dt=START, downtimes=resources.downtimes,
            )
            assert downtime == {"M_A": []}
            pool = {"operators_by_machine": {"M_A": ["O1"], "M_B": ["O1"]}}
            for _ in range(2):
                assert resource_pool_builder.extend_downtime_map_for_resource_pool(
                    cfg=SimpleNamespace(auto_assign_enabled="yes"), resource_pool=pool,
                    downtime_map=downtime, start_dt=START, downtimes=resources.downtimes,
                    meta=meta,
                ) is downtime
    finally:
        conn.set_trace_callback(None)
    assert sum(' FROM "MachineDowntimes" ' in statement for statement in sql) == 1
    assert downtime == {"M_A": [], "M_B": [(datetime(2026, 10, 14, 9), datetime(2026, 10, 14, 10))]}
    assert meta == {"downtime_extend_attempted": True}


def test_padded_machine_downtime_stays_on_its_own_machine(schema_conn):
    conn = schema_conn
    conn.executemany("INSERT INTO Machines(machine_id, name) VALUES (?, ?)", [(" M1 ", "padded"), ("M1", "plain")])
    conn.execute(
        "INSERT INTO MachineDowntimes(machine_id, start_time, end_time) VALUES (' M1 ', ?, ?)",
        ("2026-10-14 09:00:00", "2026-10-14 10:00:00"),
    )
    conn.commit()
    padded, plain = ({"op_id": op_id, "op_code": "OP" + str(op_id), "batch_id": "B1", "seq": op_id,
                      "machine_id": mid, "operator_id": "O1", "start_time": START, "end_time": datetime(2026, 10, 14, 11),
                      "source": "internal", "op_type_name": "T", "op_type_id": "T1", "seed_source": "freeze_window"}
                     for op_id, mid in ((1, " M1 "), (2, "M1")))
    stop = (datetime(2026, 10, 14, 9), datetime(2026, 10, 14, 10))
    facts = PreflightFacts(conn)
    with facts.snapshot(fingerprint=False):
        assert runtime_resource_facts(facts).downtimes == {" M1 ": [stop]}
        assert held_machine_downtimes([plain], facts=facts) == {"M1": []}
        downtimes = held_machine_downtimes([padded, plain], facts=facts)
    assert downtimes == {" M1 ": [stop], "M1": []}
    assert downtime_overlap(padded, downtimes) == stop
    assert downtime_overlap(plain, downtimes) is None


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
            resources.validate_fixed(conn, [make_algo_op(op_type_id="OT_B", machine_id="M_A", operator_id="O_SKILLED")])
            for _ in range(2):
                pool = resource_pool_builder.build_resource_pool(
                    cfg=SimpleNamespace(auto_assign_enabled="yes"),
                    algo_ops=[make_algo_op(id=op_id, op_type_id=code)
                              for op_id, code in enumerate(("OT_A", "OT_B"), 1)],
                    meta=meta, resource_facts=resources,
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
    assert meta == {"resource_pool_attempted": True}


def test_resource_pool_recognizes_chinese_primary_synonyms(schema_conn):
    conn = schema_conn
    _seed_multi_work_type_pool(conn)
    conn.execute("UPDATE OperatorMachine SET is_primary='主操' WHERE operator_id='O_LEGACY' AND machine_id='M_A'")
    conn.execute("UPDATE OperatorMachine SET is_primary='主' WHERE operator_id='O_LEGACY' AND machine_id='M_B'")
    conn.commit()
    facts = PreflightFacts(conn)
    with facts.snapshot(fingerprint=False):
        resources = runtime_resource_facts(facts)
        pool = resource_pool_builder.build_resource_pool(
            cfg=SimpleNamespace(auto_assign_enabled="yes"),
            algo_ops=[make_algo_op(id=op_id, op_type_id=code) for op_id, code in enumerate(("OT_A", "OT_B"), 1)],
            resource_facts=resources,
        )
    assert pool is not None
    assert pool["pair_rank"] == {("O_LEGACY", "M_A"): 1, ("O_SKILLED", "M_A"): 0, ("O_LEGACY", "M_B"): 2}
    assert pool["operators_by_machine"] == {"M_A": ["O_SKILLED", "O_LEGACY"], "M_B": ["O_LEGACY"]}
