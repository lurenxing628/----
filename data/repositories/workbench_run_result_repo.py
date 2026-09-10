"""Full candidate-set persistence, deliberately independent from formal Schedule."""

import json
from dataclasses import fields

from core.models.workbench_command import canonical_json
from core.models.workbench_run_compute import CandidateRunComputation
from core.models.workbench_run_job import durable_value, new_run_ref


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
    artifact = {item.name: durable_value(getattr(candidate, item.name)) for item in fields(candidate)}
    tasks = []
    if candidate.status == "completed":
        payload = computation.candidate_payloads[candidate.candidate_key]
        if payload.out_of_scope_op_ids or payload.validation_errors:
            raise ValueError("Candidate payload contains validation errors")
        artifact["validated_payload"] = durable_value(payload)
        tasks = _candidate_tasks(payload, identities, computation)
    return {"candidate_ref": new_run_ref(), "key": candidate.candidate_key,
            "sequence": candidate.sequence, "status": candidate.status, "label": candidate.label,
            "artifact": artifact, "tasks": tasks}


def prepare_run_result(computation, identities):
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
    selected = comparison.selection.selected_candidate_key
    if not any(row["key"] == selected and row["status"] == "completed" for row in candidates):
        raise ValueError("Selected candidate is missing")
    result = {"result_persisted": True, "state": computation.state, "error": None,
              "candidates": [{"candidate_ref": row["candidate_ref"], "label": row["label"], "status": row["status"],
                              "task_count": len(row["tasks"]), "selected": row["key"] == selected} for row in candidates],
              "selection": durable_value(comparison.selection.to_dict()), "dispositions": durable_value(computation.dispositions),
              "summary": durable_value(computation.orchestration.result_summary_obj)}
    canonical_json(result)
    for row in candidates:
        canonical_json(row)
    return candidates, result


class WorkbenchRunResultRepository:
    def __init__(self, conn):
        self.conn = conn

    def save(self, run_ref, candidates):
        for row in candidates:
            self.conn.execute("INSERT INTO WorkbenchRunCandidates VALUES (?,?,?,?,?,?,?)",
                (row["candidate_ref"], run_ref, row["key"], row["sequence"], row["status"], len(row["tasks"]), canonical_json(row["artifact"])))
            self.conn.executemany("INSERT INTO WorkbenchRunCandidateTasks VALUES (?,?,?,?,?)",
                [(task["row_ref"], row["candidate_ref"], task["operation_ref"], ordinal, canonical_json(task["payload"]))
                 for ordinal, task in enumerate(row["tasks"])])

    def consistent(self, run_ref, result):
        succeeded = result["state"] in ("complete", "partial")
        if result["result_persisted"] is not succeeded or bool(result["candidates"]) is not succeeded:
            return False
        rows = list(self.conn.execute("""SELECT c.candidate_ref,c.task_count,c.status,COUNT(t.row_ref) AS actual
            FROM WorkbenchRunCandidates c LEFT JOIN WorkbenchRunCandidateTasks t ON t.candidate_ref=c.candidate_ref
            WHERE c.run_ref=? GROUP BY c.candidate_ref""", (run_ref,)))
        if len(rows) != len(result["candidates"]):
            return False
        expected = {row["candidate_ref"]: row for row in result["candidates"]}
        return all(row[0] in expected and row[1] == row[3] == expected[row[0]]["task_count"]
                   and row[2] == expected[row[0]]["status"] for row in rows)

    def artifact(self, candidate_ref):
        row = self.conn.execute("SELECT artifact_json FROM WorkbenchRunCandidates WHERE candidate_ref=?", (candidate_ref,)).fetchone()
        return json.loads(row[0]) if row else None
