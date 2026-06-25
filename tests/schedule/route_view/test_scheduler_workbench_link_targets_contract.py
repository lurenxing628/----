"""契约测试：scheduler_workbench_links 工作台跳转链接的构造与护栏——各目标页 URL 保真透传版本/方案身份/日期范围/批次/资源等参数及 required_params 顺序、标签映射固定；护栏侧逐键四态拦放（R54 parity oracle）：预览/对比/历史方案禁开复盘入口、班组维度不支持页禁用、缺版本或日期范围禁用、反馈写入按完整方案身份判定、execution_review 拒绝从 extra_params 注入身份、坏摘要与缺目标页配置一律响亮报错。"""

from __future__ import annotations

from typing import Tuple
from urllib.parse import parse_qs, urlparse

import pytest

from core.models.schedule_plan_role import PLAN_ROLE_LABELS
from web.viewmodels.scheduler_workbench_links import (
    TARGET_PAGE_PATHS,
    build_workbench_link,
    build_workbench_plan_context,
    gantt_view_label,
    guardrail_reason_label,
    period_preset_label,
    plan_role_label,
    resource_type_label,
)


def _query_values(url: str) -> dict:
    return {key: values[-1] for key, values in parse_qs(urlparse(url).query).items()}



def _assert_url_fragments(url: str, fragments: Tuple[str, ...]) -> None:
    for fragment in fragments:
        assert fragment in url



def _machine_context_without_period() -> dict:
    return build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        date_from="2026-05-25",
        date_to="2026-05-31",
        query_date="2026-05-28",
        resource_type="machine",
        resource_id="M1",
        resource_label="M1 号设备",
    )


def _assert_shared_context_fragments(link: dict) -> None:
    _assert_url_fragments(link["url"], (
        "version=12",
        "plan_role=adopted",
        "date_from=2026-05-25",
        "date_to=2026-05-31",
        "query_date=2026-05-28",
    ))


def _assert_dashboard_analysis_reports_context(dashboard: dict, analysis: dict, reports: dict) -> None:
    for link in (dashboard, analysis, reports):
        _assert_shared_context_fragments(link)

    _assert_url_fragments(dashboard["url"], ("resource_type=machine", "resource_id=M1"))
    _assert_url_fragments(analysis["url"], ("resource_type=machine", "resource_id=M1"))
    _assert_url_fragments(reports["url"], ("resource_type=machine", "resource_id=M1"))


def _assert_dispatch_and_overdue_context(dispatch: dict, overdue: dict) -> None:
    _assert_url_fragments(dispatch["url"], (
        "period_preset=custom",
        "query_date=2026-05-28",
        "scope_type=machine",
        "machine_id=M1",
    ))
    _assert_url_fragments(overdue["url"], ("version=12", "plan_role=adopted"))
    for fragment in ("date_from=", "date_to=", "query_date=", "period_preset="):
        assert fragment not in overdue["url"]
    _assert_url_fragments(overdue["url"], ("resource_type=machine", "resource_id=M1"))
    assert overdue["target_page"] == "overdue_report"


def _assert_delay_context(delay: dict) -> None:
    assert delay["target_page"] == "delay_diagnosis"
    assert "/reports/overdue?" in delay["url"]
    _assert_url_fragments(delay["url"], (
        "plan_role=adopted",
        "batch_id=B202605-001",
        "resource_type=machine",
        "resource_id=M1",
    ))
    for fragment in ("date_from=", "date_to=", "query_date=", "period_preset="):
        assert fragment not in delay["url"]
    assert delay["label"] == "查看延期说明"


def test_target_pages_and_public_label_mappings_are_fixed() -> None:
    assert set(TARGET_PAGE_PATHS) == {
        "dashboard",
        "batches",
        "analysis",
        "gantt",
        "week_plan",
        "resource_dispatch",
        "overdue_report",
        "delay_diagnosis",
        "utilization_report",
        "execution_review",
        "downtime_report",
        "reports_index",
        "history",
        "batch_detail",
    }
    assert plan_role_label("baseline_best") == "原算法代表方案"
    assert plan_role_label("future_role") == "未知方案身份"
    assert guardrail_reason_label("data_gap") == "数据不足，暂时不能判断"
    assert guardrail_reason_label("future_reason") == "未知限制原因"
    assert resource_type_label("machine") == "设备视角"
    assert resource_type_label("future_resource") == "未知资源视角"
    assert period_preset_label("custom") == "自定义"
    assert period_preset_label("future_range") == "未知日期范围"
    assert gantt_view_label("operator") == "人员甘特"
    assert gantt_view_label("future_view") == "未知甘特视图"


