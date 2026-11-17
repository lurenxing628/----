"""Real draft and scenario persistence, lossless restoration and exact refs."""

from collections import Counter
from types import SimpleNamespace

import pytest
from flask import g, request

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_trial_codec import load_object
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.trial_policy import load_scenario_with_resources
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository
from tests._support.gantt_current_js import run_current_js
from tests.workbench.run_jobs_support import data_context
from tests.workbench.trial_support import (
    BASE,
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
    from core.services.workbench.trial import service as trial_service
    from core.services.workbench.trial import validation
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
    original_rows = trial_service.bind_scenario_rows
    original_facts = GenerationFacts.__init__

    def projected(*args, **kwargs):
        calls["bind_scenario_rows"] += 1
        return original_rows(*args, **kwargs)

    def generation_facts(facts, *args, **kwargs):
        calls["generation_facts"] += 1
        return original_facts(facts, *args, **kwargs)

    monkeypatch.setattr(trial_service, "bind_scenario_rows", projected)
    monkeypatch.setattr(GenerationFacts, "__init__", generation_facts)
    case.conn.set_trace_callback(statements.append)
    draft = create(case, intent)
    case.conn.set_trace_callback(None)
    assert table_reads and set(table_reads.values()) <= {1, 2} and 2 in table_reads.values()
    assert calls["draft_header"] == calls["draft_rows"] == calls["changes"] == calls["facts_unchanged"] == 0
    assert not any(
        sql.upper().startswith("SELECT") and "COUNT(" in sql.upper() and "FROM WORKBENCHTRIALROWS" in sql.upper()
        for sql in statements
    )
    assert draft["validation"]["constraints_status"] == "valid", draft["validation"]
    assert draft["validation"]["can_adopt"] is False
    # 创建时按本事务现场表投影，重新打开时按草稿存档投影：两条来源经同一读接口得到同一产能与基础方案身份。
    reopened = service(case.conn).get(draft["draft_ref"])
    assert reopened["capacity"] == draft["capacity"] and reopened["base_identity"] == draft["base_identity"]
    calls.clear()
    statements.clear()
    case.conn.set_trace_callback(statements.append)
    updated = change(case, draft)["data"]
    case.conn.set_trace_callback(None)
    assert calls["draft_header"] == calls["draft_rows"] == calls["changes"] == calls["facts_unchanged"] == 1
    assert not any(
        sql.upper().startswith("SELECT") and "COUNT(" in sql.upper() and "FROM WORKBENCHTRIALROWS" in sql.upper()
        for sql in statements
    )
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
        saved = service(conn).save(
            draft["draft_ref"],
            {"name": "Saved trial"},
            restored["write_context"]["write_token"],
            "trial-save-0000000001",
        )["data"]
        assert saved["scenario_ref"] != draft["draft_ref"]
        assert saved["tasks"][0]["task_ref"] != task["task_ref"]
        calls.clear()
        assert service(conn).scenario(saved["scenario_ref"]) == saved
        assert calls["draft_header"] == calls["draft_rows"] == calls["bind_scenario_rows"] == 1
        assert calls["generation_facts"] == (1 if kind == "candidate" else 0)
        assert service(conn).get(draft["draft_ref"])["status"] == "saved"
    finally:
        conn.close()
    assert_legacy_retained(before, snapshot(case.conn))
    repo = WorkbenchTrialRepository(case.conn)
    stored_header = repo.scenario_header(saved["scenario_ref"])
    assert stored_header is not None and "snapshot_hash" not in stored_header
    assert "resources_json" in stored_header
    raw_archive = load_object(stored_header["snapshot_json"])
    assert not ({"capacity", "change_history", "resources"} & set(raw_archive["snapshot"]))
    stored_resources = load_object(stored_header["resources_json"])
    assert set(stored_resources) == {"machines", "operators", "authorizations", "suppliers", "op_types"}
    # 任务正文只存保存时现场才有的执行状态与保护判定，其余由绑定的来源草稿行重新投影；读回仍与保存结果一致（见上）。
    assert all(set(load_object(row["payload_json"])) == {"execution", "locked"}
               for row in repo.iter_scenario_rows(saved["scenario_ref"]))
    stored_draft = repo.draft_header(draft["draft_ref"])
    assert stored_draft is not None and "admission_hash" not in stored_draft
    assert all("original_hash" not in row for row in repo.draft_rows(draft["draft_ref"]))
    admission = load_object(
        case.conn.execute(
            "SELECT admission_json FROM WorkbenchTrialDrafts WHERE draft_ref=?", (draft["draft_ref"],)
        ).fetchone()[0]
    )
    assert set(admission["facts"]) == {"columns", "tables", "revisions"}
    if kind == "candidate":
        assert "candidate_ref" in draft["base"] and "plan_ref" not in draft["base"]
        assert task["source_task_ref"] is None
        assert isinstance(admission["source"], dict)
        assert "artifact" not in admission["source"]
        assert "capture" not in admission["source"]
        assert {"run_ref", "candidate_ref", "dispositions", "identity"} <= set(admission["source"])

    # Post-save resource renames must never drift a reopened saved scenario.
    case.conn.execute("UPDATE Machines SET name='Post-save Lathe 2' WHERE machine_id='M2'")
    case.conn.execute("UPDATE Operators SET name='Post-save Operator 2' WHERE operator_id='O2'")
    case.conn.commit()
    assert service(case.conn).scenario(saved["scenario_ref"]) == saved


def test_compact_scenario_codec_strips_ui_redundancy_and_enforces_byte_limit(monkeypatch):
    from datetime import date

    from core.models import workbench_trial_scenario_archive as codec

    # 任务载荷只按键表存保存时现场才有的执行状态与保护判定；投影字段（如 part_name）、operation_effort 和所在行的
    # 三列都不存，三列读回时由永久行给出。
    tasks = [
        {
            "execution": {"remark": "保存任务正文" * 40, "sequence": index},
            "locked": False,
            "row_ref": format(index, "048x"),
            "task_ref": format(100 + index, "048x"),
            "source_row_ref": format(200 + index, "048x"),
            "part_name": "读取时重新投影",
            "operation_effort": {"before": {"ui": True}, "after": {"ui": True}},
        }
        for index in range(1, 5)
    ]
    effort = {"effort_basis": "runtime_requirement_v1", "items": []}
    resources_data = {
        "machines": [{"ref": "m1", "business_code": "M1", "label": "Lathe 1", "status": "active"}],
        "operators": [],
        "authorizations": [],
        "suppliers": [],
        "op_types": [],
    }
    snapshot_input = {
        "name": "中文试调",
        "saved_date": date(2026, 10, 15),
        "binary": b"\x00\xff",
        "operation_effort": effort,
        "comparison": {"basis": "draft_original", "preparation_common": {"recomputed": True}},
        "unplanned_operations": [{"operation_ref": "op1", "operation_effort": {"recomputed": True}}],
        "frozen_operation_refs": [],
        "capacity": {"huge_ui_tree": [1, 2, 3]},
        "change_history": [{"change_ref": "c1"}],
        "resources": {"machines": [], "operators": [], "authorizations": []},
        "tasks": tasks,
    }
    resources_json, resources_bytes = codec.encode_scenario_resources(resources_data)
    encoded = codec.encode_scenario(snapshot_input, resources_bytes=resources_bytes)
    total_bytes = (
        len(encoded.header.encode("utf-8"))
        + resources_bytes
        + sum(len(text.encode("utf-8")) for text in encoded.tasks)
    )
    expected_compact = {
        "name": "中文试调",
        "saved_date": date(2026, 10, 15),
        "binary": b"\x00\xff",
        "operation_effort": effort,
        "comparison": {"basis": "draft_original"},
        "unplanned_operations": [{"operation_ref": "op1"}],
        "frozen_operation_refs": [],
        "tasks": [{key: value for key, value in row.items() if key not in ("operation_effort", "part_name")}
                  for row in tasks],
    }
    repo = SimpleNamespace(
        conn=None,
        scenario_header=lambda _ref: {
            "scenario_ref": "saved",
            "revision": 1,
            "saved_at": "2026-09-10T12:00:00",
            "snapshot_json": encoded.header,
            "resources_json": resources_json,
        },
        iter_scenario_rows=lambda _ref: [
            {"row_ref": row["row_ref"], "task_ref": row["task_ref"], "source_row_ref": row["source_row_ref"],
             "payload_json": text}
            for row, text in zip(tasks, encoded.tasks)
        ],
    )
    assert load_scenario_with_resources(repo, "saved")[1] == expected_compact
    monkeypatch.setattr(codec, "MAX_TRIAL_BYTES", total_bytes)
    assert load_scenario_with_resources(repo, "saved")[1] == expected_compact

    def redundant(*args, **kwargs):
        raise AssertionError("Canonical stored fragments already own their text and task bodies")

    with monkeypatch.context() as read:
        read.setattr(codec, "encode_trial_text", redundant)
        assert load_scenario_with_resources(repo, "saved")[1] == expected_compact
    monkeypatch.setattr(codec, "MAX_TRIAL_BYTES", total_bytes - 1)
    for operation in (
        lambda: codec.encode_scenario(snapshot_input, resources_bytes=resources_bytes),
        lambda: load_scenario_with_resources(repo, "saved"),
    ):
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

    token = client.post("/api/workbench/v1/trial/drafts/preview", json=intent).get_json()["data"]["write_context"][
        "write_token"
    ]
    response = client.post(
        "/api/workbench/v1/trial/drafts", json={"request_key": key, "write_token": token, "input": intent}
    )
    assert response.status_code == 500
    value = response.get_json()
    assert value["committed"] == "unknown" and value["error"]["request_key"] == key and value["error"]["retryable"] is False
    assert value["error"]["result_target"] == "/api/workbench/v1/trial/commands/" + key
    lookup_data = client.get(value["error"]["result_target"]).get_json()
    assert (
        lookup_data["state"] == "recorded"
        and lookup_data["may_be_in_flight"] is False
        and lookup_data["resolution"] == "recorded"
    )



def test_http_trial_write_time_comes_from_the_app_clock(trial_case):
    from datetime import datetime

    from web.runtime_host import install_wall_clock

    case = trial_case
    intent = official(case)
    client = api(case)
    install_wall_clock(case.app, lambda: datetime(2026, 10, 7, 23, 59, 59, 900000))
    token = client.post("/api/workbench/v1/trial/drafts/preview", json=intent).get_json()["data"]["write_context"][
        "write_token"
    ]
    response = client.post(
        "/api/workbench/v1/trial/drafts", json={"request_key": "trial-create-clock-01", "write_token": token, "input": intent}
    )
    assert response.status_code == 200, response.get_json()
    draft = response.get_json()["data"]
    assert draft["created_at"] == draft["updated_at"] == "2026-10-07T23:59:59"

def test_http_trial_preview_refuses_batches_past_the_bound_and_names_it(trial_case, monkeypatch):
    from core.models import workbench_trial

    case = trial_case
    case.batch("B2")
    intent = official(case)
    refs = [case.ref("batch", "B1"), case.ref("batch", "B2")]
    client = api(case)
    monkeypatch.setattr(workbench_trial, "MAX_WINDOW_BATCHES", 1)
    admitted = client.post("/api/workbench/v1/trial/drafts/preview", json=dict(intent, scope={"batch_refs": refs[:1]}))
    assert admitted.status_code == 200, admitted.get_json()
    refused = client.post("/api/workbench/v1/trial/drafts/preview", json=dict(intent, scope={"batch_refs": refs}))
    assert refused.status_code == 400 and refused.get_json()["error"]["code"] == "invalid_input"
    assert refused.get_json()["error"]["message"] == "一次最多选 1 个批次，请缩小范围后重试。"


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

    monkeypatch.setattr(trial_service, "saved_capture", forbid)
    monkeypatch.setattr(trial_service, "live_context", forbid)
    monkeypatch.setattr(projection, "trial_capacity", forbid)
    monkeypatch.setattr(trial_service, "trial_capacity", forbid)
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
    scen_first["tasks"][0]["operation_effort"]["before"]["evidence_source"]["blocked_reasons"].append(
        {"code": "polluted"}
    )
    scen_first["comparison"]["batches"][0]["part_name"] = "POLLUTED"
    scen_first["comparison"]["delivery_summary"]["overdue_count"] = 99999
    scen_first["capacity"]["resources"][0]["label"] = "POLLUTED"
    scen_first["capacity"]["resource_common"]["cohort"].clear()
    scen_first["resources"]["machines"][0]["label"] = "POLLUTED"
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
    if draft_first["validation"]["issues"]:
        draft_first["validation"]["issues"][0]["message"] = "POLLUTED"
    draft_first["validation"]["issues"].append({"code": "polluted"})
    draft_first["validation_at_last_write"]["issues"].append({"code": "polluted"})
    draft_first["tasks"][0]["operation_effort"]["before"]["evidence_source"]["capabilities"]["view"] = False
    draft_first["tasks"][0]["operation_effort"]["before"]["evidence_source"]["blocked_reasons"].append(
        {"code": "polluted"}
    )
    if type(draft_first["tasks"][0].get("execution_at_creation")) is dict:
        draft_first["tasks"][0]["execution_at_creation"]["data_gaps"].append({"code": "polluted"})
    if type(draft_first.get("operation_effort")) is dict and draft_first["operation_effort"].get("items"):
        draft_first["operation_effort"]["items"][0]["data_gaps"].append({"code": "polluted"})

    draft_second = service(case.conn).get(draft_ref)
    assert draft_second == draft_expected
    assert draft_second["base_identity"]["display_name"] != "POLLUTED"
    assert draft_second["capacity"]["resources"][0]["calendar"]["source"]["source_ref"]["display_name"] != "POLLUTED"
    assert (
        draft_second["capacity"]["resources"][0]["calendar"]["days"][0]["source"]["source_ref"]["display_name"]
        != "POLLUTED"
    )


def test_trial_preview_and_live_validation_skip_full_archive_and_reuse_validated_intervals(trial_case, monkeypatch):
    from core.services.workbench.trial import adoption_validation

    case = trial_case
    intent = official(case)
    draft = create(case, intent)
    draft_ref = draft["draft_ref"]
    saved = service(case.conn).save(
        draft_ref, {"name": "Interval reuse scenario"}, draft["write_context"]["write_token"], "trial-save-interval-01"
    )["data"]

    from core.services.workbench.trial import validation

    interval_builds = []
    schedule_row_inputs = []
    orig_build_intervals = validation.build_trial_intervals
    orig_schedule_rows = adoption_validation.schedule_rows

    def tracked_build_intervals(*args, **kwargs):
        built = orig_build_intervals(*args, **kwargs)
        interval_builds.append(built["current_by_row"])
        return built

    def tracked_schedule_rows(rows, intervals_by_row):
        schedule_row_inputs.append(intervals_by_row)
        return orig_schedule_rows(rows, intervals_by_row)

    with monkeypatch.context() as patch:
        patch.setattr(validation, "build_trial_intervals", tracked_build_intervals)
        patch.setattr(adoption_validation, "schedule_rows", tracked_schedule_rows)
        evidence = adoption_validation.validate_trial_adoption(
            case.conn, saved["scenario_ref"], data_context=data_context(case.conn)
        )
    assert len(interval_builds) == 1 and len(schedule_row_inputs) == 1
    assert schedule_row_inputs[0] is interval_builds[0] and len(interval_builds[0]) > 0
    assert len(evidence.outcome.validated_payload.schedule_rows) == len(interval_builds[0])

    # Advance a live table revision (e.g. part name change) so archive match is False.
    case.conn.execute("UPDATE Parts SET part_name='Updated Part Name' WHERE part_no='P1'")
    case.conn.commit()

    previewed = service(case.conn).preview_create(intent)
    assert "plan_ref" in previewed["base"]
    loaded = service(case.conn).get(draft_ref)
    assert loaded["draft_ref"] == draft_ref


def test_corrupted_draft_row_end_time_is_rejected_as_damaged_draft_storage(trial_case):
    from core.models.workbench_trial_codec import dump
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

    raw_current = load_object(
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

    # 草稿行（current_json）是存储副本：起止读不出就是存储损坏，在试调行起止的唯一读边界拒收，不当成可提示的校验问题。
    with pytest.raises(WorkbenchCommandRejected) as caught:
        service(case.conn).get(draft_ref)
    assert (caught.value.code, caught.value.status) == ("trial_snapshot_invalid", 409)


_TRIAL_EXPORT_PROGRAM = r"""
const w = h.runtime, { path, before, after } = sourceData;
w.ReactDOM = { createPortal: element => element };
w.localStorage = h.memoryStorage(); w.sessionStorage = h.memoryStorage();
// 浏览器下载面：transport.saveBlob 交出的对象原样留下，读回文件内容。
const blobs = [];
w.URL = class extends URL { static createObjectURL(blob) { blobs.push(blob); return 'blob:trial-' + blobs.length; } static revokeObjectURL() {} };
w.document.createElement = () => ({ click() {}, remove() {} }); w.document.body.appendChild = () => {};
// 试调读取经真实的 TrialAPI、transport 与 TrialContract；网络应答依次取下面排好的答案。
const answers = [() => before];
h.serve({ ['GET ' + path]: () => answers.shift()() });
// 甘特、结果表和详情只负责展示（甘特要量真实 DOM），这里换成占位；导出、读取和页面状态都是真实模块。
h.setStubs({ 'TrialGantt.jsx': 'trial-gantt', 'TrialDetails.jsx': 'trial-details', 'TrialResults.jsx': { Summary: 'trial-summary', Results: 'trial-results' } });
const { TrialWorkspaceSession } = h.module('TrialWorkspace.jsx');
const page = h.mount(TrialWorkspaceSession, { initialTarget: { draft_ref: before.data.draft_ref }, onNavigate() {}, renderAdoption: () => null, onTargetChange() {} });
await page.settle();
const button = (tree, label) => h.walk(tree).find(node => node.type === 'button' && (node.props['aria-label'] === label || h.text(node) === label));
const downloads = tree => ['下载 CSV（方案对比）', '下载 CSV（准备需求）', '下载 CSV（工种切换）', '下载 JSON（原始数据）'].map(label => button(tree, label));
const exported = async () => JSON.parse(await blobs.at(-1).text());
const click = node => node.props.onClick({ currentTarget: {}, preventDefault() {} });
const waiting = '试调内容还没有重新读到，读到后才能导出。';
// 打开导出弹窗后再刷新：弹窗留着，但旧草稿不能再下载。
click(button(page.update(), '导出'));
assert(downloads(page.update()).every(node => node.props.disabled === false));
let release;
answers.push(() => new Promise((resolve, reject) => { release = { resolve, reject }; }));
click(button(page.update(), '刷新当前试调'));
let tree = await page.settle();
for (const node of downloads(tree)) assert.strictEqual(node.props.disabled, true, 'A pending refresh blocks every download in the open dialog');
assert.strictEqual(button(tree, '导出').props['data-wb-disabled-reason'], waiting);
assert(h.text(tree).includes(waiting));
assert.strictEqual(blobs.length, 0);
// 刷新失败：页面仍显示上次内容，导出照样拦住。
release.resolve(h.route.json(h.route.failure('storage_failure', '试调草稿没有读出来。', { retryable: true }), 500));
tree = await page.settle();
assert(h.text(tree).includes('试调草稿没有读出来。'));
for (const node of downloads(tree)) assert.strictEqual(node.props.disabled, true, 'A failed refresh does not export the retained draft');
assert.strictEqual(button(tree, '导出').props['data-wb-disabled-reason'], waiting);
// 读到新结果后，同一个弹窗导出的是新内容。
answers.push(() => after);
click(button(tree, '刷新当前试调'));
tree = await page.settle();
assert(downloads(tree).every(node => node.props.disabled === false) && !h.text(tree).includes(waiting));
click(downloads(tree)[3]);
await page.settle();
assert.strictEqual(blobs.length, 1);
const saved = await exported();
assert.strictEqual(saved.tasks[0].start, after.data.tasks[0].start);
assert.notStrictEqual(saved.tasks[0].start, before.data.tasks[0].start);
page.unmount();
return { exported_start: saved.tasks[0].start };
"""


def test_trial_export_reads_only_the_current_result_while_refreshing(trial_case):
    case = trial_case
    client = api(case)
    draft = create(case)
    path = BASE + "/drafts/" + draft["draft_ref"]
    before = client.get(path).get_json()
    assert change(case, draft)["ok"] is True
    after = client.get(path).get_json()
    assert before["data"]["tasks"][0]["start"] != after["data"]["tasks"][0]["start"]
    result = run_current_js(_TRIAL_EXPORT_PROGRAM, {"path": path, "before": before, "after": after})
    assert result["result"]["exported_start"] == after["data"]["tasks"][0]["start"]
