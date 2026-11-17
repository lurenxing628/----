"""Transactional writers and condition digests for WorkbenchHistoryEntries."""

from typing import Any, Dict, List, Mapping, Optional, Tuple

from core.models.workbench_run_history import local_datetime
from core.models.workbench_run_receipt import PersistedReceipt, RunReceipt
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.trial_scenario_archive import load_verified_scenario
from core.shared.local_datetime import datetime_to_us
from core.shared.strict_json import canonical_json
from data.repositories.workbench_history_catalog_repo import WorkbenchHistoryCatalogRepository

from .catalog import history_gap
from .conditions import extract_entry_condition_digests, saved_objective
from .conditions_source import ConditionSource
from .metric_window import history_window
from .packets import RunPacket, TrialPacket

_DEFAULT_7D_QUERY = {
    "range_start": None,
    "range_end": None,
    "resource_window_days": 7,
}


def _require_write_tx(conn) -> None:
    if not conn.in_transaction:
        raise RuntimeError("History entry writer requires the caller's write transaction")


def _parse_occurred_local(
    value: Optional[str],
    field: str,
    basis: str,
    gaps: List[Dict[str, str]],
) -> Tuple[Optional[str], Optional[str], Optional[int], Optional[str]]:
    if value is None:
        gaps.append(history_gap(field))
        return None, None, None, None
    try:
        parsed = local_datetime(value)
    except (ValueError, TypeError):
        gaps.append(history_gap(field, "invalid_stored_time"))
        return None, None, None, None
    return value, value[:10], datetime_to_us(parsed), basis


def _entry_digests(packet) -> Tuple[Dict[str, Any], Optional[str], Optional[str]]:
    window = history_window(packet, _DEFAULT_7D_QUERY)
    return extract_entry_condition_digests(packet, window)


def record_run_admitted(
    conn,
    *,
    head: Mapping[str, Any],
    capture: Mapping[str, Any],
    facts: Any,
) -> None:
    _require_write_tx(conn)
    run_ref = head["run_ref"]
    entry_ref = "run:" + run_ref
    accepted_at = head["accepted_at"]
    gaps: List[Dict[str, str]] = []
    occurred_at, occurred_day, occurred_us, time_basis = _parse_occurred_local(
        accepted_at, "accepted_at", "accepted_at_factory_local", gaps
    )
    baseline = capture["baseline"]
    times = {
        "accepted_at": accepted_at,
        "started_at": head["started_at"],
        "finished_at": head["finished_at"],
        "adopted_at": None,
        "committed_at_utc": None,
        "schedule_time": None,
    }
    packet = RunPacket(run_ref, entry_ref, capture, facts, None, None, None)
    source = ConditionSource(packet)
    objective = saved_objective(source, packet)
    WorkbenchHistoryCatalogRepository(conn).insert_run_entry(
        (
            entry_ref,
            head["state"],
            occurred_at,
            occurred_day,
            occurred_us,
            time_basis,
            run_ref,
            head["request_key"],
            baseline["plan_ref"],
            baseline["version"],
            canonical_json(times),
            canonical_json(gaps),
            canonical_json(objective),
        )
    )