# --- 新目标契约（fusion-handrolled-links-adoption）：history / batch_detail ---


def test_history_target_query_only_carries_optional_version_and_back_to() -> None:
    context = build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        date_from="2026-05-25",
        date_to="2026-05-31",
        query_date="2026-05-28",
        period_preset="week",
        batch_id="B202605-001",
        resource_type="machine",
        resource_id="M1",
        back_to="/scheduler/analysis",
    )
    link = build_workbench_link(context, "history")
    assert link["label"] == "查看排产历史"
    assert link["disabled"] is False
    assert urlparse(link["url"]).path == "/system/history"
    # version 可选筛选 + back_to；日期/批次/period/资源/方案身份一律不泄漏
    assert _query_values(link["url"]) == {"version": "12", "back_to": "/scheduler/analysis"}

    bare = build_workbench_link(build_workbench_plan_context(), "history")
    assert bare["disabled"] is False  # 非 VERSION_REQUIRED：无版本也可进历史页
    assert bare["url"] == "/system/history"


def test_batch_detail_target_puts_batch_id_in_path_and_fails_loud_without_it() -> None:
    context = build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        date_from="2026-05-25",
        date_to="2026-05-31",
        batch_id="B 1/2",
        back_to="/system/history",
    )
    link = build_workbench_link(context, "batch_detail")
    assert link["label"] == "查看批次详情"
    # 路径占位 quote(safe="")：空格与斜杠都转义，不出歧义路径
    assert urlparse(link["url"]).path == "/scheduler/batches/B%201%2F2"
    assert _query_values(link["url"]) == {"back_to": "/system/history"}

    explicit = build_workbench_link(context, "batch_detail", batch_id="B202605-002")
    assert urlparse(explicit["url"]).path == "/scheduler/batches/B202605-002"

    no_batch = build_workbench_plan_context(version=12, plan_role="adopted")
    with pytest.raises(ValueError):
        build_workbench_link(no_batch, "batch_detail")
    # 缺 batch_id 是编程错误，不随 disabled 摇摆——禁用态同样 raise
    with pytest.raises(ValueError):
        build_workbench_link(no_batch, "batch_detail", disabled=True, disabled_reason="人为禁用")


def test_context_free_targets_reject_extra_params_escape() -> None:
    # history/batch_detail 的 query 合同不可被 extra_params 绕过（execution_review 先例同款）
    context = build_workbench_plan_context(version=12, plan_role="adopted", batch_id="B1")
    for target, params in (
        ("history", {"batch_id": "B2"}),
        ("history", {"query_date": "2026-05-28"}),
        ("history", {"plan_role": "adopted"}),
        ("history", {"version": "99"}),
        ("history", {"view": "operator"}),
        ("batch_detail", {"batch_id": "B2"}),
        ("batch_detail", {"period_preset": "week"}),
        ("batch_detail", {"date_from": "2026-05-25"}),
        ("batch_detail", {"resource_id": "M1"}),
        ("batch_detail", {"version": "99"}),
        ("batch_detail", {"gantt_resource": "M1"}),
        # 'batches'（执行排产页）也是 context-free：不能被 extra_params 注入工作台上下文维度
        ("batches", {"version": "99"}),
        ("batches", {"plan_role": "adopted"}),
        ("batches", {"batch_id": "B2"}),
        ("batches", {"date_from": "2026-05-25"}),
        ("batches", {"resource_id": "M1"}),
        # 内部身份一律不得经 extra_params 注入 context-free 目标 URL（页面禁外显内部身份硬纪律）
        ("batches", {"op_id": "101"}),
        ("batches", {"schedule_id": "9"}),
        ("batches", {"candidate_id": "101"}),
        ("batches", {"source_table": "schedule_rows"}),
    ):
        with pytest.raises(ValueError):
            build_workbench_link(context, target, extra_params=params)
    # 非上下文键（如分页）不受限——只封工作台上下文维度；断完整 query 防合同变脏
    link = build_workbench_link(context, "history", extra_params={"page": "2"})
    assert _query_values(link["url"]) == {"version": "12", "page": "2"}


def test_workbench_plan_role_labels_delegate_to_core_labels() -> None:
    for role, label in PLAN_ROLE_LABELS.items():
        assert plan_role_label(role) == label
    assert plan_role_label(None) == PLAN_ROLE_LABELS["adopted"]
    assert plan_role_label("future_role") == "未知方案身份"


# ===========================================================================
