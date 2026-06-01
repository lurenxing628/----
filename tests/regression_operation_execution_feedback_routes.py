from __future__ import annotations

from typing import Tuple

from core.infrastructure.database import get_connection
from tests.operation_execution_feedback_test_support import (
    _base_payload,
    _build_app,
    _current_card,
    _current_query,
    _event_count,
    _event_count_for_op,
    _json,
    _post_controlled,
)


def test_execution_data_returns_task_card_contract(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get(
        "/scheduler/resource-dispatch/execution/data?scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01&version=2&plan_role=adopted"
    )
    payload = _json(resp)

    assert resp.status_code == 200
    assert payload["success"] is True
    data = payload["data"]
    assert data["plan_identity_label"] == "正式采用方案"
    identity_json = str(data["plan_identity"])
    for forbidden in (
        "requested_plan_role",
        "effective_plan_role",
        "source_table",
        "scenario_id",
        "candidate_id",
        "candidate_key",
    ):
        assert forbidden not in data["plan_identity"]
        assert forbidden not in identity_json
    assert data["can_write_feedback"] is True
    assert data["disabled_reason"] == ""
    assert len(data["tasks"]) == 1
    card = data["tasks"][0]
    for key in (
        "op_id",
        "schedule_id",
        "batch_id",
        "op_name",
        "current_status_label",
        "state_revision",
        "available_actions",
        "unavailable_reasons",
    ):
        assert key in card
    assert card["current_status_label"] == "待开工"
    assert isinstance(card["unavailable_reasons"], dict)
    action_by_name = {item["action"]: item for item in card["available_actions"]}
    assert list(action_by_name) == ["fill_actual", "view_records"]
    assert action_by_name["fill_actual"]["label"] == "填写实际情况"
    assert action_by_name["fill_actual"]["enabled"] is True
    assert action_by_name["fill_actual"]["disabled_reason"] == ""
    assert action_by_name["view_records"]["label"] == "查看计划和实际"
    assert action_by_name["view_records"]["enabled"] is True
    for realtime_action in ("start", "pause", "resume", "finish", "report_exception"):
        assert realtime_action not in action_by_name
        assert realtime_action not in card["unavailable_reasons"]


def test_execution_data_public_plan_identity_hides_internal_fields_for_read_only_plans(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    urls = [
        "/scheduler/resource-dispatch/execution/data?scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-04-30&version=1&plan_role=adopted",
        "/scheduler/resource-dispatch/execution/data?scope_type=operator&operator_id=O2&period_preset=week&query_date=2026-05-01&version=2&plan_role=baseline_best",
        "/scheduler/resource-dispatch/execution/data?scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01&version=2&plan_role=adopted&scenario_id=scenario-plain",
    ]

    for url in urls:
        resp = client.get(url)
        payload = _json(resp)

        assert resp.status_code == 200
        identity = payload["data"]["plan_identity"]
        identity_json = str(identity)
        assert identity["can_write_feedback"] is False
        for forbidden in (
            "requested_plan_role",
            "effective_plan_role",
            "source_table",
            "scenario_id",
            "candidate_id",
            "candidate_key",
            "scenario-plain",
        ):
            assert forbidden not in identity
            assert forbidden not in identity_json


def test_plain_user_start_finish_posts_write_after_guardrail(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    start_resp = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/start?{_current_query()}",
        json=_base_payload(card),
    )
    start_data = _json(start_resp)["data"]

    assert start_resp.status_code == 200
    assert start_data["event"]["action_label"] == "开工"
    assert start_data["current_status_label"] == "生产中"
    assert start_data["task_card"]["current_status_label"] == "生产中"
    assert start_data["state_revision"] != card["state_revision"]
    assert _event_count(db_path) == 1

    finish_resp = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/finish?{_current_query()}",
        json=_base_payload(
            card,
            expected_state_revision=start_data["state_revision"],
            idempotency_key="route-key-finish",
            event_time="2026-05-01 09:00:00",
            quantity_done=10,
        ),
    )
    finish_data = _json(finish_resp)["data"]

    assert finish_resp.status_code == 200
    assert finish_data["event"]["action_label"] == "完工"
    assert finish_data["current_status_label"] == "已完工"
    assert finish_data["task_card"]["current_status_label"] == "已完工"
    assert finish_data["state_revision"] != start_data["state_revision"]
    assert _event_count(db_path) == 2


def test_controlled_start_finish_posts_return_refresh_contract(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    start_resp = _post_controlled(client, f"/scheduler/resource-dispatch/execution/{card['op_id']}/start", _base_payload(card))
    start_data = _json(start_resp)["data"]

    assert start_resp.status_code == 200
    for key in (
        "event",
        "current_status",
        "current_status_label",
        "state_revision",
        "idempotency_reused",
        "task_card",
    ):
        assert key in start_data
    for key in (
        "event_id",
        "op_id",
        "schedule_id",
        "action",
        "action_label",
        "event_time",
        "created_by",
        "remark",
    ):
        assert key in start_data["event"]
    assert start_data["event"]["action_label"] == "开工"
    assert start_data["current_status_label"] == "生产中"
    assert start_data["idempotency_reused"] is False
    for key in (
        "op_id",
        "schedule_id",
        "batch_id",
        "op_name",
        "current_status",
        "current_status_label",
        "state_revision",
        "actual_start_time",
        "actual_end_time",
        "planned_machine_display_label",
        "planned_machine_identity_label",
        "actual_machine_label",
        "actual_machine_display_label",
        "actual_machine_identity_label",
        "planned_operator_display_label",
        "planned_operator_identity_label",
        "actual_operator_label",
        "actual_operator_display_label",
        "actual_operator_identity_label",
        "last_event_action_label",
        "last_event_remark",
        "latest_exception_reason_label",
        "latest_exception_severity_label",
        "latest_exception_impact_minutes_label",
        "latest_exception_affected_machine_label",
        "latest_exception_affected_operator_label",
        "latest_exception_handling_status_label",
        "latest_exception_suggest_reschedule_label",
        "latest_exception_remark",
        "updated_at",
        "available_actions",
        "unavailable_reasons",
    ):
        assert key in start_data["task_card"]
    assert start_data["task_card"]["current_status_label"] == "生产中"
    assert start_data["task_card"]["planned_machine_label"] == "M1 一号设备"
    assert start_data["task_card"]["planned_machine_display_label"] == "一号设备"
    assert start_data["task_card"]["planned_machine_identity_label"] == "M1 一号设备"
    assert start_data["task_card"]["actual_machine_label"] == "M1 一号设备"
    assert start_data["task_card"]["actual_machine_display_label"] == "一号设备"
    assert start_data["task_card"]["actual_machine_identity_label"] == "M1 一号设备"
    assert start_data["task_card"]["planned_operator_label"] == "O1 张三"
    assert start_data["task_card"]["planned_operator_display_label"] == "张三"
    assert start_data["task_card"]["planned_operator_identity_label"] == "O1 张三"
    assert start_data["task_card"]["actual_operator_label"] == "O1 张三"
    assert start_data["task_card"]["actual_operator_display_label"] == "张三"
    assert start_data["task_card"]["actual_operator_identity_label"] == "O1 张三"
    action_by_name = {item["action"]: item for item in start_data["task_card"]["available_actions"]}
    assert list(action_by_name) == ["fill_actual", "view_records"]
    assert action_by_name["fill_actual"]["enabled"] is True

    finish_payload = _base_payload(
        card,
        expected_state_revision=start_data["state_revision"],
        idempotency_key="route-key-finish",
        event_time="2026-05-01 09:00:00",
        quantity_done=8,
        quantity_scrapped="",
    )
    finish_resp = _post_controlled(client, f"/scheduler/resource-dispatch/execution/{card['op_id']}/finish", finish_payload)
    finish_data = _json(finish_resp)["data"]

    assert finish_resp.status_code == 200
    assert finish_data["event"]["action_label"] == "完工"
    assert finish_data["current_status_label"] == "已完工"
    assert finish_data["task_card"]["current_status_label"] == "已完工"
    assert finish_data["task_card"]["actual_end_time"] == "2026-05-01 09:00:00"
    assert _event_count(db_path) == 2


def test_plain_write_does_not_depend_on_testing_header(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    app.config["TESTING"] = False
    resp = _post_controlled(client, f"/scheduler/resource-dispatch/execution/{card['op_id']}/start", _base_payload(card))
    payload = _json(resp)["data"]

    assert resp.status_code == 200
    assert payload["event"]["action_label"] == "开工"
    assert _event_count(db_path) == 1


def test_actual_post_uses_server_side_plan_identity_from_query(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    payload = _base_payload(
        card,
        idempotency_key="actual-query-identity",
        actual_start_time="2026-05-01 08:20:00",
    )
    for key in ("version", "requested_plan_role", "effective_plan_role", "source_table", "scenario_id"):
        payload.pop(key, None)

    resp = client.post(
        (
            f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual"
            "?scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01"
            "&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=adopted"
        ),
        json=payload,
    )
    data = _json(resp)["data"]

    assert resp.status_code == 200
    assert data["task_card"]["actual_start_time"] == "2026-05-01 08:20:00"
    assert _event_count(db_path) == 1


def test_actual_post_without_query_rejects_body_plan_identity(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    resp = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual",
        json=_base_payload(
            card,
            idempotency_key="actual-no-query-identity",
            requested_plan_role="adopted",
            effective_plan_role="adopted",
            source_table="schedule",
            actual_start_time="2026-05-01 08:20:00",
        ),
    )
    payload = _json(resp)

    assert resp.status_code == 400
    assert payload["error"]["details"]["field"] == "plan_identity"
    assert _event_count(db_path) == 0


def test_write_post_rejects_incomplete_query_plan_identity(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    partial_queries: Tuple[str, ...] = (
        "version=2",
        "plan_role=adopted",
        "version=2&plan_role=adopted",
        "scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01&version=2&plan_role=adopted",
        "operator_id=O1&period_preset=week&query_date=2026-05-01&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=adopted",
        "scope_type=operator&operator_id=O1&query_date=2026-05-01&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=adopted",
    )

    for index, query in enumerate(partial_queries):
        resp = client.post(
            f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual?{query}",
            json=_base_payload(
                card,
                idempotency_key=f"incomplete-query-{index}",
                actual_start_time="2026-05-01 08:20:00",
            ),
        )
        payload = _json(resp)
        assert resp.status_code == 400
        assert payload["error"]["details"]["field"] == "plan_identity"
        assert "missing_fields" in payload["error"]["details"]
    assert _event_count(db_path) == 0


def test_write_post_rejects_candidate_preview_and_history_query_context(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    cases: Tuple[str, ...] = (
        "scope_type=operator&operator_id=O2&period_preset=week&query_date=2026-05-01&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=baseline_best",
        "scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=adopted&scenario_id=scenario-plain",
        "scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-04-30&date_from=2026-04-27&date_to=2026-05-03&version=1&plan_role=adopted",
    )

    for index, query in enumerate(cases):
        resp = _post_controlled(
            client,
            f"/scheduler/resource-dispatch/execution/{card['op_id']}/start?{query}",
            _base_payload(card, idempotency_key=f"reject-key-{index}"),
        )
        payload = _json(resp)
        assert resp.status_code == 409
        assert payload["error"]["code"] == "6003"
        assert payload["error"]["details"]["reason"] == "not_current_official_plan"
        assert payload["error"]["details"]["action_label"] == "开工"
        assert payload["error"]["details"]["can_retry"] is False
    assert _event_count(db_path) == 0


def test_write_post_requires_query_plan_identity_and_batch_match(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    no_query_payload = _base_payload(
        card,
        idempotency_key="no-query-identity",
        requested_plan_role="adopted",
        effective_plan_role="adopted",
        source_table="schedule",
    )
    resp = client.post(f"/scheduler/resource-dispatch/execution/{card['op_id']}/start", json=no_query_payload)
    payload = _json(resp)
    assert resp.status_code == 400
    assert payload["error"]["details"]["field"] == "plan_identity"
    assert payload["error"]["details"]["can_retry"] is False
    assert _event_count(db_path) == 0

    wrong_batch = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/start",
        _base_payload(card, idempotency_key="wrong-batch", batch_id="B-other"),
    )
    wrong_batch_payload = _json(wrong_batch)
    assert wrong_batch.status_code == 409
    assert wrong_batch_payload["error"]["details"]["reason"] == "schedule_mismatch"
    assert wrong_batch_payload["error"]["details"]["can_retry"] is True
    assert _event_count(db_path) == 0


def test_validation_errors_use_chinese_field_label(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    cases = [
        ("start", {"operator_id": ""}, "操作人员", "operator_id"),
        ("start", {"machine_id": ""}, "设备", "machine_id"),
        ("finish", {"quantity_done": ""}, "完成数量", "quantity_done"),
        ("start", {"expected_state_revision": ""}, "页面状态", "expected_state_revision"),
    ]

    for action, overrides, field_label, raw_field in cases:
        resp = _post_controlled(
            client,
            f"/scheduler/resource-dispatch/execution/{card['op_id']}/{action}",
            _base_payload(card, idempotency_key=f"bad-{raw_field}", **overrides),
        )
        payload = _json(resp)
        assert resp.status_code == 400
        assert payload["error"]["details"]["field_label"] == field_label
        assert payload["error"]["details"]["can_retry"] is True
        assert raw_field not in payload["error"]["message"]


def test_conflicts_return_reason_and_action_label(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    finish_before_start = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/finish",
        _base_payload(card, idempotency_key="finish-before-start", quantity_done=10),
    )
    finish_error = _json(finish_before_start)["error"]
    assert finish_before_start.status_code == 409
    assert finish_error["details"]["reason"] == "invalid_state_transition"
    assert finish_error["details"]["action_label"] == "完工"
    assert finish_error["details"]["can_retry"] is False
    assert "刷新页面查看最新状态" in finish_error["message"]
    assert "联系计划员处理" in finish_error["message"]

    start_resp = _post_controlled(client, f"/scheduler/resource-dispatch/execution/{card['op_id']}/start", _base_payload(card))
    state_revision = _json(start_resp)["data"]["state_revision"]

    early_finish = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/finish",
        _base_payload(
            card,
            expected_state_revision=state_revision,
            idempotency_key="early-finish",
            event_time="2026-05-01 08:05:00",
            quantity_done=10,
        ),
    )
    early_finish_error = _json(early_finish)["error"]
    assert early_finish.status_code == 409
    assert early_finish_error["details"]["reason"] == "invalid_state_transition"
    assert early_finish_error["details"]["action_label"] == "完工"
    assert early_finish_error["details"]["can_retry"] is False

    stale_resp = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/finish",
        _base_payload(card, idempotency_key="stale-finish", quantity_done=10),
    )
    stale_error = _json(stale_resp)["error"]
    assert stale_resp.status_code == 409
    assert stale_error["details"]["reason"] == "stale_state_revision"
    assert stale_error["details"]["action_label"] == "完工"
    assert stale_error["details"]["can_retry"] is True

    conflict_resp = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/start",
        _base_payload(card, event_time="2026-05-01 08:20:00"),
    )
    conflict_error = _json(conflict_resp)["error"]
    assert conflict_resp.status_code == 409
    assert conflict_error["details"]["reason"] == "idempotency_conflict"
    assert conflict_error["details"]["action_label"] == "开工"
    assert conflict_error["details"]["can_retry"] is True

    finish_resp = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/finish",
        _base_payload(card, expected_state_revision=state_revision, idempotency_key="finish-ok", quantity_done=10),
    )
    finish_state_revision = _json(finish_resp)["data"]["state_revision"]
    restart_resp = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/start",
        _base_payload(card, expected_state_revision=finish_state_revision, idempotency_key="restart-key"),
    )
    restart_error = _json(restart_resp)["error"]
    assert restart_resp.status_code == 409
    assert restart_error["details"]["reason"] == "invalid_state_transition"
    assert restart_error["details"]["action_label"] == "开工"
    assert restart_error["details"]["can_retry"] is False
    assert "刷新页面查看最新状态" in restart_error["message"]
    assert "联系计划员处理" in restart_error["message"]


def test_start_finish_business_validation_is_user_facing(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    wrong_machine = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/start",
        _base_payload(card, machine_id="M2"),
    )
    assert wrong_machine.status_code == 400
    wrong_machine_error = _json(wrong_machine)["error"]
    assert wrong_machine_error["details"]["reason"] == "invalid_field_value"
    assert wrong_machine_error["details"]["field_label"] == "设备"

    start_resp = _post_controlled(client, f"/scheduler/resource-dispatch/execution/{card['op_id']}/start", _base_payload(card))
    state_revision = _json(start_resp)["data"]["state_revision"]
    over_planned = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/finish",
        _base_payload(
            card,
            expected_state_revision=state_revision,
            idempotency_key="over-planned-finish",
            quantity_done=9,
            quantity_scrapped=2,
        ),
    )
    assert over_planned.status_code == 200
    finish_event = _json(over_planned)["data"]["event"]
    assert finish_event["action_label"] == "完工"


def test_start_rejects_schedule_without_planned_machine(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
            VALUES (11, 'OP11', 'B1', 'piece-b', 20, '铣削', 'internal', 'scheduled')
            """
        )
        conn.execute(
            """
            INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (102, 11, NULL, 'O1', '2026-05-01 10:00:00', '2026-05-01 11:00:00', 'unlocked', 2)
            """
        )
        conn.commit()
    finally:
        conn.close()

    resp = _post_controlled(
        client,
        "/scheduler/resource-dispatch/execution/11/start",
        _base_payload(card, schedule_id=102, idempotency_key="missing-plan-machine", expected_state_revision="11:0:0"),
    )
    payload = _json(resp)

    assert resp.status_code == 400
    assert payload["error"]["details"]["reason"] == "invalid_field_value"
    assert payload["error"]["details"]["field_label"] == "设备"
    assert _event_count_for_op(db_path, 11) == 0


def test_finish_quantity_boundaries_use_chinese_field_labels(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    start_resp = _post_controlled(client, f"/scheduler/resource-dispatch/execution/{card['op_id']}/start", _base_payload(card))
    state_revision = _json(start_resp)["data"]["state_revision"]

    cases = [
        ({"quantity_done": -1}, "完成数量"),
        ({"quantity_done": "abc"}, "完成数量"),
        ({"quantity_done": 1.5}, "完成数量"),
        ({"quantity_done": "1.5"}, "完成数量"),
        ({"quantity_done": True}, "完成数量"),
        ({"quantity_done": 8, "quantity_scrapped": -1}, "报废数量"),
        ({"quantity_done": 8, "quantity_scrapped": "abc"}, "报废数量"),
        ({"quantity_done": 8, "quantity_scrapped": 1.5}, "报废数量"),
    ]

    for index, (overrides, field_label) in enumerate(cases):
        resp = _post_controlled(
            client,
            f"/scheduler/resource-dispatch/execution/{card['op_id']}/finish",
            _base_payload(
                card,
                expected_state_revision=state_revision,
                idempotency_key=f"bad-quantity-{index}",
                **overrides,
            ),
        )
        payload = _json(resp)
        assert resp.status_code == 400
        assert payload["error"]["details"]["reason"] == "invalid_field_value"
        assert payload["error"]["details"]["field_label"] == field_label
        assert payload["error"]["details"]["can_retry"] is True
        assert "quantity_" not in payload["error"]["message"]
