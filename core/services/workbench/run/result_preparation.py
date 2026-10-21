"""Prepare final identities, serialization and decision projections in the compute snapshot."""

from dataclasses import fields

from core.algorithm_contracts.operation_effort import RUNTIME_REQUIREMENT_BASIS
from core.models.objective import best_score_schema
from core.models.workbench_run_compute import CandidateRunComputation, PreparedRunResult
from core.models.workbench_run_job import durable_value, new_run_ref
from core.services.scheduler.run.optimizer.shared_process import _numeric_score
from core.services.workbench.facts.decision_read_model import build_decision_read_models


def _candidate_tasks(payload, identities, computation):
    tasks = []
    for row in payload.schedule_rows:
        if row.op_id not in identities:
            raise ValueError("Candidate operation identity is missing")
        tasks.append({"row_ref": new_run_ref(), "operation_ref": identities[row.op_id],
                      "payload": {**durable_value(row), "locked": row.op_id in computation.schedule_input.frozen_op_ids}})
    if len(tasks) != len(payload.scheduled_op_ids) or {row.op_id for row in payload.schedule_rows} != payload.scheduled_op_ids:
        raise ValueError("Candidate rows and scheduled operation scope disagree")
    return tasks


def _prepare_candidate(candidate, computation, identities):
    unified = candidate.generation_policy_version == "unified_search_v1"
    artifact = {}
    for item in fields(candidate):
        value = getattr(candidate, item.name)
        if unified and item.name == "score":
            scope = candidate.evaluations[candidate.objective_name]["scoring_scope"]
            value = _numeric_score(value, components_known=scope["components_known"])
        if not unified and item.name in ("generation_policy_version", "representative_objectives", "evaluations", "origin",
                                       "first_found_elapsed_ms", "search_evidence_ref"):
            continue
        artifact[item.name] = durable_value(value)
    if unified:
        artifact["target_objectives"] = list(computation.orchestration.candidate_comparison.target_objectives)
    if getattr(computation.schedule_input, "operation_efforts", None) is not None:
        artifact["analysis_contract_version"] = "decision-preparation-v4"
    tasks = []
    if candidate.status == "completed":
        payload = computation.candidate_payloads[candidate.candidate_key]
        if payload.out_of_scope_op_ids or payload.validation_errors:
            raise ValueError("Candidate payload contains validation errors")
        tasks = _candidate_tasks(payload, identities, computation)
        validated = durable_value(payload)
        arrangement_fields = ("op_id", "machine_id", "operator_id", "start_time", "end_time", "source")
        engine_rows = artifact.pop("results")
        if [{key: row.get(key) for key in arrangement_fields} for row in engine_rows] != validated["schedule_rows"]:
            raise ValueError("Candidate engine results and validated rows disagree")
        # Permanent task rows own the arrangement. Keep only engine-specific trace
        # fields and validation conclusions; historical artifacts retain their old shape.
        artifact["task_payload_source"] = "candidate_tasks_v1"
        artifact["results"] = [{key: value for key, value in row.items()
                                if key == "op_id" or key not in arrangement_fields} for row in engine_rows]
        artifact["validated_payload"] = {key: value for key, value in validated.items()
                                         if key not in ("schedule_rows", "assigned_by_op_id")}
    return {"candidate_ref": new_run_ref(), "key": candidate.candidate_key,
            "sequence": candidate.sequence, "status": candidate.status, "label": candidate.label,
            "artifact": artifact, "tasks": tasks}


def _prepare_result_artifacts(computation, identities, *, run_ref=None, batch_refs=None):
    if not isinstance(computation, CandidateRunComputation) or computation.result_persisted:
        raise TypeError("Expected an unpersisted CandidateRunComputation")
    if computation.state not in ("complete", "partial"):
        raise ValueError("Computation did not produce candidate results")
    comparison = computation.orchestration.candidate_comparison
    candidates = []
    for candidate in comparison.candidates:
        candidates.append(_prepare_candidate(candidate, computation, identities))
    if len({row["key"] for row in candidates}) != len(candidates):
        raise ValueError("Duplicate candidate identity")
    candidate_refs = {row["key"]: row["candidate_ref"] for row in candidates}
    unified = getattr(comparison, "generation_policy_version", None) == "unified_search_v1"
    for row in candidates:
        artifact = row["artifact"]
        if unified:
            artifact["evaluations"] = {target: {**evaluation, "scoring_scope":
                _scope_references(evaluation["scoring_scope"], identities, batch_refs)}
                for target, evaluation in artifact["evaluations"].items()}
            artifact["search_evidence_ref"] = {**artifact["search_evidence_ref"], "run_ref": run_ref}
        process = artifact.get("process_evidence")
        if process is not None:
            artifact["process_evidence"] = _evidence_references(process, candidate_refs)
    selected = comparison.selection.selected_candidate_key
    if not any(row["key"] == selected and row["status"] == "completed" for row in candidates):
        raise ValueError("Selected candidate is missing")
    result = {"result_persisted": True, "state": computation.state, "error": None,
              "candidates": [{"candidate_ref": row["candidate_ref"], "label": row["label"], "status": row["status"],
                              "task_count": len(row["tasks"]), "selected": row["key"] == selected} for row in candidates],
              "selection": _selection_references(comparison.selection, candidates, identities=identities, batch_refs=batch_refs), "dispositions": durable_value(computation.dispositions),
              "summary": durable_value(computation.orchestration.result_summary_obj)}
    if unified:
        process = comparison.unified_process
        result["unified_process"] = {**process, "scopes": {key: _scope_references(scope, identities, batch_refs)
            for key, scope in process["scopes"].items()}}
        comparison_summary = (result["summary"].get("algo") or {}).get("candidate_comparison")
        if comparison_summary is not None:
            comparison_summary.pop("unified_process", None)
            comparison_summary["selection"] = result["selection"]
            for summary in comparison_summary.get("candidates", []):
                summary["evaluations"] = {target: {**evaluation, "scoring_scope":
                    _scope_references(evaluation["scoring_scope"], identities, batch_refs)}
                    for target, evaluation in summary["evaluations"].items()}
                summary["search_evidence_ref"] = {**summary["search_evidence_ref"], "run_ref": run_ref}
    efforts = getattr(computation.schedule_input, "operation_efforts", None)
    if efforts is not None:
        items, seen = [], set()
        for effort in efforts:
            if effort.op_id not in identities or effort.op_id in seen:
                raise ValueError("Runtime effort operation identity is missing or duplicated")
            seen.add(effort.op_id)
            items.append({**durable_value(effort.to_dict()), "operation_ref": identities[effort.op_id]})
        result["operation_effort"] = {"effort_basis": RUNTIME_REQUIREMENT_BASIS, "items": items}
    return candidates, result


