"""Regression tests for candidate trial base preparation reuse without full summary or metrics projection."""

from collections import Counter

from core.services.workbench.facts import candidate_projection
from core.services.workbench.trial.base import _candidate
from tests.workbench.trial_support import candidate, trial_case

__all__ = ["trial_case"]


def test_trial_candidate_base_validates_completeness_once_without_metrics_or_business_clones(
    trial_case, monkeypatch
):
    case = trial_case
    intent = candidate(case)
    candidate_ref = intent["base"]["candidate_ref"]

    calls = Counter()
    for name in (
        "_check_candidate_row",
        "_validate_business_candidate_fields",
        "completion",
        "metrics",
        "business_candidate_fields",
    ):
        original = getattr(candidate_projection, name)

        def tracked(*args, _name=name, _original=original, **kwargs):
            calls[_name] += 1
            return _original(*args, **kwargs)

        monkeypatch.setattr(candidate_projection, name, tracked)

    rows, extra, _all_ops, _op_refs, issues, _facts = _candidate(case.conn, candidate_ref)

    assert len(rows) == 1
    assert issues == []
    assert extra["identity"] == {
        "candidate_ref": candidate_ref,
        "run_ref": extra["identity"]["run_ref"],
        "kind": "candidate",
        "display_name": extra["identity"]["display_name"],
        "completeness": "complete",
    }
    assert isinstance(extra["identity"]["display_name"], str) and extra["identity"]["display_name"]
    assert calls["_check_candidate_row"] == 1
    assert calls["_validate_business_candidate_fields"] == 1
    assert calls["completion"] == 1
    assert calls["metrics"] == 0
    assert calls["business_candidate_fields"] == 0
