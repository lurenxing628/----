"""HTTP method/input boundaries, original-key recovery and unknown ACK response."""

import json

import pytest
from flask import Blueprint, g, request

from core.errors import AppError, ErrorCode
from core.models.workbench_run_job import valid_data_context_ref
from core.services.workbench.facts.run_data_context import RunDataContext, restored_context_ref
from core.services.workbench.trial.adoption import WorkbenchTrialAdoptionService
from core.services.workbench.trial.adoption_history import WorkbenchTrialAdoptionHistoryService
from tests.workbench.trial_adoption_support import BASE, INTENT, KEY, api, saved_scenario
from tests.workbench.trial_adoption_support import trial_case as trial_case
from tests.workbench.trial_support import CommitFailureConnection, candidate, snapshot
from web.routes.workbench.read_context import bind_read_snapshot
from web.routes.workbench.trial import register_trial_routes


def test_real_http_preview_confirm_and_receipt(trial_case):
    case = trial_case
    saved = saved_scenario(case)
    client = api(case)
    path = BASE + saved["scenario_ref"]
    before = snapshot(case.conn)
    response = client.post(path + "/adopt-preview", json={})
    assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
    preview_payload = response.get_json()
    assert preview_payload["meta"]["snapshot_ref"] is None and "." not in preview_payload["meta"]["as_of"]
    preview = preview_payload["data"]
    assert preview["scenario_ref"] == saved["scenario_ref"] and preview["draft_ref"] == saved["draft_ref"]
    assert preview["validation"]["can_adopt"] and snapshot(case.conn) == before
    body = {"write_token": preview["write_context"]["write_token"], "request_key": KEY, "input": INTENT}
    response = client.post(path + "/adopt", json=body)
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    context = {"data_context_ref": preview["data_context_ref"]}
    receipt_resp = client.get(path + "/adoption-commands/" + KEY, query_string=context)
    assert receipt_resp.status_code == 200 and receipt_resp.headers["Cache-Control"] == "no-store"
    receipt = receipt_resp.get_json()
    assert receipt == {
        "state": "recorded",
        "receipt": {**result, "replayed": True},
        "may_be_in_flight": False,
        "resolution": "recorded",
        "data_context_ref": preview["data_context_ref"],
    }
    statements = []
    before, changes = snapshot(case.conn), case.conn.total_changes
    case.conn.set_trace_callback(statements.append)
    try:
        history, history_state = WorkbenchTrialAdoptionHistoryService(case.conn).read(
            saved["scenario_ref"], bind_snapshot=lambda _scope, content: content
        )
    finally:
        case.conn.set_trace_callback(None)
    queries = [sql.upper() for sql in statements if sql.upper().startswith("SELECT")]
    receipt_queries = [sql for sql in queries if "FROM WORKBENCHCOMMANDRECEIPTS" in sql]
    adopted_receipts = [sql for sql in receipt_queries if "WHERE ACTION=" in sql and "CONTEXT_REF=" in sql]
    assert len(adopted_receipts) == 1
    assert "ORDER BY COMMITTED_AT_UTC DESC,REQUEST_KEY DESC LIMIT 1001" in adopted_receipts[0]
    assert all("WHERE" in sql for sql in receipt_queries)
    assert not any("LENGTH(" in sql or "COUNT(" in sql or "SUM(" in sql for sql in receipt_queries)
    assert not any("LENGTH(" in sql and "PAYLOAD_JSON" in sql for sql in queries)
    assert sum("FROM WORKBENCHTRIALSCENARIOS WHERE SCENARIO_REF=" in sql for sql in queries) == 1
    assert sum("FROM WORKBENCHTRIALSCENARIOROWS WHERE SCENARIO_REF=" in sql for sql in queries) == 1
    assert sum("FROM WORKBENCHTRIALDRAFTS WHERE DRAFT_REF=" in sql for sql in queries) == 1
    selected_histories = [sql for sql in queries if "FROM SCHEDULEHISTORY WHERE VERSION=" in sql and "RESULT_SUMMARY" in sql]
    assert len(selected_histories) == 1 and "LIMIT 2" in selected_histories[0]
    assert snapshot(case.conn) == before and case.conn.total_changes == changes
    with case.app.app_context():
        assert bind_read_snapshot(history["scope"], history_state)["snapshot_ref"]
    entry = history["items"][0]
    assert entry["adoption"]["reason"] == INTENT["reason"]
    assert entry["adoption"]["declared_operator"] == INTENT["declared_operator"]
    assert not any(gap["code"].startswith("audit_") for gap in entry["evidence_gaps"])
    summary = json.loads(case.conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=?",
                        (result["data"]["official_plan"]["version"],)).fetchone()[0])
    assert set(summary["proof"]) == {"proof_version", "scenario_ref", "draft_ref", "scenario_revision", "baseline_ref", "baseline_version"}
    assert summary["proof"]["proof_version"] == "content_refs_v1"
    assert client.get(path + "/adopt").status_code == 405
    unknown = client.get(path + "/adoption-commands/not-yet-seen-request", query_string=context).get_json()
    assert unknown == {
        "state": "not_observed",
        "receipt": None,
        "may_be_in_flight": True,
        "resolution": "unresolved",
        "data_context_ref": preview["data_context_ref"],
    }


