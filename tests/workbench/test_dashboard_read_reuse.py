"""One dashboard capture supplies its projections and calendar source reads."""

import sqlite3
from collections import Counter

import pytest

from core.infrastructure.workbench_metadata_schema import canonical_sql
from core.infrastructure.workbench_outsourcing_schema import objects as outsourcing_objects
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.capacity.plan_calendar_io import CalendarFacts, CapturedCalendarInputs, ProjectionLimit
from core.services.workbench.dashboard import downtime, execution
from core.services.workbench.dashboard import facts as facts_module
from core.services.workbench.dashboard.analysis_projection import project_dashboard_analysis
from core.services.workbench.dashboard.service import WorkbenchDashboardService
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from core.services.workbench.plan.read_context import PlanReadContext
from data.repositories.calendar_facts_repo import CalendarFactsRepository
from data.repositories.workbench_dashboard_source_repo import DashboardSourceRepository
from data.repositories.workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository


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
    enriched, enrich = [], WorkbenchPlanCatalogRepository.enrich_arrangements

    def enrich_once(repo, arrangements, *, version, captured_machines=None):
        enriched.append(captured_machines)
        return enrich(repo, arrangements, version=version, captured_machines=captured_machines)

    monkeypatch.setattr(WorkbenchPlanCatalogRepository, "enrich_arrangements", enrich_once)
    case.conn.set_trace_callback(sql.append)
    reader = WorkbenchDashboardService(case.conn, clock=lambda: NOW)
    with reader.read_snapshot():
        sources = reader.load()
        facts, material = sources.facts, sources.material
        assert facts.plan_state == "loaded" and len(facts.tasks) == 1
        assert facts.entity_refs("batch", ["DB1"]) is not facts.entity_refs("batch", ["DB1"])
        with pytest.raises(WorkbenchCommandRejected, match="来源关联资料缺失"):
            facts.entity_refs("batch", ["DB1", "missing-batch"])
        with pytest.raises(WorkbenchCommandRejected, match="来源关联资料缺失"):
            facts.entity_refs("batch", ["missing-batch"])
    monkeypatch.setattr(facts_module, "candidate_catalog", lambda _: pytest.fail("Analysis read candidate catalog"))
    data = reader.project(sources)
    assert len(enriched) == 1 and enriched[0] is facts.raw["Machines"]
    assert sorted(item["category"] for item in data["items"]) == ["actual", "delivery", "downtime", "material"]
    assert data["categories"]["external"]["state"] == "no_data"
    assert {name: canonical_sql(sql) for name, sql in facts.raw["external"]["schema"].items()} == {
        name: canonical_sql(sql) for name, sql in outsourcing_objects().items()}
    assert [requested for kind, requested in keys if kind == "batch"] == [["DB1"], ["missing-batch"]]
    rows, summary = facts.observations("actual")
    summary["handling_count"] = 999
    assert facts.observations("actual")[0] is rows
    assert "handling_count" not in facts.observations("actual")[1]
    facts.observations("downtime")
    projected = project_dashboard_analysis(facts, material)
    assert len(projected["tasks"]) == 1 and calls == {"actual": 1, "downtime": 1}
    normalized = [" ".join(statement.upper().replace('"', '').split()) for statement in sql]
    assert sum(" FROM SQLITE_MASTER" in statement for statement in normalized) == 1
    assert sum("FROM MACHINEDOWNTIMES " in statement for statement in normalized) == 1
    assert sum("FROM MACHINES " in statement for statement in normalized) == 1
    assert sum("FROM SCHEMAVERSION " in statement for statement in normalized) == 1


@pytest.mark.parametrize("captured_machines,expected_name,reads", [
    (None, "Lathe", 1), ([], None, 0), ([{"machine_id": "other", "name": "Other machine"}], None, 0)])
def test_plan_details_respect_complete_machine_capture(dashboard_case, captured_machines, expected_name, reads):
    case, sql = dashboard_case, []
    plan_ref = case.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='official' AND version=1 AND active=1").fetchone()[0]
    case.conn.set_trace_callback(sql.append)
    with WorkbenchPlanQueryService(case.conn).read_snapshot():
        context = PlanReadContext(case.conn, captured_machines=captured_machines)
        with context.read_scope():
            _, entry, _ = context.selected(plan_ref)
            row, = context.detail_rows(entry)
    assert row["machine_name"] == expected_name and row["operator_name"] == "Operator"
    normalized = [" ".join(statement.upper().replace('"', '').split()) for statement in sql]
    assert sum("FROM MACHINES " in statement for statement in normalized) == reads


def test_captured_calendar_preserves_sql_status_time_types_order_and_budget(monkeypatch):
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
    from data.repositories import workbench_dashboard_source_repo
    original, parsed = workbench_dashboard_source_repo.parse_dt_for_sql, []

    def parse_once(value):
        parsed.append(value)
        return original(value)

    monkeypatch.setattr(workbench_dashboard_source_repo, "parse_dt_for_sql", parse_once)
    repo = DashboardSourceRepository(conn)
    raw, prepared = repo.downtime_capture(machine_ids=["M1"])
    assert len(parsed) == 8  # Four admitted rows, each endpoint once; cancelled/unselected blobs stay raw.
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
