"""Indexed history ordering and foreign-key lookups preserve saved business facts."""

import json
import sqlite3
from datetime import datetime

import pytest

from core.errors import AppError, ErrorCode
from core.infrastructure import database
from core.infrastructure.efficiency_indexes_schema import ADDED, contract_issues
from core.infrastructure.migration_state import current_schema_contract_issues
from core.models.workbench_command import WorkbenchCommandOutcome
from core.models.workbench_run_history import RunHistoryScope
from core.services.workbench.facts.production_capture import ProductionFactsCapture
from core.services.workbench.facts.schema_compat import project_facts
from core.services.workbench.run.jobs_facts import production_facts_match
from data.repositories.batch_operation_repo import BatchOperationRepository
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from data.repositories.workbench_run_query_repo import WorkbenchRunHistoryQueryRepository
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from tests.workbench.plan_catalog_support import scenario
from tests.workbench.run_schema_migration_support import snapshot, source_ddl


@pytest.fixture
def indexed_db(tmp_path):
    path = str(tmp_path / "efficiency-indexes.sqlite")
    database.ensure_schema(path)
    conn = database.get_connection(path)
    try:
        yield path, conn
    finally:
        conn.close()


def _run(conn, number, accepted, *, time=None, archive='{"synthetic":"saved input"}'):
    """Use real journal writers; timestamps deliberately retain their original precision."""
    ref, request_key = f"{number:048x}", f"efficiency-run-{number:04d}"
    WorkbenchCommandRepository(conn).insert(
        request_key=request_key, receipt_ref=f"{number:032x}", action="scheduling.run",
        context_ref="input-" + ref, outcome=WorkbenchCommandOutcome("committed", {"run_ref": ref}))
    repo = WorkbenchRunRepository(conn)
    repo.insert(request_key=request_key, input_ref="input-" + ref, settings={"saved": number},
                facts_hash=None, facts_json=archive, projections=[], baseline={}, now=accepted, run_ref=ref)
    if time is not None:
        repo.claim(ref, f"{number + 100:048x}", time)
        repo.finish(ref, "complete", {"state": "complete", "candidates": [], "error": None}, time)
    return ref