def _selection_references(selection, candidates, *, identities=None, batch_refs=None):
    """Map engine keys once, beside the candidate identities allocated in this transaction."""
    refs = {row["key"]: row["candidate_ref"] for row in candidates}
    value = durable_value(selection.to_dict())
    if value.get("selection_policy_version") == "business_objectives_v1":
        key = value.pop("selected_candidate_key")
        value["selected_candidate_ref"] = refs[key]
        value["objective_winners"] = {target: refs[winner] if winner is not None else None
                                     for target, winner in value["objective_winners"].items()}
        value["scoring_scope"] = _scope_references(value["scoring_scope"], identities, batch_refs)
        return value
    keys = {"selected_candidate_key": "selected_candidate_ref", "raw_score_best_key": "raw_score_best_candidate_ref",
            "baseline_best_key": "health_reference_candidate_ref", "critical_best_key": "critical_best_candidate_ref",
            "critical_health_best_key": "critical_health_best_candidate_ref"}
    for source, target in keys.items():
        key = value.pop(source)
        value[target] = refs[key] if key is not None else None
    selected = next(row for row in candidates if row["candidate_ref"] == value["selected_candidate_ref"])
    objective = selected["artifact"].get("objective_name") or selected["artifact"].get("objective")
    value.update(objective_name=objective, objective_field_order=[field["key"] for field in best_score_schema(objective)])
    if "decision_evidence" in value:
        value["decision_evidence"] = _evidence_references(value["decision_evidence"], refs)
    return value


def _evidence_references(value, refs):
    """Freeze nested candidate identities alongside the existing receipt anchors."""
    if isinstance(value, list):
        return [_evidence_references(item, refs) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key == "candidate_key" or key.endswith("_candidate_key"):
            result[key[:-3] + "ref"] = refs[item] if item is not None else None
        elif key == "candidate_keys" or key.endswith("_candidate_keys"):
            result[key[:-4] + "refs"] = [refs[candidate] for candidate in item]
        else:
            result[key] = _evidence_references(item, refs)
    return result




def _scope_references(scope, identities, batch_refs):
    return {**{key: value for key, value in scope.items()
               if key not in ("scheduled_operation_ids", "complete_batch_ids")},
            "scheduled_operation_refs": [identities[op_id] for op_id in scope["scheduled_operation_ids"]],
            "complete_batch_refs": [batch_refs[batch_id] for batch_id in scope["complete_batch_ids"]]}


def prepare_run_result(computation, identities, *, run, capture, admission, facts):
    """Build the final bundle once before the parent completion transaction."""
    batch_refs = {key: ref for (kind, key), ref in facts.entity_refs.items() if kind == "batch"}
    candidates, result = _prepare_result_artifacts(computation, identities, run_ref=run["run_ref"], batch_refs=batch_refs)
    packets = {}
    for candidate in candidates:
        candidate.update(run_ref=run["run_ref"], task_count=len(candidate["tasks"]))
        payload = computation.candidate_payloads.get(candidate["key"])
        intervals = ({task["row_ref"]: (row.start_time, row.end_time)
                      for task, row in zip(candidate["tasks"], payload.schedule_rows)} if payload is not None else {})
        packets[candidate["candidate_ref"]] = {"raw_tasks": candidate["tasks"], "intervals": intervals,
            "scheduled_op_ids": payload.scheduled_op_ids if payload is not None else None}
    models = build_decision_read_models(run, capture, result, candidates, packets,
        facts=facts, admission=admission, process=result.get("unified_process"))
    from data.repositories.workbench_run_repo import encode_decision_read_models, encode_result
    from data.repositories.workbench_run_result_repo import encode_candidate_rows

    return PreparedRunResult(encode_candidate_rows(candidates), encode_result(result), encode_decision_read_models(models),
                             models["run_model"]["header"])
