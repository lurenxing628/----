"""A count of 34 alone is insufficient evidence for default initialization."""

import copy

import pytest

from tests.workbench.final_master_config_preservation_support import expected_defaults, rows_hash, validate_bootstrap


def sample():
    rows = [{"__rowid__": index, "id": index, "config_key": key, **value, "updated_at": "2026-09-10 16:00:20"}
            for index, (key, value) in enumerate(expected_defaults().items(), 1)]
    request = {"method": "POST", "path": "/api/workbench/v1/calendar/upsert", "request_key": "actual-command"}
    stack = [{"path": "/sealed/" + path, "function": function} for path, function in (
        ("core/services/workbench/calendars.py", "apply"),
        ("core/services/scheduler/config/config_bootstrap_service.py", "ensure_defaults_if_pristine"),
        ("core/services/scheduler/config/config_bootstrap_service.py", "bootstrap_registered_defaults"),
        ("data/repositories/config_repo.py", "set_batch"))]
    trace = {"completed": True, "attempted_writes": 34, "before_requests": {"rows": 0, "sha256": rows_hash([])},
             "first": {"at": "2026-09-10T16:00:20+00:00", "statement_kind": "INSERT", "request": request, "stack": stack},
             "finished": "2026-09-10T16:00:25+00:00", "requests": [{"request": request, "attempted_writes": 34,
                "response_status": 200, "committed_config": {"rows": 34, "sha256": rows_hash(rows)}}]}
    commands = [{"path": request["path"], "request_key": request["request_key"], "status": 200, "result": "committed", "receipt_ref": "receipt"}]
    return [], rows, trace, commands


def test_exact_observed_default_bootstrap_is_accepted():
    result = validate_bootstrap(*sample())
    assert result["passed"] and result["rows_added"] == 34
    assert (result["registered_fields"], result["built_in_presets"], result["provenance_fields"]) == (27, 4, 3)


@pytest.mark.parametrize("fault", ["old_store", "value", "description", "missing", "extra", "identity", "timestamp",
                                  "failed_response", "wrong_command", "wrong_count", "missing_stack", "missing_receipt", "digest"])
def test_bootstrap_allowance_rejects_unproven_mutations(fault):
    old, rows, trace, commands = sample()
    if fault == "old_store":
        old.append(copy.deepcopy(rows[0]))
    elif fault in ("value", "description"):
        rows[0]["config_value" if fault == "value" else "description"] = "changed"
    elif fault == "missing":
        rows.pop()
    elif fault == "extra":
        rows.append(copy.deepcopy(rows[0]))
    elif fault == "identity":
        rows[0]["id"] = 100
    elif fault == "timestamp":
        rows[0]["updated_at"] = "2020-01-01 00:00:00"
    elif fault == "failed_response":
        trace["requests"][0]["response_status"] = 409
    elif fault == "wrong_command":
        commands[0]["request_key"] = "different-command"
    elif fault == "wrong_count":
        trace["attempted_writes"] = 35
    elif fault == "missing_stack":
        trace["first"]["stack"] = []
    elif fault == "missing_receipt":
        commands[0]["receipt_ref"] = None
    else:
        trace["requests"][0]["committed_config"]["sha256"] = "different"
    with pytest.raises(AssertionError):
        validate_bootstrap(old, rows, trace, commands)
