"""A completed scenario may bind only its explicitly reviewed actions and gates."""

import copy

import pytest

from tests.workbench.final_master_action_ledger_support import FOLDER, VARIANTS, read_json
from tests.workbench.final_master_domain_ledger_support import bind
from tests.workbench.final_master_domain_map_support import entry, process_mappings, resource_mappings


def sample():
    actions = [{"action_id": "WBP-PROC-001-A0" + str(i), "description": "action " + str(i),
                "gates": {"B": "pending", "K": "pending", "V": "pending_main_review", "P": "pending"}, "evidence": []}
               for i in [1, 2]]
    return {"families": [{"family_id": "WBP-PROC-001", "actions": actions}]}


def cases():
    return [{"name": "tested", "variant": variant} for variant in VARIANTS]


def test_sparse_maps_reference_only_existing_atomic_ids():
    domain = read_json(FOLDER / "actions.json")
    ids = {row["action_id"] for family in domain["families"] for row in family["actions"]}
    mappings = resource_mappings() + process_mappings()
    assert mappings and all(set(row["actions"]) <= ids for row in mappings)
    supplier = [row for row in resource_mappings() if row["case"] == "resource-files-import-4"]
    assert "WBP-PROC-021-A41" in {key for row in supplier for key in row["actions"]}
    assert all("V" not in row["gates"] for row in mappings)


def test_input_only_never_promotes_business_persistence_or_other_actions():
    ledger = sample()
    original = copy.deepcopy(ledger["families"][0]["actions"][1])
    bind(ledger, [entry("tested", "PROC-001", [1], "K")], cases(), {"source_sha256": "a" * 64})
    first, second = ledger["families"][0]["actions"]
    assert first["gates"] == {"B": "pending", "K": "reused", "V": "pending_main_review", "P": "pending"}
    assert second == original


def test_missing_variant_and_unlisted_action_are_rejected():
    with pytest.raises(AssertionError, match="Incomplete actual variants"):
        bind(sample(), [entry("tested", "PROC-001", [1])], cases()[:-1], {})
    with pytest.raises(AssertionError, match="Unknown action"):
        bind(sample(), [entry("tested", "PROC-001", [3])], cases(), {})


def test_read_only_persistence_is_explained_and_idempotent():
    ledger = sample()
    mapping = [entry("tested", "PROC-001", [1])]
    bind(ledger, mapping, cases(), {"source_sha256": "a" * 64})
    once = copy.deepcopy(ledger)
    bind(ledger, mapping, cases(), {"source_sha256": "a" * 64})
    assert ledger == once
    action = ledger["families"][0]["actions"][0]
    assert action["gates"]["P"] == "not_applicable"
    assert next(row for row in action["evidence"] if row["gate"] == "P")["reason"]
