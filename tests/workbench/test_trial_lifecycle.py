"""Real draft and scenario persistence, lossless restoration and exact refs."""

from collections import Counter
from types import SimpleNamespace

import pytest
from flask import g, request

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_trial_codec import dump, load
from core.services.workbench.facts.trial_policy import load_scenario_record
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository
from tests.workbench.run_jobs_support import data_context
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
    from core.services.workbench.facts import trial_origin
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
    original_rows, original_facts = projection.scenario_rows, trial_origin.cached_generation_facts
    def projected(*args, **kwargs):
        calls["scenario_rows"] += 1
        return original_rows(*args, **kwargs)
    def generation_facts(*args, **kwargs):
        calls["generation_facts"] += 1
        return original_facts(*args, **kwargs)
    monkeypatch.setattr(projection, "scenario_rows", projected)
    monkeypatch.setattr(trial_service, "scenario_rows", projected)
    monkeypatch.setattr(trial_origin, "cached_generation_facts", generation_facts)
    case.conn.set_trace_callback(statements.append)
    draft = create(case, intent)
    case.conn.set_trace_callback(None)
    assert table_reads and set(table_reads.values()) <= {1, 2} and 2 in table_reads.values()
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
    repo = SimpleNamespace(conn=None,
        scenario_header=lambda _ref: {"scenario_ref": "saved", "revision": 1, "saved_at": "2026-09-10T12:00:00", "snapshot_json": encoded.header},
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


def test_http_trial_reads_and_catalogs_prebind_snapshot_before_heavy_projections(trial_case, monkeypatch):
    from core.services.workbench.trial import catalog as trial_catalog
    from core.services.workbench.trial import projection
    from core.services.workbench.trial import service as trial_service

    case = trial_case
    draft = create(case)
    saved = service(case.conn).save(
        draft["draft_ref"], {"name": "Prebind scenario"}, draft["write_context"]["write_token"], "trial-save-prebind-01"
    )["data"]
    client = api(case)

    draft_res = client.get("/api/workbench/v1/trial/drafts/" + draft["draft_ref"]).get_json()
    scenario_res = client.get("/api/workbench/v1/trial/scenarios/" + saved["scenario_ref"]).get_json()
    catalog_res = client.get("/api/workbench/v1/trial/drafts").get_json()
    draft_snap = draft_res["meta"]["snapshot_ref"]
    scenario_snap = scenario_res["meta"]["snapshot_ref"]
    catalog_snap = catalog_res["meta"]["snapshot_ref"]

    # Advance source revision so previous snapshot_refs become stale.
    case.conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P-STALE','Stale trigger')")
    case.conn.commit()

    missing_ref = "f" * 48
    assert client.get(f"/api/workbench/v1/trial/drafts/{missing_ref}?snapshot_ref={draft_snap}").status_code == 404
    assert client.get(f"/api/workbench/v1/trial/scenarios/{missing_ref}?snapshot_ref={scenario_snap}").status_code == 404

    def forbid(*args, **kwargs):
        raise AssertionError("Stale snapshot_ref must be rejected before heavy projection or catalog iteration")

    monkeypatch.setattr(trial_service, "live_context", forbid)
    monkeypatch.setattr(projection, "trial_capacity", forbid)
    monkeypatch.setattr(trial_catalog, "_bounded_page", forbid)

    stale_draft = client.get(f"/api/workbench/v1/trial/drafts/{draft['draft_ref']}?snapshot_ref={draft_snap}")
    assert stale_draft.status_code == 409
    assert stale_draft.get_json()["error"]["code"] == "snapshot_stale"

    stale_scenario = client.get(f"/api/workbench/v1/trial/scenarios/{saved['scenario_ref']}?snapshot_ref={scenario_snap}")
    assert stale_scenario.status_code == 409
    assert stale_scenario.get_json()["error"]["code"] == "snapshot_stale"

    stale_catalog = client.get(f"/api/workbench/v1/trial/drafts?snapshot_ref={catalog_snap}")
    assert stale_catalog.status_code == 409
    assert stale_catalog.get_json()["error"]["code"] == "snapshot_stale"


def test_saved_scenario_and_draft_dtos_isolate_in_process_caches_on_mutation(trial_case):
    from copy import deepcopy

    case = trial_case
    draft = create(case)
    saved = service(case.conn).save(
        draft["draft_ref"], {"name": "Isolated scenario"}, draft["write_context"]["write_token"], "trial-save-isolate-01"
    )["data"]
    scenario_ref = saved["scenario_ref"]
    draft_ref = draft["draft_ref"]

    scen_first = service(case.conn).scenario(scenario_ref)
    scen_expected = deepcopy(scen_first)
    scen_first["tasks"][0]["process_label"] = "POLLUTED"
    scen_first["tasks"][0]["data_gaps"].append({"field": "polluted"})
    scen_first["tasks"][0]["hours"]["total_hours"] = -999
    scen_first["tasks"][0]["operation_effort"]["before"]["evidence_source"]["capabilities"]["view"] = False
    scen_first["tasks"][0]["operation_effort"]["before"]["evidence_source"]["blocked_reasons"].append({"code": "polluted"})
    scen_first["comparison"]["batches"][0]["part_name"] = "POLLUTED"
    scen_first["comparison"]["delivery_summary"]["overdue_count"] = 99999
    scen_first["capacity"]["resources"][0]["label"] = "POLLUTED"
    scen_first["capacity"]["resource_common"]["cohort"].clear()
    if scen_first["validation"]["issues"]:
        scen_first["validation"]["issues"][0]["message"] = "POLLUTED"
    scen_first["validation"]["issues"].append({"code": "polluted"})
    scen_first["base"]["plan_ref"] = "0" * 48
    scen_first["base_identity"]["display_name"] = "POLLUTED"
    scen_first["scope"]["selection"] = "POLLUTED"
    if type(scen_first["operation_effort"]) is dict:
        scen_first["operation_effort"]["polluted"] = True

    scen_second = service(case.conn).scenario(scenario_ref)
    assert scen_second == scen_expected

    draft_first = service(case.conn).get(draft_ref)
    draft_expected = deepcopy(draft_first)
    draft_first["base"]["plan_ref"] = "0" * 48
    draft_first["base_identity"]["display_name"] = "POLLUTED"
    draft_first["base_identity"]["capabilities"]["view"] = False
    draft_first["scope"]["selection"] = "POLLUTED"
    draft_first["capacity"]["resources"][0]["calendar"]["source"]["source_ref"]["display_name"] = "POLLUTED"
    assert draft_first["capacity"]["resources"][0]["calendar"]["days"][0]["source"]["source_ref"]["display_name"] != "POLLUTED"
    draft_first["capacity"]["resources"][0]["calendar"]["days"][0]["source"]["source_ref"]["display_name"] = "POLLUTED"
    if draft_first["validation"]["issues"]:
        draft_first["validation"]["issues"][0]["message"] = "POLLUTED"
    draft_first["validation"]["issues"].append({"code": "polluted"})
    draft_first["validation_at_last_write"]["issues"].append({"code": "polluted"})
    draft_first["tasks"][0]["operation_effort"]["before"]["evidence_source"]["capabilities"]["view"] = False
    draft_first["tasks"][0]["operation_effort"]["before"]["evidence_source"]["blocked_reasons"].append({"code": "polluted"})
    if type(draft_first["tasks"][0].get("execution_at_creation")) is dict:
        draft_first["tasks"][0]["execution_at_creation"]["data_gaps"].append({"code": "polluted"})
    if type(draft_first.get("operation_effort")) is dict and draft_first["operation_effort"].get("items"):
        draft_first["operation_effort"]["items"][0]["data_gaps"].append({"code": "polluted"})

    draft_second = service(case.conn).get(draft_ref)
    assert draft_second == draft_expected
    assert draft_second["base_identity"]["display_name"] != "POLLUTED"
    assert draft_second["capacity"]["resources"][0]["calendar"]["source"]["source_ref"]["display_name"] != "POLLUTED"
    assert draft_second["capacity"]["resources"][0]["calendar"]["days"][0]["source"]["source_ref"]["display_name"] != "POLLUTED"


def test_trial_preview_and_live_validation_skip_full_archive_and_reuse_validated_intervals(trial_case, monkeypatch):
    from core.services.workbench.facts.production_capture import ProductionFactsCapture
    from core.services.workbench.trial import adoption_validation

    case = trial_case
    intent = official(case)
    draft = create(case, intent)
    draft_ref = draft["draft_ref"]
    saved = service(case.conn).save(
        draft_ref, {"name": "Interval reuse scenario"}, draft["write_context"]["write_token"], "trial-save-interval-01"
    )["data"]

    # Adoption validation threads validated current_by_row intervals into _span_end and schedule_rows.
    span_calls = []
    orig_span = adoption_validation._span_end

    def checked_span(rows, intervals_by_row):
        span_calls.append(len(intervals_by_row))
        return orig_span(rows, intervals_by_row)

    with monkeypatch.context() as patch:
        patch.setattr(adoption_validation, "_span_end", checked_span)
        adoption_validation.validate_trial_adoption(case.conn, saved["scenario_ref"],
                                                    data_context=data_context(case.conn))
    assert span_calls and all(count > 0 for count in span_calls)

    # Advance a live table revision (e.g. part name change) so matches_archive is False (not None).
    case.conn.execute("UPDATE Parts SET part_name='Updated Part Name' WHERE part_no='P1'")
    case.conn.commit()

    def forbid_full_archive(self, *args, **kwargs):
        raise AssertionError("Preview and live validation must read tables on demand without capture.archive")

    with monkeypatch.context() as patch:
        patch.setattr(ProductionFactsCapture, "archive", forbid_full_archive)
        previewed = service(case.conn).preview_create(intent)
        assert "plan_ref" in previewed["base"]
        loaded = service(case.conn).get(draft_ref)
        assert loaded["draft_ref"] == draft_ref


def test_corrupted_draft_row_end_time_reports_calendar_unproven_without_unhandled_value_error(trial_case):
    from tests.workbench.execution_ledger_support import publish_official_plan

    case = trial_case
    op2_id = case.operation(seq=2, setup_hours=0, unit_hours=1)
    publish_official_plan(
        case.conn,
        1,
        [
            {
                "op_id": case.op_id,
                "machine_id": "M1",
                "operator_id": "O1",
                "start_time": "2026-09-09T08:00:00",
                "end_time": "2026-09-09T11:00:00",
            },
            {
                "op_id": op2_id,
                "machine_id": "M1",
                "operator_id": "O1",
                "start_time": "2026-09-10T08:00:00",
                "end_time": "2026-09-10T11:00:00",
            },
        ],
    )
    case.conn.commit()
    draft = create(case, {"base": {"plan_ref": case.plan_ref(1)}})
    draft_ref = draft["draft_ref"]

    raw_current = load(
        case.conn.execute(
            "SELECT current_json FROM WorkbenchTrialRows WHERE draft_ref=? AND ordinal=0",
            (draft_ref,),
        ).fetchone()[0]
    )
    assert isinstance(raw_current, dict)
    raw_current["end"] = "2026-09-09Tbad"
    case.conn.execute(
        "UPDATE WorkbenchTrialRows SET current_json=? WHERE draft_ref=? AND ordinal=0",
        (dump(raw_current), draft_ref),
    )
    case.conn.commit()

    loaded = service(case.conn).get(draft_ref)
    assert loaded["validation"]["constraints_status"] == "blocked"
    assert any(
        item["code"] == "calendar_unproven" and item["task_ref"] == draft["tasks"][0]["task_ref"]
        for item in loaded["validation"]["issues"]
    )
