"""Real draft and scenario persistence, lossless restoration and exact refs."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_trial_codec import dump, load
from core.services.workbench.facts.trial_policy import load_scenario_record
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository
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
    repo = WorkbenchTrialRepository(case.conn)
    stored_header = repo.scenario_header(saved["scenario_ref"])
    assert stored_header["snapshot_hash"] is None
    assert repo.draft_header(draft["draft_ref"])["admission_hash"] is None
    assert all(row["original_hash"] is None for row in repo.draft_rows(draft["draft_ref"]))
    if kind == "official":
        # The original full-snapshot format and its old metadata remain readable.
        old_header = dict(stored_header, snapshot_json=dump(saved), snapshot_hash="legacy-saved-marker")
        stored_rows = deepcopy(repo.scenario_rows(saved["scenario_ref"]))
        old_repo = SimpleNamespace(schema_issues=lambda: [], scenario_header=lambda _ref: old_header,
                                   scenario_rows=lambda _ref: stored_rows)
        assert load_scenario_record(old_repo, saved["scenario_ref"])[1] == saved
        assert old_header["snapshot_hash"] == "legacy-saved-marker"
        # Python equality merges True and 1; permanent rows must keep the stored type.
        altered = load(stored_rows[0]["payload_json"])
        assert altered["sequence"] == 1
        altered["sequence"] = True
        stored_rows[0]["payload_json"] = dump(altered)
        with pytest.raises(WorkbenchCommandRejected) as error:
            load_scenario_record(old_repo, saved["scenario_ref"])
        assert error.value.code == "trial_snapshot_invalid"
    if kind == "candidate":
        assert "candidate_ref" in draft["base"] and "plan_ref" not in draft["base"]
        assert task["source_task_ref"] is None
        admission = load(case.conn.execute(
            "SELECT admission_json FROM WorkbenchTrialDrafts WHERE draft_ref=?", (draft["draft_ref"],)).fetchone()[0])
        assert "artifact" not in admission["source"]
        assert {"capture", "dispositions", "identity"} <= set(admission["source"])
