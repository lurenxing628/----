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
