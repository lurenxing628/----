"""Whole-database retention checks for real task C resource UI commands."""

import json


def restart_preservation(before, after):
    assert before["schema"] == after["schema"]
    assert after["integrity"] == "ok" and after["foreign_keys"] == []
    changed = []
    for table, old in before["tables"].items():
        if table not in ("OperationLogs", "sqlite_sequence"):
            assert after["tables"][table] == old, "Restart changed business rows: " + table
        elif after["tables"][table] != old:
            changed.append(table)
    old_logs, new_logs = before["tables"]["OperationLogs"], after["tables"]["OperationLogs"]
    assert new_logs[:len(old_logs)] == old_logs
    appended = new_logs[len(old_logs):]
    assert len(appended) == 1, "Factory restart must append its one observed plugin audit"
    entry = appended[0]
    assert entry["module"] == "plugins" and entry["action"] == "load"
    assert entry["target_type"] == "runtime" and entry["target_id"] == "plugins"
    assert entry["log_level"] == "INFO" and entry["error_code"] is None and entry["error_message"] is None
    detail = json.loads(entry["detail"])
    assert detail["loaded_at"] and detail["statuses"]
    assert all(row["enabled"] == "no" and row["loaded"] == "no" and row["error"] is None for row in detail["statuses"])
    sequences = {row["name"]: row for row in after["tables"]["sqlite_sequence"]}
    assert set(sequences) == {row["name"] for row in before["tables"]["sqlite_sequence"]}
    for row in before["tables"]["sqlite_sequence"]:
        expected = dict(row)
        if row["name"] == "OperationLogs":
            expected["seq"] += 1
        assert sequences[row["name"]] == expected
    return {"passed": True, "business_rows_exact": True, "original_audits_retained": len(old_logs),
            "startup_audits_appended": appended, "changed_tables": changed,
            "reason": "Real factory bootstrap_plugins appends exactly one successful disabled-plugin startup audit"}


def resource_preservation(before, after, probe, root=None, initial_pid=None):
    from tests.workbench.final_master_config_preservation_support import config_preservation
    from tests.workbench.final_master_resource_revisions_support import verify_original_revisions

    assert before["schema"] == after["schema"]
    assert after["integrity"] == "ok" and after["foreign_keys"] == []
    metadata = {"WorkbenchEntityRefs", "WorkbenchCommandReceipts", "sqlite_sequence"}
    config = config_preservation(before, after, root, probe["commands"], initial_pid)
    if config["rows_added"]:
        metadata.add("ScheduleConfig")
    checked = []
    for table, old in before["tables"].items():
        if table not in metadata:
            assert after["tables"][table] == old, "Unexpected business mutation: " + table
            checked.append(table)
    revisions = verify_original_revisions(before["tables"]["WorkbenchEntityRefs"], after["tables"]["WorkbenchEntityRefs"], probe["cases"])
    old_keys = {row["request_key"] for row in before["tables"]["WorkbenchCommandReceipts"]}
    receipts = {row["request_key"]: row for row in after["tables"]["WorkbenchCommandReceipts"]}
    for row in before["tables"]["WorkbenchCommandReceipts"]:
        assert receipts[row["request_key"]] == row
    observed = {row["request_key"]: row["receipt_ref"] for row in probe["commands"] if row.get("receipt_ref")}
    assert set(receipts) - old_keys == set(observed)
    assert all(receipts[key]["receipt_ref"] == value for key, value in observed.items())
    sequences = {row["name"]: row["seq"] for row in after["tables"]["sqlite_sequence"]}
    assert all(sequences[row["name"]] >= row["seq"] for row in before["tables"]["sqlite_sequence"])
    return {"passed": True, "schema_unchanged": True, "business_tables_exact": checked,
            "config_bootstrap": config,
            "original_revision_proof": revisions,
            "original_identities_retained": len(before["tables"]["WorkbenchEntityRefs"]),
            "new_receipts_matched_to_actual_commands": len(observed)}


def process_batch_preservation(before, after, root=None):
    from tests.workbench.final_master_metadata_guard_support import TABLES, changes_between, validate_metadata
    from tests.workbench.migrated_process_batch_oracle import preservation

    def compatible(value):
        return {**value, "tables": {table: [{("__oracle_rowid__" if key == "__rowid__" else key): field
                 for key, field in row.items()} for row in rows] for table, rows in value["tables"].items()}}

    metadata = validate_metadata(changes_between(before, after), after, "write", root)
    original = {**after, "tables": {**after["tables"], **{table: before["tables"][table] for table in TABLES}}}
    result = preservation(compatible(before), compatible(original))
    result["tracking_preservation"] = metadata
    result["actual_changed_tables"] = {table: {"before_rows": len(rows), "after_rows": len(after["tables"][table])}
                                      for table, rows in before["tables"].items() if rows != after["tables"][table]}
    return result
