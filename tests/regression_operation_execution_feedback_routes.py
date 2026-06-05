from __future__ import annotations

from tests.operation_execution_feedback_test_support import (
    _base_payload,
    _build_app,
    _current_card,
    _current_query,
    _event_count,
    _json,
    _post_controlled,
)


def test_execution_data_returns_task_card_contract(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    resp = client.get(
        f"/scheduler/resource-dispatch/execution/data?{_current_query()}"
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
    for forbidden in ("op_id", "schedule_id", "batch_id", "state_revision"):
        assert forbidden not in card
    for key in (
        "task_key",
        "state_key",
        "batch_label",
        "op_name",
        "current_status_label",
        "available_actions",
        "unavailable_reasons",
    ):
        assert key in card
    assert str(card["task_key"]).startswith("exec_")
    assert str(card["state_key"]).startswith("state_")
    assert card["batch_label"] == "B1"
    assert card["current_status_label"] == "待开工"
    assert isinstance(card["unavailable_reasons"], dict)
    action_by_name = {item["action"]: item for item in card["available_actions"]}
    assert list(action_by_name) == ["fill_actual", "view_records"]
    assert action_by_name["fill_actual"]["label"] == "填写实际情况"
    assert action_by_name["fill_actual"]["enabled"] is True
    assert action_by_name["fill_actual"]["disabled_reason"] == ""
    assert action_by_name["view_records"]["label"] == "查看现场记录"
    assert action_by_name["view_records"]["enabled"] is True
    for realtime_action in ("start", "pause", "resume", "finish", "report_exception"):
        assert realtime_action not in action_by_name
        assert realtime_action not in card["unavailable_reasons"]


def test_execution_data_public_plan_identity_hides_internal_fields_for_read_only_plans(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    urls = [
        "/scheduler/resource-dispatch/execution/data?scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-04-30&date_from=2026-04-30&date_to=2026-05-06&version=1&plan_role=adopted",
        "/scheduler/resource-dispatch/execution/data?scope_type=operator&operator_id=O2&period_preset=week&query_date=2026-05-01&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=baseline_best",
        "/scheduler/resource-dispatch/execution/data?scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=adopted&scenario_id=scenario-plain",
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
        "action",
        "action_label",
        "event_time",
        "created_by",
        "remark",
    ):
        assert key in start_data["event"]
    for forbidden in ("op_id", "schedule_id"):
        assert forbidden not in start_data["event"]
    assert start_data["event"]["action_label"] == "开工"
    assert start_data["current_status_label"] == "生产中"
    assert start_data["idempotency_reused"] is False
    for key in (
        "task_key",
        "state_key",
        "batch_label",
        "op_name",
        "current_status",
        "current_status_label",
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
    for forbidden in ("op_id", "schedule_id", "batch_id", "state_revision"):
        assert forbidden not in start_data["task_card"]
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
