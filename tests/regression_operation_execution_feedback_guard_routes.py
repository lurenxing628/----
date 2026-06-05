from __future__ import annotations

from typing import Tuple

from core.infrastructure.database import get_connection
from tests.operation_execution_feedback_test_support import (
    _base_payload,
    _build_app,
    _current_card,
    _event_count,
    _event_count_for_scope,
    _json,
    _post_controlled,
)


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


def test_idempotency_replay_rejects_superseded_plan_context(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    start_payload = _base_payload(card, idempotency_key="superseded-replay-start")

    start_resp = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/start",
        start_payload,
    )
    assert start_resp.status_code == 200

    conn = get_connection(db_path)
    try:
        conn.executescript(
            """
            INSERT INTO ScheduleVersionSeq(version) VALUES (3);

            INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (104, 10, 'M1', 'O1', '2026-05-02 08:00:00', '2026-05-02 09:00:00', 'unlocked', 3);

            INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (3, 'priority_first', 1, 1, 'success', '{}', 'pytest');

            INSERT INTO ScheduleCandidate(version, candidate_key, candidate_label, candidate_kind, status, graph_enabled, detail_saved)
            VALUES (3, 'adopted', '正式采用', 'baseline', 'completed', 'no', 'no');

            INSERT INTO ScheduleCandidateSelection(version, role, candidate_id, source_table)
            VALUES (3, 'adopted', (SELECT id FROM ScheduleCandidate WHERE version = 3 AND candidate_key = 'adopted'), 'schedule');
            """
        )
        conn.commit()
    finally:
        conn.close()

    replay_resp = _post_controlled(
        client,
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/start",
        start_payload,
    )
    replay_payload = _json(replay_resp)

    assert replay_resp.status_code == 409
    assert replay_payload["error"]["details"]["reason"] == "not_current_official_plan"
    assert replay_payload["error"]["details"]["can_retry"] is False
    assert _event_count(db_path) == 1


def test_write_post_rejects_task_outside_current_dispatch_query(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    current_card = _current_card(client)
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
            VALUES ('B2', 'P001', '零件一', 5, '2026-05-10', 'normal', 'yes', 'scheduled')
            """
        )
        conn.execute(
            """
            INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
            VALUES (12, 'OP12', 'B2', 'piece-c', 30, '钻孔', 'internal', 'scheduled')
            """
        )
        conn.execute(
            """
            INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (103, 12, 'M1', 'O2', '2026-05-01 08:30:00', '2026-05-01 09:30:00', 'unlocked', 2)
            """
        )
        conn.commit()
    finally:
        conn.close()

    resp = _post_controlled(
        client,
        "/scheduler/resource-dispatch/execution/12/start",
        _base_payload(
            current_card,
            schedule_id=103,
            batch_id="B2",
            operator_id="O2",
            expected_state_revision="12:0:0",
            idempotency_key="outside-current-query",
        ),
    )
    payload = _json(resp)

    assert resp.status_code == 409
    assert payload["error"]["details"]["reason"] == "schedule_mismatch"
    assert _event_count(db_path) == 0


def test_actual_post_rejects_outside_query_even_when_batch_id_is_missing(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    current_card = _current_card(client)
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
            VALUES ('B2', 'P001', '零件一', 5, '2026-05-10', 'normal', 'yes', 'scheduled')
            """
        )
        conn.execute(
            """
            INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
            VALUES (12, 'OP12', 'B2', 'piece-c', 30, '钻孔', 'internal', 'scheduled')
            """
        )
        conn.execute(
            """
            INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES (103, 12, 'M1', 'O2', '2026-05-01 08:30:00', '2026-05-01 09:30:00', 'unlocked', 2)
            """
        )
        conn.commit()
    finally:
        conn.close()

    payload = _base_payload(
        current_card,
        schedule_id=103,
        operator_id="O2",
        actual_start_time="2026-05-01 08:35:00",
        idempotency_key="outside-query-actual-no-batch",
    )
    payload.pop("batch_id", None)
    resp = _post_controlled(client, "/scheduler/resource-dispatch/execution/12/actual", payload)
    data = _json(resp)

    assert resp.status_code == 400
    assert data["error"]["details"]["field"] == "batch_id"
    assert data["error"]["details"]["reason"] == "missing_required_field"
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
    assert _event_count_for_scope(db_path, schedule_id=102, op_id=11, batch_id="B1") == 0


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