def test_http_adoption_recovery_distinguishes_replaced_context_and_replays_receipt(trial_case, monkeypatch):
    case = trial_case
    saved = saved_scenario(case)
    client = api(case)
    path = BASE + saved["scenario_ref"]
    response = client.post(path + "/adopt-preview", json={})
    assert response.status_code == 200
    preview_payload = response.get_json()
    assert preview_payload["meta"]["snapshot_ref"] is None
    checked = preview_payload["data"]
    context = checked["data_context_ref"]
    assert valid_data_context_ref(context)
    other_context = restored_context_ref("another-database", [])
    assert valid_data_context_ref(other_context) and other_context != context
    command_path = path + "/adoption-commands/" + KEY
    before = snapshot(case.conn)
    # The browser always sends the data generation it previewed under; a query without it is rejected.
    for query in ({}, {"data_context_ref": "a" * 64}, {"data_context_ref": context, "extra": "1"}):
        response = client.get(command_path, query_string=query)
        assert response.status_code == 400 and response.get_json()["error"]["code"] == "invalid_input"
    response = client.get(command_path, query_string={"data_context_ref": context})
    assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
    assert response.get_json() == {
        "state": "not_observed",
        "receipt": None,
        "may_be_in_flight": True,
        "resolution": "unresolved",
        "data_context_ref": context,
    }
    for target, query in (
        (command_path, {"data_context_ref": other_context}),
        (BASE + "f" * 48 + "/adoption-commands/" + KEY, {"data_context_ref": context}),
    ):
        response = client.get(target, query_string=query)
        assert response.status_code == 200
        assert response.get_json() == {
            "state": "not_observed",
            "receipt": None,
            "may_be_in_flight": False,
            "resolution": "context_replaced",
            "data_context_ref": context,
        }
    assert snapshot(case.conn) == before

    adopted = client.post(path + "/adopt", json={"write_token": checked["write_context"]["write_token"],
        "request_key": KEY, "input": INTENT})
    assert adopted.status_code == 200
    context_reads = []
    original_ref = RunDataContext.ref

    def tracked_context(data_context):
        context_reads.append(data_context.database_path)
        return original_ref(data_context)

    monkeypatch.setattr(RunDataContext, "ref", tracked_context)
    response = client.get(command_path, query_string={"data_context_ref": other_context})
    assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
    result = response.get_json()
    assert result == {
        "state": "recorded",
        "receipt": {**adopted.get_json(), "replayed": True},
        "may_be_in_flight": False,
        "resolution": "recorded",
        "data_context_ref": other_context,
    }
    assert context_reads == []


def _damage_saved_admission(conn, draft_ref, mutate):
    guards = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger' "
                          "AND name IN ('wb_trialdrafts_identity', 'wb_trial_transition')").fetchall()
    stored = conn.execute("SELECT admission_json FROM WorkbenchTrialDrafts WHERE draft_ref=?", (draft_ref,)).fetchone()[0]
    admission = json.loads(stored)
    mutate(admission)
    for name, _sql in guards:
        conn.execute("DROP TRIGGER " + name)
    conn.execute("UPDATE WorkbenchTrialDrafts SET admission_json=? WHERE draft_ref=?",
                 (json.dumps(admission, ensure_ascii=False, sort_keys=True, separators=(",", ":")), draft_ref))
    for _name, sql in guards:
        conn.execute(sql)
    conn.commit()


def _damage_saved_facts(conn, draft_ref, damage):
    """Storage damage to a saved draft's production facts archive, at a key the trial origin reads.

    Trial evidence is permanent: its two update guards are what make such damage impossible through the
    application, so only this simulation lifts them around the one corrupting UPDATE and restores them.
    """
    _damage_saved_admission(conn, draft_ref, lambda admission: damage(admission["facts"]))


