from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_scheduler_core_pages_use_plain_page_hero_contract() -> None:
    pages = {
        "templates/scheduler/batches.html": "aps_page_hero",
        "web_new_test/templates/scheduler/batches.html": "aps_page_hero",
        "templates/scheduler/config.html": "aps_page_hero",
        "web_new_test/templates/scheduler/config.html": "aps_page_hero",
        "templates/scheduler/analysis.html": "aps_page_hero",
        "templates/scheduler/calendar.html": "aps_page_hero",
        "templates/scheduler/gantt.html": "aps_page_hero",
        "web_new_test/templates/scheduler/gantt.html": "aps_page_hero",
        "templates/scheduler/week_plan.html": "aps_page_hero",
        "templates/scheduler/resource_dispatch.html": "aps_page_hero",
        "templates/reports/index.html": "aps_page_hero",
    }
    for rel_path, required_marker in pages.items():
        source = _read(rel_path)
        assert required_marker in source, f"{rel_path} 没接入统一页头"
        assert "aps-scenario-strip" not in source, f"{rel_path} 顶部不应再使用常用场景标签条"


def test_main_business_pages_do_not_use_scenario_strip_in_top_card() -> None:
    rel_paths = (
        "templates/process/list.html",
        "templates/process/op_types_list.html",
        "templates/process/suppliers_list.html",
        "templates/process/detail.html",
        "templates/equipment/list.html",
        "templates/personnel/list.html",
        "templates/scheduler/batches_manage.html",
        "web_new_test/templates/scheduler/batches_manage.html",
    )
    for rel_path in rel_paths:
        source = _read(rel_path)
        assert "aps-page-purpose" in source
        assert "aps-scenario-strip" not in source


def test_dynamic_business_state_is_not_rendered_inside_hero() -> None:
    gantt = _read("templates/scheduler/gantt.html")
    gantt_start = gantt.index("ui.aps_page_hero(")
    gantt_end = gantt.index("{% if not has_history %}", gantt_start)
    gantt_hero = gantt[gantt_start:gantt_end]
    for forbidden in ("显示范围", "暂无排产版本", "meta_items", "aps-page-meta-row"):
        assert forbidden not in gantt_hero, f"甘特图页头不应承载动态业务状态：{forbidden}"
    assert "aps_context_bar" in gantt, "甘特图业务上下文应下移到业务卡片"

    week_plan = _read("templates/scheduler/week_plan.html")
    week_start = week_plan.index("ui.aps_page_hero(")
    week_end = week_plan.index('<div class="card">', week_start)
    week_hero = week_plan[week_start:week_end]
    for forbidden in ("周范围", "暂无版本", "meta_items", "aps-page-meta-row"):
        assert forbidden not in week_hero, f"周计划页头不应承载动态业务状态：{forbidden}"
    assert "aps_context_bar" in week_plan, "周计划业务上下文应下移到查询卡片"

    resource_dispatch = _read("templates/scheduler/resource_dispatch.html")
    rd_start = resource_dispatch.index("ui.aps_page_hero(")
    rd_end = resource_dispatch.index('<div class="card">', rd_start)
    rd_hero = resource_dispatch[rd_start:rd_end]
    for forbidden in ("查询对象", "区间", "当前暂无排产历史", "请选择单人", "aps-page-meta-row"):
        assert forbidden not in rd_hero, f"资源排班页头不应承载动态业务状态：{forbidden}"
    assert "aps_context_bar" in resource_dispatch, "资源排班业务上下文应下移到查询卡片"

    reports = _read("templates/reports/index.html")
    report_start = reports.index("ui.aps_page_hero(")
    report_end = reports.index("{% if has_history %}", report_start)
    report_hero = reports[report_start:report_end]
    for forbidden in ("最新排产版本", "超期批次", "当前状态", "meta_items"):
        assert forbidden not in report_hero, f"报表首页页头不应承载动态业务状态：{forbidden}"
    assert "暂无排产历史，请先执行排产后再查看报表。" in reports


def main() -> None:
    test_scheduler_core_pages_use_plain_page_hero_contract()
    test_main_business_pages_do_not_use_scenario_strip_in_top_card()
    test_dynamic_business_state_is_not_rendered_inside_hero()
    print("OK")


if __name__ == "__main__":
    main()
