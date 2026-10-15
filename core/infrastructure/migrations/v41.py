"""Build immutable decision projections once from the original historical archive."""

from core.infrastructure.migration_common import MigrationOutcome
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_run_read_model_schema import install

_JOBS = """SELECT j.run_ref,j.request_key,j.input_ref,j.accepted_at,j.state,j.stage,j.executor_ref,
    j.started_at,j.finished_at,j.error_json,
    a.action AS admission_action,a.context_ref AS admission_context,a.outcome_json AS admission_json,
    r.receipt_ref,r.state AS receipt_state,r.recorded_at AS receipt_recorded_at
    FROM WorkbenchRunJobs j LEFT JOIN WorkbenchCommandReceipts a ON a.request_key=j.request_key
    LEFT JOIN WorkbenchRunReceipts r ON r.run_ref=j.run_ref ORDER BY j.accepted_at,j.run_ref"""


def _read_packet(store, run):
    from core.services.workbench.facts.candidate_facts import GenerationFacts
    from core.services.workbench.facts.candidate_projection import dispositions, validate_manifest
    from core.services.workbench.facts.candidate_values import corrupt

    receipt = store.receipt(run)
    candidates = store.candidates(run["run_ref"])
    validate_manifest(run, candidates, receipt)
    if run["state"] in ("failed", "interrupted") and candidates:
        corrupt()
    capture = store.capture(run["run_ref"])
    return {"run": run, "receipt": receipt, "rows": candidates, "capture": capture,
            "facts": GenerationFacts(capture), "disposition": dispositions(receipt), "prepared_candidates": {}}


def _prepare_candidate(store, packet, candidate):
    from core.services.workbench.facts.candidate_tasks import validate_saved_tasks
    from core.services.workbench.facts.candidate_values import corrupt

    ref = candidate["candidate_ref"]
    ready = packet["prepared_candidates"].get(ref)
    if ready is None:
        rows = store.tasks(ref)
        if len(rows) != candidate["task_count"]:
            corrupt()
        prepared_tasks = {}
        rows, intervals, ids = validate_saved_tasks(rows, candidate, packet["facts"], prepared_tasks=prepared_tasks)
        ready = packet["prepared_candidates"][ref] = {
            "raw_tasks": rows, "intervals": intervals, "prepared_tasks": prepared_tasks, "scheduled_op_ids": ids}
    return ready


def _candidate_provider(store, repo, current):
    from core.services.workbench.facts.candidate_read_source import read_candidate_source
    from core.services.workbench.facts.candidate_tasks import project_validated_tasks
    from core.services.workbench.facts.candidate_values import corrupt

    # Only the current run and its real official sources stay alive. The next run
    # gets a new owner instead of accumulating every archived task in memory.
    packets = {current["run"]["run_ref"]: current}
    owners = {row["candidate_ref"]: current for row in current["rows"]}

    def load(candidate_ref):
        if candidate_ref not in owners:
            run_ref = store.candidate_run(candidate_ref)
            if run_ref not in packets:
                run = repo.head(run_ref)
                if run is None:
                    corrupt()
                packet = packets[run_ref] = _read_packet(store, run)
                owners.update((row["candidate_ref"], packet) for row in packet["rows"])
        packet = owners.get(candidate_ref)
        if packet is None:
            corrupt()
        candidate = next(row for row in packet["rows"] if row["candidate_ref"] == candidate_ref)
        ready = _prepare_candidate(store, packet, candidate)
        if "tasks" not in ready:
            ready["tasks"] = project_validated_tasks(ready["raw_tasks"], candidate, packet["facts"], ready["intervals"],
                                                     prepared_tasks=ready["prepared_tasks"])
        return read_candidate_source(store, candidate_ref, prepared={
            **packet, "candidate": candidate, "raw_tasks": ready["raw_tasks"], "tasks": ready["tasks"],
            "scheduled_op_ids": ready["scheduled_op_ids"]})

    return load


def _backfill(conn):
    rows = conn.execute(_JOBS)
    first = rows.fetchone()
    if first is None:
        return

    from itertools import chain

    from core.models.workbench_run_history import TERMINAL_STATES
    from core.services.workbench.facts.candidate_store import CandidateStore
    from core.services.workbench.facts.candidate_values import corrupt
    from core.services.workbench.facts.decision_baseline import read_decision_baseline
    from core.services.workbench.facts.decision_baseline_source import decision_baseline_source_resolver
    from core.services.workbench.facts.decision_read_model import (
        build_decision_read_models,
        build_failure_read_models,
        prepare_admission_read_models,
    )
    from core.services.workbench.facts.run_history_projection import _job
    from data.repositories.workbench_run_repo import WorkbenchRunRepository

    store, repo = CandidateStore(conn), WorkbenchRunRepository(conn)
    for row in chain((first,), rows):
        run = dict(row)
        _job(run)
        terminal = run["state"] in TERMINAL_STATES
        if (terminal != (run["receipt_ref"] is not None) or
                terminal and (run["receipt_state"] != run["state"] or run["receipt_recorded_at"] != run["finished_at"])):
            corrupt()
        packet = _read_packet(store, run)
        if (run["state"] in ("queued", "running", "failed", "interrupted") and
                not packet["rows"] and packet["disposition"] is None):
            admission = prepare_admission_read_models(run, packet["capture"], None, facts=packet["facts"],
                                                      receipt=packet["receipt"])
            repo.insert_admission_read_model(run["run_ref"], admission["scope"], admission["decision"])
            if terminal:
                models = build_failure_read_models(run, admission["decision"], packet["receipt"])
                repo.insert_decision_read_models(run["run_ref"], models["run_model"], models["candidate_models"])
            continue
        for candidate in packet["rows"]:
            _prepare_candidate(store, packet, candidate)
        resolver = decision_baseline_source_resolver(conn, candidate_provider=_candidate_provider(store, repo, packet))
        official = read_decision_baseline(packet["capture"], packet["facts"], packet["disposition"], run["accepted_at"],
                                          source_resolver=resolver)
        candidate_refs = list(dict.fromkeys(item["source_candidate_ref"] for item in official["source_states"]
                                           if item.get("source_candidate_ref") is not None))
        scenario_refs = list(dict.fromkeys(item["source_scenario_ref"] for item in official["source_states"]
                                          if item.get("source_scenario_ref") is not None))
        dependencies = repo.dependency_heads(candidate_refs, scenario_refs)
        admission = prepare_admission_read_models(run, packet["capture"], official, facts=packet["facts"],
                                                  receipt=packet["receipt"], dependencies=dependencies)
        repo.insert_admission_read_model(run["run_ref"], admission["scope"], admission["decision"])
        if terminal:
            models = build_decision_read_models(run, packet["capture"], packet["receipt"], packet["rows"],
                packet["prepared_candidates"], official, facts=packet["facts"], dependencies=dependencies,
                process=(packet["receipt"] or {}).get("unified_process"), admission=admission["decision"])
            repo.insert_decision_read_models(run["run_ref"], models["run_model"], models["candidate_models"])


def run(conn, logger=None):
    with TransactionManager(conn).transaction():
        install(conn)
        _backfill(conn)
    return MigrationOutcome.APPLIED
