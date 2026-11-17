"""HTTP method/input boundaries, three-timepoint fidelity, original-key recovery and unknown ACK response."""

from datetime import date, datetime

import pytest
from flask import Blueprint, g, request

from core.errors import AppError, ErrorCode
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_run_job import valid_data_context_ref
from core.services.scheduler.template_lineage import TemplateLineageWriter
from core.services.workbench.batch.facts import BatchFacts
from core.services.workbench.batch.scope import BatchFactScope
from core.services.workbench.facts.run_data_context import RunDataContext, restored_context_ref
from core.services.workbench.trial.adoption import WorkbenchTrialAdoptionService
from core.services.workbench.trial.adoption_history import WorkbenchTrialAdoptionHistoryService
from tests.workbench.trial_adoption_support import BASE, INTENT, KEY, api, preview, saved_scenario
from tests.workbench.trial_adoption_support import service as adoption_service
from tests.workbench.trial_adoption_support import trial_case as trial_case
from tests.workbench.trial_support import CommitFailureConnection, candidate, change, create, snapshot
from tests.workbench.trial_support import service as trial_service
from web.routes.workbench.read_context import bind_read_snapshot


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
    preview_data = preview_payload["data"]
    assert preview_data["scenario_ref"] == saved["scenario_ref"] and preview_data["draft_ref"] == saved["draft_ref"]
    assert preview_data["validation"]["can_adopt"] and snapshot(case.conn) == before
    body = {"write_token": preview_data["write_context"]["write_token"], "request_key": KEY, "input": INTENT}
    response = client.post(path + "/adopt", json=body)
    assert response.status_code == 200, response.get_json()
    result = response.get_json()
    context = {"data_context_ref": preview_data["data_context_ref"]}
    receipt_resp = client.get(path + "/adoption-commands/" + KEY, query_string=context)
    assert receipt_resp.status_code == 200 and receipt_resp.headers["Cache-Control"] == "no-store"
    receipt = receipt_resp.get_json()
    assert receipt == {
        "state": "recorded",
        "receipt": {**result, "replayed": True},
        "may_be_in_flight": False,
        "resolution": "recorded",
        "data_context_ref": preview_data["data_context_ref"],
    }
    history_entry = case.conn.execute(
        "SELECT entry_ref, timeline, source_kind, scenario_ref, draft_ref, plan_ref, plan_version, receipt_ref "
        "FROM WorkbenchHistoryEntries WHERE request_key=?",
        (KEY,),
    ).fetchone()
    assert history_entry is not None
    assert history_entry["entry_ref"] == "adoption:" + result["receipt_ref"]
    assert history_entry["timeline"] == "official"
    assert history_entry["source_kind"] == "trial_adoption"
    assert history_entry["scenario_ref"] == saved["scenario_ref"]
    assert history_entry["draft_ref"] == saved["draft_ref"]
    assert history_entry["plan_ref"] == result["data"]["official_plan"]["plan_ref"]
    assert history_entry["plan_version"] == result["data"]["official_plan"]["version"]
    assert history_entry["receipt_ref"] == result["receipt_ref"]

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
    selected_histories = [sql for sql in queries if "FROM SCHEDULEHISTORY WHERE VERSION" in sql and "PLAN_REF" in sql]
    assert len(selected_histories) == 1
    assert snapshot(case.conn) == before and case.conn.total_changes == changes
    with case.app.app_context():
        assert bind_read_snapshot(history["scope"], history_state, as_of=datetime(2026, 10, 18, 4, 0))["snapshot_ref"]
    entry = history["items"][0]
    assert entry["adoption"]["reason"] == INTENT["reason"]
    assert entry["adoption"]["declared_operator"] == INTENT["declared_operator"]
    assert not any(gap["code"].startswith("audit_") for gap in entry["evidence_gaps"])
    history_row = case.conn.execute(
        "SELECT source_kind, source_ref, draft_ref FROM ScheduleHistory WHERE version=?",
        (result["data"]["official_plan"]["version"],),
    ).fetchone()
    assert history_row["source_kind"] == "trial_adoption"
    assert history_row["source_ref"] == saved["scenario_ref"]
    assert history_row["draft_ref"] == saved["draft_ref"]
    assert client.get(path + "/adopt").status_code == 405
    unknown = client.get(path + "/adoption-commands/not-yet-seen-request", query_string=context).get_json()
    assert unknown == {
        "state": "not_observed",
        "receipt": None,
        "may_be_in_flight": True,
        "resolution": "unresolved",
        "data_context_ref": preview_data["data_context_ref"],
    }


