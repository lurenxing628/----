"""Real candidate -> official v1 -> trial -> official v2, including original identity."""

import sqlite3

import pytest

from core.models.workbench_trial_codec import fingerprint
from tests.workbench.plan_read_support import make_api
from tests.workbench.test_plan_adoption_baseline_support import adopt_candidate, adopt_trial, read, two_versions
from tests.workbench.test_plan_adoption_baseline_support import trial_case as trial_case  # noqa: F401
from tests.workbench.test_run_candidate_adoption_support import snapshot
from tests.workbench.trial_adoption_support import INTENT, saved_scenario
from tests.workbench.trial_adoption_support import service as trial_service
from tests.workbench.trial_support import candidate as unadopted_candidate


@pytest.mark.parametrize("source", ["candidate", "trial"])
def test_two_real_adoptions_use_original_full_official_tasks(trial_case, source):
    case = trial_case
    first, second = two_versions(case, source)
    data, facts = read(case, second)
    assert data["state"] == "available", (data, facts.get("evidence_gap"))
    assert data["basis"] == source + "_adoption"
    assert data["baseline_plan"]["plan_ref"] == first["plan_ref"] == second["baseline_ref"]
    assert data["baseline_plan"]["is_current_official"] is False
    item = data["items"][0]
    assert item["before"]["plan_ref"] == first["plan_ref"]
    assert item["after"]["plan_ref"] == second["plan_ref"]
    assert item["before"]["task_ref"] != item["after"]["task_ref"]
    assert item["before"]["operation_ref"] == item["after"]["operation_ref"]
    api = make_api(case.path)
    original = api.read("/" + first["plan_ref"] + "/workspace")["data"]["tasks"]
    assert [item["before"] for item in data["items"]] == original
    assert api.read("/" + second["plan_ref"] + "/workspace")["data"]["projections"]["baseline"] == data


def test_first_adoption_records_no_baseline_not_not_recorded(trial_case):
    official = adopt_candidate(trial_case)
    data, facts = read(trial_case, official)
    assert data["state"] == "unavailable" and data["reason_code"] == "no_adoption_baseline", facts
    assert data["baseline_plan"] is None and not data["items_complete"]


def test_first_trial_adoption_records_empty_official_baseline(trial_case):
    saved = saved_scenario(trial_case, unadopted_candidate(trial_case))
    service = trial_service(trial_case.conn)
    preview = service.preview(saved["scenario_ref"])
    result = service.adopt(saved["scenario_ref"], preview["write_context"]["write_token"], "da-first-trial-adopt", INTENT)
    data, facts = read(trial_case, result["data"]["official_plan"])
    assert data["reason_code"] == "no_adoption_baseline", (data, facts)


def test_never_infers_version_minus_one_or_current_official(trial_case):
    first = adopt_candidate(trial_case)
    trial_case.conn.execute("INSERT INTO ScheduleVersionSeq(version) VALUES (11)")
    trial_case.conn.commit()
    second, _ = adopt_trial(trial_case, first)
    assert second["version"] == 12
    before, _ = read(trial_case, second)
    third = adopt_candidate(trial_case, "third")
    after, _ = read(trial_case, second)
    assert after["items"] == before["items"]
    assert after["baseline_plan"]["plan_ref"] == first["plan_ref"] != third["plan_ref"]


def test_either_side_half_open_range_keeps_both_unclipped(trial_case):
    _, second = two_versions(trial_case)
    full, _ = read(trial_case, second)
    assert full["state"] == "available"
    before, after = full["items"][0]["before"], full["items"][0]["after"]
    assert before["end"] < after["start"]
    for side, start, end in (("before", before["start"], before["end"]), ("after", after["start"], after["end"])):
        data, _ = read(trial_case, second, start, end)
        item = data["items"][0]
        assert item["before"] == before and item["after"] == after
        assert item[side + "_in_scope"] and not item[("after" if side == "before" else "before") + "_in_scope"]
    empty, _ = read(trial_case, second, before["end"], after["start"])
    assert empty["state"] == "available" and empty["items"] == [] and empty["items_complete"]


def test_readonly_all_original_values_types_and_restart(trial_case):
    first, second = two_versions(trial_case)
    case = trial_case
    original, changes = snapshot(case.conn), case.conn.total_changes
    trace = []
    case.conn.execute("PRAGMA query_only=ON")
    case.conn.set_trace_callback(trace.append)
    first_read = read(case, second)
    case.conn.set_trace_callback(None)
    assert first_read[0]["state"] == "available", first_read
    assert snapshot(case.conn) == original and case.conn.total_changes == changes
    assert all(sql.lstrip().upper().startswith(("SELECT", "WITH", "BEGIN", "COMMIT", "--")) for sql in trace)
    old = case.conn
    case.conn = sqlite3.connect(str(case.path), detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    case.conn.row_factory = sqlite3.Row
    case.conn.execute("PRAGMA query_only=ON")
    try:
        reopened = read(case, second)
        assert reopened == first_read
        assert read(case, first)[0]["reason_code"] == "no_adoption_baseline"
    finally:
        case.conn.close()
        case.conn = old


def test_historical_labels_not_current_same_number_metadata(trial_case):
    _, second = two_versions(trial_case)
    original, _ = read(trial_case, second)
    trial_case.conn.execute("UPDATE BatchOperations SET op_type_name='Changed current label'")
    trial_case.conn.commit()
    changed, _ = read(trial_case, second)
    assert changed["state"] == "available"
    assert changed["items"][0]["before"] == original["items"][0]["before"]
    assert changed["items"][0]["after"]["process_label"] == "Changed current label"


def test_offscreen_original_raw_change_invalidates_snapshot(trial_case):
    first, second = two_versions(trial_case)
    before, facts = read(trial_case, second, "2026-09-09T13:00:00", "2026-09-09T14:00:00")
    trial_case.conn.execute("UPDATE Schedule SET created_at=? WHERE version=?", (sqlite3.Binary(b"original blob"), first["version"]))
    trial_case.conn.commit()
    after, changed = read(trial_case, second, "2026-09-09T13:00:00", "2026-09-09T14:00:00")
    assert before["state"] == "available" and after["reason_code"] == "adoption_baseline_drift"
    assert fingerprint(facts) != fingerprint(changed)
