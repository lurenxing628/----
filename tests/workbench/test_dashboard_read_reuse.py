"""One dashboard capture supplies its projections and calendar source reads."""

import sqlite3
from collections import Counter

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.capacity.plan_calendar_io import CalendarFacts, CapturedCalendarInputs, ProjectionLimit
from core.services.workbench.dashboard import downtime, execution
from core.services.workbench.dashboard import facts as facts_module
from core.services.workbench.dashboard.analysis_projection import project_dashboard_analysis
from core.services.workbench.dashboard.facts import DashboardFacts
from core.services.workbench.dashboard.projection import safe_material
from core.services.workbench.dashboard.service import WorkbenchDashboardService
from data.repositories.calendar_facts_repo import CalendarFactsRepository
from data.repositories.workbench_dashboard_source_repo import DashboardSourceRepository


@pytest.fixture
def dashboard_case(tmp_path):
    from tests.workbench.dashboard_support import dashboard_case as existing_case
    yield from existing_case.__wrapped__(tmp_path)


def test_one_capture_reuses_projections_and_only_reads_new_identity_keys(dashboard_case, monkeypatch):
    from tests.workbench.dashboard_support import NOW
    case, calls, keys, sql = dashboard_case, Counter(), [], []
    for name, module in (("actual", execution), ("downtime", downtime)):
        original = getattr(module, name)

        def tracked(*args, _name=name, _original=original):
            calls[_name] += 1
            return _original(*args)

        monkeypatch.setattr(module, name, tracked)
    original_refs = DashboardSourceRepository.entity_ref_rows

    def refs(repo, kind, requested):
        keys.append((kind, list(requested)))
        return original_refs(repo, kind, requested)

    monkeypatch.setattr(DashboardSourceRepository, "entity_ref_rows", refs)
    monkeypatch.setattr(facts_module, "candidate_catalog", lambda _: pytest.fail("Analysis read candidate catalog"))
    case.conn.set_trace_callback(sql.append)
    with WorkbenchDashboardService(case.conn).read_snapshot():
        facts = DashboardFacts(case.conn, NOW).load(include_candidates=False)
        material = safe_material(facts)
        assert facts.plan_state == "loaded" and len(facts.tasks) == 1
        assert facts.entity_refs("batch", ["DB1"]) is not facts.entity_refs("batch", ["DB1"])
        with pytest.raises(WorkbenchCommandRejected, match="来源关联资料缺失"):
            facts.entity_refs("batch", ["DB1", "missing-batch"])
        with pytest.raises(WorkbenchCommandRejected, match="来源关联资料缺失"):
            facts.entity_refs("batch", ["missing-batch"])
    assert [requested for kind, requested in keys if kind == "batch"] == [["DB1"], ["missing-batch"]]
    rows, summary = facts.observations("actual")
    summary["handling_count"] = 999
    assert facts.observations("actual")[0] is rows
    assert "handling_count" not in facts.observations("actual")[1]
    facts.observations("downtime")
    projected = project_dashboard_analysis(facts, material)
    assert len(projected["tasks"]) == 1 and calls == {"actual": 1, "downtime": 1}
    normalized = [" ".join(statement.upper().replace('"', '').split()) for statement in sql]
    assert sum("FROM MACHINEDOWNTIMES " in statement for statement in normalized) == 1
    assert sum("FROM MACHINES " in statement for statement in normalized) == 1
    assert sum("FROM SCHEMAVERSION " in statement for statement in normalized) == 1


def test_captured_calendar_preserves_sql_status_time_types_order_and_budget():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""CREATE TABLE Machines(machine_id TEXT,name TEXT,status TEXT,op_type_id TEXT);
        CREATE TABLE MachineDowntimes(id INTEGER PRIMARY KEY,machine_id TEXT,start_time,end_time,status);
        CREATE TABLE SchemaVersion(id INTEGER,version INTEGER);
        INSERT INTO SchemaVersion VALUES(1,35); INSERT INTO Machines VALUES('M1','Lathe','active','T1');""")
    rows = [("M1", "2026-09-10T08:00:00", "2026-09-10T10:00:00", "active"),
            ("M1", b"2026-09-10T09:00:00", b"2026-09-10T11:00:00", "active"),
            ("M1", None, "2026-09-10T12:00:00", "unexpected"),
            ("M1", 123.5, 124, None),
            ("M1", b"\xff", b"\xfe", "cancelled"),
            ("M2", b"\xff", b"\xfe", "active")]
    conn.executemany("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,status) VALUES(?,?,?,?)", rows)
    repo = DashboardSourceRepository(conn)
    raw, prepared = repo.downtime_capture(machine_ids=["M1"])
    captured = CapturedCalendarInputs(machines=repo.table("Machines"), downtimes=prepared,
        schema_version=repo.table("SchemaVersion"), downtime_machine_ids=["M1"])
    expected = CalendarFactsRepository(conn).downtimes(["M1"], "2026-09-10T11:00:00", "2026-09-10T09:00:00", limit=100)
    assert captured.downtimes(["M1"], "2026-09-10T11:00:00", "2026-09-10T09:00:00", limit=100) == expected
    assert [tuple(row[key] for key in ("machine_id", "start_time", "end_time", "status")) for row in raw] == rows
    assert captured.schema_version() == 35
    limited = CalendarFacts(conn, captured=captured)
    limited.count = 49999
    with pytest.raises(ProjectionLimit, match="calendar_fact_limit"):
        limited.keyed("downtimes", captured.downtimes, ["M1"], ("2026-09-10T11:00:00", "2026-09-10T09:00:00"))
    with pytest.raises(ProjectionLimit, match="calendar_unavailable"):
        captured.downtimes(["M2"], "2026-09-10T11:00:00", "2026-09-10T09:00:00", limit=100)
    missing = CapturedCalendarInputs(machines=None, downtimes=None, schema_version=None)
    with pytest.raises(ProjectionLimit, match="calendar_unavailable"):
        missing.downtimes(["M1"], "2026-09-10T11:00:00", "2026-09-10T09:00:00", limit=100)
    conn.close()
