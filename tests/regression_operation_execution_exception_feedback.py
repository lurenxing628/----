from __future__ import annotations

from typing import Any, Dict

from core.infrastructure.database import get_connection
from tests.operation_execution_feedback_test_support import (
    _base_payload,
    _build_app,
    _current_card,
    _current_query,
    _event_count,
    _events_url,
    _json,
    _post_controlled,
)


def _action_by_name(card: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {item["action"]: item for item in card.get("available_actions") or []}


def _post(client, card: Dict[str, Any], action_path: str, **overrides: Any):
    return _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/{action_path}",
        _base_payload(card, **overrides),
    )


def test_pause_resume_exception_flow_updates_task_card_and_actions(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    initial_actions = _action_by_name(card)
    assert list(initial_actions) == ["fill_actual", "view_records"]
    assert initial_actions["fill_actual"]["enabled"] is True

    start_resp = _post(client, card, "start", idempotency_key="exception-flow-start")
    start_data = _json(start_resp)["data"]
    processing_actions = _action_by_name(start_data["task_card"])
    assert start_resp.status_code == 200
    assert start_data["current_status_label"] == "生产中"
    assert list(processing_actions) == ["fill_actual", "view_records"]
    assert processing_actions["fill_actual"]["enabled"] is True

    pause_resp = _post(
        client,
        card,
        "pause",
        expected_state_revision=start_data["state_revision"],
        event_time="2026-05-01 08:20:00",
        idempotency_key="exception-flow-pause",
        reason_code="equipment",
        remark="设备需要检查",
    )
    pause_data = _json(pause_resp)["data"]
    paused_actions = _action_by_name(pause_data["task_card"])
    assert pause_resp.status_code == 200
    assert pause_data["event"]["action_label"] == "暂停"
    assert pause_data["event"]["reason_label"] == "设备问题"
    assert pause_data["current_status_label"] == "已暂停"
    assert list(paused_actions) == ["fill_actual", "view_records"]
    assert paused_actions["fill_actual"]["enabled"] is True

    resume_resp = _post(
        client,
        card,
        "resume",
        expected_state_revision=pause_data["state_revision"],
        event_time="2026-05-01 08:35:00",
        idempotency_key="exception-flow-resume",
        remark="继续生产",
    )
    resume_data = _json(resume_resp)["data"]
    assert resume_resp.status_code == 200
    assert resume_data["event"]["action_label"] == "继续生产"
    assert resume_data["current_status_label"] == "生产中"

    exception_resp = _post(
        client,
        card,
        "report-exception",
        expected_state_revision=resume_data["state_revision"],
        event_time="2026-05-01 08:45:00",
        idempotency_key="exception-flow-report",
        reason_code="equipment",
        severity="high",
        impact_minutes=30,
        affected_machine_id="M2",
        affected_operator_id="O2",
        handling_status="checking",
        suggest_reschedule=True,
        remark="主轴异常",
        reason_detail="主轴异常",
    )
    exception_data = _json(exception_resp)["data"]
    exception_actions = _action_by_name(exception_data["task_card"])

    assert exception_resp.status_code == 200
    assert exception_data["event"]["action"] == "report_exception"
    assert exception_data["event"]["action_label"] == "报异常"
    assert exception_data["event"]["reason_label"] == "设备问题"
    assert exception_data["event"]["severity_label"] == "严重"
    assert exception_data["event"]["impact_minutes_label"] == "预计影响 30 分钟"
    assert exception_data["event"]["affected_machine_label"] == "M2 二号设备"
    assert exception_data["event"]["affected_machine_display_label"] == "二号设备"
    assert exception_data["event"]["affected_machine_identity_label"] == "M2 二号设备"
    assert exception_data["event"]["affected_operator_label"] == "O2 李四"
    assert exception_data["event"]["affected_operator_display_label"] == "李四"
    assert exception_data["event"]["affected_operator_identity_label"] == "O2 李四"
    assert exception_data["event"]["handling_status_label"] == "处理中"
    assert exception_data["event"]["suggest_reschedule_label"] == "建议重新排程"
    assert exception_data["current_status_label"] == "异常中"
    assert exception_data["task_card"]["current_status_label"] == "异常中"
    assert exception_data["task_card"]["latest_exception_reason_label"] == "设备问题"
    assert exception_data["task_card"]["latest_exception_severity_label"] == "严重"
    assert exception_data["task_card"]["latest_exception_impact_minutes_label"] == "预计影响 30 分钟"
    assert exception_data["task_card"]["latest_exception_affected_machine_label"] == "M2 二号设备"
    assert exception_data["task_card"]["latest_exception_affected_machine_display_label"] == "二号设备"
    assert exception_data["task_card"]["latest_exception_affected_machine_identity_label"] == "M2 二号设备"
    assert exception_data["task_card"]["latest_exception_affected_operator_label"] == "O2 李四"
    assert exception_data["task_card"]["latest_exception_affected_operator_display_label"] == "李四"
    assert exception_data["task_card"]["latest_exception_affected_operator_identity_label"] == "O2 李四"
    assert exception_data["task_card"]["latest_exception_handling_status_label"] == "处理中"
    assert exception_data["task_card"]["latest_exception_suggest_reschedule_label"] == "建议重新排程"
    assert exception_data["task_card"]["latest_exception_remark"] == "主轴异常"
    assert list(exception_actions) == ["fill_actual", "view_records"]
    assert exception_actions["fill_actual"]["enabled"] is True
    assert exception_data["state_revision"] != resume_data["state_revision"]
    assert _event_count(db_path) == 4

    events_resp = client.get(_events_url(card))
    events_payload = _json(events_resp)["data"]
    events = events_payload["events"]
    assert events_resp.status_code == 200
    assert [item["action_label"] for item in events] == ["开工", "暂停", "继续生产", "报异常"]
    assert events[-1]["action"] == "report_exception"
    assert events[-1]["reason_label"] == "设备问题"
    assert events[-1]["severity_label"] == "严重"
    assert events[-1]["affected_machine_label"] == "M2 二号设备"
    assert events[-1]["affected_operator_label"] == "O2 李四"
    assert events[-1]["remark"] == "主轴异常"
    assert "event_type" not in events[-1]
    assert events_payload["task_card"]["current_status_label"] == "异常中"


def test_exception_feedback_validation_and_conflicts_are_user_facing(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    not_started_exception = _post(
        client,
        card,
        "report-exception",
        idempotency_key="not-started-exception",
        reason_code="equipment",
        severity="high",
        remark="设备异常",
    )
    error = _json(not_started_exception)["error"]
    assert not_started_exception.status_code == 409
    assert error["details"]["reason"] == "invalid_state_transition"
    assert error["details"]["action_label"] == "报异常"

    start_data = _json(_post(client, card, "start", idempotency_key="validation-start"))["data"]
    cases = [
        ("pause", {"reason_code": "", "remark": "设备需要检查"}, "原因", "reason_code"),
        ("pause", {"reason_code": "equipment", "remark": ""}, "情况说明", "remark"),
        ("report-exception", {"reason_code": "equipment", "severity": "", "remark": "设备异常"}, "严重程度", "severity"),
        (
            "report-exception",
            {"reason_code": "equipment", "severity": "high", "impact_minutes": -1, "remark": "设备异常"},
            "预计影响时间",
            "impact_minutes",
        ),
        (
            "report-exception",
            {"reason_code": "equipment", "severity": "high", "affected_machine_id": "NO_SUCH", "remark": "设备异常"},
            "影响设备",
            "affected_machine_id",
        ),
        (
            "report-exception",
            {"reason_code": "equipment", "severity": "high", "affected_operator_id": "NO_SUCH", "remark": "设备异常"},
            "影响人员",
            "affected_operator_id",
        ),
    ]
    for index, (action_path, overrides, field_label, raw_field) in enumerate(cases):
        resp = _post(
            client,
            card,
            action_path,
            expected_state_revision=start_data["state_revision"],
            idempotency_key=f"bad-exception-feedback-{index}",
            **overrides,
        )
        payload = _json(resp)
        assert resp.status_code == 400
        assert payload["error"]["details"]["field_label"] == field_label
        assert raw_field not in payload["error"]["message"]

    stale_resp = _post(
        client,
        card,
        "report-exception",
        idempotency_key="stale-exception-feedback",
        reason_code="equipment",
        severity="high",
        remark="设备异常",
    )
    stale_error = _json(stale_resp)["error"]
    assert stale_resp.status_code == 409
    assert stale_error["details"]["reason"] == "stale_state_revision"
    assert stale_error["details"]["action_label"] == "报异常"
    assert _event_count(db_path) == 1


def test_reason_detail_only_is_visible_as_exception_remark(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    start_data = _json(_post(client, card, "start", idempotency_key="reason-detail-start"))["data"]

    exception_resp = _post(
        client,
        card,
        "report-exception",
        expected_state_revision=start_data["state_revision"],
        event_time="2026-05-01 08:30:00",
        idempotency_key="reason-detail-exception",
        reason_code="equipment",
        severity="high",
        remark="",
        reason_detail="只填原因详情",
    )
    exception_data = _json(exception_resp)["data"]

    assert exception_resp.status_code == 200
    assert exception_data["event"]["remark"] == "只填原因详情"
    assert exception_data["task_card"]["latest_exception_remark"] == "只填原因详情"

    data_resp = client.get(
        f"/scheduler/resource-dispatch/data?{_current_query()}"
    )
    detail_row = _json(data_resp)["data"]["detail_rows"][0]
    assert detail_row["latest_exception_remark"] == "只填原因详情"

    events_resp = client.get(_events_url(card))
    assert _json(events_resp)["data"]["events"][-1]["remark"] == "只填原因详情"
    assert _event_count(db_path) == 2


def test_internal_execution_token_is_not_visible_as_exception_remark(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    start_data = _json(_post(client, card, "start", idempotency_key="internal-token-start"))["data"]

    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO OperationExecutionEvents(
                schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
                event_type, reported_status, event_time, reason_code, reason_detail, severity,
                impact_minutes, handling_status, suggest_reschedule, remark, created_by,
                idempotency_key, request_fingerprint, previous_state_revision
            )
            VALUES (?, ?, ?, ?, 'schedule', 'adopted', 'exception', 'exception', ?, 'equipment', 'exception',
                    'high', 5, 'checking', 1, 'exception', 'tester', ?, 'fingerprint', ?)
            """,
            (
                2,
                card["schedule_id"],
                card["op_id"],
                card["batch_id"],
                "2026-05-01 08:30:00",
                "legacy-internal-token-exception",
                start_data["state_revision"],
            ),
        )
        conn.commit()
    finally:
        conn.close()

    task_resp = client.get(
        f"/scheduler/resource-dispatch/execution/data?{_current_query()}"
    )
    task_card = _json(task_resp)["data"]["tasks"][0]
    assert task_card["last_event_action_label"] == "报异常"
    assert task_card["last_event_remark"] is None
    assert task_card["latest_exception_reason_label"] == "设备问题"
    assert task_card["latest_exception_remark"] is None

    data_resp = client.get(
        f"/scheduler/resource-dispatch/data?{_current_query()}"
    )
    detail_row = _json(data_resp)["data"]["detail_rows"][0]
    assert detail_row["latest_exception_reason_label"] == "设备问题"
    assert detail_row["latest_exception_remark"] == ""

    events_resp = client.get(_events_url(card))
    assert _json(events_resp)["data"]["events"][-1]["action_label"] == "报异常"
    assert _json(events_resp)["data"]["events"][-1]["remark"] is None


def test_internal_execution_token_is_rejected_as_exception_remark(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    start_data = _json(_post(client, card, "start", idempotency_key="bad-token-start"))["data"]

    bad_resp = _post(
        client,
        card,
        "report-exception",
        expected_state_revision=start_data["state_revision"],
        event_time="2026-05-01 08:30:00",
        idempotency_key="bad-token-exception",
        reason_code="equipment",
        severity="high",
        remark="exception",
        reason_detail="exception",
    )
    error = _json(bad_resp)["error"]

    assert bad_resp.status_code == 400
    assert error["details"]["field"] == "remark"
    assert "情况说明" in error["message"]
    assert _event_count(db_path) == 1


def test_internal_token_cleanup_is_case_insensitive(tmp_path, monkeypatch) -> None:
    """大写的内部码（如 Exception）也要被清洗，不能因大小写绕过过滤。"""
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    start_data = _json(_post(client, card, "start", idempotency_key="case-token-start"))["data"]

    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO OperationExecutionEvents(
                schedule_version, schedule_id, op_id, batch_id, source_table, effective_plan_role,
                event_type, reported_status, event_time, reason_code, reason_detail, severity,
                impact_minutes, handling_status, suggest_reschedule, remark, created_by,
                idempotency_key, request_fingerprint, previous_state_revision
            )
            VALUES (?, ?, ?, ?, 'schedule', 'adopted', 'exception', 'exception', ?, 'equipment', 'Exception',
                    'high', 5, 'checking', 1, 'EXCEPTION', 'tester', ?, 'fingerprint', ?)
            """,
            (
                2,
                card["schedule_id"],
                card["op_id"],
                card["batch_id"],
                "2026-05-01 08:30:00",
                "legacy-mixed-case-token",
                start_data["state_revision"],
            ),
        )
        conn.commit()
    finally:
        conn.close()

    task_resp = client.get(
        f"/scheduler/resource-dispatch/execution/data?{_current_query()}"
    )
    task_card = _json(task_resp)["data"]["tasks"][0]
    assert task_card["last_event_remark"] is None
    assert task_card["latest_exception_remark"] is None


def test_user_remark_matching_unrelated_internal_code_is_kept(tmp_path, monkeypatch) -> None:
    """用户在一条设备异常里写的说明，即使恰好等于别的记录会用到的英文码（如 person），也要原样保留。"""
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    start_data = _json(_post(client, card, "start", idempotency_key="unrelated-token-start"))["data"]

    exception_resp = _post(
        client,
        card,
        "report-exception",
        expected_state_revision=start_data["state_revision"],
        event_time="2026-05-01 08:30:00",
        idempotency_key="unrelated-token-exception",
        reason_code="equipment",
        severity="high",
        remark="person",
        reason_detail="person",
    )
    exception_data = _json(exception_resp)["data"]

    # reason_code 是 equipment，person 并不是这条记录自己的内部码，应当原样保留为用户说明。
    assert exception_resp.status_code == 200
    assert exception_data["event"]["remark"] == "person"
    assert exception_data["task_card"]["latest_exception_remark"] == "person"
    assert _event_count(db_path) == 2


def test_events_list_keeps_each_exception_own_impact_and_affected_resources(tmp_path, monkeypatch) -> None:
    app, _db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    start_data = _json(_post(client, card, "start", idempotency_key="two-exceptions-start"))["data"]
    first_exception = _json(
        _post(
            client,
            card,
            "report-exception",
            expected_state_revision=start_data["state_revision"],
            event_time="2026-05-01 08:30:00",
            idempotency_key="two-exceptions-first",
            reason_code="equipment",
            severity="high",
            impact_minutes=30,
            affected_machine_id="M2",
            affected_operator_id="O2",
            handling_status="new",
            suggest_reschedule=True,
            remark="第一次异常",
        )
    )["data"]
    resumed = _json(
        _post(
            client,
            card,
            "resume",
            expected_state_revision=first_exception["state_revision"],
            event_time="2026-05-01 08:45:00",
            idempotency_key="two-exceptions-resume",
            remark="继续生产",
        )
    )["data"]
    _post(
        client,
        card,
        "report-exception",
        expected_state_revision=resumed["state_revision"],
        event_time="2026-05-01 09:00:00",
        idempotency_key="two-exceptions-second",
        reason_code="person",
        severity="medium",
        impact_minutes=60,
        affected_machine_id="M1",
        affected_operator_id="O1",
        handling_status="checking",
        suggest_reschedule=False,
        remark="第二次异常",
    )

    events_resp = client.get(_events_url(card))
    events = _json(events_resp)["data"]["events"]
    exception_events = [item for item in events if item["action"] == "report_exception"]

    assert events_resp.status_code == 200
    assert len(exception_events) == 2
    assert exception_events[0]["reason_label"] == "设备问题"
    assert exception_events[0]["impact_minutes_label"] == "预计影响 30 分钟"
    assert exception_events[0]["affected_machine_label"] == "M2 二号设备"
    assert exception_events[0]["affected_operator_label"] == "O2 李四"
    assert exception_events[0]["remark"] == "第一次异常"
    assert exception_events[1]["reason_label"] == "人员问题"
    assert exception_events[1]["impact_minutes_label"] == "预计影响 60 分钟"
    assert exception_events[1]["affected_machine_label"] == "M1 一号设备"
    assert exception_events[1]["affected_operator_label"] == "O1 张三"
    assert exception_events[1]["remark"] == "第二次异常"
