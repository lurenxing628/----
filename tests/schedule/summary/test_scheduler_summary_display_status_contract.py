"""测试：scheduler_summary_display 完工状态推断契约——derive_completion_status 在缺 completion_status 但有错误/坏 error_count 时判 unknown、显式 completion_status 优先于错误、无错误时回退按 counts 推断；counts 含 bad/bool/小数/非有限/负数时标 summary_count_parse_failed 并把状态压成 unknown（即使 DB/显式为 success），该标志经 size_guard 截断仍存活；坏 error_count/缺资源计数/坏降级事件 count 展示为“记录异常”且绝不泄漏原始脏值。"""

from __future__ import annotations

from core.services.scheduler.summary.summary_size_guard import apply_summary_size_guard
from web.viewmodels.scheduler_summary_display import build_summary_display_state, derive_completion_status


def test_missing_completion_status_with_errors_is_unknown_even_if_counts_look_successful() -> None:
    summary = {
        "counts": {"op_count": 1, "scheduled_ops": 1, "failed_ops": 0},
        "error_count": 1,
        "errors": ["Traceback sqlite /tmp/private.db"],
    }

    assert derive_completion_status(result_status=None, summary=summary) == "unknown"


def test_missing_completion_status_with_string_error_count_is_unknown() -> None:
    summary = {
        "counts": {"op_count": 1, "scheduled_ops": 1, "failed_ops": 0},
        "error_count": "1",
    }

    assert derive_completion_status(result_status=None, summary=summary) == "unknown"


def test_missing_completion_status_with_malformed_error_count_is_unknown() -> None:
    summary = {
        "counts": {"op_count": 1, "scheduled_ops": 1, "failed_ops": 0},
        "error_count": "not-a-number",
    }

    assert derive_completion_status(result_status=None, summary=summary) == "unknown"


def test_explicit_completion_status_still_wins_over_errors_for_history_contract() -> None:
    summary = {
        "completion_status": "partial",
        "counts": {"op_count": 1, "scheduled_ops": 1, "failed_ops": 0},
        "error_count": 1,
        "errors": ["internal"],
    }

    assert derive_completion_status(result_status=None, summary=summary) == "partial"


def test_missing_completion_status_without_errors_keeps_legacy_counts_inference() -> None:
    summary = {
        "counts": {"op_count": 2, "scheduled_ops": 2, "failed_ops": 0},
    }

    assert derive_completion_status(result_status=None, summary=summary) == "success"


def test_unknown_result_status_with_successful_counts_is_unknown() -> None:
    # 未知 result_status（如已删 ok2 残值、写入方笔误）即便计数全成功，也必须诚实降级
    # 为 unknown，不能被计数推断盖成 success——schedule-result-status.md 裁决。
    summary = {"counts": {"op_count": 5, "scheduled_ops": 5, "failed_ops": 0}}

    assert derive_completion_status(result_status="ok2", summary=summary) == "unknown"
    assert derive_completion_status(result_status="future_x", summary=summary) == "unknown"
    # 对照：result_status 缺省（空）时仍走计数推断，不误伤合法的「状态字段未记录」场景
    assert derive_completion_status(result_status="", summary=summary) == "success"
    assert derive_completion_status(result_status=None, summary=summary) == "success"
    # 显式 'unknown' 原值走 known_status 早返回分支（在词表内），不依赖新增的未知拦截分支
    assert derive_completion_status(result_status="unknown", summary=summary) == "unknown"


def test_simulated_result_status_still_derives_outcome_from_counts() -> None:
    # simulated 是合法模式标记（在词表内），不属于完成态——其 outcome 仍由计数推断，
    # 不能被未知降级误伤；否则模拟排产历史会全部错标「有问题，需检查」。
    full = {"counts": {"op_count": 5, "scheduled_ops": 5, "failed_ops": 0}}
    partial = {"counts": {"op_count": 5, "scheduled_ops": 3, "failed_ops": 2}}

    assert derive_completion_status(result_status="simulated", summary=full) == "success"
    assert derive_completion_status(result_status="simulated", summary=partial) == "partial"


def test_malformed_counts_make_status_unknown_and_visible() -> None:
    summary = {
        "counts": {"op_count": "bad", "scheduled_ops": 1, "failed_ops": 0},
    }

    assert derive_completion_status(result_status=None, summary=summary) == "unknown"
    display = build_summary_display_state(summary, result_status=None)
    assert display["summary_count_parse_failed"] is True
    assert "数量记录异常" in str(display["summary_count_parse_message"])


def test_malformed_counts_override_database_success_status() -> None:
    summary = {
        "counts": {"op_count": "bad", "scheduled_ops": 1, "failed_ops": 0},
    }

    assert derive_completion_status(result_status="success", summary=summary) == "unknown"


