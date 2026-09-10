"""No same-number rebinding, writeback, snapshot substitution or hidden truncation."""

import json
import sqlite3

import pytest

from core.errors import AppError
from core.services.workbench.plan_baseline import build_plan_baseline
from tests.workbench.plan_baseline_support import baseline_fixture as baseline_fixture  # noqa: F401
from tests.workbench.test_plan_adoption_baseline_support import (
    adopt_candidate,
    adopt_trial,
    mutate_json,
    read,
    two_versions,
)
from tests.workbench.test_plan_adoption_baseline_support import trial_case as trial_case  # noqa: F401
from tests.workbench.test_run_candidate_adoption_support import snapshot
from tests.workbench.test_run_candidate_support import corrupt_update


@pytest.mark.parametrize("source", ["candidate", "trial"])
def test_original_blob_type_preserved_and_text_lookalike_is_drift(trial_case, source):
    case = trial_case
    first = adopt_candidate(case)
    raw = b"2026-09-09 00:00:00\x00original"
    case.conn.execute("UPDATE Schedule SET created_at=? WHERE version=1", (sqlite3.Binary(raw),))
    case.conn.commit()
    second = adopt_candidate(case, "second") if source == "candidate" else adopt_trial(case, first)[0]
    before, changes = snapshot(case.conn), case.conn.total_changes
    data, facts = read(case, second)
    assert data["state"] == "available", (data, facts.get("evidence_gap"))
    assert facts["adoption"]["baseline"]["rows"][0]["created_at"] == raw
    assert snapshot(case.conn) == before and case.conn.total_changes == changes
    assert case.conn.execute("SELECT typeof(created_at) FROM Schedule WHERE version=1").fetchone()[0] == "blob"
    case.conn.execute("UPDATE Schedule SET created_at=? WHERE version=1", (raw.decode("utf-8"),))
    case.conn.commit()
    data, _ = read(case, second)
    assert data["reason_code"] == "adoption_baseline_drift" and data["items"] == []


@pytest.mark.parametrize("sql,reason", [
    ("DELETE FROM ScheduleHistory WHERE version=1", "adoption_baseline_archived"),
    ("DELETE FROM Schedule WHERE version=1", "adoption_baseline_archived"),
    ("UPDATE Schedule SET end_time='2026-09-09 11:01:00' WHERE version=1", "adoption_baseline_drift"),
    ("UPDATE Schedule SET machine_id='M3' WHERE version=1", "adoption_baseline_drift"),
    ("UPDATE Schedule SET created_at=1.5 WHERE version=1", "adoption_baseline_drift"),
    ("UPDATE WorkbenchPlanSourceRefs SET active=0 WHERE kind='official' AND version=1", "adoption_reference_invalid"),
    ("UPDATE WorkbenchPlanSourceRefs SET active=0 WHERE kind='schedule_row' AND version=1", "adoption_reference_invalid"),
    ("UPDATE WorkbenchPlanSourceRefs SET operation_ref=NULL WHERE kind='schedule_row' AND version=1", "adoption_reference_invalid"),
    ("DELETE FROM WorkbenchTaskRefs WHERE plan_ref=(SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='official' AND version=1)", "adoption_reference_invalid"),
    ("UPDATE WorkbenchEntityRefs SET active=0 WHERE kind='machine' AND entity_key='M1'", "adoption_reference_invalid"),
    ("UPDATE Schedule SET end_time='2026-09-09 17:00:00' WHERE version=2", "adoption_plan_drift"),
])
def test_distinct_original_row_binding_and_archive_failures(trial_case, sql, reason):
    _, second = two_versions(trial_case)
    trial_case.conn.execute("PRAGMA foreign_keys=OFF")
    trial_case.conn.execute(sql)
    trial_case.conn.commit()
    before, changes = snapshot(trial_case.conn), trial_case.conn.total_changes
    data, facts = read(trial_case, second)
    assert data["state"] == "unavailable" and data["reason_code"] == reason, (data, facts.get("evidence_gap"))
    assert data["baseline_plan"] is None and data["items"] == [] and not data["items_complete"]
    assert snapshot(trial_case.conn) == before and trial_case.conn.total_changes == changes


def test_same_number_schedule_recreation_cannot_reuse_original_task(trial_case):
    _, second = two_versions(trial_case)
    conn = trial_case.conn
    row = dict(conn.execute("SELECT * FROM Schedule WHERE version=1").fetchone())
    conn.execute("DELETE FROM Schedule WHERE version=1")
    columns = ",".join(row)
    conn.execute("INSERT INTO Schedule (" + columns + ") VALUES (" + ",".join("?" for _ in row) + ")", tuple(row.values()))
    conn.commit()
    data, facts = read(trial_case, second)
    assert data["reason_code"] == "adoption_reference_invalid", (data, facts)


