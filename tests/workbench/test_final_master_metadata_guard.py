"""New tracking rows need exact owners; immutable history never gets a bypass."""

import copy

import pytest

from tests.workbench.final_master_metadata_guard_support import validate_metadata


def sample():
    ref = "a" * 48
    batch = {"__oracle_rowid__": 1, "ref": ref, "kind": "batch", "entity_key": "AN-B-TEST", "active": 1}
    rows = [{"__oracle_rowid__": index, "item_ref": letter * 48, "category": category, "batch_ref": ref, "task_ref": None}
            for index, letter, category in ((1, "b", "delivery"), (2, "c", "material"))]
    after = {"tables": {"WorkbenchEntityRefs": [batch], "WorkbenchPlanSourceRefs": [], "WorkbenchDashboardItems": rows,
                        "WorkbenchTemplateLineageEvents": [], "WorkbenchTemplateLineageOrigins": [], "WorkbenchOutsourcingOperationOrigins": []}}
    changes = [{"table": "WorkbenchEntityRefs", "before": None, "after": batch}]
    changes += [{"table": "WorkbenchDashboardItems", "before": None, "after": row} for row in rows]
    return changes, after


def test_exact_new_batch_dashboard_pair_is_accepted():
    changes, after = sample()
    result = validate_metadata(changes, after, "write")
    assert result["new_batch_pairs"] == 1
    assert result["accepted_append_only_tables"] == {"WorkbenchDashboardItems": 2}


def test_snapshot_row_aliases_do_not_change_business_fields():
    changes, after = sample()
    after = copy.deepcopy(after)
    for row in after["tables"]["WorkbenchDashboardItems"]:
        row["__rowid__"] = row.pop("__oracle_rowid__")
    assert validate_metadata(changes, after, "write")["new_batch_pairs"] == 1


def test_two_conflicting_row_aliases_are_rejected():
    changes, after = sample()
    changes[1]["after"]["__rowid__"] = 99
    with pytest.raises(AssertionError):
        validate_metadata(changes, after, "write")


@pytest.mark.parametrize("fault", ["read", "noop", "protected_owner", "old_identity", "update_old", "delete_old",
                                  "missing_pair", "duplicate_category", "task_target", "bad_ref", "extra_column", "missing_all"])
def test_tracking_exceptions_reject_unproven_changes(fault):
    changes, after = sample()
    policy = fault if fault in ("read", "noop") else "write"
    if fault == "protected_owner":
        after["tables"]["WorkbenchEntityRefs"][0]["entity_key"] = "ORIGINAL-B"
    elif fault == "old_identity":
        changes[0]["before"] = copy.deepcopy(changes[0]["after"])
    elif fault == "update_old":
        changes[1]["before"] = copy.deepcopy(changes[1]["after"])
    elif fault == "delete_old":
        changes[1]["before"], changes[1]["after"] = changes[1]["after"], None
    elif fault == "missing_pair":
        changes.pop()
    elif fault == "duplicate_category":
        changes[2]["after"]["category"] = "delivery"
    elif fault == "task_target":
        changes[1]["after"]["task_ref"] = "d" * 48
    elif fault == "bad_ref":
        changes[1]["after"]["item_ref"] = "not-a-ref"
    elif fault == "extra_column":
        changes[1]["after"]["ignored"] = True
    elif fault == "missing_all":
        changes = changes[:1]
    with pytest.raises(AssertionError):
        validate_metadata(changes, after, policy)


def test_new_operation_cannot_omit_origins():
    _, after = sample()
    operation = {"ref": "d" * 48, "kind": "operation", "source_key": "1", "alternate_key": "AN-B-TEST_10"}
    after["tables"]["WorkbenchPlanSourceRefs"].append(operation)
    with pytest.raises(AssertionError):
        validate_metadata([{"table": "WorkbenchPlanSourceRefs", "before": None, "after": operation}], after, "write")