def test_bool_counts_mark_summary_count_parse_failed() -> None:
    summary = {"counts": {"scheduled_ops": True, "failed_ops": 0, "op_count": 1}}
    display = build_summary_display_state(summary, result_status="success")

    assert display["summary_count_parse_failed"] is True
    assert display["completion_status"] == "unknown"


def test_non_integer_counts_mark_summary_count_parse_failed() -> None:
    bad_values = ["1.5", float("nan"), float("inf"), -1]
    for bad_value in bad_values:
        summary = {"counts": {"scheduled_ops": 1, "failed_ops": 0, "op_count": bad_value}}
        display = build_summary_display_state(summary, result_status="success")

        assert display["summary_count_parse_failed"] is True, bad_value
        assert display["completion_status"] == "unknown", bad_value


def test_bad_counts_override_explicit_success_completion_status() -> None:
    summary = {
        "completion_status": "success",
        "counts": {"op_count": "bad", "scheduled_ops": 1, "failed_ops": 0},
    }

    assert derive_completion_status(result_status="failed", summary=summary) == "unknown"


def test_backend_summary_count_parse_failed_flag_overrides_explicit_success() -> None:
    summary = {
        "completion_status": "success",
        "summary_count_parse_failed": True,
        "counts": {"op_count": 0, "scheduled_ops": 0, "failed_ops": 0},
    }

    assert derive_completion_status(result_status="success", summary=summary) == "unknown"
    display = build_summary_display_state(summary, result_status="success")
    assert display["summary_count_parse_failed"] is True
    assert display["completion_status"] == "unknown"


def test_summary_count_parse_failed_survives_size_guard() -> None:
    summary = {
        "completion_status": "success",
        "summary_count_parse_failed": True,
        "summary_count_parse_errors": ["total_ops 必须是非负整数：'bad'"],
        "counts": {"op_count": 0, "scheduled_ops": 0, "failed_ops": 0},
        "degradation_events": [
            {
                "code": "summary_count_parse_failed",
                "scope": "schedule.summary.counts",
                "field": "counts",
                "message": "排产摘要里的数量记录异常，不能按这些数量判断结果。",
                "count": 1,
            }
        ],
        "degraded_causes": ["summary_count_parse_failed"],
        "selected_batch_ids": ["B" + str(i).zfill(8) for i in range(60000)],
    }

    guarded = apply_summary_size_guard(summary)
    assert guarded["summary_truncated"] is True
    assert guarded["summary_count_parse_failed"] is True
    assert guarded["summary_count_parse_errors"]

    display = build_summary_display_state(guarded, result_status="success")
    assert display["summary_count_parse_failed"] is True
    assert display["completion_status"] == "unknown"


def test_summary_count_parse_failed_degradation_marker_overrides_success() -> None:
    summary = {
        "completion_status": "success",
        "counts": {"op_count": 0, "scheduled_ops": 0, "failed_ops": 0},
        "degradation_events": [{"code": "summary_count_parse_failed"}],
    }

    display = build_summary_display_state(summary, result_status="success")
    assert display["summary_count_parse_failed"] is True
    assert display["completion_status"] == "unknown"


def test_bad_error_and_missing_resource_counts_are_visible_record_errors() -> None:
    summary = {
        "completion_status": "partial",
        "error_count": "bad-error-count",
        "errors": ["内部错误详情不外露"],
        "missing_internal_resource_count": "1.5",
        "missing_internal_resource_ops": [
            {"batch_id": "B1", "seq": 10, "missing_fields": ["设备"]},
        ],
    }

    display = build_summary_display_state(summary, result_status="partial")

    assert display["error_count_parse_failed"] is True
    assert display["missing_internal_resource_count_parse_failed"] is True
    assert display["error_total_label"] == "记录异常"
    assert display["missing_internal_resource_count_label"] == "记录异常"
    assert display["summary_count_parse_failed"] is True
    assert "bad-error-count" not in str(display)
    assert "1.5" not in str(display)


def test_bad_degradation_event_count_is_visible_record_error_without_raw_value() -> None:
    summary = {
        "completion_status": "success",
        "counts": {"op_count": 1, "scheduled_ops": 1, "failed_ops": 0},
        "degradation_events": [
            {
                "code": "resource_pool_degraded",
                "count": "bad-degradation-count",
            }
        ],
    }

    display = build_summary_display_state(summary, result_status="success")

    assert "资源池资料不完整（数量记录异常）" in str(display["primary_degradation"]["details"])
    assert "bad-degradation-count" not in str(display)
