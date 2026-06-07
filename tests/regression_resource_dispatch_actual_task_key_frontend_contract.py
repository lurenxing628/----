"""回归测试：资源派工执行反馈的 task_key 上报实际路由（/scheduler/resource-dispatch/execution/tasks/<task_key>/actual）能接受前端真实 payload——即使省略 version/schedule_id/operator_id/expected_state_revision 等旧身份字段也返回 200，并据 task_key 与 query 推出身份，按序写出 start、finish 两条事件且记下完工/报废数量。"""

from __future__ import annotations

from typing import Any, Dict

from tests.operation_execution_feedback_test_support import (
    _base_payload,
    _build_app,
    _current_card,
    _current_query,
    _events_for_card,
    _json,
)


def _actual_url(card: Dict[str, Any]) -> str:
    return f"/scheduler/resource-dispatch/execution/tasks/{card['task_key']}/actual?{_current_query()}"


def _frontend_payload(card: Dict[str, Any], **overrides: Any) -> Dict[str, Any]:
    payload = _base_payload(card, **overrides)
    for key in (
        "version",
        "schedule_id",
        "batch_id",
        "requested_plan_role",
        "effective_plan_role",
        "source_table",
        "scenario_id",
        "expected_state_revision",
        "event_time",
        "operator_id",
        "machine_id",
    ):
        payload.pop(key, None)
    return payload


def test_task_key_actual_route_accepts_frontend_payload_without_legacy_identity_fields(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    payload = _frontend_payload(
        card,
        created_by="张三",
        feedback_person="张三",
        idempotency_key="frontend-task-key-actual",
        actual_start_time="2026-05-01 08:00:00",
        actual_finish_time="2026-05-01 09:00:00",
        quantity_done="10",
        quantity_scrapped="0",
        remark="页面直接提交",
    )

    resp = client.post(_actual_url(card), json=payload)
    events = _events_for_card(db_path, card)

    assert resp.status_code == 200, _json(resp)
    assert [row["event_type"] for row in events] == ["start", "finish"]
    assert events[1]["quantity_done"] == 10
    assert events[1]["quantity_scrapped"] == 0
