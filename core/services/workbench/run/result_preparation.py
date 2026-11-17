"""Prepare final identities, serialization and decision projections in the compute snapshot."""

from core.algorithm_contracts.operation_effort import RUNTIME_REQUIREMENT_BASIS
from core.models.workbench_run_compute import PreparedRunResult
from core.models.workbench_run_job import durable_value
from core.models.workbench_run_receipt import PersistedReceipt
from core.services.scheduler.run.optimizer.shared_process import numeric_score
from core.services.scheduler.run.schedule_candidate_plan import BUSINESS_FIELDS
from core.services.workbench.facts.candidate_artifact import (
    PLAN_FIELDS,
    evaluation_record,
    metrics_record,
    result_traces,
    scoring_scope_record,
    summary_record,
    validated_payload_record,
)
from core.services.workbench.facts.decision_read_model import build_decision_read_models
from core.shared.refs import new_ref
from data.repositories.workbench_run_repo import encode_decision_read_models, encode_result
from data.repositories.workbench_run_result_repo import encode_candidate_rows


def _candidate_tasks(payload, identities, computation):
    """The candidate's arrangements as the typed rows ``CandidateStore.tasks`` reads back; times stay datetimes."""
    frozen = computation.schedule_input.seeds.frozen_op_ids
    tasks = []
    for row in payload.schedule_rows:
        if row.op_id not in identities:
            raise ValueError("Candidate operation identity is missing")
        tasks.append({"row_ref": new_ref(), "operation_ref": identities[row.op_id], "op_id": row.op_id,
                      "source": row.source, "machine_id": row.machine_id, "operator_id": row.operator_id,
                      "start_time": row.start_time, "end_time": row.end_time, "locked": row.op_id in frozen})
    return tasks


def _business_record(candidate, run_ref):
    """The plan's BUSINESS_FIELDS as the artifact and the receipt summary both store them: each evaluation as its
    stored record, and the search evidence names this run."""
    record = {name: durable_value(getattr(candidate, name)) for name in BUSINESS_FIELDS}
    record["evaluations"] = {target: evaluation_record(evaluation) for target, evaluation in record["evaluations"].items()}
    record["search_evidence_ref"] = {**record["search_evidence_ref"], "run_ref": run_ref}
    return record


def _candidate_artifact(candidate, payload, *, target_objectives, run_ref):
    """The stored artifact, built from the facts/candidate_artifact key table; task rows own the arrangement."""
    artifact = {name: durable_value(getattr(candidate, name)) for name in PLAN_FIELDS}
    artifact.update(_business_record(candidate, run_ref))
    scope = candidate.evaluations[candidate.objective_name]["scoring_scope"]
    artifact.update(
        sort_strategy=candidate.used_strategy.value,
        score=numeric_score(candidate.score, components_known=scope["components_known"]),
        target_objectives=list(target_objectives),
        summary=summary_record(candidate.summary),
        metrics=metrics_record(candidate.metrics),
        results=result_traces(candidate.results),
        validated_payload=validated_payload_record(payload),
    )
    return artifact


def _prepare_candidate(candidate, computation, identities, *, run_ref):
    payload = computation.candidate_outcomes[candidate.candidate_key].validated_payload
    artifact = _candidate_artifact(candidate, payload, run_ref=run_ref,
                                   target_objectives=computation.candidate_comparison.target_objectives)
    return {"candidate_ref": new_ref(), "key": candidate.candidate_key, "sequence": candidate.sequence,
            "label": candidate.label, "artifact": artifact, "tasks": _candidate_tasks(payload, identities, computation)}


def _prepare_result_artifacts(computation, identities, *, run_ref, batch_refs):
    comparison = computation.candidate_comparison
    candidates = [_prepare_candidate(candidate, computation, identities, run_ref=run_ref)
                  for candidate in comparison.candidates]
    selected = comparison.selection.selected_candidate_key
    selection = _selection_references(comparison.selection, candidates)
    summary = durable_value(computation.result_summary_obj)
    process = comparison.unified_process
    comparison_summary = summary["algo"]["candidate_comparison"]
    comparison_summary["selection"] = selection
    for candidate_summary, candidate in zip(comparison_summary["candidates"], comparison.candidates):
        candidate_summary.update(_business_record(candidate, run_ref))
    items, seen = [], set()
    for effort in computation.schedule_input.operation_efforts:
        if effort.op_id not in identities or effort.op_id in seen:
            raise ValueError("Runtime effort operation identity is missing or duplicated")
        seen.add(effort.op_id)
        items.append({**durable_value(effort.to_dict()), "operation_ref": identities[effort.op_id]})
    receipt = PersistedReceipt(
        state=computation.state,
        candidates=[{"candidate_ref": row["candidate_ref"], "label": row["label"],
                     "task_count": len(row["tasks"]), "selected": row["key"] == selected} for row in candidates],
        selection=selection,
        dispositions=durable_value(computation.dispositions),
        summary=summary,
        unified_process={**process, "scopes": {key: _scope_references(scope, identities, batch_refs)
                                               for key, scope in process["scopes"].items()}},
        operation_effort={"effort_basis": RUNTIME_REQUIREMENT_BASIS, "items": items},
    )
    return candidates, receipt


def _selection_references(selection, candidates):
    """Map engine keys once, beside the candidate identities allocated in this transaction."""
    refs = {row["key"]: row["candidate_ref"] for row in candidates}
    value = durable_value(selection.to_dict())
    key = value.pop("selected_candidate_key")
    value["selected_candidate_ref"] = refs[key]
    value["objective_winners"] = {target: refs[winner] if winner is not None else None
                                 for target, winner in value["objective_winners"].items()}
    scope = value["scoring_scope"]
    value["scoring_scope"] = scoring_scope_record(scope, scheduled=scope["scheduled_operation_ids"],
                                                  complete=scope["complete_batch_ids"])
    return value


def _scope_references(scope, identities, batch_refs):
    return {**{key: value for key, value in scope.items()
               if key not in ("scheduled_operation_ids", "complete_batch_ids")},
            "scheduled_operation_refs": [identities[op_id] for op_id in scope["scheduled_operation_ids"]],
            "complete_batch_refs": [batch_refs[batch_id] for batch_id in scope["complete_batch_ids"]]}


def prepare_run_result(computation, identities, *, run, capture, admission, facts):
    """Build the final bundle once before the parent completion transaction."""
    batch_refs = {key: ref for (kind, key), ref in facts.entity_refs.items() if kind == "batch"}
    candidates, receipt = _prepare_result_artifacts(computation, identities, run_ref=run["run_ref"], batch_refs=batch_refs)
    packets = {}
    for candidate in candidates:
        candidate.update(run_ref=run["run_ref"], task_count=len(candidate["tasks"]))
        outcome = computation.candidate_outcomes[candidate["key"]]
        payload = outcome.validated_payload
        intervals = {task["row_ref"]: outcome.resolved_intervals[row.op_id]
                     for task, row in zip(candidate["tasks"], payload.schedule_rows)}
        packets[candidate["candidate_ref"]] = {"raw_tasks": candidate["tasks"], "intervals": intervals,
            "scheduled_op_ids": payload.scheduled_op_ids}
    models = build_decision_read_models(run, capture, receipt, candidates, packets,
        facts=facts, admission=admission, process=receipt.unified_process)
    return PreparedRunResult(encode_candidate_rows(candidates), encode_result(receipt.document()), receipt,
                             encode_decision_read_models(models), models["run_model"]["header"])
