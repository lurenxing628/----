"""Capacity harness cannot turn truncation, changed scope or dirty restart into pass."""

import copy
from contextlib import closing
from types import SimpleNamespace

import pytest

from tests.workbench.final_capacity_probe import require_current_build, run_managed
from tests.workbench.final_capacity_support import (
    RUN_TABLES,
    digest,
    retain_business,
    retain_restart,
    seed_dense,
    verify_payload,
)


@pytest.mark.parametrize("options", [
    {"operations": 50},
    {"operations": 50, "exclusive_window": "main-test", "profile": True},
    {"operations": 10, "exclusive_window": "main-test"},
    {"operations": 50, "batches": 99, "exclusive_window": "main-test"},
])
def test_formal_capacity_rejects_unscheduled_profiled_or_wrong_scope_before_writes(tmp_path, options):
    output = tmp_path / "must-not-exist"
    with pytest.raises(ValueError):
        run_managed(output, **options)
    assert not output.exists()


def test_formal_capacity_rejects_stale_assets_without_relabeling_exploration():
    stale = {"assets": {"source_differences": ["frontend/workbench/app/main.jsx"]}}
    require_current_build(stale, formal=False)
    with pytest.raises(AssertionError, match="full build"):
        require_current_build(stale, formal=True)
    require_current_build({"assets": {"source_differences": []}}, formal=True)


@pytest.fixture
def actual_payload(tmp_path):
    from core.infrastructure.database import ensure_schema, get_connection
    from core.models.workbench_run_job import durable_value
    from core.services.workbench.run_compute import compute_candidate_run
    from tests.workbench.run_compute_support import RunCase

    path = tmp_path / "capacity.sqlite"
    ensure_schema(str(path))
    spec = seed_dense(SimpleNamespace(config={"DATABASE_PATH": str(path)}), batches=2, operations=2)
    with closing(get_connection(str(path))) as conn:
        case = RunCase(conn)
        before = conn.total_changes
        result = compute_candidate_run(conn, spec["settings"], case.projections())
        assert conn.total_changes == before
        assert result.state == "complete" and len(result.candidate_payloads) == 4
        assert {row[0] for row in conn.execute("SELECT quantity FROM Batches")} == {3}
        operations = {row["id"]: dict(row) for row in conn.execute("SELECT * FROM BatchOperations")}
        payloads = [durable_value(payload) for payload in result.candidate_payloads.values()]
        for payload in payloads:
            verify_payload(payload, operations)
        yield payloads[0], operations


def test_seed_retains_one_resource_positive_hours_complete_four_candidates(actual_payload):
    payload, operations = actual_payload
    assert len(verify_payload(payload, operations)) == 4
    assert len({row["batch_id"] for row in operations.values()}) == 2
    assert {row["unit_hours"] for row in operations.values()} == {0.001}
    assert {row["setup_hours"] for row in operations.values()} == {0.0}


@pytest.mark.parametrize("damage", ["truncate", "duplicate", "zero_duration", "overlap", "wrong_resource", "reordered_chain"])
def test_full_payload_checks_reject_actual_result_corruption(actual_payload, damage):
    original, operations = actual_payload
    payload = copy.deepcopy(original)
    rows = payload["schedule_rows"]
    ordered = sorted(rows, key=lambda row: row["start_time"])
    if damage == "truncate":
        rows.pop()
    elif damage == "duplicate":
        rows[-1]["op_id"] = rows[0]["op_id"]
    elif damage == "zero_duration":
        rows[0]["end_time"] = rows[0]["start_time"]
    elif damage == "overlap":
        ordered[1]["start_time"] = ordered[0]["start_time"]
    elif damage == "wrong_resource":
        rows[0]["machine_id"] = "M2"
    else:
        batch = operations[ordered[0]["op_id"]]["batch_id"]
        pair = [row for row in ordered if operations[row["op_id"]]["batch_id"] == batch]
        pair[0]["op_id"], pair[1]["op_id"] = pair[1]["op_id"], pair[0]["op_id"]
    with pytest.raises(AssertionError):
        verify_payload(payload, operations)


def test_business_guard_allows_only_new_run_tables_and_retains_exact_values():
    before = {name: [] for name in RUN_TABLES}
    before["Batches"] = [{"batch_id": "B1", "quantity": 3}]
    after = copy.deepcopy(before)
    after["WorkbenchRunJobs"] = [{"run_ref": "example"}]
    assert retain_business(before, after)["changed_tables"] == ["WorkbenchRunJobs"]
    after["Batches"][0]["quantity"] = 2
    with pytest.raises(AssertionError):
        retain_business(before, after)


def test_payload_digest_is_key_order_independent_but_not_content_independent():
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})
    assert digest({"a": 1, "b": 2}) != digest({"a": 1, "b": 3})


@pytest.fixture
def restart_snapshots():
    log = {"id": 1, "log_time": "2026-09-10 11:00:00", "module": "plugins", "target_id": "plugins",
           "action": "load", "log_level": "INFO", "detail": '{"loaded_at":"2026-09-10 19:00:00","statuses":[]}'}
    before = {"OperationLogs": [log], "sqlite_sequence": [{"name": "OperationLogs", "seq": 1}],
              "WorkbenchRunCandidateTasks": [{"operation_ref": "retained"}]}
    startup = copy.deepcopy(before)
    startup["OperationLogs"].append({**log, "id": 2, "log_time": "2026-09-10 11:00:01",
                                    "detail": '{"loaded_at":"2026-09-10 19:00:01","statuses":[]}'})
    startup["sqlite_sequence"][0]["seq"] = 2
    return before, startup


def test_restart_allows_exactly_one_normal_plugin_audit_and_keeps_every_old_row(restart_snapshots):
    before, startup = restart_snapshots
    assert retain_restart(before, startup, copy.deepcopy(startup))["all_old_rows_preserved"]


@pytest.mark.parametrize("damage", ["old_log", "extra_log", "business", "get_write", "plugin_change", "sequence"])
def test_restart_guard_does_not_hide_other_changes(restart_snapshots, damage):
    before, startup = restart_snapshots
    after = copy.deepcopy(startup)
    if damage == "old_log":
        startup["OperationLogs"][0]["action"] = "changed"
    elif damage == "extra_log":
        startup["OperationLogs"].append(startup["OperationLogs"][-1])
    elif damage == "business":
        startup["WorkbenchRunCandidateTasks"][0]["operation_ref"] = "wrong"
    elif damage == "get_write":
        after["WorkbenchRunCandidateTasks"].clear()
    elif damage == "plugin_change":
        startup["OperationLogs"][-1]["detail"] = '{"loaded_at":"2026-09-10 19:00:01","statuses":["changed"]}'
    else:
        startup["sqlite_sequence"][0]["seq"] = 3
    if damage != "get_write":
        after = copy.deepcopy(startup)
    with pytest.raises(AssertionError):
        retain_restart(before, startup, after)
