from __future__ import annotations

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


def test_explicit_summary_completion_status_still_wins_over_bad_counts() -> None:
    summary = {
        "completion_status": "success",
        "counts": {"op_count": "bad", "scheduled_ops": 1, "failed_ops": 0},
    }

    assert derive_completion_status(result_status="failed", summary=summary) == "success"
