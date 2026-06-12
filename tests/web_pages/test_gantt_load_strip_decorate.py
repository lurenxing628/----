"""负荷条带 web 装饰契约（fusion-gantt-load-strip）。

钉死点：severity 边界五点（0.74/0.75/0.89/0.90/None——阈值 import
dashboard_workbench_cards 唯一字源，无第三份常量）；links 两条形状
（resource_dispatch 带资源上下文 / utilization_report）；scenario 预览态
派工链接 disabled+原因；装饰幂等（重复调用不重复追加）；阈值常量全仓
唯一定义点反向 grep。
"""

from __future__ import annotations

from tests._support.paths import REPO_ROOT
from web.viewmodels.scheduler_gantt_load_strip import (
    decorate_gantt_resource_load_payload,
    load_severity,
)


def _payload(rows, **extra):
    data = {
        "view": "machine",
        "version": 7,
        "week_start": "2026-06-15",
        "week_end": "2026-06-21",
        "effective_plan_role": "adopted",
        "resource_load": rows,
    }
    data.update(extra)
    return data


def _row(ratio=0.5):
    return {
        "date": "2026-06-15",
        "resource_id": "MC1",
        "resource_label": "MC1 CNC-01",
        "hours": 4.0,
        "capacity_hours": 8.0,
        "ratio": ratio,
    }


def test_severity_boundaries_locked():
    assert load_severity(None) == "unknown"
    assert load_severity(0.74) == "normal"
    assert load_severity(0.75) == "warning"
    assert load_severity(0.89) == "warning"
    assert load_severity(0.90) == "danger"
    assert load_severity(1.25) == "danger"


def test_decorate_adds_severity_and_two_links():
    data = decorate_gantt_resource_load_payload(_payload([_row(0.92)]))
    row = data["resource_load"][0]
    assert row["severity"] == "danger"
    assert [link["target_page"] for link in row["links"]] == ["resource_dispatch", "utilization_report"]
    dispatch = row["links"][0]
    assert dispatch["disabled"] is False
    # 资源上下文经 query_for_target 编码为 scope/machine_id（link 层既定参数词表）
    assert "machine_id=MC1" in dispatch["url"]
    assert "version=7" in dispatch["url"]
    assert "date_from=2026-06-15" in dispatch["url"]
    report = row["links"][1]
    assert report["label"] == "查看资源负荷报表"
    assert report["url"].startswith("/reports/utilization?")


def test_scenario_preview_disables_dispatch_link_with_reason():
    data = decorate_gantt_resource_load_payload(
        _payload([_row(0.5)], scenario_id="sc-1", is_scenario_preview=True)
    )
    dispatch = data["resource_load"][0]["links"][0]
    assert dispatch["disabled"] is True
    assert "模拟预览" in dispatch["disabled_reason"]
    assert dispatch["url"] == ""


def test_decorate_idempotent_and_tolerates_missing_field():
    data = _payload([_row(0.5)])
    decorate_gantt_resource_load_payload(data)
    first_links = data["resource_load"][0]["links"]
    decorate_gantt_resource_load_payload(data)
    assert data["resource_load"][0]["links"] is first_links  # 已装饰行原样跳过
    assert decorate_gantt_resource_load_payload({"tasks": []}) == {"tasks": []}


def test_thresholds_single_source_no_third_copy():
    # 阈值唯一定义点仍是 dashboard_workbench_cards.py；装饰层只 import 不复制
    strip_text = (REPO_ROOT / "web/viewmodels/scheduler_gantt_load_strip.py").read_text(encoding="utf-8")
    assert "0.75" not in strip_text
    assert "0.90" not in strip_text
    assert "from .dashboard_workbench_cards import" in strip_text