def _drop_tables(facts):
    del facts["tables"]


def _drop_batch_operations(facts):
    del facts["tables"]["BatchOperations"]


def _drop_revisions(facts):
    del facts["revisions"]


def _positional_machines(facts):
    columns = facts["columns"]["Machines"]
    facts["tables"]["Machines"] = [[row[column] for column in columns] for row in facts["tables"]["Machines"]]


def _renamed_machine_column(facts):
    facts["columns"]["Machines"] = [column + "_x" if column == "remark" else column for column in facts["columns"]["Machines"]]
    facts["tables"]["Machines"] = [{(key + "_x" if key == "remark" else key): value for key, value in row.items()}
                                   for row in facts["tables"]["Machines"]]


def _renamed_batch_operations_column(facts):
    facts["columns"]["BatchOperations"] = [
        column + "_x" if column == "status" else column for column in facts["columns"]["BatchOperations"]
    ]
    facts["tables"]["BatchOperations"] = [
        {(key + "_x" if key == "status" else key): value for key, value in row.items()}
        for row in facts["tables"]["BatchOperations"]
    ]


@pytest.mark.parametrize("source", ["official", "candidate"])
@pytest.mark.parametrize(
    "damage",
    [_drop_tables, _drop_batch_operations, _drop_revisions, _positional_machines,
     _renamed_machine_column, _renamed_batch_operations_column],
    ids=["tables", "batch_operations", "revisions", "positional_rows", "renamed_column", "renamed_op_column"],
)
def test_damaged_saved_trial_facts_are_a_clear_rejection_not_an_uncertain_write(trial_case, source, damage):
    """Archive damage is rejected once at draft decode, symmetrically across reads, previews and writes."""
    case = trial_case
    saved = saved_scenario(case, candidate(case) if source == "candidate" else None)
    client = api(case)
    reads = Blueprint("damaged_trial_reads", __name__)
    register_trial_routes(reads)
    case.app.register_blueprint(reads)
    path = BASE + saved["scenario_ref"]
    token = client.post(path + "/adopt-preview", json={}).get_json()["data"]["write_context"]["write_token"]
    _damage_saved_facts(case.conn, saved["draft_ref"], damage)
    before = snapshot(case.conn)

    preview = client.post(path + "/adopt-preview", json={})
    assert preview.status_code == 200
    validation = preview.get_json()["data"]["validation"]
    assert validation["can_adopt"] is False and [row["code"] for row in validation["issues"]] == ["trial_snapshot_invalid"]
    adopted = client.post(path + "/adopt", json={"write_token": token, "request_key": KEY, "input": INTENT})
    assert adopted.status_code == 409
    value = adopted.get_json()
    assert value["committed"] is False and "request_key" not in value["error"]
    assert value["error"]["code"] == "trial_snapshot_invalid" and value["error"]["retryable"] is False
    for read in ("/api/workbench/v1/trial/drafts/" + saved["draft_ref"],
                 "/api/workbench/v1/trial/scenarios/" + saved["scenario_ref"]):
        response = client.get(read)
        assert response.status_code == 409 and response.get_json()["error"]["code"] == "trial_snapshot_invalid", read
    assert snapshot(case.conn) == before


def _corrupt_unarranged_source_ref(admission):
    for row in admission["facts"]["tables"]["WorkbenchPlanSourceRefs"]:
        if row["kind"] == "operation" and row["active"] == 1:
            row["ref"] = "not-a-hex-ref"
            break


def _corrupt_batch_id_type(admission):
    admission["facts"]["tables"]["BatchOperations"][-1]["batch_id"] = 999


