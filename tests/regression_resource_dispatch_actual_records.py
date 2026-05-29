from __future__ import annotations

from tests.operation_execution_feedback_test_support import (
    _base_payload,
    _build_app,
    _current_card,
    _event_count,
    _events_for_op,
    _json,
)


def test_actual_record_allows_blank_feedback_person_and_manual_times(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    resp = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual",
        json=_base_payload(
            card,
            created_by="",
            feedback_person="",
            idempotency_key="actual-manual-times",
            actual_start_time="2026-05-01 08:12:00",
            actual_finish_time="2026-05-01 08:58:00",
            quantity_done=9,
            quantity_scrapped=1,
            event_time="2026-05-01 12:00:00",
        ),
    )
    data = _json(resp)["data"]
    events = _events_for_op(db_path, card["op_id"])

    assert resp.status_code == 200
    assert data["task_card"]["actual_start_time"] == "2026-05-01 08:12:00"
    assert data["task_card"]["actual_end_time"] == "2026-05-01 08:58:00"
    assert [row["event_type"] for row in events] == ["start", "finish"]
    assert [row["event_time"] for row in events] == ["2026-05-01 08:12:00", "2026-05-01 08:58:00"]
    assert events[0]["created_by"] == "未填写反馈人"
    assert events[1]["quantity_done"] == 9
    assert events[1]["quantity_scrapped"] == 1


def test_actual_record_allows_total_quantity_over_planned_for_rework(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    resp = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual",
        json=_base_payload(
            card,
            idempotency_key="actual-rework-over-planned",
            actual_start_time="2026-05-01 08:00:00",
            actual_finish_time="2026-05-01 09:00:00",
            quantity_done=8,
            quantity_scrapped=5,
        ),
    )
    events = _events_for_op(db_path, card["op_id"])

    assert resp.status_code == 200
    assert events[1]["quantity_done"] == 8
    assert events[1]["quantity_scrapped"] == 5


def test_actual_record_validation_error_uses_fill_actual_label(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    resp = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual",
        json=_base_payload(
            card,
            idempotency_key="actual-finish-before-start",
            actual_start_time="2026-05-01 09:00:00",
            actual_finish_time="2026-05-01 08:00:00",
            quantity_done=5,
        ),
    )
    error = _json(resp)["error"]

    assert resp.status_code == 400
    assert error["details"]["action_label"] == "填写实际情况"
    assert _event_count(db_path) == 0