@pytest.mark.parametrize(("field", "value"), [("reason", ""), ("declared_operator", "a\x00b")])
def test_http_trial_adopt_rejection_points_at_the_reason_or_operator_field(trial_case, field, value):
    case = trial_case
    saved = saved_scenario(case)
    client = api(case)
    path = BASE + saved["scenario_ref"]
    token = client.post(path + "/adopt-preview", json={}).get_json()["data"]["write_context"]["write_token"]
    before = snapshot(case.conn)
    response = client.post(path + "/adopt", json={"write_token": token, "request_key": KEY, "input": {**INTENT, field: value}})
    assert response.status_code == 422, response.get_json()
    error = response.get_json()["error"]
    message = "采用原因或声明操作人为空、过长或含无效字符。"
    assert (error["code"], error["message"], error["fields"]) == ("invalid_input", message, [{"path": field, "message": message}])
    assert snapshot(case.conn) == before


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

    adopted = client.post(
        path + "/adopt",
        json={"write_token": checked["write_context"]["write_token"], "request_key": KEY, "input": INTENT},
    )
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


def test_trial_adoption_preserves_three_timepoint_resource_labels(trial_case):
    """Source (T1), draft admission (T2) and scenario save (T3) labels remain distinct across post-save renames."""
    case = trial_case
    case.conn.execute("UPDATE OpTypes SET category='both', name='Turning T1' WHERE op_type_id='T1'")
    case.conn.execute("UPDATE Machines SET name='Lathe 1 T1' WHERE machine_id='M1'")
    case.conn.execute("UPDATE Machines SET name='Lathe 2 T1' WHERE machine_id='M2'")
    case.conn.execute("UPDATE Operators SET name='Operator 1 T1' WHERE operator_id='O1'")
    case.conn.execute("UPDATE Operators SET name='Operator 2 T1' WHERE operator_id='O2'")
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name,default_days) VALUES ('S1','Supplier T1',1)")
    case.conn.execute("INSERT INTO WorkbenchSupplierOpTypes(supplier_id,op_type_id) VALUES ('S1','T1')")
    op2_id = case.operation(seq=2, setup_hours=0, unit_hours=1)
    with TransactionManager(case.conn).transaction():
        writer = TemplateLineageWriter(case.conn)
        cursor = case.conn.execute(
            "INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,"
            "ext_days,setup_hours,unit_hours) VALUES ('P1',3,'T1','Turning','external','S1',1,0,0)"
        )
        prepared_tpl = writer.prepare_templates(
            [{"id": cursor.lastrowid}], facts=BatchFactScope(BatchFacts(case.conn, material_day=date.today().isoformat())).load()
        )
        ext_op_id = writer.copy_prepared_template("B1", prepared_tpl[0])
    case.conn.commit()

    # T1: Run and persist immutable candidate under T1 labels.
    base_intent = candidate(case)

    # Between T1 and T2: rename resources before creating the trial draft.
    case.conn.execute("UPDATE OpTypes SET name='Turning T2' WHERE op_type_id='T1'")
    case.conn.execute("UPDATE Machines SET name='Lathe 1 T2' WHERE machine_id='M1'")
    case.conn.execute("UPDATE Machines SET name='Lathe 2 T2' WHERE machine_id='M2'")
    case.conn.execute("UPDATE Operators SET name='Operator 1 T2' WHERE operator_id='O1'")
    case.conn.execute("UPDATE Operators SET name='Operator 2 T2' WHERE operator_id='O2'")
    case.conn.execute("UPDATE Suppliers SET name='Supplier T2' WHERE supplier_id='S1'")
    case.conn.commit()

    # T2: Create trial draft; move op2 onto M2/O2 (new_slot=True) while keeping op1 and ext_op unchanged.
    draft = create(case, base_intent, key="three-timepoint-create-01")
    op2_index = next(idx for idx, task in enumerate(draft["tasks"]) if task["sequence"] == 2)
    adjusted = change(
        case,
        draft,
        task=op2_index,
        start="2026-09-09T11:00:00",
        machine="M2",
        operator="O2",
        key="three-timepoint-change-01",
    )["data"]
    ext_index = next(idx for idx, task in enumerate(adjusted["tasks"]) if task["sequence"] == 3)
    adjusted = change(
        case,
        adjusted,
        task=ext_index,
        start="2026-09-09T14:00:00",
        machine=None,
        operator=None,
        key="three-timepoint-change-02",
    )["data"]
    assert adjusted["validation"]["constraints_status"] == "valid", adjusted["validation"]

    # T3: Save scenario and adopt into Official Plan.
    saved = trial_service(case.conn).save(
        adjusted["draft_ref"],
        {"name": "Three-timepoint scenario"},
        adjusted["write_context"]["write_token"],
        "three-timepoint-save-01",
    )["data"]
    token = preview(case, saved)
    adopted = adoption_service(case.conn).adopt(
        saved["scenario_ref"], token, "three-timepoint-adopt-01", INTENT
    )
    version = adopted["data"]["official_plan"]["version"]
    by_op = {
        row["op_id"]: dict(row)
        for row in case.conn.execute(
            "SELECT op_id, machine_label, operator_label, supplier_label, op_type_label "
            "FROM Schedule WHERE version=?",
            (version,),
        ).fetchall()
    }
    # Retained internal op1: T2 draft machine/operator labels + T1 source op_type label.
    assert by_op[case.op_id]["machine_label"] == "Lathe 1 T2"
    assert by_op[case.op_id]["operator_label"] == "Operator 1 T2"
    assert by_op[case.op_id]["op_type_label"] == "Turning T1"
    # Newly scheduled internal op2: T3 scenario save resources_json labels.
    assert by_op[op2_id]["machine_label"] == "Lathe 2 T2"
    assert by_op[op2_id]["operator_label"] == "Operator 2 T2"
    assert by_op[op2_id]["op_type_label"] == "Turning T2"
    # External op3: supplier_id unchanged, freezes T1 source supplier label.
    assert by_op[ext_op_id]["supplier_label"] == "Supplier T1"

    # T4: Post-save renames do not drift reopened saved scenario resources.
    case.conn.execute("UPDATE Machines SET name='Lathe 2 T4' WHERE machine_id='M2'")
    case.conn.execute("UPDATE Operators SET name='Operator 2 T4' WHERE operator_id='O2'")
    case.conn.commit()
    reopened = trial_service(case.conn).scenario(saved["scenario_ref"])
    machines_by_code = {item["business_code"]: item["label"] for item in reopened["resources"]["machines"]}
    operators_by_code = {item["business_code"]: item["label"] for item in reopened["resources"]["operators"]}
    assert machines_by_code["M2"] == "Lathe 2 T2"
    assert operators_by_code["O2"] == "Operator 2 T2"

    # Official-plan-based trial: rename OpTypes(T1) and Suppliers(S1) before creating draft from v1;
    # unchanged operations in v2 must retain v1's frozen source-time op_type_label and supplier_label.
    case.conn.execute("UPDATE OpTypes SET name='Turning T4' WHERE op_type_id='T1'")
    case.conn.execute("UPDATE Suppliers SET name='Supplier T4' WHERE supplier_id='S1'")
    case.conn.commit()
    official_draft = create(
        case,
        {"base": {"plan_ref": adopted["data"]["official_plan"]["plan_ref"]}},
        key="three-timepoint-create-02",
    )
    official_saved = trial_service(case.conn).save(
        official_draft["draft_ref"],
        {"name": "Official-base three-timepoint scenario"},
        official_draft["write_context"]["write_token"],
        "three-timepoint-save-02",
    )["data"]
    official_token = preview(case, official_saved)
    adopted_v2 = adoption_service(case.conn).adopt(
        official_saved["scenario_ref"], official_token, "three-timepoint-adopt-02", INTENT
    )
    version_v2 = adopted_v2["data"]["official_plan"]["version"]
    by_op_v2 = {
        row["op_id"]: dict(row)
        for row in case.conn.execute(
            "SELECT op_id, machine_label, operator_label, supplier_ref, supplier_label, op_type_label "
            "FROM Schedule WHERE version=?",
            (version_v2,),
        ).fetchall()
    }
    assert by_op_v2[case.op_id]["op_type_label"] == "Turning T1"
    assert by_op_v2[op2_id]["op_type_label"] == "Turning T2"
    # The external operation's type is its archived operation's too, frozen at the source time like the others.
    assert by_op_v2[ext_op_id]["op_type_label"] == "Turning T1"
    assert by_op_v2[ext_op_id]["supplier_label"] == "Supplier T1"
    assert by_op_v2[ext_op_id]["supplier_ref"] == case.ref("supplier", "S1")


