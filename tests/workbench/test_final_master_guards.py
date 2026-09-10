"""The startup-audit allowance never permits business edits or old-row loss."""

import copy
import json

import pytest

from tests.workbench.final_master_fixture_support import changed_sources
from tests.workbench.final_master_preservation_support import restart_preservation


def samples():
    before = {"schema": [], "integrity": "ok", "foreign_keys": [], "tables": {
        "Parts": [{"part_no": "ORIGINAL", "remark": "keep"}], "OperationLogs": [{"id": 1, "detail": "old"}],
        "sqlite_sequence": [{"name": "OperationLogs", "seq": 1}]}}
    after = copy.deepcopy(before)
    after["tables"]["OperationLogs"].append({"id": 2, "module": "plugins", "action": "load",
        "target_type": "runtime", "target_id": "plugins", "log_level": "INFO", "error_code": None,
        "error_message": None, "detail": json.dumps({"loaded_at": "2026-09-10T20:00:00",
            "statuses": [{"enabled": "no", "loaded": "no", "error": None}]})})
    after["tables"]["sqlite_sequence"][0]["seq"] = 2
    return before, after


def test_restart_only_appends_observed_plugin_audit():
    before, after = samples()
    result = restart_preservation(before, after)
    assert result["passed"] and result["business_rows_exact"]
    assert result["original_audits_retained"] == 1


def test_source_diff_includes_added_deleted_and_changed_paths():
    assert changed_sources({"same": "a", "changed": "a", "deleted": "a"},
                           {"same": "a", "changed": "b", "added": "b"}) == ["added", "changed", "deleted"]


@pytest.mark.parametrize("change", ["part", "old_log", "extra_log", "wrong_action", "sequence", "foreign_key"])
def test_restart_rejects_unrelated_changes(change):
    before, after = samples()
    if change == "part":
        after["tables"]["Parts"][0]["remark"] = "lost"
    elif change == "old_log":
        after["tables"]["OperationLogs"][0]["detail"] = "overwritten"
    elif change == "extra_log":
        after["tables"]["OperationLogs"].append({"id": 3})
    elif change == "wrong_action":
        after["tables"]["OperationLogs"][1]["action"] = "delete"
    elif change == "sequence":
        after["tables"]["sqlite_sequence"][0]["seq"] = 3
    else:
        after["foreign_keys"] = [["Parts", 1, "Materials", 0]]
    with pytest.raises(AssertionError):
        restart_preservation(before, after)
