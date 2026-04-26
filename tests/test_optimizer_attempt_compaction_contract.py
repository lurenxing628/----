from __future__ import annotations

from core.services.scheduler.run.optimizer_search_state import compact_attempts
from core.services.scheduler.summary.optimizer_public_summary import project_public_algo_summary


def _scored_attempt(index: int) -> dict[str, object]:
    return {
        "tag": f"start:priority_first|batch_order:rule_{index}",
        "strategy": "priority_first",
        "dispatch_mode": "batch_order",
        "dispatch_rule": f"rule_{index}",
        "score": [float(index)],
    }


def _rejected_attempt(index: int) -> dict[str, object]:
    return {
        "tag": f"start:priority_first|sgs:rule_{index}",
        "strategy": "priority_first",
        "dispatch_mode": "sgs",
        "dispatch_rule": f"rule_{index}",
        "source": "candidate_rejected",
        "origin": {"type": "ValidationError", "field": "resource", "message": f"缺少资源 {index}"},
    }


def test_compact_attempts_keeps_scored_public_attempts_when_rejections_exceed_limit() -> None:
    attempts = [_scored_attempt(0), _scored_attempt(1)]
    attempts.extend(_rejected_attempt(index) for index in range(13))

    compacted = compact_attempts(attempts, limit=12)
    public_algo, diagnostics = project_public_algo_summary({"attempts": compacted})

    assert [attempt["score"] for attempt in public_algo["attempts"]] == [[0.0], [1.0]]
    rejected = [attempt for attempt in diagnostics["optimizer"]["attempts"] if attempt.get("source") == "candidate_rejected"]
    assert len(rejected) == 10
    assert all("score" not in attempt for attempt in rejected)


def test_compact_attempts_preserves_rejected_diagnostics_without_fake_score() -> None:
    attempts = [_scored_attempt(index) for index in range(11)]
    attempts.append(
        {
            "tag": "start:priority_first|batch_order:rejected",
            "strategy": "priority_first",
            "dispatch_mode": "batch_order",
            "dispatch_rule": "rejected",
            "source": "candidate_rejected",
            "origin": {"type": "ValidationError", "field": "resource", "message": "缺少资源"},
        }
    )

    compacted = compact_attempts(attempts, limit=12)

    rejected = [attempt for attempt in compacted if attempt.get("source") == "candidate_rejected"]
    assert len(rejected) == 1
    assert rejected[0]["origin"]["field"] == "resource"
    assert "score" not in rejected[0]
    assert len(compacted) == 12


def test_compact_attempts_preserves_rejected_diagnostic_when_scored_attempts_fill_limit() -> None:
    attempts = [_scored_attempt(index) for index in range(12)]
    attempts.append(_rejected_attempt(0))

    compacted = compact_attempts(attempts, limit=12)
    public_algo, diagnostics = project_public_algo_summary({"attempts": compacted})

    assert len(compacted) == 12
    assert len(public_algo["attempts"]) == 11
    assert all(attempt.get("source") != "candidate_rejected" for attempt in public_algo["attempts"])
    rejected = list(
        filter(
            lambda attempt: attempt.get("source") == "candidate_rejected",
            diagnostics["optimizer"]["attempts"],
        )
    )
    assert len(rejected) == 1
    assert rejected[0]["origin"]["field"] == "resource"
    assert rejected[0]["origin"]["message"] == "缺少资源 0"
    assert "score" not in rejected[0]


def test_compact_attempts_keeps_distinct_rejected_origins_for_same_tag() -> None:
    attempts = [_scored_attempt(index) for index in range(10)]
    attempts.extend(
        [
            {
                "tag": "local:swap",
                "strategy": "priority_first",
                "dispatch_mode": "sgs",
                "dispatch_rule": "slack",
                "source": "candidate_rejected",
                "origin": {"type": "ValidationError", "field": "resource", "message": "缺少资源"},
            },
            {
                "tag": "local:swap",
                "strategy": "priority_first",
                "dispatch_mode": "sgs",
                "dispatch_rule": "slack",
                "source": "candidate_rejected",
                "origin": {"type": "ValidationError", "field": "hours", "message": "工时非法"},
            },
        ]
    )

    compacted = compact_attempts(attempts, limit=12)

    rejected_fields = {
        attempt["origin"]["field"]
        for attempt in compacted
        if attempt.get("source") == "candidate_rejected"
    }
    assert rejected_fields == {"resource", "hours"}
