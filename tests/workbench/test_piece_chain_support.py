"""EF real worker/SQLite fixtures; no prepared input or guard substitutions."""

import json

from tests.workbench.test_piece_adoption_support import split
from tests.workbench.test_run_candidate_adoption_support import INTENT, assert_retained
from tests.workbench.test_run_candidate_adoption_support import service as candidate_adoption
from tests.workbench.test_run_candidate_support import compute
from tests.workbench.trial_adoption_support import service as trial_adoption
from tests.workbench.trial_support import change, create, snapshot
from tests.workbench.trial_support import service as trial_service
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401


def piece_candidate(case, *, parallel=True, common=True, unit=0.25):
    ids = piece_layout(case, parallel=parallel, common=common, unit=unit)
    run_ref, refs = compute(case)
    row = case.conn.execute("SELECT * FROM WorkbenchRunJobs WHERE run_ref=?", (run_ref,)).fetchone()
    assert row["state"] == "complete", dict(row)
    return ids, run_ref, refs


def piece_layout(case, *, parallel=True, common=True, unit=0.25):
    ids = split(case, common=common, unit=unit)
    if parallel:
        for index, piece in enumerate(("item-A", "item-B", "item-C"), 1):
            case.conn.execute("UPDATE BatchOperations SET machine_id=?,operator_id=? WHERE piece_id=?",
                              ("M" + str(index), "O" + str(index), piece))
        case.conn.commit()
    return ids


def artifact(case, ref):
    raw = case.conn.execute("SELECT artifact_json FROM WorkbenchRunCandidates WHERE candidate_ref=?", (ref,)).fetchone()[0]
    return json.loads(raw)


def adopt_candidate(case, ref, key="ef-candidate-adopt-0001"):
    svc = candidate_adoption(case.conn)
    preview = svc.preview(ref)
    assert preview["validation"]["can_adopt"], preview
    before = snapshot(case.conn)
    result = svc.adopt(ref, preview["write_context"]["write_token"], key, INTENT)
    assert result["ok"], result
    assert_retained(before, snapshot(case.conn))
    return result


def saved_trial(case, base, *, op_id=None):
    draft = create(case, {"base": base}, key="ef-piece-trial-create-0001")
    assert draft["validation"]["constraints_status"] == "valid", draft["validation"]
    operation_ref = None if op_id is None else case.conn.execute(
        "SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1", (str(op_id),)).fetchone()[0]
    index = len(draft["tasks"]) - 1 if op_id is None else next(
        index for index, row in enumerate(draft["tasks"])
        if row["operation_ref"] == operation_ref)
    result = change(case, draft, task=index, start="2026-09-09T13:00:00", key="ef-piece-trial-change-0001")
    assert result["ok"], result
    changed = result["data"]
    assert changed["validation"]["constraints_status"] == "valid", changed["validation"]
    saved = trial_service(case.conn).save(changed["draft_ref"], {"name": "EF exact split work"},
        changed["write_context"]["write_token"], "ef-piece-trial-save-0001")
    assert saved["ok"], saved
    return draft, changed, saved["data"]


def adopt_trial(case, saved, key="ef-piece-trial-adopt-0001"):
    svc = trial_adoption(case.conn)
    preview = svc.preview(saved["scenario_ref"])
    assert preview["validation"]["can_adopt"], preview
    before = snapshot(case.conn)
    result = svc.adopt(saved["scenario_ref"], preview["write_context"]["write_token"], key, INTENT)
    assert result["ok"], result
    assert_retained(before, snapshot(case.conn))
    return result
