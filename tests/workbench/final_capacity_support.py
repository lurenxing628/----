"""Dense workload seed and full persisted-result checks; no optimizer substitute."""

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

RUN_TABLES = frozenset(("WorkbenchRunJobs", "WorkbenchRunReceipts", "WorkbenchRunCandidates",
                        "WorkbenchRunCandidateTasks", "WorkbenchCommandReceipts"))


def seed_dense(app, *, operations, batches=100, **_fixture_options):
    from core.infrastructure.database import get_connection
    from core.services.scheduler.config.config_field_spec import default_snapshot_values
    from tests.workbench.test_run_compute_support import RunCase

    if not 1 <= batches <= 100 or not 1 <= operations <= 50:
        raise ValueError("Dense fixture requires 1..100 batches and 1..50 operations")
    with closing(get_connection(app.config["DATABASE_PATH"])) as conn:
        conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
        conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Lathe','T1')")
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
        conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
        conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Dense capacity part')")
        for key, value in default_snapshot_values().items():
            conn.execute("INSERT OR REPLACE INTO ScheduleConfig(config_key,config_value) VALUES (?,?)", (key, str(value)))
        case = RunCase(conn)
        codes = ["B1"] + [f"CAP-{index:03d}" for index in range(1, batches)]
        for code in codes:
            case.batch(code)
            for seq in range(1, operations + 1):
                case.operation(code, seq, unit_hours=0.001)
        case.config(algo_mode="greedy", graph_candidate_weight_count=3, time_budget_seconds=600,
                    ortools_enabled="no", freeze_window_enabled="no")
        for key in ("auto_backup_enabled", "auto_backup_cleanup_enabled", "auto_log_cleanup_enabled"):
            conn.execute("INSERT OR REPLACE INTO SystemConfig(config_key,config_value) VALUES (?,'no')", (key,))
        conn.commit()
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        return {"settings": case.settings(*codes), "batches": batches, "operations_per_batch": operations,
                "operation_count": batches * operations, "candidate_count": 4, "resource_pairs": [["M1", "O1"]],
                "quantity": 3, "setup_hours": 0, "unit_hours": 0.001, "configured_optimization_budget_seconds": 600}


