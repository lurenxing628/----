"""Relationship revisions require precise owners and counts, not just monotonicity."""

import copy

import pytest

from tests.workbench.final_master_resource_revisions_support import (
    expected_original_revisions,
    verify_original_revisions,
)


def test_related_parent_revision_matches_create_and_delete():
    old = [{"ref": "group", "kind": "machine_group", "entity_key": "RT-G", "revision": 2, "active": 1},
           {"ref": "protected", "kind": "material", "entity_key": "ORIGINAL", "revision": 1, "active": 1}]
    new = copy.deepcopy(old)
    new[0]["revision"] = 4
    cases = [{"state": "1920-light", "name": name, "status": "passed"} for name in ("create-2", "cancel-update-delete-2")]
    result = verify_original_revisions(old, new, cases)
    assert result["passed"] and result["observed"][0]["increment"] == 2
    for field, value in (("revision", 5), ("active", 0), ("entity_key", "changed")):
        invalid = copy.deepcopy(new)
        invalid[0][field] = value
        with pytest.raises(AssertionError):
            verify_original_revisions(old, invalid, cases)


def test_import_cleanup_has_exact_22_relationship_mutations_per_parent():
    cases = [{"state": "1392-dark", "name": name, "status": "passed"} for name in (
        "resource-files-import-3", "resource-files-bulk-delete-3")]
    result, _ = expected_original_revisions(cases)
    assert dict(result) == {("op_type", "RT-IN"): 44, ("shift_profile", "RT-SH"): 44}


def test_failed_case_cannot_justify_revision_and_duplicate_case_is_rejected():
    case = {"state": "1920-light", "name": "create-2", "status": "failed"}
    assert not expected_original_revisions([case])[0]
    with pytest.raises(AssertionError):
        expected_original_revisions([case, case])


def test_unknown_original_identity_revision_is_rejected():
    old = [{"ref": "protected", "kind": "material", "entity_key": "ORIGINAL", "revision": 1}]
    with pytest.raises(AssertionError):
        verify_original_revisions(old, [{**old[0], "revision": 2}], [])


def test_supplier_file_index_differs_from_create_index():
    cases = [{"state": "1920-light", "name": name, "status": "passed"} for name in (
        "create-5", "cancel-update-delete-5", "resource-files-import-4", "resource-files-bulk-delete-4")]
    result, _ = expected_original_revisions(cases)
    assert dict(result) == {("op_type", "RT-EX"): 46}