def test_http_ack_unknown_points_to_original_scenario_and_key(trial_case):
    case = trial_case
    saved = saved_scenario(case)
    client = api(case, factory=CommitFailureConnection)
    path = BASE + saved["scenario_ref"]

    @case.app.before_request
    def lose_ack():
        if request.path.endswith("/adopt"):
            g.db.fail_commit = g.db.acknowledge_only = True

    preview_data = client.post(path + "/adopt-preview", json={}).get_json()["data"]
    response = client.post(
        path + "/adopt",
        json={"write_token": preview_data["write_context"]["write_token"], "request_key": KEY, "input": INTENT},
    )
    assert response.status_code == 500
    value = response.get_json()
    assert value["committed"] == "unknown" and value["error"]["request_key"] == KEY
    assert value["error"]["result_target"] == path + "/adoption-commands/" + KEY
    assert value["error"]["retryable"] is False
    receipt = client.get(
        value["error"]["result_target"],
        query_string={"data_context_ref": preview_data["data_context_ref"]},
    ).get_json()
    assert receipt["state"] == "recorded" and receipt["may_be_in_flight"] is False and receipt["resolution"] == "recorded"
    assert receipt["data_context_ref"] == preview_data["data_context_ref"]
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


def test_unreadable_trial_row_json_surfaces_as_typed_storage_corruption(trial_case):
    from core.models.content import StoredJsonCorrupt

    # 已保存方案的存档列和草稿行都由触发器锁定，坏文本只能写进编辑中草稿的 current_json；
    # 它和已保存方案的草稿行走同一个 load_draft 解码。读不出来就是带类型的存储损坏，原样上抛 500。
    case = trial_case
    draft = create(case)
    case.conn.execute("UPDATE WorkbenchTrialRows SET current_json='{' WHERE draft_ref=?", (draft["draft_ref"],))
    case.conn.commit()
    with pytest.raises(StoredJsonCorrupt) as raised:
        trial_service(case.conn).get(draft["draft_ref"])
    assert (raised.value.code, raised.value.status) == ("storage_failure", 500)


def test_unreadable_live_calendar_in_adoption_preview_stays_storage_failure(trial_case):
    from core.models.content import StoredJsonCorrupt

    # 试调采用只把已保存方案的存档读不出来说成“不能采用”；活表日历读不出来是存储损坏，照常 500，不归到试调数据头上。
    case = trial_case
    saved = saved_scenario(case)
    assert case.conn.execute("UPDATE WorkbenchCalendarDefaults SET periods_json='{'").rowcount > 0
    case.conn.commit()
    with pytest.raises(StoredJsonCorrupt) as raised:
        adoption_service(case.conn).preview(saved["scenario_ref"])
    assert (raised.value.code, raised.value.status) == ("storage_failure", 500)