@pytest.mark.parametrize("field", ("accepted_at", "started_at", "finished_at"))
@pytest.mark.parametrize("order", ("asc", "desc"))
def test_history_uses_expression_index_with_mixed_precision_nulls_and_page_ties(indexed_db, field, order):
    _path, conn = indexed_db
    values = ((1, "2026-10-17T08:00:00.1"), (9, "2026-10-17T08:00:00.100000"),
              (3, "2026-10-17T08:00:00.10"), (8, "2026-10-17T08:00:00"),
              (4, "2026-10-17T08:00:00.000000"), (6, "2026-10-17T08:00:00.09"),
              (2, "2026-10-17T08:00:01"), (7, None), (5, None))
    recorded = []
    for number, time in values:
        accepted = time if time is not None else "2026-10-17T08:00:02"
        ref = _run(conn, number, accepted, time=time)
        recorded.append((ref, accepted if field == "accepted_at" else time))
    conn.commit()
    present = sorted(((ref, datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%f" if "." in time else "%Y-%m-%dT%H:%M:%S"))
                      for ref, time in recorded if time is not None),
                     key=lambda row: (row[1], row[0]), reverse=order == "desc")
    absent = sorted((ref for ref, time in recorded if time is None), reverse=order == "desc")
    expected = [ref for ref, _time in present] + absent

    statements = []
    conn.set_trace_callback(statements.append)
    repo, actual = WorkbenchRunHistoryQueryRepository(conn), []
    try:
        for page in range(1, 4):
            rows = repo.list_jobs(RunHistoryScope(sort=field, order=order, page=page, size=3))
            actual.extend(row["run_ref"] for row in rows)
    finally:
        conn.set_trace_callback(None)
    assert actual == expected

    query = next(sql for sql in statements if "FROM (SELECT j.run_ref" in sql)
    plan = [row[3] for row in conn.execute("EXPLAIN QUERY PLAN " + query)]
    source = next(index for index, detail in enumerate(plan) if "WorkbenchRunJobs" in detail)
    subquery = next(index for index, detail in enumerate(plan) if "SCAN SUBQUERY" in detail or "SCAN j" == detail)
    assert "idx_wb_run_" + field[:-3] + "_sort" in plan[source]
    assert not any("TEMP B-TREE" in detail for detail in plan[source:subquery])


def _operations(conn):
    conn.executescript("""INSERT INTO Parts(part_no,part_name) VALUES ('P','Part');
        INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('DELETE','P',1),('KEEP','P',1);
        INSERT INTO BatchOperations(id,op_code,batch_id,seq,op_type_name)
            VALUES (1,'DELETE-1','DELETE',1,'Turning'),(2,'KEEP-1','KEEP',1,'Turning');
        INSERT INTO Materials(material_id,name) VALUES ('MAT','Material');
        INSERT INTO BatchMaterials(id,batch_id,material_id,required_qty) VALUES (1,'KEEP','MAT',1);
        INSERT INTO BatchMaterialStages(requirement_id,operation_id) VALUES (1,2);
        INSERT INTO ScheduleAdjustmentDraft(draft_id,base_version,base_plan_role)
            VALUES ('delete-draft',1,'adopted'),('keep-draft',1,'adopted');
        INSERT INTO ScheduleAdjustmentChange(draft_id,op_id,change_type)
            VALUES ('delete-draft',1,'move_time'),('keep-draft',2,'move_time');""")
    scenario(conn, "delete-scenario", 1, op_id=1)
    scenario(conn, "keep-scenario", 1, op_id=2)
    conn.commit()


def test_operation_deletion_searches_all_three_child_keys_and_keeps_foreign_key_actions(indexed_db):
    _path, conn = indexed_db
    _operations(conn)
    plan = [row[3] for row in conn.execute(
        "EXPLAIN QUERY PLAN DELETE FROM BatchOperations WHERE batch_id=?", ("DELETE",))]
    children = (("BatchMaterialStages", "idx_material_stage_operation"),
                ("ScheduleAdjustmentChange", "idx_schedule_adjustment_change_op"),
                ("ScheduleAdjustmentScenarioRow", "idx_schedule_adjustment_scenario_row_op_id"))
    for table, index in children:
        related = [detail for detail in plan if table in detail]
        assert related and all("SEARCH" in detail and index in detail for detail in related)

    repo = BatchOperationRepository(conn)
    repo.delete_by_batch("DELETE")
    assert [row[0] for row in conn.execute("SELECT op_id FROM ScheduleAdjustmentChange")] == [2]
    assert [row[0] for row in conn.execute("SELECT op_id FROM ScheduleAdjustmentScenarioRow")] == [2]
    assert [tuple(row) for row in conn.execute("SELECT * FROM BatchMaterialStages")] == [(1, 2)]
    with pytest.raises(AppError) as rejected:
        repo.delete_by_batch("KEEP")
    assert rejected.value.code == ErrorCode.DB_INTEGRITY_ERROR
    assert isinstance(rejected.value.cause, sqlite3.IntegrityError)
    assert conn.execute("SELECT id FROM BatchOperations").fetchone()[0] == 2
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def test_v43_to_v44_changes_only_declared_indexes_and_preserves_archives(indexed_db, tmp_path):
    path, conn = indexed_db
    _operations(conn)
    for name in ADDED:
        conn.execute('DROP INDEX "' + name + '"')
    conn.execute("UPDATE SchemaVersion SET version=43 WHERE id=1")
    conn.commit()
    archived = ProductionFactsCapture(conn).content()
    ref = _run(conn, 1, "2026-10-17T08:00:00", time="2026-10-17T08:01:00.100000", archive=archived)
    conn.commit()
    before_rows, before_ddl = snapshot(conn), source_ddl(conn)

    database.ensure_schema(path, backup_dir=str(tmp_path / "backups"))
    assert conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == 44
    assert contract_issues(conn) == current_schema_contract_issues(conn) == []
    after_rows, after_ddl = snapshot(conn), source_ddl(conn)
    assert {name: rows for name, rows in before_rows.items() if name != "SchemaVersion"} == {
        name: rows for name, rows in after_rows.items() if name != "SchemaVersion"}
    assert [row for row in after_ddl if row[1] not in ADDED] == before_ddl
    assert {row[1] for row in after_ddl if row not in before_ddl} == set(ADDED)
    assert conn.execute("SELECT facts_json FROM WorkbenchRunJobs WHERE run_ref=?", (ref,)).fetchone()[0] == archived
    assert production_facts_match(conn, archived)
    current = ProductionFactsCapture(conn).content()
    assert project_facts(json.loads(archived)) == project_facts(json.loads(current))

    for mutation in (
            "CREATE INDEX idx_undeclared_efficiency_change ON Parts(part_name)",
            "DROP INDEX idx_wb_run_accepted_sort; CREATE INDEX idx_wb_run_accepted_sort "
            "ON WorkbenchRunJobs(substr(accepted_at,1,18),substr(accepted_at || '0000000',21,6),run_ref)"):
        conn.execute("BEGIN")
        try:
            for sql in mutation.split(";"):
                conn.execute(sql)
            assert not production_facts_match(conn, archived)
        finally:
            conn.rollback()
