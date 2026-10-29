"""Real draft and scenario persistence, lossless restoration and exact refs."""

from collections import Counter
from types import SimpleNamespace

import pytest
from flask import g, request

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_trial_codec import dump, load
from core.services.workbench.facts.trial_policy import load_scenario_record
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository
from tests.workbench.trial_support import (
    CommitFailureConnection,
    api,
    assert_legacy_retained,
    candidate,
    change,
    connect,
    create,
    official,
    service,
    snapshot,
)
from tests.workbench.trial_support import trial_case as trial_case


@pytest.mark.parametrize("kind", ["official", "candidate"])
def test_complete_create_change_save_and_reopen(trial_case, kind, monkeypatch):
    case = trial_case
    intent = official(case) if kind == "official" else candidate(case)
    before = snapshot(case.conn)
    from core.services.workbench.trial import projection, validation
    from core.services.workbench.trial import service as trial_service
    from data.repositories.workbench_preflight_facts_repo import WorkbenchPreflightFactsRepository

    calls, table_reads, statements = Counter(), Counter(), []
    original_compare = validation.facts_unchanged
    def compared(*args, **kwargs):
        calls["facts_unchanged"] += 1
        return original_compare(*args, **kwargs)
    monkeypatch.setattr(validation, "facts_unchanged", compared)
    for method in ("draft_header", "draft_rows", "changes"):
        original = getattr(WorkbenchTrialRepository, method)
        def tracked(repo, *args, _method=method, _original=original, **kwargs):
            calls[_method] += 1
            return _original(repo, *args, **kwargs)
        monkeypatch.setattr(WorkbenchTrialRepository, method, tracked)
    original_table = WorkbenchPreflightFactsRepository.capture_table
    def table_read(repo, name):
        table_reads[name] += 1
        return original_table(repo, name)
    monkeypatch.setattr(WorkbenchPreflightFactsRepository, "capture_table", table_read)
    original_rows, original_facts = projection.scenario_rows, projection.GenerationFacts
    def projected(*args, **kwargs):
        calls["scenario_rows"] += 1
        return original_rows(*args, **kwargs)
    def generation_facts(*args, **kwargs):
        calls["generation_facts"] += 1
        return original_facts(*args, **kwargs)
    monkeypatch.setattr(projection, "scenario_rows", projected)
    monkeypatch.setattr(trial_service, "scenario_rows", projected)
    monkeypatch.setattr(projection, "GenerationFacts", generation_facts)
    case.conn.set_trace_callback(statements.append)
    draft = create(case, intent)
    case.conn.set_trace_callback(None)
    assert table_reads and set(table_reads.values()) == {2}  # preview and command own separate facts.
    assert calls["draft_header"] == calls["draft_rows"] == calls["changes"] == calls["facts_unchanged"] == 0
    assert not any(sql.upper().startswith("SELECT") and "COUNT(" in sql.upper() and "FROM WORKBENCHTRIALROWS" in sql.upper() for sql in statements)
    assert draft["validation"]["constraints_status"] == "valid", draft["validation"]
    assert draft["validation"]["can_adopt"] is False
    calls.clear()
    statements.clear()
    case.conn.set_trace_callback(statements.append)
    updated = change(case, draft)["data"]
    case.conn.set_trace_callback(None)
    assert calls["draft_header"] == calls["draft_rows"] == calls["changes"] == calls["facts_unchanged"] == 1
    assert not any(sql.upper().startswith("SELECT") and "COUNT(" in sql.upper() and "FROM WORKBENCHTRIALROWS" in sql.upper() for sql in statements)
    task = updated["tasks"][0]
    assert task["start"] == "2026-09-09T13:00:00"
    assert task["end"] == "2026-09-09T16:00:00"
    assert task["task_ref"] == draft["tasks"][0]["task_ref"]
    assert task["hours"] == draft["tasks"][0]["hours"]
    assert task["machine_ref"] == case.ref("machine", "M2")
    assert task["operator_ref"] == case.ref("operator", "O2")
    assert updated["validation"]["constraints_status"] == "valid", updated["validation"]
    conn = connect(case.path)
    try:
        restored = service(conn).get(draft["draft_ref"])
        assert restored["tasks"] == updated["tasks"]
        saved = service(conn).save(draft["draft_ref"], {"name": "Saved trial"}, restored["write_context"]["write_token"], "trial-save-0000000001")["data"]
        assert saved["scenario_ref"] != draft["draft_ref"]
        assert saved["tasks"][0]["task_ref"] != task["task_ref"]
        calls.clear()
        assert service(conn).scenario(saved["scenario_ref"]) == saved
        assert calls["draft_header"] == calls["draft_rows"] == calls["scenario_rows"] == 1
        assert calls["generation_facts"] == (1 if kind == "candidate" else 0)
        assert service(conn).get(draft["draft_ref"])["status"] == "saved"
    finally:
        conn.close()
    assert_legacy_retained(before, snapshot(case.conn))
    repo = WorkbenchTrialRepository(case.conn)
    stored_header = repo.scenario_header(saved["scenario_ref"])
    assert stored_header is not None and "snapshot_hash" not in stored_header
    stored_draft = repo.draft_header(draft["draft_ref"])
    assert stored_draft is not None and "admission_hash" not in stored_draft
    assert all("original_hash" not in row for row in repo.draft_rows(draft["draft_ref"]))
    if kind == "candidate":
        assert "candidate_ref" in draft["base"] and "plan_ref" not in draft["base"]
        assert task["source_task_ref"] is None
        admission = load(case.conn.execute(
            "SELECT admission_json FROM WorkbenchTrialDrafts WHERE draft_ref=?", (draft["draft_ref"],)).fetchone()[0])
        assert isinstance(admission, dict)
        assert isinstance(admission["source"], dict)
        assert "artifact" not in admission["source"]
        assert {"capture", "dispositions", "identity"} <= set(admission["source"])


