"""回归测试：现场报异常接口（/scheduler/resource-dispatch/execution/<op_id>/report-exception）在查询指向非当前正式计划（baseline_best/场景方案/历史版本）时必须 409 拒绝（reason=not_current_official_plan、can_retry=false），且不落任何反馈事件。"""

from __future__ import annotations

from tests.operation_execution.operation_execution_feedback_test_support import (
    _base_payload,
    _build_app,
    _current_card,
    _event_count,
    _json,
    _post_controlled,
)


def test_report_exception_rejects_candidate_scenario_and_history_plans(tmp_path, monkeypatch) -> None:
    app, db_path = _build_app(tmp_path, monkeypatch)
    client = app.test_client()
    card = _current_card(client)
    cases = (
        "scope_type=operator&operator_id=O2&period_preset=week&query_date=2026-05-01&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=baseline_best",
        "scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-05-01&date_from=2026-05-01&date_to=2026-05-07&version=2&plan_role=adopted&scenario_id=scenario-plain",
        "scope_type=operator&operator_id=O1&period_preset=week&query_date=2026-04-30&date_from=2026-04-27&date_to=2026-05-03&version=1&plan_role=adopted",
    )

    for index, query in enumerate(cases):
        resp = _post_controlled(
            client,
            f"/scheduler/resource-dispatch/execution/{card['op_id']}/report-exception?{query}",
            _base_payload(
                card,
                idempotency_key=f"reject-report-exception-{index}",
                reason_code="equipment",
                severity="high",
                remark="设备异常",
            ),
        )
        payload = _json(resp)
        assert resp.status_code == 409
        assert payload["error"]["details"]["reason"] == "not_current_official_plan"
        assert payload["error"]["details"]["action_label"] == "报异常"
        assert payload["error"]["details"]["can_retry"] is False
    assert _event_count(db_path) == 0