def record_run_finished(
    conn,
    *,
    run_ref: str,
    state: str,
    finished_at: str,
    receipt_ref: str,
    result: RunReceipt,
) -> None:
    _require_write_tx(conn)
    repo = WorkbenchHistoryCatalogRepository(conn)
    entry_ref = "run:" + run_ref
    job_row = repo.run_job_times(run_ref)
    if job_row is None:
        raise ValueError("Cannot finish history entry for missing WorkbenchRunJobs row")
    # Only a receipt with saved results records a selection, and it selects one of its own candidates
    # (result_preparation); a failed or interrupted run is catalogued with an empty selection.
    if isinstance(result, PersistedReceipt):
        selection = result.selection
        selected = selection["selected_candidate_ref"]
    else:
        selection, selected = {}, None
    gaps: List[Dict[str, str]] = []
    _parse_occurred_local(job_row["accepted_at"], "accepted_at", "accepted_at_factory_local", gaps)

    times = {
        "accepted_at": job_row["accepted_at"],
        "started_at": job_row["started_at"],
        "finished_at": finished_at,
        "adopted_at": None,
        "committed_at_utc": None,
        "schedule_time": None,
    }
    store = CandidateStore(conn)
    capture = store.capture(run_ref)
    facts = store.generation_facts(capture)
    cand_row = None
    raw_tasks = None
    if selected is not None:
        cand_row = next(row for row in store.candidates(run_ref) if row["candidate_ref"] == selected)
        raw_tasks = store.tasks(selected)
    packet = RunPacket(run_ref, entry_ref, capture, facts, result, cand_row, raw_tasks)
    objective, static_digest, cal_7d_digest = _entry_digests(packet)
    updated = repo.update_run_entry(
        (
            state,
            receipt_ref,
            selected,
            selected,
            canonical_json(selection),
            canonical_json(times),
            canonical_json(gaps),
            canonical_json(objective),
            static_digest,
            cal_7d_digest,
            entry_ref,
        )
    )
    if updated != 1:
        raise ValueError("Run history entry update did not affect exactly one row")


def stage_official_adoption_entry(
    conn,
    *,
    request_key: str,
    provenance: Mapping[str, Any],
    plan_ref: str,
    plan_version: int,
    adopted_at: str,
    schedule_time: str,
) -> None:
    _require_write_tx(conn)
    repo = WorkbenchHistoryCatalogRepository(conn)
    source_kind = provenance["source_kind"]
    if source_kind not in ("candidate_adoption", "trial_adoption"):
        raise ValueError(f"Unsupported official adoption source_kind: {source_kind!r}")
    entry_ref = "pending:" + request_key
    prefix = "候选正式采用" if source_kind == "candidate_adoption" else "试调正式采用"
    static_label = f"{prefix} · 正式计划 v{plan_version}"

    gaps: List[Dict[str, str]] = []
    occurred_at, occurred_day, occurred_us, time_basis = _parse_occurred_local(
        adopted_at, "adopted_at", "adopted_at_factory_local", gaps
    )
    times = {
        "accepted_at": None,
        "started_at": None,
        "finished_at": None,
        "adopted_at": adopted_at,
        "committed_at_utc": None,
        "schedule_time": schedule_time,
    }

    if source_kind == "candidate_adoption":
        store = CandidateStore(conn)
        run_ref = provenance["run_ref"]
        candidate_ref = provenance["source_ref"]
        scenario_ref = None
        draft_ref = None
        capture = store.capture(run_ref)
        facts = store.generation_facts(capture)
        run_row = store.run(run_ref)
        receipt_body = store.receipt(run_row)
        cand_row = next(
            row for row in store.candidates(run_ref) if row["candidate_ref"] == candidate_ref
        )
        raw_tasks = store.tasks(candidate_ref)
        packet = RunPacket(run_ref, entry_ref, capture, facts, receipt_body, cand_row, raw_tasks)
    else:
        run_ref = None
        candidate_ref = None
        scenario_ref = provenance["source_ref"]
        draft_ref = provenance["draft_ref"]
        scenario = load_verified_scenario(conn, scenario_ref)
        packet = TrialPacket(scenario_ref, entry_ref, scenario.saved, scenario.head, scenario.rows, scenario.origin)

    objective, static_digest, cal_7d_digest = _entry_digests(packet)
    repo.insert_official_entry(
        (
            entry_ref,
            source_kind,
            occurred_at,
            occurred_day,
            occurred_us,
            time_basis,
            static_label,
            run_ref,
            candidate_ref,
            scenario_ref,
            draft_ref,
            plan_ref,
            plan_version,
            request_key,
            provenance["baseline_ref"],
            provenance["baseline_version"],
            canonical_json(times),
            canonical_json(gaps),
            canonical_json(objective),
            static_digest,
            cal_7d_digest,
        )
    )
