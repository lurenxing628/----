"""空周跳转方案身份单测（fusion-week-plan-enrich 审核补强）。

钉死点：plan_role_resolution 的 selected_role/scenario_id 必须透传到 span 查询
与跳转链接（读错键误当 adopted 是 Codex 审核阻塞真因）；span 读取异常回落 {}
不炸页面主体；坏时间过滤态清空跳转链接（问题是数据不是选错周）。
"""

from __future__ import annotations

from types import SimpleNamespace

from flask import Flask

from web.routes.domains.scheduler.scheduler_week_plan_preview import (
    build_week_plan_preview_state,
    week_plan_span_jump,
)

_SPAN = {"start_time": "2026-06-01 08:00:00", "end_time": "2026-06-03 18:00:00"}


class _PlanQueryStub:
    """贴真实 SchedulePlanQueryService 查询面：记录两条 span 查询的调用参数。"""

    def __init__(self):
        self.span_calls = []
        self.view_calls = []

    def get_plan_time_span(self, version, plan_role):
        self.span_calls.append((version, plan_role))
        return dict(_SPAN)

    def get_plan_time_span_for_view(self, version, plan_role, scenario_id):
        self.view_calls.append((version, plan_role, scenario_id))
        return dict(_SPAN)


def _services(stub):
    return SimpleNamespace(schedule_plan_query_service=stub)


def test_span_jump_non_adopted_role_passes_through_to_query_and_link():
    stub = _PlanQueryStub()
    out = week_plan_span_jump(
        _services(stub),
        {"version": 7, "plan_role_resolution": {"selected_role": "baseline_best", "scenario_id": None}},
    )
    assert stub.span_calls == [(7, "baseline_best")]
    assert "plan_role=baseline_best" in out["jump_link"]["url"]
    assert out["span"]["start_date"] == "2026-06-01"
    assert out["span"]["end_date"] == "2026-06-03"


def test_span_jump_scenario_identity_uses_view_query_and_link_param():
    stub = _PlanQueryStub()
    app = Flask(__name__)
    with app.app_context():
        out = week_plan_span_jump(
            _services(stub),
            {"version": 7, "plan_role_resolution": {"selected_role": "adopted", "scenario_id": "SC1"}},
        )
    assert stub.view_calls == [(7, "adopted", "SC1")]
    assert stub.span_calls == []
    assert "scenario_id=SC1" not in out["jump_link"]["url"]
    assert "plan_context_token=" in out["jump_link"]["url"]


def test_span_jump_missing_meta_defaults_adopted():
    stub = _PlanQueryStub()
    week_plan_span_jump(_services(stub), {"version": 7})
    assert stub.span_calls == [(7, "adopted")]


def test_span_jump_query_failure_degrades_to_empty_dict():
    class _Boom:
        def get_plan_time_span(self, version, plan_role):
            raise RuntimeError("db gone")

    app = Flask(__name__)  # current_app.logger.warning 需要 app context
    with app.app_context():
        assert week_plan_span_jump(_services(_Boom()), {"version": 7}) == {}


def test_preview_state_bad_time_filtered_clears_jump_link():
    state = build_week_plan_preview_state(
        {
            "rows": [],
            "empty_reason": "all_rows_filtered_by_invalid_time",
            "degradation_counters": {"bad_time_row_skipped": 2},
        },
        span_jump={
            "span": {"start_date": "2026-06-01", "end_date": "2026-06-03"},
            "jump_link": {"url": "/scheduler/week-plan?version=7"},
        },
    )
    assert state["empty_jump_link"] is None
    assert "已过滤 2 条" in state["empty_message"]
