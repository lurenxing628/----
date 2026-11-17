"""Regression tests for candidate trial base preparation reuse without full summary or metrics projection."""

from collections import Counter
from copy import deepcopy

import pytest

from core.models.content import StoredJsonCorrupt
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts import candidate_archive, candidate_projection
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.trial import base as trial_base
from core.services.workbench.trial.base import _candidate
from tests.workbench.trial_support import candidate, create, service, trial_case

__all__ = ["trial_case"]


def test_trial_candidate_base_validates_completeness_once_without_metrics_or_business_clones(
    trial_case, monkeypatch
):
    case = trial_case
    intent = candidate(case)
    candidate_ref = intent["base"]["candidate_ref"]

    calls = Counter()
    # Completeness is computed where the trial base and the adoption scope proof call it.
    for module, name in (
        (trial_base, "candidate_completeness"),
        (candidate_archive, "candidate_completeness"),
        (candidate_projection, "metrics"),
        (candidate_projection, "business_candidate_fields"),
    ):
        original = getattr(module, name)

        def tracked(*args, _name=name, _original=original, **kwargs):
            calls[_name] += 1
            return _original(*args, **kwargs)

        monkeypatch.setattr(module, name, tracked)

    rows, source, _all_ops, issues = _candidate(case.conn, candidate_ref)

    identity = source.document["identity"]
    assert len(rows) == 1
    assert issues == []
    assert identity == {
        "candidate_ref": candidate_ref,
        "kind": "candidate",
        "display_name": identity["display_name"],
        "completeness": "complete",
    }
    assert isinstance(identity["display_name"], str) and identity["display_name"]
    assert calls["candidate_completeness"] == 1
    assert calls["metrics"] == 0
    assert calls["business_candidate_fields"] == 0


def test_candidate_trial_effort_names_its_source_run(trial_case):
    case = trial_case
    intent = candidate(case)
    run_ref = case.conn.execute(
        "SELECT run_ref FROM WorkbenchRunCandidates WHERE candidate_ref=?", (intent["base"]["candidate_ref"],)
    ).fetchone()[0]
    draft = create(case, intent)
    reopened = service(case.conn).get(draft["draft_ref"])
    for view in (draft, reopened):
        assert view["base_identity"]["run_ref"] == run_ref
        for task in view["tasks"]:
            assert task["operation_effort"]["before"]["evidence_source"]["run_ref"] == run_ref


@pytest.mark.parametrize("damage", ["archive_shape", "unreadable_json"])
def test_damaged_candidate_run_behind_a_saved_trial_is_a_storage_error(trial_case, monkeypatch, damage):
    case = trial_case
    draft = create(case, candidate(case))
    read = CandidateStore.capture

    def damaged(store, run_ref):
        if damage == "unreadable_json":
            raise StoredJsonCorrupt()
        capture = dict(read(store, run_ref))
        facts = deepcopy(capture["facts"])
        facts["columns"]["Parts"] = facts["columns"]["Parts"][::-1]
        capture["facts"] = facts
        return capture

    monkeypatch.setattr(CandidateStore, "capture", damaged)
    with pytest.raises(WorkbenchCommandRejected) as rejected:
        service(case.conn).get(draft["draft_ref"])
    # The run record itself is damaged: reported as such, never as a draft the user should rebuild (409).
    expected = "storage_failure" if damage == "unreadable_json" else "candidate_artifact_invalid"
    assert (rejected.value.code, rejected.value.status) == (expected, 500)