@pytest.mark.parametrize(
    ("mutate", "blocks_discard_and_adopt"),
    [
        (lambda admission: _renamed_batch_operations_column(admission["facts"]), True),
        (_corrupt_unarranged_source_ref, True),
        (_corrupt_batch_id_type, True),
        (lambda admission: admission["execution"].clear(), False),
        (lambda admission: admission["source"]["operation_effort"]["items"][0].update(operation_ref="bad-ref"), False),
    ],
    ids=[
        "batch_operations_column",
        "corrupt_unarranged_source_ref",
        "corrupt_operation_batch_id",
        "missing_unarranged_execution",
        "corrupt_operation_effort_ref",
    ],
)
def test_deferred_unarranged_trial_damage_rejects_all_draft_and_scenario_endpoints(
    trial_case, mutate, blocks_discard_and_adopt
):
    from core.services.workbench.run.worker import WorkbenchRunWorker
    from tests.workbench.run_candidate_adoption_support import INTENT as CANDIDATE_INTENT
    from tests.workbench.run_candidate_adoption_support import service as candidate_adoption_service
    from tests.workbench.test_material_stage_release import add_requirement
    from tests.workbench.trial_support import create
    from tests.workbench.trial_support import service as trial_service

    case = trial_case
    second = case.operation(seq=2)
    add_requirement(case, second, [])
    accepted = case.accept(settings=case.settings(material_strategy="stage"))
    run_result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    cand_ref = run_result["candidates"][0]["candidate_ref"]
    adopter = candidate_adoption_service(case.conn)
    cand_preview = adopter.preview(cand_ref)
    adopted_plan = adopter.adopt(
        cand_ref, cand_preview["write_context"]["write_token"], "stage-official-plan-01", CANDIDATE_INTENT
    )["data"]["official_plan"]

    editing = create(case, {"base": {"plan_ref": adopted_plan["plan_ref"]}}, key="deferred-editing-draft")
    assert len(editing["unplanned_operations"]) == 1
    for_scenario = create(case, {"base": {"plan_ref": adopted_plan["plan_ref"]}}, key="deferred-saved-draft")
    saved = trial_service(case.conn).save(
        for_scenario["draft_ref"],
        {"name": "Deferred scenario"},
        for_scenario["write_context"]["write_token"],
        "deferred-saved-scenario",
    )["data"]

    client = api(case)
    trial_bp = Blueprint("deferred_damaged_trial", __name__)
    register_trial_routes(trial_bp)
    case.app.register_blueprint(trial_bp)
    scenario_path = BASE + saved["scenario_ref"]
    adopt_token = client.post(scenario_path + "/adopt-preview", json={}).get_json()["data"]["write_context"]["write_token"]

    _damage_saved_admission(case.conn, editing["draft_ref"], mutate)
    _damage_saved_admission(case.conn, saved["draft_ref"], mutate)
    before = snapshot(case.conn)

    draft_url = "/api/workbench/v1/trial/drafts/" + editing["draft_ref"]
    draft_read = client.get(draft_url)
    assert draft_read.status_code == 409 and draft_read.get_json()["error"]["code"] == "trial_snapshot_invalid"
    edit_token = editing["write_context"]["write_token"]
    task_ref = editing["tasks"][0]["task_ref"]
    draft_writes = [
        ("/change", {"task_ref": task_ref, "machine_ref": case.ref("machine", "M2"),
                     "operator_ref": case.ref("operator", "O2"), "start": "2026-09-09T13:00:00"},
         "damaged-change-request-01"),
        ("/save", {"name": "Blocked save"}, "damaged-save-request-01"),
    ]
    if blocks_discard_and_adopt:
        draft_writes.append(("/discard", {"confirm": True}, "damaged-discard-request-01"))
    for suffix, payload, req_key in draft_writes:
        resp = client.post(
            draft_url + suffix,
            json={"write_token": edit_token, "request_key": req_key, "input": payload},
        )
        body = resp.get_json()
        assert resp.status_code == 409, (suffix, body)
        assert body["committed"] is False and body["error"]["code"] == "trial_snapshot_invalid"

    for url in ("/api/workbench/v1/trial/drafts/" + saved["draft_ref"],
                "/api/workbench/v1/trial/scenarios/" + saved["scenario_ref"]):
        resp = client.get(url)
        assert resp.status_code == 409 and resp.get_json()["error"]["code"] == "trial_snapshot_invalid"

    if blocks_discard_and_adopt:
        preview_resp = client.post(scenario_path + "/adopt-preview", json={})
        assert preview_resp.status_code == 200
        preview_val = preview_resp.get_json()["data"]["validation"]
        assert preview_val["can_adopt"] is False
        assert [row["code"] for row in preview_val["issues"]] == ["trial_snapshot_invalid"]

        adopt_resp = client.post(
            scenario_path + "/adopt",
            json={"write_token": adopt_token, "request_key": KEY, "input": INTENT},
        )
        adopt_body = adopt_resp.get_json()
        assert adopt_resp.status_code == 409
        assert adopt_body["committed"] is False and adopt_body["error"]["code"] == "trial_snapshot_invalid"
    assert snapshot(case.conn) == before


