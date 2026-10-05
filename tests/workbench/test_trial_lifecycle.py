"""Real draft and scenario persistence, lossless restoration and exact refs."""

import pytest

from core.models.workbench_trial_codec import load
from tests.workbench.trial_support import (
    assert_legacy_retained,
    candidate,
    change,
    connect,
    create,
    official,
    service,
    snapshot,
)
from tests.workbench.trial_support import trial_case as trial_case


@pytest.mark.parametrize("kind", ["official", "candidate"])
def test_complete_create_change_save_and_reopen(trial_case, kind):
    case = trial_case
    intent = official(case) if kind == "official" else candidate(case)
    before = snapshot(case.conn)
    draft = create(case, intent)
    assert draft["validation"]["constraints_status"] == "valid", draft["validation"]
    assert draft["validation"]["can_adopt"] is False
    updated = change(case, draft)["data"]
    task = updated["tasks"][0]
    assert task["start"] == "2026-09-09T13:00:00"
    assert task["end"] == "2026-09-09T16:00:00"
    assert task["task_ref"] == draft["tasks"][0]["task_ref"]
    assert task["hours"] == draft["tasks"][0]["hours"]
    assert task["machine_ref"] == case.ref("machine", "M2")
    assert task["operator_ref"] == case.ref("operator", "O2")
    assert updated["validation"]["constraints_status"] == "valid", updated["validation"]
    conn = connect(case.path)
    try:
        restored = service(conn).get(draft["draft_ref"])
        assert restored["tasks"] == updated["tasks"]
        saved = service(conn).save(draft["draft_ref"], {"name": "Saved trial"}, restored["write_context"]["write_token"], "trial-save-0000000001")["data"]
        assert saved["scenario_ref"] != draft["draft_ref"]
        assert saved["tasks"][0]["task_ref"] != task["task_ref"]
        assert service(conn).scenario(saved["scenario_ref"]) == saved
        assert service(conn).get(draft["draft_ref"])["status"] == "saved"
    finally:
        conn.close()
    assert_legacy_retained(before, snapshot(case.conn))
    if kind == "candidate":
        assert "candidate_ref" in draft["base"] and "plan_ref" not in draft["base"]
        assert task["source_task_ref"] is None
        admission = load(case.conn.execute(
            "SELECT admission_json FROM WorkbenchTrialDrafts WHERE draft_ref=?", (draft["draft_ref"],)).fetchone()[0])
        assert "artifact" not in admission["source"]
        assert {"capture", "dispositions", "identity"} <= set(admission["source"])
