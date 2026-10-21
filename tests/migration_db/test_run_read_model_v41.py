"""Real v40/v41 archives, immutable projections, and native roles after v42."""

import json
import sqlite3

import pytest

from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema
from core.infrastructure.migration_state import current_schema_contract_issues, get_schema_version, set_schema_version
from core.infrastructure.migrations import run_migration
from core.infrastructure.schedule_business_roles_schema import REBUILD_TABLES
from core.infrastructure.schedule_business_roles_schema import contract_issues as business_role_contract_issues
from core.infrastructure.workbench_run_read_model_schema import READ_MODEL_TABLES, contract_issues
from core.services.workbench.facts.admission_scope import project_admitted_scope
from core.services.workbench.facts.candidate_values import stored_json
from core.services.workbench.facts.production_capture import ProductionFactsCapture
from core.services.workbench.facts.run_history_projection import scope_summary
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.run.jobs_facts import capture_run_facts, run_facts_unchanged
from core.services.workbench.trial.facts import capture_facts, facts_unchanged
from tests._support.paths import REPO_ROOT
from tests.workbench.frozen_business_seed_support import seed_frozen_business
from tests.workbench.plan_catalog_support import candidate as native_candidate
from tests.workbench.plan_catalog_support import history as native_history
from tests.workbench.plan_catalog_support import selection as native_selection
from tests.workbench.run_schema_migration_support import connect, snapshot


