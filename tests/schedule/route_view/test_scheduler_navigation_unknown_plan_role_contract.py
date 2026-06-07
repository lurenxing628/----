"""回归测试：build_scheduler_navigation_links 在请求带未知 plan_role（如 future_role）时，应从生成的导航链接中剔除该未知值并回退为 plan_role=adopted。"""

from __future__ import annotations

from tests.web_pages.reports_workbench_backlink_helpers import _client


def test_scheduler_navigation_fallback_drops_unknown_plan_role_from_links() -> None:
    app = _client().application
    from web.navigation_context import build_scheduler_navigation_links

    with app.test_request_context(
        "/scheduler/config?version=12&plan_role=future_role&date_from=2026-05-06&date_to=2026-05-06"
    ):
        links = build_scheduler_navigation_links()

    href_blob = "\n".join(str(item.get("url") or "") for item in links)
    assert "future_role" not in href_blob
    assert "plan_role=adopted" in href_blob
