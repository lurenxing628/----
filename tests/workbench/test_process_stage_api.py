"""Public stage API: full-row preservation, preflight binding and atomic receipts."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier

import pytest

from core.services.workbench.commands import WorkbenchCommandService
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from tests.workbench.process_stage_api_support import (
    BASE,
    PART,
    rejected,
    seed_stage_scale,
    stage_api_fixture,
    success,
)

_stage_fixture = stage_api_fixture
ACTIONS = ("route_confirm", "source_confirm", "hours_confirm")


@pytest.mark.parametrize("mode", ("text", "rows"))
def test_detail_preview_and_three_confirmations_preserve_every_business_row(stage_api, mode):
    api = stage_api
    api.execute("UPDATE PartOperations SET op_type_id='PROC-Q',setup_hours=5.5,unit_hours=6.75 WHERE part_no=? AND seq=10", (PART,))
    if mode == "rows":
        api.execute("UPDATE Parts SET route_raw=? WHERE part_no=?", ("10车削\n20热处理\n30检验", PART))
    before = api.preserved()
    original = api.detail()
    assert original["data"]["workflow"]["origin"] == "legacy"
    assert original["data"]["write_context"] is None
    assert original["data"]["capabilities"]["stage_confirm"] is True
    for action, stage in zip(ACTIONS, ("route", "source", "hours")):
        payload = {"route": api.route(), "discard_group_refs": []} if stage == "route" else getattr(api, stage)()
        if stage == "route" and mode == "rows":
            payload["route"] = {"mode": "rows", "rows": [{"seq": row["sequence"], "op_type_name": row["label"]}
                                                           for row in original["data"]["operations"]]}
        stored = api.snapshot()
        body = api.body(action, payload)
        assert api.snapshot() == stored
        receipt = success(api.post(action, body))
        assert receipt["result"] == "committed" and receipt["replayed"] is False
        assert api.preserved() == before
        current = api.detail()["data"]
        assert current["workflow"][stage]["state"] == "confirmed"
        assert current["workflow"][stage]["confirmed_at"]
        assert current["workflow"][stage]["confirmed_by"] is None
        if stage != "route":
            assert all(row["confirmation"][stage]["state"] == "confirmed" for row in current["operations"])
    assert current["workflow"]["ready"] and current["workflow"]["stage"] == "ready"
    assert len(api.rows("WorkbenchCommandReceipts")) == 3
    assert len(api.rows("WorkbenchProcessOperationConfirmations")) == 6


@pytest.mark.parametrize("action", ACTIONS[:2])
def test_preview_token_cannot_confirm_changed_input(stage_api, action):
    body = stage_api.intent(action)
    if action == "route_confirm":
        body["input"]["route"]["route_raw"] += " "
    else:
        body["input"]["operations"][0]["op_type_ref"] = stage_api.ref("op_type", "PROC-Q")
    before = stage_api.snapshot()
    rejected(stage_api.post(action, body), "stale_write")
    assert stage_api.snapshot() == before


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("change", ("unknown_token", "other_part", "other_action"))
def test_token_subject_and_action_are_not_interchangeable(stage_api, action, change):
    api = stage_api
    body = api.intent(action)
    code = PART
    if change == "unknown_token":
        body["write_token"] = "expired-or-unknown"
    elif change == "other_part":
        code = "PROC-002"
    else:
        other = {"route": api.route(), "discard_group_refs": []}
        if action == "route_confirm":
            api.prepare()
            body["write_token"] = api.context("hours_confirm", api.hours())["write_token"]
        else:
            body["write_token"] = api.context("route_confirm", other)["write_token"]
    before = api.snapshot()
    rejected(api.post(action, body, code), "stale_write")
    assert api.snapshot() == before


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("sql", (
    "UPDATE PartOperations SET unit_hours=.75 WHERE part_no='PROC-001' AND seq=10",
    "UPDATE ExternalGroups SET total_days=9 WHERE group_id='PROC-G'",
    "UPDATE Parts SET remark='changed' WHERE part_no='PROC-001'",
    "DELETE FROM WorkbenchSupplierOpTypes WHERE supplier_id='PROC-S'",
))
def test_changed_facts_reject_old_write_token(stage_api, action, sql):
    body = stage_api.intent(action)
    stage_api.execute(sql)
    before = stage_api.snapshot()
    rejected(stage_api.post(action, body), "stale_write")
    assert stage_api.snapshot() == before


@pytest.mark.parametrize("action", ACTIONS[:2])
def test_exact_group_ack_is_required_and_unrelated_history_is_preserved(stage_api, action):
    api = stage_api
    body = api.intent(action)
    if action == "route_confirm":
        body["input"]["route"]["route_raw"] = "10车削30检验"
    else:
        body["input"]["operations"][1].update(source="internal", op_type_ref=api.ref("op_type", "PROC-IN"), supplier_ref=None)
    before = api.snapshot()
    preview = success(api.preview(action, body["input"]))["data"]
    group = api.ref("template_external_group", "PROC-G")
    assert [row["ref"] for row in preview["affected_groups"]] == [group]
    body["write_token"] = preview["write_context"]["write_token"]
    assert api.snapshot() == before
    for ack in ([], ["f" * 48], [group, "f" * 48], [group, group]):
        body["input"]["discard_group_refs"] = ack
        rejected(api.post(action, body), "invalid_input" if len(ack) == 2 and ack[0] == ack[1] else "group_discard_required",
                 422 if len(ack) == 2 and ack[0] == ack[1] else 409)
        assert api.snapshot() == before
    old_ops = api.rows("PartOperations")
    body["input"]["discard_group_refs"] = [group]
    success(api.post(action, body))
    for old, new in zip(old_ops, api.rows("PartOperations")):
        expected = dict(old)
        if old["part_no"] == PART and old["seq"] == 20:
            expected["ext_group_id"] = None
            expected.update({"status": "deleted"} if action == "route_confirm" else
                            {"source": "internal", "op_type_id": "PROC-IN", "supplier_id": None})
        assert new == expected
    for table in ("Batches", "BatchOperations", "Schedule", "OpTypes", "Suppliers"):
        assert api.snapshot()[1][table] == before[1][table]
    assert api.rows("ExternalGroups") == []
    assert api.rows("WorkbenchEntityRefs", "ref=?", (group,))[0]["active"] == 0


@pytest.mark.parametrize("action", ("source_confirm", "hours_confirm"))
@pytest.mark.parametrize("change", ("missing", "duplicate", "foreign", "deleted", "wrong_kind"))
def test_complete_active_operation_sets_are_required_over_http(stage_api, action, change):
    api = stage_api
    body = api.intent(action)
    rows = body["input"]["operations"]
    if change == "missing":
        rows.pop()
    elif change == "duplicate":
        rows.append(dict(rows[0]))
    else:
        rows[0]["ref"] = api.ref() if change == "wrong_kind" else api.detail("PROC-004" if change == "deleted" else "PROC-003")["data"]["operations"][0]["ref"]
    before = api.snapshot()
    # Source's preflight must also reject; its old token cannot bless a different set.
    response = api.preview(action, body["input"]) if action == "source_confirm" else api.post(action, body)
    rejected(response, "invalid_input" if change == "duplicate" else "operation_set_mismatch", 422 if change == "duplicate" else 409)
    assert api.snapshot() == before


@pytest.mark.parametrize("field", ("setup_hours", "unit_hours", "external_days", "total_days"))
@pytest.mark.parametrize("bad", (True, False, None, "1", -1, float("nan"), float("inf")))
def test_json_numbers_are_strict_and_fail_without_any_write(stage_api, field, bad):
    if field == "external_days" and bad is None:
        stage_api.execute("UPDATE ExternalGroups SET merge_mode='separate' WHERE group_id='PROC-G'")
    body = stage_api.intent("hours_confirm")
    row = body["input"]["groups"][0] if field == "total_days" else next(row for row in body["input"]["operations"] if field in row)
    row[field] = bad
    before = stage_api.snapshot()
    code = "external_days_required" if field == "external_days" and bad is None else "invalid_input"
    rejected(stage_api.post("hours_confirm", body), code, 422)
    assert stage_api.snapshot() == before


@pytest.mark.parametrize("change,code,status", (("zero", "zero_unit_hours_confirmation_required", 422),
    ("zero_period", "invalid_input", 422), ("zero_total", "invalid_input", 422), ("bool_review", "invalid_input", 422),
    ("missing_group", "group_set_mismatch", 409), ("foreign_group", "group_set_mismatch", 409),
    ("duplicate_group", "invalid_input", 422), ("source_shape", "hours_source_mismatch", 422)))
def test_hours_review_groups_and_source_specific_fields(stage_api, change, code, status):
    body = stage_api.intent("hours_confirm")
    payload = body["input"]
    if change in ("zero", "bool_review"):
        payload["confirm_zero_unit_hours"] = False if change == "zero" else 1
    elif change == "zero_period":
        payload["operations"][1]["external_days"] = 0
    elif change == "zero_total":
        payload["groups"][0]["total_days"] = 0
    elif change == "missing_group":
        payload["groups"] = []
    elif change == "foreign_group":
        payload["groups"][0]["ref"] = "f" * 48
    elif change == "duplicate_group":
        payload["groups"].append(dict(payload["groups"][0]))
    else:
        payload["operations"][0] = {"ref": payload["operations"][0]["ref"], "external_days": 2}
    before = stage_api.snapshot()
    response = stage_api.post("hours_confirm", body)
    rejected(response, code, status)
    if change == "zero":
        expected = {"operations." + row["ref"] + ".unit_hours" for row in payload["operations"]
                    if row.get("unit_hours") == 0}
        assert {row["path"] for row in response.get_json()["error"]["fields"]} == expected
    assert stage_api.snapshot() == before


@pytest.mark.parametrize("change,code", (("category", "source_category_mismatch"), ("inactive", "supplier_unavailable"),
    ("capability", "supplier_capability_mismatch"), ("confirmed", "invalid_input"), ("wrong_type", "invalid_relation")))
def test_source_rejects_invalid_resources_and_requires_literal_confirmation(stage_api, change, code):
    api = stage_api
    api.prepare("source")
    payload = api.source()
    row = payload["operations"][1]
    if change == "category":
        row.update(source="internal", supplier_ref=None)
    elif change == "inactive":
        api.execute("UPDATE Suppliers SET status='inactive' WHERE supplier_id='PROC-S'")
    elif change == "capability":
        api.execute("DELETE FROM WorkbenchSupplierOpTypes WHERE supplier_id='PROC-S'")
        api.execute("UPDATE Suppliers SET op_type_id=NULL WHERE supplier_id='PROC-S'")
    elif change == "confirmed":
        row["confirmed"] = 1
    else:
        row["op_type_ref"] = row["supplier_ref"]
    before = api.snapshot()
    rejected(api.preview("source_confirm", payload), code, 422)
    assert api.snapshot() == before


@pytest.mark.parametrize("endpoint", ("route-preview", "stage-preview", "route_confirm", "source_confirm", "hours_confirm"))
@pytest.mark.parametrize("raw", ('{"input":{},"input":{}}', '{"input":{"ref":1,"ref":2}}', '[1]', '{', 'null'))
def test_duplicate_and_malformed_json_rejected_before_domain_calls(stage_api, endpoint, raw):
    before = stage_api.snapshot()
    response = stage_api.client.post(BASE + "/process/" + stage_api.ref() + "/" + endpoint, data=raw, content_type="application/json")
    rejected(response, "invalid_input", 400)
    assert stage_api.snapshot() == before


@pytest.mark.parametrize("endpoint,limit", (("route-preview", 1024 ** 2), ("stage-preview", 4 * 1024 ** 2), ("hours_confirm", 4 * 1024 ** 2)))
def test_oversize_body_is_rejected_not_truncated(stage_api, endpoint, limit):
    before = stage_api.snapshot()
    response = stage_api.client.post(BASE + "/process/" + stage_api.ref() + "/" + endpoint,
                                     data=" " * (limit + 1), content_type="application/json")
    rejected(response, "capacity_exceeded", 413)
    assert stage_api.snapshot() == before


@pytest.mark.parametrize("action", ACTIONS)
def test_receipt_first_replay_survives_expiry_but_changed_intent_conflicts(stage_api, action):
    api = stage_api
    body = api.intent(action)
    first = success(api.post(action, body))
    api.execute("UPDATE Parts SET remark='edited after committed receipt' WHERE part_no=?", (PART,))
    body["write_token"] = "expired"
    if action != "route_confirm":
        body["input"]["operations"].reverse()
    before = api.snapshot()
    second = success(api.post(action, body))
    assert second == {**first, "replayed": True}
    assert success(api.client.get(BASE + "/commands/" + body["request_key"])) == second
    if action == "route_confirm":
        body["input"]["route"]["route_raw"] += " "
    elif action == "source_confirm":
        body["input"]["operations"][0]["op_type_ref"] = api.ref("op_type", "PROC-IN")
    else:
        body["input"]["operations"][0]["unit_hours"] = 7
    rejected(api.post(action, body), "request_key_conflict")
    assert api.snapshot() == before


@pytest.mark.parametrize("action", ACTIONS)
@pytest.mark.parametrize("failure", ("business", "confirmation", "receipt"))
def test_transaction_failures_roll_back_rows_refs_confirmations_and_receipt(stage_api, monkeypatch, action, failure):
    api = stage_api
    body = api.intent(action)
    if action == "route_confirm":
        body["input"]["route"]["route_raw"] += "40新序"
    elif action == "source_confirm":
        body["input"]["operations"][0]["op_type_ref"] = api.ref("op_type", "PROC-Q")
    else:
        body["input"]["operations"][0]["unit_hours"] = 9
    body["write_token"] = api.context(action, body["input"])["write_token"]
    import core.services.process.workflow_state as workflow
    import core.services.workbench.process_mutations as mutations

    owner, name = ((WorkbenchCommandRepository, "insert") if failure == "receipt" else
                   (workflow, "record_confirmation") if failure == "confirmation" else
                   (mutations, {"route_confirm": "apply_route", "source_confirm": "apply_source", "hours_confirm": "apply_hours"}[action]))
    original = getattr(owner, name)
    touched = []

    def fail_after(*args, **kwargs):
        original(*args, **kwargs)
        touched.append(True)
        raise OSError("stage API injected failure after " + failure)

    before = api.snapshot()
    with monkeypatch.context() as patch:
        patch.setattr(owner, name, fail_after)
        error = rejected(api.post(action, body), "storage_failure", 500, committed="unknown")["error"]
    assert touched == [True] and api.snapshot() == before
    assert error["request_key"] == body["request_key"]
    missing = success(api.client.get(error["result_target"]))
    assert missing["state"] == "not_recorded" and missing["may_be_in_flight"] is True
    first = success(api.post(action, body))
    assert success(api.post(action, body)) == {**first, "replayed": True}


def test_response_lost_after_commit_recovers_persisted_receipt(stage_api, monkeypatch):
    api = stage_api
    body = api.intent("hours_confirm")
    original = WorkbenchCommandService.execute

    def lose_response(self, **kwargs):
        original(self, **kwargs)
        raise OSError("simulated response loss after actual SQLite commit")

    with monkeypatch.context() as patch:
        patch.setattr(WorkbenchCommandService, "execute", lose_response)
        error = rejected(api.post("hours_confirm", body), "storage_failure", 500, committed="unknown")["error"]
    committed = api.snapshot()
    receipt = success(api.client.get(error["result_target"]))
    assert receipt["result"] == "committed" and receipt["replayed"] is True
    assert api.detail()["data"]["workflow"]["ready"]
    assert success(api.post("hours_confirm", body)) == receipt
    assert api.snapshot() == committed


def test_removed_restored_and_physically_recreated_operations_never_reuse_old_confirmations(stage_api):
    api = stage_api
    api.prepare()
    api.confirm("hours_confirm", api.hours())
    original = api.detail()["data"]["operations"][2]
    for text in ("10车削20热处理", "10车削20热处理30检验"):
        api.confirm("route_confirm", {"route": {"mode": "text", "route_raw": text}, "discard_group_refs": []})
    restored = api.detail()["data"]["operations"][2]
    assert restored["ref"] == original["ref"]
    assert restored["confirmation"]["source"]["state"] == "unconfirmed"
    api.execute("DELETE FROM PartOperations WHERE part_no=? AND seq=30", (PART,))
    api.confirm("route_confirm", {"route": api.route(), "discard_group_refs": []})
    rebuilt = api.detail()["data"]["operations"][2]
    assert rebuilt["ref"] != original["ref"]
    assert api.rows("WorkbenchEntityRefs", "ref=?", (original["ref"],))[0]["active"] == 0
    assert rebuilt["confirmation"]["source"]["state"] == "unconfirmed"
    assert api.detail()["data"]["workflow"]["ready"] is False


@pytest.mark.parametrize("count", (2000, 10000))
def test_full_existing_stage_collections_survive_real_http_roundtrip(stage_api, count):
    api = stage_api
    code = "API-SCALE-" + str(count)
    with api.database() as conn:
        seed_stage_scale(conn, code, count)
    before = api.preserved()
    detail = api.detail(code)["data"]
    assert len(detail["operations"]) == count
    api.confirm("source_confirm", api.source(code), code)
    payload = api.hours(code)
    for index, row in enumerate(payload["operations"]):
        row["unit_hours"] = index + .125
    api.confirm("hours_confirm", payload, code)
    result = api.detail(code)["data"]
    assert result["workflow"]["ready"]
    assert [row["unit_hours"] for row in result["operations"]] == [i + .125 for i in range(count)]
    assert len({row["ref"] for row in result["operations"]}) == count
    assert len(api.rows("WorkbenchProcessOperationConfirmations", "part_ref=?", (result["ref"],))) == count * 2
    for table in ("Batches", "BatchOperations", "Schedule", "ExternalGroups"):
        assert api.preserved()[table] == before[table]


@pytest.mark.parametrize("action", ACTIONS)
def test_concurrent_same_key_produces_one_commit_and_one_replay(stage_api, action):
    api = stage_api
    body = api.intent(action)
    before = len(api.rows("WorkbenchCommandReceipts"))
    barrier = Barrier(2)
    url = BASE + "/process/" + api.ref() + "/" + action

    def submit():
        with api.client.application.test_client() as client:
            barrier.wait(timeout=15)
            return success(client.post(url, json=deepcopy(body)))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(), range(2)))
    assert {row["replayed"] for row in results} == {False, True}
    assert results[0]["receipt_ref"] == results[1]["receipt_ref"]
    assert len(api.rows("WorkbenchCommandReceipts")) == before + 1


def test_part_recreated_with_same_business_code_has_new_ref_and_no_old_workflow(stage_api):
    api = stage_api
    code = "PROC-002"
    payload = {"route": {"mode": "text", "route_raw": "10车削"}, "discard_group_refs": []}
    body = api.body("route_confirm", payload, code)
    original_ref = api.ref(code=code)
    first = success(api.post("route_confirm", body, code))
    api.execute("DELETE FROM Parts WHERE part_no=?", (code,))
    api.execute("INSERT INTO Parts(part_no,part_name) VALUES (?,?)", (code, "recreated part"))
    assert api.ref(code=code) != original_ref
    assert api.detail(code)["data"]["workflow"]["origin"] == "legacy"
    before = api.snapshot()
    old_url = BASE + "/process/" + original_ref + "/route_confirm"
    assert success(api.client.post(old_url, json=body)) == {**first, "replayed": True}
    rejected(api.post("route_confirm", body, code), "request_key_conflict")
    body["request_key"] += "-new"
    rejected(api.post("route_confirm", body, code), "stale_write")
    rejected(api.client.get(BASE + "/entities/part/" + original_ref), "entity_not_found", 404)
    assert api.snapshot() == before


def test_recreated_group_needs_new_preview_ref_and_exact_ack(stage_api):
    api = stage_api
    payload = {"route": {"mode": "text", "route_raw": "10车削30检验"}, "discard_group_refs": []}
    old = api.ref("template_external_group", "PROC-G")
    body = api.body("route_confirm", payload)
    body["input"]["discard_group_refs"] = [old]
    with api.database() as conn:
        group = dict(conn.execute("SELECT * FROM ExternalGroups WHERE group_id='PROC-G'").fetchone())
        conn.execute("DELETE FROM ExternalGroups WHERE group_id='PROC-G'")
        conn.execute("INSERT INTO ExternalGroups (" + ",".join(group) + ") VALUES (" + ",".join("?" for _ in group) + ")", list(group.values()))
    new = api.ref("template_external_group", "PROC-G")
    assert new != old
    before = api.snapshot()
    rejected(api.post("route_confirm", body), "stale_write")
    preview = success(api.preview("route_confirm", payload))["data"]
    assert [row["ref"] for row in preview["affected_groups"]] == [new]
    body["write_token"] = preview["write_context"]["write_token"]
    rejected(api.post("route_confirm", body), "group_discard_required")
    assert api.snapshot() == before
    body["input"]["discard_group_refs"] = [new]
    success(api.post("route_confirm", body))


@pytest.mark.parametrize("change,code,status", (("locked", "stage_locked", 409), ("stale", "snapshot_stale", 409),
    ("wrong_scope", "snapshot_stale", 409), ("action", "invalid_input", 400), ("missing_snapshot", "invalid_input", 400)))
def test_source_preview_requires_fresh_bound_detail_and_previous_stage(stage_api, change, code, status):
    api = stage_api
    if change != "locked":
        api.prepare("source")
    body = {"action": "source_confirm", "input": api.source(), "snapshot_ref": api.detail()["meta"]["snapshot_ref"]}
    if change == "stale":
        api.execute("UPDATE Parts SET remark='stale preview' WHERE part_no=?", (PART,))
    elif change == "wrong_scope":
        body["snapshot_ref"] = success(api.client.get(BASE + "/entities/part"))["meta"]["snapshot_ref"]
    elif change == "action":
        body["action"] = "hours_confirm"
    elif change == "missing_snapshot":
        del body["snapshot_ref"]
    before = api.snapshot()
    rejected(api.post("stage-preview", body), code, status)
    assert api.snapshot() == before


@pytest.mark.parametrize("action", ("source_confirm", "hours_confirm"))
def test_http_rejects_10001_stage_rows_without_truncation(stage_api, action):
    api = stage_api
    body = api.intent(action)
    body["input"]["operations"] = [dict(body["input"]["operations"][0], ref=format(i, "048x")) for i in range(10001)]
    before = api.snapshot()
    response = api.preview(action, body["input"]) if action == "source_confirm" else api.post(action, body)
    rejected(response, "stage_too_large", 413)
    assert api.snapshot() == before


@pytest.mark.parametrize("previous", (None, 3.25))
def test_merged_external_null_keeps_group_total_and_reaches_ready(stage_api, previous):
    api = stage_api
    api.execute("UPDATE PartOperations SET ext_days=? WHERE part_no=? AND seq=20", (previous, PART))
    api.prepare()
    payload = api.hours()
    payload["operations"][1]["external_days"] = None
    old_ops, old_groups = api.rows("PartOperations"), api.rows("ExternalGroups")
    api.confirm("hours_confirm", payload)
    assert api.detail()["data"]["workflow"]["ready"]
    assert api.rows("ExternalGroups") == old_groups
    for old, new in zip(old_ops, api.rows("PartOperations")):
        assert new == ({**old, "ext_days": None} if old["part_no"] == PART and old["seq"] == 20 else old)


@pytest.mark.parametrize("grouped", (False, True))
def test_nonmerged_external_null_never_becomes_zero_or_group_total(stage_api, grouped):
    api = stage_api
    api.execute("UPDATE ExternalGroups SET merge_mode='separate' WHERE group_id='PROC-G'" if grouped else
                "UPDATE PartOperations SET ext_group_id=NULL WHERE part_no='PROC-001' AND seq=20")
    api.prepare()
    payload = api.hours()
    payload["operations"][1]["external_days"] = None
    body = api.body("hours_confirm", payload)
    before = api.snapshot()
    rejected(api.post("hours_confirm", body), "external_days_required", 422)
    assert api.snapshot() == before


@pytest.mark.parametrize("action", ACTIONS[:2])
def test_preview_failure_is_readonly_public_error_without_uncertain_receipt(stage_api, monkeypatch, action):
    from core.services.workbench.process_mutations import WorkbenchProcessMutationService

    api = stage_api
    api.prepare("source")
    detail = api.detail()
    endpoint = "route-preview" if action == "route_confirm" else "stage-preview"
    body = {**api.route(), "snapshot_ref": detail["meta"]["snapshot_ref"]} if action == "route_confirm" else {
        "action": action, "input": api.source(), "snapshot_ref": detail["meta"]["snapshot_ref"]}

    def fail(*args, **kwargs):
        raise OSError("isolated preview read failure")

    before = api.snapshot()
    monkeypatch.setattr(WorkbenchProcessMutationService, "affected_groups", fail)
    error = rejected(api.post(endpoint, body), "storage_failure", 500)["error"]
    assert "request_key" not in error and "result_target" not in error
    assert api.snapshot() == before