def test_v40_archive_backfill_preserves_originals_budget_and_immutable_projections(tmp_path):
    path = tmp_path / "historical-v40.sqlite"
    conn = seed_frozen_business(path, 30)
    try:
        with conn:
            for version in range(31, 41):
                run_migration(conn, version)
                set_schema_version(conn, version)
            operation_id = conn.execute("SELECT id FROM BatchOperations ORDER BY id LIMIT 1").fetchone()[0]
            native_history(conn, 7, op_id=operation_id)
            original_candidate_id = native_candidate(conn, 7, "baseline_best", op_id=operation_id)
            native_candidate(conn, 7, "critical_best", op_id=operation_id)
            native_selection(conn, 7, "adopted", original_candidate_id)
            removed_candidate_id = native_candidate(conn, 8, "baseline_best", op_id=operation_id)
            conn.execute("DELETE FROM ScheduleCandidate WHERE id=?", (removed_candidate_id,))
        assert get_schema_version(conn) == 40
        before = snapshot(conn)
        assert not set(READ_MODEL_TABLES) & before.keys()
        run_ref = conn.execute("SELECT run_ref FROM WorkbenchRunJobs").fetchone()[0]
        original_job = dict(conn.execute("SELECT * FROM WorkbenchRunJobs WHERE run_ref=?", (run_ref,)).fetchone())
        original_scope = scope_summary(original_job["normalized_input_json"])
        original_workload = project_admitted_scope(
            json.loads(original_job["normalized_input_json"]), stored_json(original_job["facts_json"]),
            summary=original_scope)
        original_receipt = json.loads(conn.execute(
            "SELECT result_json FROM WorkbenchRunReceipts WHERE run_ref=?", (run_ref,)).fetchone()[0])
        candidate_refs = [row[0] for row in conn.execute("SELECT candidate_ref FROM WorkbenchRunCandidates ORDER BY sequence")]
        assert len(candidate_refs) == 4
        assert conn.execute("SELECT config_value FROM ScheduleConfig WHERE config_key='time_budget_seconds'").fetchone()[0] == "60"
        with candidate_read_snapshot(conn):
            capture = ProductionFactsCapture(conn)
            captured_hash, captured_text = capture_run_facts(conn, capture)
            named_facts = capture_facts(conn, capture)
        with conn:
            run_migration(conn, 41)
            set_schema_version(conn, 41)
        assert get_schema_version(conn) == 41
        assert contract_issues(conn) == []
        before_42 = snapshot(conn)
        native_rows = {table: [tuple(row) for row in conn.execute("SELECT rowid,* FROM " + table + " ORDER BY rowid")]
                       for table in REBUILD_TABLES}
        sequences = [tuple(row) for row in conn.execute("SELECT rowid,name,seq FROM sqlite_sequence "
                                                      "WHERE name IN (?,?,?) ORDER BY rowid", REBUILD_TABLES)]
        assert [len(native_rows[table]) for table in REBUILD_TABLES] == [2, 2, 3]
        assert all(sequence > conn.execute("SELECT max(id) FROM " + table).fetchone()[0]
                   for _, table, sequence in sequences)
        attached = [tuple(row) for row in conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE tbl_name IN (?,?,?) AND type IN ('index','trigger') ORDER BY type,name", REBUILD_TABLES)]
        rows_ddl = conn.execute("SELECT sql FROM sqlite_master WHERE name='ScheduleCandidateRows'").fetchone()[0]
        conn.execute("BEGIN")
        try:
            set_schema_version(conn, 42)
            assert set(current_schema_contract_issues(conn)) == {
                "invalid_schedule_business_roles:ScheduleCandidate", "invalid_schedule_business_roles:ScheduleCandidateSelection"}
        finally:
            conn.rollback()
    finally:
        conn.close()

    ensure_schema(str(path), schema_path=str(REPO_ROOT / "schema.sql"), backup_dir=str(tmp_path / "backups"))
    conn = connect(path)
    try:
        assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION == 44
        assert contract_issues(conn) == []
        assert business_role_contract_issues(conn) == []
        assert current_schema_contract_issues(conn) == []
        after = snapshot(conn)
        assert {name: after[name] for name in before if name != "SchemaVersion"} == {
            name: rows for name, rows in before.items() if name != "SchemaVersion"}
        assert set(after) - set(before) == set(READ_MODEL_TABLES)
        assert {name: after[name] for name in before_42 if name != "SchemaVersion"} == {
            name: rows for name, rows in before_42.items() if name != "SchemaVersion"}
        assert {table: [tuple(row) for row in conn.execute("SELECT rowid,* FROM " + table + " ORDER BY rowid")]
                for table in REBUILD_TABLES} == native_rows
        assert [tuple(row) for row in conn.execute("SELECT rowid,name,seq FROM sqlite_sequence "
            "WHERE name IN (?,?,?) ORDER BY rowid", REBUILD_TABLES)] == sequences
        assert [tuple(row) for row in conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE tbl_name IN (?,?,?) AND type IN ('index','trigger') ORDER BY type,name", REBUILD_TABLES)] == [row for row in attached if row[1] not in ("idx_schedule_candidate_selection_version", "idx_schedule_candidate_version")]
        assert conn.execute("SELECT sql FROM sqlite_master WHERE name='ScheduleCandidateRows'").fetchone()[0] == rows_ddl
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        admission = conn.execute("SELECT * FROM WorkbenchRunAdmissionReadModels WHERE run_ref=?", (run_ref,)).fetchone()
        scope = json.loads(admission["scope_json"])
        assert scope["scope_summary"] == original_scope
        workload = {**scope["scope_summary"],
                    **{field: scope[field] for field in ("batches", "operation_count", "objective", "objective_label")},
                    "data_gaps": scope["workload_data_gaps"]}
        assert workload == original_workload
        decision = json.loads(admission["decision_json"])
        assert {"context", "memberships", "calendar", "official"} <= decision.keys()
        terminal = conn.execute("SELECT header_json FROM WorkbenchRunDecisionReadModels WHERE run_ref=?", (run_ref,)).fetchone()
        header_candidates = json.loads(terminal[0])["candidates"]
        assert [row["candidate_ref"] for row in header_candidates] == candidate_refs
        public_fields = ("candidate_ref", "label", "status", "task_count", "selected")
        assert [{field: row[field] for field in public_fields} for row in header_candidates] == [
            {field: row[field] for field in public_fields} for row in original_receipt["candidates"]]
        models = conn.execute("SELECT candidate_ref,projection_version,arrangements_json,delivery_detail_json "
                              "FROM WorkbenchRunCandidateReadModels ORDER BY candidate_ref").fetchall()
        assert {row["candidate_ref"] for row in models} == set(candidate_refs)
        assert all(row["projection_version"] == "decision-read-v1" and
                   len(json.loads(row["arrangements_json"])["rows"]) == 1 and
                   type(json.loads(row["delivery_detail_json"])) is list for row in models)
        assert run_facts_unchanged(conn, captured_text, captured_hash)
        with candidate_read_snapshot(conn):
            current_facts = capture_facts(conn)
        assert facts_unchanged({"facts": named_facts}, {"facts": current_facts})
        conn.execute("BEGIN")
        try:
            new_id = conn.execute("INSERT INTO ScheduleCandidate(version,candidate_key,candidate_label,candidate_kind,status) "
                "VALUES (9,'business','Business objective','business_objective','completed')").lastrowid
            for role in ("min_overdue", "min_tardiness", "min_changeover", "min_weighted_tardiness"):
                native_selection(conn, 9, role, new_id)
            assert conn.execute("SELECT count(*) FROM ScheduleCandidateSelection WHERE version=9").fetchone()[0] == 4
            for sql in ("UPDATE ScheduleCandidate SET candidate_kind='unknown' WHERE id=" + str(new_id),
                        "UPDATE ScheduleCandidateSelection SET role='unknown' WHERE version=9"):
                with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
                    conn.execute(sql)
        finally:
            conn.rollback()
        indexes = {
            "idx_wb_run_input": ("input_ref",),
            "idx_wb_command_action_context_time": ("action", "context_ref", "committed_at_utc", "request_key"),
            "idx_wb_run_candidate_model_run": ("run_ref", "candidate_ref"),
            "idx_wb_run_accepted": ("accepted_at", "run_ref"),
            "idx_wb_run_started": ("started_at", "run_ref"),
            "idx_wb_run_finished": ("finished_at", "run_ref"),
        }
        for name, columns in indexes.items():
            assert tuple(row["name"] for row in conn.execute("PRAGMA index_info(" + name + ")")) == columns
        assert next(row["unique"] for row in conn.execute("PRAGMA index_list(WorkbenchRunJobs)")
                    if row["name"] == "idx_wb_run_input") == 0
        plan = conn.execute("EXPLAIN QUERY PLAN SELECT request_key FROM WorkbenchCommandReceipts "
            "WHERE action=? AND context_ref=? ORDER BY committed_at_utc,request_key LIMIT ?", ("candidate.adopt", candidate_refs[0], 10))
        assert any("idx_wb_command_action_context_time" in row["detail"] for row in plan)
        for table in READ_MODEL_TABLES:
            for sql in ("UPDATE " + table + " SET projection_version='changed'", "DELETE FROM " + table):
                with pytest.raises(sqlite3.IntegrityError, match="run read model is permanent"):
                    conn.execute(sql)
        conn.rollback()
        for change in ("UPDATE Parts SET part_name='Changed production fact' WHERE part_no='P1'",
                       "CREATE INDEX idx_undeclared_production_change ON Parts(part_name)",
                       "ALTER TABLE ScheduleCandidate ADD COLUMN unsupported_field TEXT"):
            conn.execute("BEGIN")
            try:
                conn.execute(change)
                assert not run_facts_unchanged(conn, captured_text, captured_hash)
                with candidate_read_snapshot(conn):
                    current_facts = capture_facts(conn)
                assert not facts_unchanged({"facts": named_facts}, {"facts": current_facts})
                if change.startswith("ALTER TABLE"):
                    assert business_role_contract_issues(conn) == ["invalid_schedule_business_roles:ScheduleCandidate"]
                    with pytest.raises(RuntimeError, match="exact historical structure"):
                        run_migration(conn, 42)
            finally:
                conn.rollback()
    finally:
        conn.close()