def digest(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def retain_business(before, after):
    assert set(before) == set(after), "Capacity run must not change schema"
    changed = sorted(name for name in before if before[name] != after[name])
    assert set(changed) <= RUN_TABLES, "Unexpected business writes: " + str(changed)
    for name in RUN_TABLES:
        assert before[name] == [], "Capacity seed must contain no prior run"
    return {"unchanged_tables": sorted(set(before) - RUN_TABLES), "changed_tables": changed,
            "before_sha256": digest(before), "after_sha256": digest(after)}


def retain_restart(before, startup, after):
    assert startup == after, "Reads and shutdown after restart must not write database rows"
    assert set(before) == set(startup)
    changed = sorted(name for name in before if before[name] != startup[name])
    assert changed == ["OperationLogs", "sqlite_sequence"]
    original, logs = before["OperationLogs"], startup["OperationLogs"]
    assert logs[:-1] == original and len(logs) == len(original) + 1
    old, added = original[-1], logs[-1]
    assert old["module"] == old["target_id"] == "plugins" and old["action"] == "load"
    assert set(added) == set(old)
    assert added["id"] == old["id"] + 1
    assert datetime.fromisoformat(added["log_time"]) >= datetime.fromisoformat(old["log_time"])
    assert {key: value for key, value in added.items() if key not in ("id", "log_time", "detail")} == {
        key: value for key, value in old.items() if key not in ("id", "log_time", "detail")}
    old_detail, new_detail = json.loads(old["detail"]), json.loads(added["detail"])
    assert set(old_detail) == set(new_detail)
    assert datetime.fromisoformat(new_detail["loaded_at"]) >= datetime.fromisoformat(old_detail["loaded_at"])
    assert {key: value for key, value in old_detail.items() if key != "loaded_at"} == {
        key: value for key, value in new_detail.items() if key != "loaded_at"}
    expected_sequence = [dict(row) for row in before["sqlite_sequence"]]
    sequence = next(row for row in expected_sequence if row["name"] == "OperationLogs")
    assert sequence["seq"] == old["id"]
    sequence["seq"] = added["id"]
    assert expected_sequence == startup["sqlite_sequence"]
    return {"unchanged_tables": sorted(set(before) - set(changed)), "preserved_log_rows": len(original),
            "startup_audit_append": added, "all_old_rows_preserved": True, "get_requests_zero_writes": True}


def verify_payload(payload, operations):
    expected_ids = set(operations)
    rows = payload["schedule_rows"]
    assert len(rows) == len(expected_ids)
    assert {row["op_id"] for row in rows} == expected_ids
    assert set(payload["scheduled_op_ids"]) == expected_ids
    assert payload["out_of_scope_op_ids"] == [] and payload["validation_errors"] == []
    ordered = sorted(rows, key=lambda row: (row["start_time"], row["end_time"], row["op_id"]))
    previous, next_seq = None, {}
    for row in ordered:
        start, end = datetime.fromisoformat(row["start_time"]), datetime.fromisoformat(row["end_time"])
        assert end > start
        assert previous is None or start >= previous, "Single resource operations must not overlap"
        assert (row["machine_id"], row["operator_id"]) == ("M1", "O1")
        operation = operations[row["op_id"]]
        batch_id = operation["batch_id"]
        assert operation["seq"] == next_seq.get(batch_id, 1), "A batch chain was reordered"
        next_seq[batch_id] = operation["seq"] + 1
        previous = end
    return rows


def verify_database(path, run_ref, expected_count, *, expected_batches, expected_operations):
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        operations = {row["id"]: dict(row) for row in conn.execute("SELECT * FROM BatchOperations")}
        assert expected_count == expected_batches * expected_operations
        assert len(operations) == expected_count
        batch_counts = {row[0]: row[1] for row in conn.execute("SELECT batch_id,COUNT(*) FROM BatchOperations GROUP BY batch_id")}
        assert len(batch_counts) == expected_batches and set(batch_counts.values()) == {expected_operations}
        assert {row[0] for row in conn.execute("SELECT batch_id FROM Batches")} == set(batch_counts)
        assert {row["unit_hours"] for row in operations.values()} == {0.001}
        assert {row["setup_hours"] for row in operations.values()} == {0.0}
        assert conn.execute("SELECT COUNT(*) FROM Machines").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM Operators").fetchone()[0] == 1
        refs = {int(row["source_key"]): row["ref"] for row in conn.execute(
            "SELECT source_key,ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1")}
        assert set(refs) == set(operations) and len(set(refs.values())) == expected_count
        assert {row[0] for row in conn.execute("SELECT quantity FROM Batches")} == {3}
        assert {tuple(row) for row in conn.execute("SELECT DISTINCT machine_id,operator_id FROM BatchOperations")} == {("M1", "O1")}
        rows = list(conn.execute("SELECT * FROM WorkbenchRunCandidates WHERE run_ref=? ORDER BY sequence", (run_ref,)))
        assert len(rows) == 4 and len({row["candidate_ref"] for row in rows}) == 4
        assert [row["candidate_key"] for row in rows] == ["baseline", "graph_w1_of_3", "graph_w2_of_3", "graph_w3_of_3"]
        candidates, payloads = [], []
        for row in rows:
            artifact = json.loads(row["artifact_json"])
            payload = artifact["validated_payload"]
            scheduled = verify_payload(payload, operations)
            assert row["status"] == "completed" and row["task_count"] == expected_count
            tasks = list(conn.execute("SELECT * FROM WorkbenchRunCandidateTasks WHERE candidate_ref=? ORDER BY ordinal", (row["candidate_ref"],)))
            assert len(tasks) == expected_count and len({task["row_ref"] for task in tasks}) == expected_count
            for ordinal, (task, source) in enumerate(zip(tasks, scheduled)):
                assert task["ordinal"] == ordinal and task["operation_ref"] == refs[source["op_id"]]
                assert json.loads(task["payload_json"]) == {**source, "locked": False}
            payloads.append(payload)
            candidates.append({"candidate_ref": row["candidate_ref"], "candidate_key": row["candidate_key"],
                               "task_count": len(tasks), "artifact_sha256": digest(artifact),
                               "payload_sha256": digest(payload), "tasks_sha256": digest([dict(task) for task in tasks]),
                               "engine_elapsed_seconds": artifact["elapsed_seconds"],
                               "time_budget_seconds": artifact["time_budget_seconds"]})
        receipt = conn.execute("SELECT result_json FROM WorkbenchRunReceipts WHERE run_ref=?", (run_ref,)).fetchone()
        result = json.loads(receipt[0])
        assert result["state"] == "complete" and result["result_persisted"] is True
        assert len(result["dispositions"]) == expected_count and len(result["candidates"]) == 4
        assert conn.execute("SELECT COUNT(*) FROM WorkbenchRunJobs").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM WorkbenchRunReceipts").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0] == 4 * expected_count
        return {"candidates": candidates, "candidate_payloads_sha256": digest(payloads),
                "operation_refs_sha256": digest(refs), "receipt_sha256": digest(result),
                "operation_count": expected_count, "batch_operation_counts": batch_counts,
                "all_persisted_tasks": expected_count * 4,
                "integrity_check": "ok", "foreign_key_check": [], "payloads": payloads}