def test_http_ack_unknown_points_to_original_scenario_and_key(trial_case):
    case = trial_case
    saved = saved_scenario(case)
    client = api(case, factory=CommitFailureConnection)
    path = BASE + saved["scenario_ref"]

    @case.app.before_request
    def lose_ack():
        if request.path.endswith("/adopt"):
            g.db.fail_commit = g.db.acknowledge_only = True

    preview = client.post(path + "/adopt-preview", json={}).get_json()["data"]
    response = client.post(path + "/adopt", json={"write_token": preview["write_context"]["write_token"],
                                                  "request_key": KEY, "input": INTENT})
    assert response.status_code == 500
    value = response.get_json()
    assert value["committed"] == "unknown" and value["error"]["request_key"] == KEY
    assert value["error"]["result_target"] == path + "/adoption-commands/" + KEY
    assert value["error"]["retryable"] is False
    receipt = client.get(value["error"]["result_target"],
                         query_string={"data_context_ref": preview["data_context_ref"]}).get_json()
    assert receipt["state"] == "recorded" and receipt["may_be_in_flight"] is False and receipt["resolution"] == "recorded"
    assert receipt["data_context_ref"] == preview["data_context_ref"]
    assert receipt["receipt"]["data"]["scenario_ref"] == saved["scenario_ref"]
    assert case.conn.execute("SELECT COUNT(*) FROM ScheduleHistory").fetchone()[0] == 2


def test_trial_adoption_history_stale_snapshot_short_circuits_without_decoding_scenario_rows(trial_case):
    from web.routes.workbench.trial_adoption_history import register_trial_adoption_history_routes

    case = trial_case
    case.app.config["SECRET_KEY"] = "temporary-trial-adoption-history"
    saved = saved_scenario(case)
    client = api(case)
    history_bp = Blueprint("trial_adoption_history_routes", __name__)
    register_trial_adoption_history_routes(history_bp)
    case.app.register_blueprint(history_bp)

    statements = []

    @case.app.before_request
    def trace_db():
        g.db.set_trace_callback(statements.append)

    path = BASE + saved["scenario_ref"]
    token = client.post(path + "/adopt-preview", json={}).get_json()["data"]["write_context"]["write_token"]
    adopted = client.post(path + "/adopt", json={"write_token": token, "request_key": KEY, "input": INTENT})
    assert adopted.status_code == 200

    statements.clear()
    first = client.get(path + "/adoption-history")
    assert first.status_code == 200, first.get_json()
    first_queries = [sql.upper() for sql in statements if sql.upper().startswith("SELECT")]
    assert sum("FROM WORKBENCHTRIALSCENARIOS WHERE SCENARIO_REF=" in sql for sql in first_queries) == 1
    assert sum("FROM WORKBENCHTRIALSCENARIOROWS WHERE SCENARIO_REF=" in sql for sql in first_queries) == 1
    stale_snapshot_ref = first.get_json()["meta"]["snapshot_ref"]
    assert stale_snapshot_ref

    case.plan(3, [case.op_id])
    case.conn.commit()

    statements.clear()
    stale = client.get(path + "/adoption-history", query_string={"snapshot_ref": stale_snapshot_ref, "page": "2"})
    assert stale.status_code == 409
    assert stale.get_json()["error"]["code"] == "snapshot_stale"
    stale_queries = [sql.upper() for sql in statements if sql.upper().startswith("SELECT")]
    assert sum("WORKBENCHTRIALSCENARIOROWS" in sql for sql in stale_queries) == 0


@pytest.mark.parametrize("injected", [AppError(ErrorCode.DB_QUERY_ERROR, "注入的存储失败"), RuntimeError("注入的未预期失败")])
def test_http_adopt_failure_after_binding_key_points_to_original_receipt(trial_case, monkeypatch, injected):
    case = trial_case
    saved = saved_scenario(case)
    client = api(case)
    path = BASE + saved["scenario_ref"]
    token = client.post(path + "/adopt-preview", json={}).get_json()["data"]["write_context"]["write_token"]

    def fail(*_args, **_kwargs):
        raise injected

    monkeypatch.setattr(WorkbenchTrialAdoptionService, "preview", fail)
    read = client.post(path + "/adopt-preview", json={})
    assert read.status_code == 500
    assert read.get_json()["committed"] is False and "request_key" not in read.get_json()["error"]
    monkeypatch.setattr(WorkbenchTrialAdoptionService, "adopt", fail)
    response = client.post(path + "/adopt", json={"write_token": token, "request_key": KEY, "input": INTENT})
    assert response.status_code == 500
    error = response.get_json()["error"]
    assert response.get_json()["committed"] == "unknown" and error["code"] == "storage_failure" and error["retryable"] is False
    assert error["request_key"] == KEY and error["result_target"] == path + "/adoption-commands/" + KEY