def test_actual_record_same_idempotency_reuses_existing_events(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    payload = _base_payload(
        card,
        created_by="",
        feedback_person="",
        idempotency_key="actual-idempotency-retry",
        actual_start_time="2026-05-01 08:12:00",
        actual_finish_time="2026-05-01 08:58:00",
        quantity_done=9,
        quantity_scrapped=1,
    )

    first = client.post(f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual", json=payload)
    retry = client.post(f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual", json=payload)

    assert first.status_code == 200
    assert retry.status_code == 200
    assert _json(retry)["data"]["idempotency_reused"] is True
    assert [row["event_type"] for row in _events_for_op(db_path, card["op_id"])] == ["start", "finish"]


def test_actual_record_reused_idempotency_key_with_new_content_still_validates(tmp_path, monkeypatch) -> None:
    """复用同一个 idempotency_key 但提交了新内容时，新增部分仍必须跑完整校验。

    回归 P4：旧逻辑“任一派生 key 命中就整体跳过校验”，会让客户端复用同一个 key 追加新事件时
    绕过完工早于开工等跨字段校验。修复后只有“全部事件都已写过”的纯重放才跳过校验。
    """
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    first = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual",
        json=_base_payload(
            card,
            idempotency_key="reused-key",
            actual_start_time="2026-05-01 08:00:00",
        ),
    )
    assert first.status_code == 200
    fresh_card = _json(first)["data"]["task_card"]

    # 同一个 client key 复用：重发已写过的开工（其派生 key 命中）+ 追加一条新的非法完工。
    # 旧逻辑“任一派生 key 命中就整体跳过校验”会让这次提交绕过 service 层校验，最终落到
    # record_event 层报底层 409 冲突；修复后必须在 service 层用清晰的中文校验前置拦下（400）。
    illegal_finish = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual",
        json=_base_payload(
            fresh_card,
            idempotency_key="reused-key",
            actual_start_time="2026-05-01 08:00:00",
            actual_finish_time="2026-05-01 07:00:00",
            quantity_done=10,
        ),
    )
    payload = _json(illegal_finish)

    assert illegal_finish.status_code == 400
    assert payload["error"]["details"].get("reason") != "invalid_state_transition"
    assert "已记录实际开工" in payload["error"]["message"]
    # 只有第一次的开工事件落库，非法完工没有写入。
    assert [row["event_type"] for row in _events_for_op(db_path, card["op_id"])] == ["start"]


def test_actual_record_without_client_idempotency_key_can_append_new_pause_and_exception(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    first_payload = _base_payload(
        card,
        idempotency_key="",
        actual_start_time="2026-05-01 08:00:00",
        pause_start_time="2026-05-01 08:20:00",
        pause_end_time="2026-05-01 08:30:00",
        pause_reason="equipment",
        pause_remark="设备点检",
    )

    first = client.post(f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual", json=first_payload)
    retry = client.post(f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual", json=first_payload)
    fresh_card = _json(first)["data"]["task_card"]
    second = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual",
        json=_base_payload(
            fresh_card,
            idempotency_key="",
            actual_start_time="",
            pause_start_time="2026-05-01 08:40:00",
            pause_end_time="2026-05-01 08:45:00",
            pause_reason="material",
            pause_remark="等待物料",
        ),
    )
    fresh_card = _json(second)["data"]["task_card"]
    exception = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual",
        json=_base_payload(
            fresh_card,
            idempotency_key="",
            actual_start_time="",
            exception_time="2026-05-01 08:50:00",
            exception_reason="quality",
            exception_severity="medium",
            exception_remark="尺寸复检",
        ),
    )
    events = _events_for_op(db_path, card["op_id"])

    assert first.status_code == 200
    assert retry.status_code == 200
    assert _json(retry)["data"]["idempotency_reused"] is True
    assert second.status_code == 200
    assert exception.status_code == 200
    assert [row["event_type"] for row in events] == ["start", "pause", "resume", "pause", "resume", "exception"]
    assert [row["event_time"] for row in events] == [
        "2026-05-01 08:00:00",
        "2026-05-01 08:20:00",
        "2026-05-01 08:30:00",
        "2026-05-01 08:40:00",
        "2026-05-01 08:45:00",
        "2026-05-01 08:50:00",
    ]


def test_actual_record_rejects_overwrite_existing_start_and_finish(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    first = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual",
        json=_base_payload(
            card,
            idempotency_key="actual-existing-first",
            actual_start_time="2026-05-01 08:10:00",
            actual_finish_time="2026-05-01 09:00:00",
            quantity_done=10,
        ),
    )
    fresh_card = _json(first)["data"]["task_card"]

    overwrite_start = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual",
        json=_base_payload(
            fresh_card,
            idempotency_key="actual-existing-start",
            actual_start_time="2026-05-01 08:20:00",
        ),
    )
    overwrite_finish = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual",
        json=_base_payload(
            fresh_card,
            idempotency_key="actual-existing-finish",
            actual_finish_time="2026-05-01 09:10:00",
            quantity_done=10,
        ),
    )
    events = _events_for_op(db_path, card["op_id"])

    assert first.status_code == 200
    assert overwrite_start.status_code == 400
    assert "已记录实际开工" in _json(overwrite_start)["error"]["message"]
    assert overwrite_finish.status_code == 400
    assert "已记录实际完工" in _json(overwrite_finish)["error"]["message"]
    assert [row["event_type"] for row in events] == ["start", "finish"]
    assert [row["event_time"] for row in events] == ["2026-05-01 08:10:00", "2026-05-01 09:00:00"]


