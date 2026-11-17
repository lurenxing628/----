"""Decode durable WorkbenchHistoryEntries rows into typed history descriptors."""

from typing import Any, Dict, List, Sequence, Tuple

from core.models.content import read_stored_json
from core.services.workbench.facts.run_history_projection import admitted_run_input
from data.repositories.workbench_history_catalog_repo import WorkbenchHistoryCatalogRepository

_TIME_FIELDS = ("accepted_at", "started_at", "finished_at", "adopted_at", "committed_at_utc", "schedule_time")


def history_gap(field: str, code: str = "not_recorded") -> Dict[str, str]:
    return {
        "field": field,
        "code": code,
        "message": "原记录未保存此项。" if code == "not_recorded" else "原记录的此项无法确认。",
    }


def _decode_row(row: Dict[str, Any]) -> Dict[str, Any]:
    raw_times = read_stored_json(row["times_json"], dict)
    times = {key: raw_times.get(key) for key in _TIME_FIELDS}
    if row["live_job_started_at"] is not None and times["started_at"] is None:
        times["started_at"] = row["live_job_started_at"]

    gaps = read_stored_json(row["evidence_gaps_json"], list)
    source_kind = row["source_kind"]
    history_id = None
    if source_kind != "run":
        if row["existing_history_version"] is not None:
            history_id = row["existing_history_version"]
        else:
            if not any(item.get("code") == "audit_missing" for item in gaps):
                gaps.append(history_gap("adoption", "audit_missing"))
            if not any(item.get("field") == "official_plan" for item in gaps):
                gaps.append(history_gap("official_plan", "official_identity_unavailable"))

    selection = read_stored_json(row["selection_json"], dict)
    objective = read_stored_json(row["objective_json"], dict)
    # Only entries of a run join its stored input.
    run_input = (
        admitted_run_input(read_stored_json(row["run_normalized_input_json"], dict))
        if row["run_normalized_input_json"] is not None
        else None
    )
    source = {
        "run_ref": row["run_ref"],
        "candidate_ref": row["candidate_ref"],
        "scenario_ref": row["scenario_ref"],
        "draft_ref": row["draft_ref"],
        "plan_ref": row["plan_ref"],
        "version": row["plan_version"],
        "history_id": history_id,
        "receipt_ref": row["receipt_ref"],
        "request_key": row["request_key"],
    }
    return {
        "entry_ref": row["entry_ref"],
        "timeline": row["timeline"],
        "source_kind": source_kind,
        "state": row["effective_state"],
        "label": row["display_label"],
        "source": source,
        "times": times,
        "baseline": {
            "plan_ref": row["baseline_plan_ref"],
            "version": row["baseline_version"],
        },
        "selected_candidate_ref": row["selected_candidate_ref"],
        "selection": selection,
        "occurred_at": row["occurred_at"],
        "occurred_us": row["occurred_us"],
        "time_basis": row["time_basis"],
        "evidence_gaps": gaps,
        "objective": objective,
        "static_condition_digest": row["static_condition_digest"],
        "default_7d_calendar_digest": row["default_7d_calendar_digest"],
        "run_input": run_input,
    }


def _require_read_tx(conn) -> WorkbenchHistoryCatalogRepository:
    if not conn.in_transaction:
        raise RuntimeError("History catalog requires the caller's read transaction")
    return WorkbenchHistoryCatalogRepository(conn)


def read_history_snapshot_context(
    conn,
    query: Dict[str, Any],
    anchor_refs: Sequence[str],
) -> Tuple[Dict[str, int], Dict[str, Any], Dict[str, Dict[str, Any]]]:
    """Read lightweight directory summary, totals and explicitly selected anchor descriptors."""
    repo = _require_read_tx(conn)
    summary_rows = repo.directory_summary()
    run_total = sum(row["cnt"] for row in summary_rows if row["timeline"] == "run")
    official_total = sum(row["cnt"] for row in summary_rows if row["timeline"] == "official")
    filtered_total = repo.count_filtered(
        timeline=query["timeline"],
        state=query["state"],
        date_from=query["date_from"],
        date_to=query["date_to"],
    )
    totals = {
        "run": run_total,
        "official": official_total,
        "filtered": filtered_total,
    }
    raw_anchors = repo.entries_by_refs(anchor_refs)
    anchors = {ref: _decode_row(raw) for ref, raw in raw_anchors.items()}
    state = {
        "directory_summary": summary_rows,
        "active_runs": repo.active_runs_state(),
        "identity_clock": repo.identity_clock(),
    }
    return totals, state, anchors


def read_history_entries_page(
    conn,
    query: Dict[str, Any],
    *,
    all_rows: bool,
) -> List[Dict[str, Any]]:
    """Read only the requested SQL page (or all filtered rows for export)."""
    repo = _require_read_tx(conn)
    if all_rows:
        rows = repo.query_entries(
            timeline=query["timeline"],
            state=query["state"],
            date_from=query["date_from"],
            date_to=query["date_to"],
            order=query["order"],
        )
    else:
        offset = (query["page"] - 1) * query["size"]
        rows = repo.query_entries(
            timeline=query["timeline"],
            state=query["state"],
            date_from=query["date_from"],
            date_to=query["date_to"],
            order=query["order"],
            limit=query["size"],
            offset=offset,
        )
    return [_decode_row(row) for row in rows]