@pytest.mark.parametrize("source", ["candidate", "trial"])
@pytest.mark.parametrize("mutation,reason", [
    ("receipt_missing", "adoption_evidence_missing"), ("receipt_foreign", "adoption_snapshot_invalid"),
    ("receipt_baseline", "adoption_snapshot_invalid"), ("proof_hash", "adoption_snapshot_invalid"),
    ("proof_missing", "adoption_evidence_missing"),
    ("audit_gap", "adoption_evidence_missing"), ("source_archived", "adoption_source_archived"),
    ("snapshot_corrupt", "adoption_snapshot_invalid"), ("snapshot_blob", "adoption_snapshot_invalid"),
])
def test_bad_adoption_evidence_never_becomes_current_data(trial_case, source, mutation, reason):
    _, second = two_versions(trial_case, source)
    conn = trial_case.conn
    key = "da-adopt-" + source + "-second"
    if mutation == "receipt_missing":
        corrupt_update(conn, "WorkbenchCommandReceipts", "DELETE FROM WorkbenchCommandReceipts WHERE request_key=?", (key,))
    elif mutation == "receipt_foreign":
        corrupt_update(conn, "WorkbenchCommandReceipts", "UPDATE WorkbenchCommandReceipts SET context_ref=? WHERE request_key=?", ("a" * 48, key))
    elif mutation == "receipt_baseline":
        mutate_json(conn, "WorkbenchCommandReceipts", "outcome_json",
                    lambda value: value["data"]["official_plan"].update(baseline_ref=second["plan_ref"]), "request_key=?", (key,))
    elif mutation == "proof_hash":
        mutate_json(conn, "ScheduleHistory", "result_summary", lambda value: value["proof"].update(baseline_hash="f" * 64), "version=2")
    elif mutation == "proof_missing":
        mutate_json(conn, "ScheduleHistory", "result_summary", lambda value: value["proof"].pop("baseline_hash"), "version=2")
    elif mutation == "audit_gap":
        mutate_json(conn, "ScheduleHistory", "result_summary", lambda value: value.pop("baseline_ref"), "version=2")
    elif source == "candidate":
        ref = second["source_run_ref"]
        sql = "DELETE FROM WorkbenchRunJobs WHERE run_ref=?" if mutation == "source_archived" else "UPDATE WorkbenchRunJobs SET facts_json=? WHERE run_ref=?"
        args = (ref,) if mutation == "source_archived" else ((b"{}" if mutation == "snapshot_blob" else "{}"), ref)
        conn.execute("PRAGMA foreign_keys=OFF")
        corrupt_update(conn, "WorkbenchRunJobs", sql, args)
    else:
        ref = second["source_scenario_ref"]
        sql = "DELETE FROM WorkbenchTrialScenarios WHERE scenario_ref=?" if mutation == "source_archived" else "UPDATE WorkbenchTrialScenarios SET snapshot_json=? WHERE scenario_ref=?"
        args = (ref,) if mutation == "source_archived" else ((b"{}" if mutation == "snapshot_blob" else "{}"), ref)
        conn.execute("PRAGMA foreign_keys=OFF")
        corrupt_update(conn, "WorkbenchTrialScenarios", sql, args)
    before = snapshot(conn)
    data, facts = read(trial_case, second)
    assert data["reason_code"] == reason, (data, facts.get("evidence_gap"))
    assert snapshot(conn) == before


def test_original_task_ref_mutation_and_extra_membership_are_rejected(trial_case):
    _, second = two_versions(trial_case)
    conn = trial_case.conn
    conn.execute("PRAGMA foreign_keys=OFF")
    old = conn.execute("SELECT ref FROM WorkbenchTaskRefs WHERE plan_ref=?", (second["baseline_ref"],)).fetchone()[0]
    conn.execute("UPDATE WorkbenchTaskRefs SET ref=? WHERE ref=?", ("a" * 48, old))
    conn.commit()
    data, _ = read(trial_case, second)
    assert data["reason_code"] == "adoption_reference_invalid"


def test_trial_snapshot_same_hash_but_different_persistent_task_identity_rejected(trial_case):
    _, second = two_versions(trial_case)
    corrupt_update(trial_case.conn, "WorkbenchTrialScenarioRows",
                   "UPDATE WorkbenchTrialScenarioRows SET task_ref=? WHERE scenario_ref=?", ("b" * 48, second["source_scenario_ref"]))
    data, facts = read(trial_case, second)
    assert data["reason_code"] == "adoption_snapshot_invalid", (data, facts)


def test_audit_wrong_baseline_version_does_not_choose_same_number(trial_case):
    _, second = two_versions(trial_case)
    mutate_json(trial_case.conn, "ScheduleHistory", "result_summary", lambda value: value.update(baseline_version=2), "version=2")
    data, _ = read(trial_case, second)
    assert data["reason_code"] == "adoption_snapshot_invalid"


def test_legacy_database_missing_source_table_is_an_evidence_gap(trial_case):
    _, second = two_versions(trial_case)
    conn = trial_case.conn
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("DROP TABLE WorkbenchTrialScenarioRows")
    conn.commit()
    data, facts = read(trial_case, second)
    assert data["reason_code"] == "adoption_evidence_missing"
    assert facts["evidence_gap"] == "WorkbenchTrialScenarioRows"


def test_legacy_missing_entity_table_still_propagates_storage_error(baseline_case):
    conn = baseline_case.conn
    # New unrelated tables may reference entity refs; corruption stays fixture-only.
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN")
    inputs = baseline_case.inputs()
    conn.execute("DROP TABLE WorkbenchEntityRefs")
    with pytest.raises(AppError):
        build_plan_baseline(conn, **inputs)
    conn.rollback()