def test_actual_record_rejects_finish_before_start(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    resp = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual",
        json=_base_payload(
            card,
            idempotency_key="actual-finish-before-start",
            actual_start_time="2026-05-01 09:00:00",
            actual_finish_time="2026-05-01 08:50:00",
            quantity_done=10,
        ),
    )
    payload = _json(resp)

    assert resp.status_code == 400
    assert "实际完工时间不能早于实际开工时间" in payload["error"]["message"]
    assert _event_count(db_path) == 0


def test_actual_record_pause_range_and_duration_write_pause_events(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    resp = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual",
        json=_base_payload(
            card,
            idempotency_key="actual-pause-duration",
            actual_start_time="2026-05-01 08:00:00",
            pause_start_time="2026-05-01 08:20:00",
            pause_duration_minutes=15,
            pause_reason="equipment",
            pause_remark="设备点检",
            actual_finish_time="2026-05-01 09:00:00",
            quantity_done=10,
        ),
    )
    events = _events_for_op(db_path, card["op_id"])
    task_card = _json(resp)["data"]["task_card"]

    assert resp.status_code == 200
    assert [row["event_type"] for row in events] == ["start", "pause", "resume", "finish"]
    assert events[1]["event_time"] == "2026-05-01 08:20:00"
    assert events[2]["event_time"] == "2026-05-01 08:35:00"
    assert task_card["last_event_action_label"] == "完工"
    assert task_card["current_status_label"] == "已完工"


def test_actual_record_rejects_pause_duration_mismatch_and_overlap(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    mismatch = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual",
        json=_base_payload(
            card,
            idempotency_key="actual-pause-mismatch",
            actual_start_time="2026-05-01 08:00:00",
            pause_start_time="2026-05-01 08:20:00",
            pause_end_time="2026-05-01 08:40:00",
            pause_duration_minutes=10,
            pause_reason="equipment",
            pause_remark="设备点检",
        ),
    )
    assert mismatch.status_code == 400
    assert "暂停结束时间和暂停时长对不上" in _json(mismatch)["error"]["message"]
    assert _event_count(db_path) == 0

    first = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual",
        json=_base_payload(
            card,
            idempotency_key="actual-pause-first",
            actual_start_time="2026-05-01 08:00:00",
            pause_start_time="2026-05-01 08:20:00",
            pause_end_time="2026-05-01 08:35:00",
            pause_reason="equipment",
            pause_remark="设备点检",
        ),
    )
    assert first.status_code == 200
    first_events = _events_for_op(db_path, card["op_id"])
    assert [row["event_type"] for row in first_events] == ["start", "pause", "resume"]
    assert [row["event_time"] for row in first_events] == [
        "2026-05-01 08:00:00",
        "2026-05-01 08:20:00",
        "2026-05-01 08:35:00",
    ]
    fresh_card = _json(first)["data"]["task_card"]
    overlap = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual",
        json=_base_payload(
            fresh_card,
            idempotency_key="actual-pause-overlap",
            actual_start_time="",
            pause_start_time="2026-05-01 08:30:00",
            pause_end_time="2026-05-01 08:45:00",
            pause_reason="equipment",
            pause_remark="重复暂停",
        ),
    )
    assert overlap.status_code == 400
    assert "暂停时间和已有记录重叠" in _json(overlap)["error"]["message"]
    assert _event_count(db_path) == 3


def test_actual_record_supports_exception_record_fields(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)

    resp = client.post(
        f"/scheduler/resource-dispatch/execution/{card['op_id']}/actual",
        json=_base_payload(
            card,
            idempotency_key="actual-exception",
            actual_start_time="2026-05-01 08:00:00",
            exception_time="2026-05-01 08:25:00",
            exception_reason="设备问题",
            exception_severity="严重",
            exception_remark="主轴异常",
        ),
    )
    events = _events_for_op(db_path, card["op_id"])

    assert resp.status_code == 200
    assert [row["event_type"] for row in events] == ["start", "exception"]
    assert events[-1]["reason_code"] == "equipment"
    assert events[-1]["severity"] == "high"
    assert events[-1]["remark"] == "主轴异常"