def test_scenario_fragments_share_exact_logical_limit_without_counting_physical_row_refs(monkeypatch):
    from datetime import date

    from core.models import workbench_trial_scenario_archive as codec

    tasks = [{"row_ref": format(index, "048x"), "description": "保存任务正文" * 40, "ordinal": index}
             for index in range(1, 5)]
    effort = {"effort_basis": "runtime_requirement_v1", "items": []}
    snapshot = {"name": "中文试调", "saved_date": date(2026, 10, 15), "binary": b"\x00\xff",
                "operation_effort": effort, "tasks": tasks}
    encoded = codec.encode_scenario(snapshot)
    expected_bytes = len(dump(snapshot).encode("utf-8"))
    assert encoded.logical_bytes == expected_bytes
    assert len(encoded.header.encode("utf-8")) + sum(len(text.encode("utf-8")) for text in encoded.tasks) > expected_bytes
    repo = SimpleNamespace(conn=None, schema_issues=lambda: [],
        scenario_header=lambda _ref: {"snapshot_json": encoded.header},
        iter_scenario_rows=lambda _ref: [{"row_ref": row["row_ref"], "payload_json": text}
                                       for row, text in zip(tasks, encoded.tasks)])
    assert load_scenario_record(repo, "saved")[1] == snapshot
    monkeypatch.setattr(codec, "MAX_TRIAL_BYTES", expected_bytes)
    assert load_scenario_record(repo, "saved")[1] == snapshot

    def redundant(*args, **kwargs):
        raise AssertionError("Canonical stored fragments already own their text and task bodies")

    with monkeypatch.context() as read:
        read.setattr(codec, "encode_trial_text", redundant)
        assert load_scenario_record(repo, "saved")[1] == snapshot
    assert codec.encode_scenario(snapshot).logical_bytes == expected_bytes
    monkeypatch.setattr(codec, "MAX_TRIAL_BYTES", expected_bytes - 1)
    for operation in (lambda: codec.encode_scenario(snapshot), lambda: load_scenario_record(repo, "saved")):
        with pytest.raises(WorkbenchCommandRejected) as error:
            operation()
        assert (error.value.code, error.value.status) == ("query_too_large", 413)


def test_http_trial_command_with_lost_acknowledgement_points_to_its_receipt(trial_case):
    case = trial_case
    intent, key = official(case), "trial-create-lost-ack-01"
    client = api(case, factory=CommitFailureConnection)

    @case.app.before_request
    def lose_ack():
        if request.method == "POST" and request.path == "/api/workbench/v1/trial/drafts":
            g.db.fail_commit = g.db.acknowledge_only = True

    token = client.post("/api/workbench/v1/trial/drafts/preview", json=intent).get_json()["data"]["write_context"]["write_token"]
    response = client.post("/api/workbench/v1/trial/drafts", json={"request_key": key, "write_token": token, "input": intent})
    assert response.status_code == 500
    value = response.get_json()
    assert value["committed"] == "unknown" and value["error"]["request_key"] == key and value["error"]["retryable"] is False
    assert value["error"]["result_target"] == "/api/workbench/v1/trial/commands/" + key
    assert client.get(value["error"]["result_target"]).get_json()["data"]["state"] == "committed"
