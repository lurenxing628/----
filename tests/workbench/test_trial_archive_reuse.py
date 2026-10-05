"""Trial writes retain archive integrity and refresh authoritative mutable state once."""

from collections import Counter
from types import SimpleNamespace

import pytest

from core.models import workbench_trial_codec as codec
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_trial_scenario_archive import scenario_archive
from core.services.workbench.facts import trial_policy
from core.services.workbench.facts.trial_scenario_archive import load_saved_scenario
from core.services.workbench.plan.adoption_baseline_values import same
from core.services.workbench.trial import adoption_history_evidence
from core.services.workbench.trial.adoption_history_evidence import matches
from core.services.workbench.trial.adoption_history_policy import MAX_SCENARIO_BYTES
from data.repositories.workbench_trial_adoption_history import TrialAdoptionHistoryRepository
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository
from tests.workbench.trial_support import change, create, service
from tests.workbench.trial_support import trial_case as trial_case


class StoredWrites:
    in_transaction = True
    rowcount = 1

    def __init__(self):
        self.writes = []

    def execute(self, sql, parameters):
        self.writes.append(parameters)
        return self

    def executemany(self, sql, parameters):
        self.writes.extend(parameters)


def test_archive_text_and_digest_share_one_lossless_encoding(monkeypatch):
    admission = {"input": {"base": {"plan_ref": "original-plan"}}, "raw": b"\x00legacy\xff"}
    original = {"raw": float("nan"), "value": -0.0}
    row = {"row_ref": "row", "task_ref": "task", "operation_ref": "operation", "source_task_ref": None,
           "source_row_ref": "source", "original": original, "current": {"start": "2026-09-09T08:00:00"}}
    checked = {"issues": []}
    snapshot = {"scenario_ref": "scenario", "name": "Saved trial", "tasks": [], "validation": checked}
    tracked = {id(admission), id(original), id(snapshot)}
    encodings = Counter()
    pack = codec.packed

    def counted(value):
        if id(value) in tracked:
            encodings[id(value)] += 1
        return pack(value)

    monkeypatch.setattr(codec, "packed", counted)
    conn = StoredWrites()
    repo = WorkbenchTrialRepository(conn)
    ref = repo.create(admission, [row], checked, "create", "operator", "2026-09-10T12:00:00")
    stored_admission, stored_original = conn.writes[:2]
    assert codec.load(stored_admission[3], stored_admission[4])["raw"] == admission["raw"]
    restored = codec.load(stored_original[7], stored_original[8])
    assert restored["raw"] != restored["raw"]
    assert restored["value"].hex() == original["value"].hex()
    repo.save({"draft_ref": ref, "revision": 1}, snapshot, "save", "operator", "2026-09-10T12:00:00")
    archive = codec.load(conn.writes[2][4])
    assert archive == {"format": "permanent_rows_v1", "snapshot": {key: value for key, value in snapshot.items() if key != "tasks"},
                       "task_row_refs": []}
    assert encodings == {id(admission): 1, id(original): 1, id(snapshot): 1}
    assert conn.writes[2][5] == codec.fingerprint(snapshot)


def test_change_refreshes_storage_without_rechecking_immutable_archives(trial_case, monkeypatch):
    case = trial_case
    draft = create(case)
    verified = []
    load = trial_policy.load_object

    def counted(text, fingerprint=None):
        if fingerprint is not None:
            verified.append(fingerprint)
        return load(text, fingerprint)

    monkeypatch.setattr(trial_policy, "load_object", counted)
    updated = change(case, draft)["data"]
    assert len(verified) == 1 + draft["task_count"]
    head = WorkbenchTrialRepository(case.conn).draft_header(draft["draft_ref"])
    assert head["revision"] == 2
    assert updated["updated_at"] == head["updated_at"]
    assert len(updated["change_history"]) == 1
    restored = service(case.conn).get(draft["draft_ref"])
    assert restored["tasks"] == updated["tasks"]
    assert restored["validation_at_last_write"] == updated["validation_at_last_write"]
    assert restored["validation"] == updated["validation"]


