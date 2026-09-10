"""Real CQ receipts, cross connections/replay and exact preservation."""

import getpass
import json
import subprocess
import sys

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.trial_adoption_history import WorkbenchTrialAdoptionHistoryService
from tests.workbench.trial_adoption_history_support import advance, deny_writes, read, seeded
from tests.workbench.trial_adoption_history_support import trial_case as trial_case  # noqa: F401
from tests.workbench.trial_adoption_support import INTENT, saved_scenario, service
from tests.workbench.trial_support import candidate, connect, snapshot


def test_empty_requires_exact_saved_scenario(trial_case):
    saved = saved_scenario(trial_case)
    data, _ = read(trial_case, saved)
    assert data["items"] == [] and data["total_adoptions"] == 0
    assert data["source"]["scenario_ref"] == saved["scenario_ref"]
    for ref in (saved["draft_ref"], saved["base"]["plan_ref"], "f" * 48):
        with pytest.raises(WorkbenchCommandRejected) as error:
            WorkbenchTrialAdoptionHistoryService(trial_case.conn).read(ref)
        assert error.value.code == "entity_not_found"


def test_real_receipt_audit_and_source_are_bound(trial_case):
    saved, committed = seeded(trial_case)
    before = snapshot(trial_case.conn)
    denied = deny_writes(trial_case.conn)
    data, digest = read(trial_case, saved)
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["receipt_ref"] == committed["receipt_ref"]
    assert item["current_state"] == "current" and item["official_plan"]["is_current_official"]
    assert item["adoption"]["reason"] == INTENT["reason"]
    assert item["adoption"]["declared_operator"] == INTENT["declared_operator"]
    assert item["adoption"]["application_operator"] == getpass.getuser()
    assert item["evidence_gaps"] == [] and len(digest) == 64
    assert data["source"]["baseline"] == saved["baseline"]
    assert data["source"]["base"] == saved["base"]
    assert snapshot(trial_case.conn) == before and not denied
    trial_case.conn.set_authorizer(None)


def test_current_changes_replay_and_reopen_never_duplicate(trial_case):
    saved, receipt = seeded(trial_case)
    initial, original_digest = read(trial_case, saved)
    for suffix in ("db02", "db03"):
        advance(trial_case, suffix)
        with connect(trial_case.path) as peer:
            data, digest = WorkbenchTrialAdoptionHistoryService(peer).read(saved["scenario_ref"])
            replay = service(peer).adopt(saved["scenario_ref"], "expired", "db-history-adopt-0001", INTENT)
            assert replay["receipt_ref"] == receipt["receipt_ref"] and replay["replayed"]
            assert data["items"][0]["current_state"] == "historical" and digest != original_digest
            assert data["items"][0]["official_plan"]["is_current_official"] is False
            assert data["items"][0]["adoption"] == initial["items"][0]["adoption"]
            assert data["total_adoptions"] == 1
    assert trial_case.conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts WHERE action='trial.scenario.adopt'").fetchone()[0] == 3


def test_candidate_source_is_retained(trial_case):
    source = candidate(trial_case)
    saved = saved_scenario(trial_case, source, changed=False)
    from tests.workbench.trial_adoption_history_support import adopt
    adopt(trial_case, saved)
    data, _ = read(trial_case, saved)
    assert data["source"]["base"] == source["base"]
    assert not data["items"][0]["evidence_gaps"]


@pytest.mark.parametrize("mutation", ["reason", "actor", "proof", "free_text", "missing"])
def test_audit_gap_never_uses_free_text_or_logs(trial_case, mutation):
    saved, receipt = seeded(trial_case)
    version = receipt["data"]["official_plan"]["version"]
    row = trial_case.conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=?", (version,)).fetchone()
    audit = json.loads(row[0])
    if mutation == "reason":
        audit["reason"] = "Unbound replacement"
    elif mutation == "actor":
        audit["application_operator"] = "Different operator"
    elif mutation == "proof":
        audit["proof"]["scenario_hash"] = "f" * 64
    elif mutation == "missing":
        del audit["declared_operator"]
    value = "operator=somebody; adopted=true" if mutation == "free_text" else json.dumps(audit)
    trial_case.conn.execute("UPDATE ScheduleHistory SET result_summary=? WHERE version=?", (value, version))
    trial_case.conn.commit()
    before = snapshot(trial_case.conn)
    data, _ = read(trial_case, saved)
    item = data["items"][0]
    assert item["receipt_ref"] == receipt["receipt_ref"]
    assert all(value is None for value in item["adoption"].values())
    assert any(g["code"] == "audit_unproven" for g in item["evidence_gaps"])
    assert snapshot(trial_case.conn) == before


def test_newer_failed_version_does_not_make_old_receipt_current(trial_case):
    saved, _ = seeded(trial_case)
    trial_case.conn.execute("INSERT INTO ScheduleHistory(version,strategy,result_status,result_summary) VALUES (99,'manual','failed','{}')")
    trial_case.conn.commit()
    data, _ = read(trial_case, saved)
    assert data["items"][0]["current_state"] == "historical"


def test_cold_process_reads_identical_history_without_browser_or_cache(trial_case):
    saved, _ = seeded(trial_case)
    advance(trial_case)
    expected = read(trial_case, saved)
    code = """
import json, sqlite3, sys
from core.services.workbench.trial_adoption_history import WorkbenchTrialAdoptionHistoryService
conn = sqlite3.connect('file:' + sys.argv[1] + '?mode=ro', uri=True)
conn.row_factory = sqlite3.Row
try:
    print(json.dumps(WorkbenchTrialAdoptionHistoryService(conn).read(sys.argv[2])))
finally:
    conn.close()
"""
    result = subprocess.run([sys.executable, "-c", code, str(trial_case.path), saved["scenario_ref"]],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == list(expected)
