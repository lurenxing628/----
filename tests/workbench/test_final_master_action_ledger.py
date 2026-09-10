"""Evidence mapping rejects missing variants and never promotes siblings or V."""

import copy

import pytest

from tests.workbench.final_master_action_ledger_support import VARIANTS, bind_shared, case_bindings


def sample():
    return {"cases": [{"name": "specific", "variant": variant, "passed": True, "actions": ["covered"],
                       "step_start": 1, "step_end": 2, "screenshot": variant + ".png"} for variant in sorted(VARIANTS)]}


def test_bind_only_explicit_action_without_promoting_sibling_or_visual():
    bindings = case_bindings(sample(), {"covered", "pending"})
    action = {"gates": {gate: "pending_main_review" if gate == "V" else "pending" for gate in ("B", "K", "V", "P")},
              "evidence": []}
    ledger = {"families": [{"actions": [{**copy.deepcopy(action), "action_id": key} for key in ("covered", "pending")]}]}
    updated = bind_shared(ledger, bindings, {"source_sha256": "source"})
    covered, pending = updated["families"][0]["actions"]
    assert covered["gates"] == {"B": "reused", "K": "reused", "V": "pending_main_review", "P": "not_applicable"}
    assert pending["gates"] == action["gates"] and pending["evidence"] == []
    assert ledger["families"][0]["actions"][0]["evidence"] == []
    assert all(row["reason"] for row in covered["evidence"])


@pytest.mark.parametrize("problem", ["failed", "missing_variant", "unlisted_action", "unknown_variant"])
def test_reject_partial_or_unlisted_proof(problem):
    report = sample()
    if problem == "failed":
        report["cases"][0]["passed"] = False
    elif problem == "missing_variant":
        report["cases"].pop()
    elif problem == "unlisted_action":
        report["cases"][0]["actions"].append("unknown")
    else:
        report["cases"][0]["variant"] = "unreviewed"
    with pytest.raises(AssertionError):
        case_bindings(report, {"covered"})