def test_saved_scenario_reuses_the_verified_header(trial_case, monkeypatch):
    draft = create(trial_case)
    result = service(trial_case.conn).save(draft["draft_ref"], {"name": "Saved trial"},
        draft["write_context"]["write_token"], "trial-archive-save-0001")
    saved = result["data"]
    header = WorkbenchTrialRepository(trial_case.conn).scenario_header(saved["scenario_ref"])
    archive = codec.load(header["snapshot_json"])
    assert "tasks" not in archive["snapshot"]
    assert archive["task_row_refs"] == [row["row_ref"] for row in saved["tasks"]]
    trial_case.conn.execute("UPDATE Operators SET name='Changed after save' WHERE operator_id='O1'")
    trial_case.conn.commit()
    replay = service(trial_case.conn).save(draft["draft_ref"], {"name": "Saved trial"},
        "expired", "trial-archive-save-0001")
    assert replay == dict(result, replayed=True)
    assert service(trial_case.conn).lookup("trial-archive-save-0001") == replay
    reads = []
    scenario_header = WorkbenchTrialRepository.scenario_header

    def counted(repo, ref):
        reads.append(ref)
        return scenario_header(repo, ref)

    monkeypatch.setattr(WorkbenchTrialRepository, "scenario_header", counted)
    assert load_saved_scenario(trial_case.conn, saved["scenario_ref"])[0] == saved
    assert reads == [saved["scenario_ref"]]


@pytest.mark.parametrize("compact", [False, True])
def test_scenario_formats_keep_original_task_order_and_lossless_values(compact):
    tasks = [{"row_ref": "second", "value": b"\x00legacy\xff"}, {"row_ref": "first", "value": -0.0}]
    snapshot = {"scenario_ref": "saved", "name": "Historical trial", "tasks": tasks}
    archive = scenario_archive(snapshot) if compact else snapshot
    text = codec.dump(archive)
    repo = SimpleNamespace(schema_issues=lambda: [],
        scenario_header=lambda ref: {"snapshot_json": text, "snapshot_hash": codec.fingerprint(snapshot)},
        scenario_rows=lambda ref: [{"row_ref": row["row_ref"], "payload_json": codec.dump(row)} for row in reversed(tasks)])
    restored = trial_policy.load_scenario(repo, "saved")
    assert codec.same(restored, snapshot)
    assert [row["row_ref"] for row in restored["tasks"]] == ["second", "first"]


@pytest.mark.parametrize("mutation", ["body", "order", "missing", "duplicate"])
def test_compact_scenario_still_rejects_changed_body_or_order(mutation):
    tasks = [{"row_ref": "second", "value": 3}, {"row_ref": "first", "value": 4}]
    snapshot = {"scenario_ref": "saved", "tasks": tasks}
    archive = scenario_archive(snapshot)
    stored = [{"row_ref": row["row_ref"], "payload_json": codec.dump(row)} for row in tasks]
    if mutation == "body":
        stored[0]["payload_json"] = codec.dump(dict(tasks[0], value=5))
    elif mutation == "order":
        archive["task_row_refs"].reverse()
    elif mutation == "missing":
        stored.pop()
    else:
        archive["task_row_refs"] = ["second", "second"]
    repo = SimpleNamespace(schema_issues=lambda: [],
        scenario_header=lambda ref: {"snapshot_json": codec.dump(archive), "snapshot_hash": codec.fingerprint(snapshot)},
        scenario_rows=lambda ref: stored)
    with pytest.raises(WorkbenchCommandRejected) as error:
        trial_policy.load_scenario(repo, "saved")
    assert error.value.code == "trial_snapshot_invalid"


def test_history_bounds_full_save_receipt_before_reconstructing_tasks(trial_case, monkeypatch):
    draft = create(trial_case)
    saved = service(trial_case.conn).save(draft["draft_ref"], {"name": "Saved trial"},
        draft["write_context"]["write_token"], "trial-archive-save-0001")["data"]
    monkeypatch.setattr(TrialAdoptionHistoryRepository, "receipt_size",
        lambda repo, key: {"bytes": MAX_SCENARIO_BYTES + 1})

    def should_not_reconstruct(repo, ref):
        pytest.fail("An oversized complete saved body must be rejected before reconstructing its tasks")

    monkeypatch.setattr(adoption_history_evidence, "load_scenario", should_not_reconstruct)
    with pytest.raises(WorkbenchCommandRejected) as error:
        adoption_history_evidence.scenario_evidence(trial_case.conn, saved["scenario_ref"])
    assert error.value.code == "query_too_large"


@pytest.mark.parametrize("left,right,equal", [
    (True, 1, False), (1, 1.0, False), (0.0, -0.0, False),
    (float("nan"), float("nan"), True), (float("nan"), float("inf"), False),
    (b"\x00\xff", b"\x00\xff", True), (b"\x00\xff", b"\x00\xfe", False),
    ([1, True], (1, True), True), ({"a": 1, "b": 2}, {"b": 2, "a": 1}, True),
])
def test_adoption_equality_keeps_lossless_type_semantics(left, right, equal):
    assert same(left, right) is equal
    assert matches({"value": left, "unrelated": "kept"}, {"value": right}) is equal
