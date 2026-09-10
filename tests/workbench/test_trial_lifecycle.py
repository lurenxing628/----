"""Real draft and scenario persistence, lossless restoration and exact refs."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
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


def test_exact_display_scope_preserved_without_filtering_base(trial_case):
    case = trial_case
    second = case.operation(seq=2)
    intent = official(case, ids=[case.op_id, second])
    intent["scope"] = {"range_start": "2026-09-10T08:00:00", "range_end": "2026-09-10T09:00:00",
                       "batch_refs": [case.ref("batch", "B1")], "query": "no visible tasks"}
    draft = create(case, intent)
    assert draft["task_count"] == 2
    assert draft["scope"] == intent["scope"]
    assert any(row["predecessor_refs"] for row in draft["tasks"])


def test_restore_keeps_original_hours_and_baseline_after_new_plan(trial_case):
    case = trial_case
    draft = create(case)
    old_tasks = draft["tasks"]
    case.conn.execute("UPDATE BatchOperations SET unit_hours=99 WHERE id=?", (case.op_id,))
    case.conn.execute("UPDATE Parts SET part_name='Changed part' WHERE part_no='P1'")
    case.conn.commit()
    case.plan(2, [case.op_id], start="2026-09-10T08:00:00", end="2026-09-10T11:00:00")
    restored = service(case.conn).get(draft["draft_ref"])
    assert restored["baseline"] == draft["baseline"]
    assert restored["tasks"][0]["hours"] == old_tasks[0]["hours"]
    assert restored["tasks"][0]["original"] == old_tasks[0]["original"]
    assert restored["tasks"][0]["task_ref"] == old_tasks[0]["task_ref"]
    assert {"trial_facts_changed", "trial_baseline_changed"} <= {row["code"] for row in restored["validation"]["issues"]}
    changed = change(case, restored)["data"]
    assert changed["tasks"][0]["end"] == "2026-09-09T16:00:00"


def test_discard_only_named_draft_and_preserves_saved_scenario(trial_case):
    case = trial_case
    intent = official(case)
    first = create(case, intent)
    second = create(case, intent, key="trial-create-00000002")
    saved = service(case.conn).save(first["draft_ref"], {"name": "Keep"}, first["write_context"]["write_token"], "trial-save-0000000001")["data"]
    result = service(case.conn).discard(second["draft_ref"], {"confirm": True}, second["write_context"]["write_token"], "trial-discard-0000001")
    assert result["data"]["status"] == "discarded"
    assert service(case.conn).scenario(saved["scenario_ref"]) == saved
    assert service(case.conn).get(first["draft_ref"])["status"] == "saved"
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchTrialRows").fetchone()[0] == 2
    with pytest.raises(WorkbenchCommandRejected):
        change(case, second)


def test_complete_raw_rows_and_sqlite_types_retained(trial_case):
    case = trial_case
    case.conn.execute("UPDATE Batches SET remark=? WHERE batch_id='B1'", (sqlite_blob(),))
    case.conn.commit()
    intent = official(case)
    before = snapshot(case.conn)
    draft = create(case, intent)
    row = case.conn.execute("SELECT original_json FROM WorkbenchTrialRows").fetchone()
    original = load(row[0])
    live = dict(case.conn.execute("SELECT * FROM BatchOperations WHERE id=?", (case.op_id,)).fetchone())
    assert set(original["operation"]) == set(live)
    assert original["operation"] == live
    assert isinstance(original["batch"]["remark"], bytes)
    changed = change(case, draft)["data"]
    assert changed["tasks"][0]["hours"]["total_hours"] == 3
    assert_legacy_retained(before, snapshot(case.conn))


def sqlite_blob():
    return b"\x00legacy\xff"
