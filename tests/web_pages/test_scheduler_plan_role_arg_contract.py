"""回归测试：scheduler 路由 plan_role 取参唯一来源 get_plan_role_arg——缺参/空串/空白一律返回 None（交由下游 resolve 决定默认值，绝不在取参层兜底成 adopted），非空值 strip 后原样返回（坏值由下游 normalize loud 拒绝）；gantt 与 week_plan 两路由共享这一份实现，不再各自手维副本。"""

from __future__ import annotations

from flask import Flask

from web.routes.domains.scheduler.scheduler_utils import get_plan_role_arg


def _arg_with_query(query: str):
    app = Flask(__name__)
    path = f"/scheduler/gantt?{query}" if query else "/scheduler/gantt"
    with app.test_request_context(path):
        return get_plan_role_arg()


def test_get_plan_role_arg_returns_none_for_missing_blank_and_whitespace() -> None:
    assert _arg_with_query("") is None
    assert _arg_with_query("plan_role=") is None
    assert _arg_with_query("plan_role=%20%20") is None


def test_get_plan_role_arg_strips_and_preserves_value_without_adopted_fallback() -> None:
    assert _arg_with_query("plan_role=adopted") == "adopted"
    assert _arg_with_query("plan_role=%20baseline_best%20") == "baseline_best"
    # 非法值也原样透传——取参层不做白名单校验，坏值由下游 resolve/normalize loud 拒绝。
    assert _arg_with_query("plan_role=bogus") == "bogus"


def test_gantt_and_week_plan_share_single_plan_role_getter() -> None:
    from web.routes.domains.scheduler import scheduler_gantt, scheduler_week_plan
    from web.routes.domains.scheduler.scheduler_utils import get_plan_role_arg as canonical

    assert scheduler_gantt.get_plan_role_arg is canonical
    assert scheduler_week_plan.get_plan_role_arg is canonical
    assert not hasattr(scheduler_gantt, "_get_plan_role_arg")
    assert not hasattr(scheduler_week_plan, "_get_plan_role_arg")
