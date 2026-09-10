"""Negative saved completeness evidence, never sampled summary completion times."""

from __future__ import annotations

from datetime import datetime
from typing import Dict

from core.models.schedule_plan_role import SOURCE_ADJUSTMENT_SCENARIO_ROWS, SOURCE_CANDIDATE_ROWS
from core.models.scheduler_history_parser import parse_result_summary_payload
from core.services.scheduler.summary.due_risk_items import incomplete_batch_ids_from_failure_details


def _counter(value):
    return value if type(value) is int and value >= 0 else None


def completion_evidence(record, task_count, finish_by_batch: Dict[str, datetime]):
    """Return (known incomplete batches, global uncertainty codes).

    Full live operation coverage is mandatory independently of these hints.
    A summary's omitted/sampled failures never prove that other batches finished.
    Scenario facts belong to the scenario, not the base version's summary.
    """
    if record["source"] == SOURCE_ADJUSTMENT_SCENARIO_ROWS:
        expected = _counter(record["scenario"]["row_count"])
        return set(), [] if expected == task_count else ["scenario_rows_incomplete"]
    parsed = parse_result_summary_payload(record["summary"])
    if parsed.parse_failed:
        return set(), ["completion_summary_invalid"]
    if parsed.payload is None:
        # Legacy candidates may have no summary; real full operation coverage is
        # still available. A missing official summary cannot attest its result.
        return set(), [] if record["source"] == SOURCE_CANDIDATE_ROWS else ["completion_summary_missing"]
    payload = parsed.payload
    details, uncertain = _summary_details(payload)
    if details is None:
        return set(), uncertain
    incomplete = incomplete_batch_ids_from_failure_details(details, finish_by_batch)
    uncertain.extend(_metric_issues(record, payload, incomplete))
    if record.get("result_status") not in (None, "success") and not incomplete:
        uncertain.append("completion_failures_unattributed")
    return incomplete, sorted(set(uncertain))


def _batch_details(value):
    if not isinstance(value, list):
        return None
    for row in value:
        if not isinstance(row, dict) or not isinstance(row.get("batch_id"), str) or not row["batch_id"].strip():
            return None
    return list(value)


def _summary_details(payload):
    details = _batch_details(payload.get("failure_details", []))
    if details is None:
        return None, ["completion_summary_invalid"]
    bucket, uncertain = payload.get("incomplete_batches"), []
    if bucket is not None:
        if not isinstance(bucket, dict):
            return None, ["completion_summary_invalid"]
        items, count = _batch_details(bucket.get("items")), _counter(bucket.get("count"))
        if items is None or count is None:
            return None, ["completion_summary_invalid"]
        details.extend(items)
        if count != len({row["batch_id"] for row in items}):
            uncertain.append("completion_summary_sampled")
    return details, uncertain


def _metric_issues(record, payload, incomplete):
    metrics = payload.get("metrics", {}) if record["source"] == SOURCE_CANDIDATE_ROWS else payload.get("counts", {})
    uncertain = []
    if not isinstance(metrics, dict):
        uncertain.append("completion_summary_invalid")
    else:
        for key in ("failed_ops", "incomplete_batch_count"):
            if key in metrics:
                count = _counter(metrics[key])
                if count is None:
                    uncertain.append("completion_summary_invalid")
                elif count > 0 and not incomplete:
                    uncertain.append("completion_failures_unattributed")
    return uncertain
