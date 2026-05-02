from __future__ import annotations

import json

from web.viewmodels.scheduler_analysis_vm import _comparison_metric_from_algo, build_analysis_context
from web.viewmodels.scheduler_summary_display import build_summary_display_state


def test_legacy_summary_bridge_only_applies_when_metric_and_schema_missing() -> None:
    assert _comparison_metric_from_algo({"objective": "min_tardiness"}) == "total_tardiness_hours"
    assert _comparison_metric_from_algo({"objective": "min_changeover"}) == "changeover_count"


def test_legacy_summary_bridge_does_not_override_new_summary_fields() -> None:
    algo = {
        "objective": "min_tardiness",
        "comparison_metric": "weighted_tardiness_hours",
        "best_score_schema": [
            {"index": 0, "key": "failed_ops", "label": "失败工序数"},
            {"index": 1, "key": "total_tardiness_hours", "label": "总拖期小时"},
        ],
    }

    assert _comparison_metric_from_algo(algo) == "weighted_tardiness_hours"


def test_build_analysis_context_returns_pure_data_payload() -> None:
    summary = {
        "algo": {
            "objective": "min_changeover",
            "config_snapshot": {"objective": "min_changeover"},
            "best_score_schema": [
                {"index": 0, "key": "failed_ops", "label": "失败工序数"},
                {"index": 1, "key": "changeover_count"},
            ],
            "metrics": {"changeover_count": 1},
        }
    }

    ctx = build_analysis_context(
        selected_ver=3,
        raw_hist=[{"version": 3, "result_summary": summary}],
        selected_item={"version": 3, "result_summary": summary},
    )

    assert "objective_label_for" not in ctx
    assert ctx["algo_objective_label"] == "最少换型次数"
    assert ctx["best_score_schema_display"][1]["display_label"] == "换型次数"
    assert ctx["algo_config_snapshot_objective_label"] == "最少换型次数"
    json.dumps(ctx, ensure_ascii=False)


def test_build_analysis_context_marks_legacy_compat_fallback_visible() -> None:
    summary = {
        "algo": {
            "objective": "min_tardiness",
            "metrics": {"total_tardiness_hours": 3.5},
        }
    }

    ctx = build_analysis_context(
        selected_ver=4,
        raw_hist=[{"version": 4, "result_summary": summary}],
        selected_item={"version": 4, "result_summary": summary},
    )

    assert ctx["compat_fallback"]["used"] is True
    assert set(ctx["compat_fallback"]["missing_fields"]) == {"comparison_metric", "best_score_schema"}


def test_build_summary_display_state_bridges_legacy_degraded_causes_when_events_missing() -> None:
    display = build_summary_display_state(
        {
            "degraded_causes": ["resource_pool_degraded", "merge_context_degraded"],
            "warnings": [],
            "errors": [],
            "counts": {"op_count": 1, "scheduled_ops": 1, "failed_ops": 0},
        },
        result_status="success",
    )

    assert display["primary_degradation"] is not None
    details = list(display["primary_degradation"]["details"] or [])
    assert any("资源池资料不完整" in item for item in details), details
    assert any("组合并资料不完整" in item for item in details), details
    secondary = list(display["secondary_degradation_messages"] or [])
    assert any(str(item.get("code") or "") == "resource_pool_degraded" for item in secondary), secondary


def test_build_summary_display_state_prefers_degradation_events_over_legacy_causes() -> None:
    display = build_summary_display_state(
        {
            "degraded_causes": ["resource_pool_degraded"],
            "degradation_events": [
                {"code": "template_missing", "message": "模板缺失", "count": 2},
            ],
            "warnings": [],
            "errors": [],
            "counts": {"op_count": 1, "scheduled_ops": 1, "failed_ops": 0},
        },
        result_status="success",
    )

    secondary = list(display["secondary_degradation_messages"] or [])
    assert [str(item.get("code") or "") for item in secondary] == ["template_missing"], secondary
